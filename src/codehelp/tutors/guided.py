# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Self

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pypdf import PdfReader
from werkzeug.wrappers.response import Response

from gened.auth import get_auth_class, instructor_required
from gened.db import get_db
from gened.experiments import experiment_required
from gened.llm import LLM, ChatMessage, with_llm

from . import prompts

TUTOR_CONF_SESSION_KEY = "guided_tutor_config"
DEFAULT_OBJECTIVES = 5
DEFAULT_QUESTIONS_PER_OBJECTIVE = 4

bp = Blueprint('config', __name__, url_prefix='/guided', template_folder='templates')

@bp.before_request
@experiment_required("chats_experiment")
@instructor_required
def before_request() -> None:
    """ Apply decorators to protect all blueprint endpoints.
    Use @experiment_required first so that non-logged-in users get a 404 as well.
    """


@dataclass
class LearningObjective:
    name: str
    questions: list[str]

@dataclass
class TutorConfig:
    context: str = ""
    topic: str = ""
    document_filename: str = ""
    document_text: str = ""
    objectives: list[LearningObjective] = field(default_factory=list)

    @classmethod
    def from_session(cls) -> Self:
        return cls.from_dict(session.get(TUTOR_CONF_SESSION_KEY, {}))

    @classmethod
    def from_dict(cls, dictionary: dict[str, Any]) -> Self:
        try:
            init_data = dictionary.copy()
            objectives_data = init_data.pop('objectives', [])
            obj = cls(**init_data)
            obj.objectives = [LearningObjective(**obj_data) for obj_data in objectives_data]
            return obj
        except TypeError:
            return cls()


@bp.route('/new', methods=['GET'])
def setup_form() -> str:
    """Display the tutor setup form."""
    config = TutorConfig.from_session()
    return render_template(
        'tutor_setup_form.html',
        tutorconf=config,
        has_questions=any(obj.questions for obj in config.objectives)
    )


@bp.route('/objectives/generate', methods=['POST'])
@with_llm(spend_token=False)
def generate_objectives(llm: LLM) -> Response:
    """Generate learning objectives for the given topic."""
    config = TutorConfig.from_session()
    config.context = request.form.get('context', '').strip()
    config.topic = request.form.get('topic', '').strip()
    num_items_initial = 30
    num_items_final = int(request.form.get('num_objectives', DEFAULT_OBJECTIVES))

    sys_prompt = prompts.tutor_setup_objectives_sys_prompt.render(topic=config.topic, learning_context=config.context, document=config.document_text)
    user_prompts = [
        prompts.tutor_setup_objectives_prompt1.render(num_items=num_items_initial),
        prompts.tutor_setup_objectives_prompt2.render(num_items=num_items_final),
    ]

    response, response_txt = asyncio.run(
        llm.get_multi_completion(
            sys_prompt=sys_prompt,
            user_prompts=user_prompts,
            extra_args={
                #'reasoning_effort': 'none',  # for thinking models: o3/o4/gemini-2.5
                'response_format': {'type': 'json_object'},
            },
        )
    )

    objectives = json.loads(response_txt)['objectives']
    assert isinstance(objectives, list)
    assert all(isinstance(val, str) for val in objectives)
    config.objectives = [LearningObjective(obj, []) for obj in objectives]

    session[TUTOR_CONF_SESSION_KEY] = config
    return redirect(url_for('.setup_form'))


@bp.route('/document/upload', methods=['POST'])
def upload_document() -> Response:
    """Upload a document and extract its text."""
    if 'document' not in request.files:
        return redirect(url_for('.setup_form'))

    pdf_file = request.files['document']
    if pdf_file.filename:
        pdf_file.seek(0, 2)  # 2 = SEEK_END
        file_size = pdf_file.tell()
        pdf_file.seek(0)
        if file_size > 1 * 1024 * 1024:
            flash("Uploaded file is too large (max 1MB).", "danger")
            return redirect(url_for('.setup_form'))

        try:
            reader = PdfReader(pdf_file)
            text = "\n\n".join(page.extract_text() for page in reader.pages)
        except Exception as e:
            flash(f"Error reading PDF: {e}", "danger")
        else:
            config = TutorConfig.from_session()
            config.document_text = text
            config.document_filename = pdf_file.filename
            session[TUTOR_CONF_SESSION_KEY] = config

    return redirect(url_for('.setup_form'))


@bp.route('/document/remove', methods=['POST'])
def remove_document() -> Response:
    """Remove an uploaded document."""
    config = TutorConfig.from_session()
    config.document_filename = ""
    config.document_text = ""
    session[TUTOR_CONF_SESSION_KEY] = config
    return redirect(url_for('.setup_form'))


async def generate_questions_for_objective(config: TutorConfig, index: int, llm: LLM, num_questions: int) -> None:
    context = config.context
    document_text = config.document_text
    objective = config.objectives[index].name
    previous  = [obj.name for obj in config.objectives[:index]]
    following = [obj.name for obj in config.objectives[index+1:]]

    messages: list[ChatMessage] = [
        {'role': 'system', 'content': prompts.tutor_setup_questions_sys_prompt.render(learning_context=context, document=document_text)},
        {'role': 'user', 'content': prompts.tutor_setup_questions_prompt.render(objective=objective, previous=previous, following=following, num_items=num_questions)},
    ]
    response, response_txt = await llm.get_completion(
        messages=messages,
        extra_args={
            #'reasoning_effort': 'none',  # for thinking models: o3/o4/gemini-2.5
            'response_format': {'type': 'json_object'},
        },
    )

    data = json.loads(response_txt)['questions']
    assert isinstance(data, list)
    assert all(isinstance(val, str) for val in data)

    config.objectives[index].questions = data


async def populate_questions(config: TutorConfig, llm: LLM, num_questions: int) -> None:
    """ Populate (in-place) all learning objectives in config with the given number of questions. """
    async with asyncio.TaskGroup() as tg:
        for i in range(len(config.objectives)):
            tg.create_task(generate_questions_for_objective(config, i, llm, num_questions))


@bp.route('/questions/generate', methods=['POST'])
@with_llm(spend_token=False)
def generate_questions(llm: LLM) -> Response:
    """Generate questions based on topic and objectives."""
    config = TutorConfig.from_session()
    config.context = request.form.get('context', '').strip()
    config.topic = request.form.get('topic', '').strip()
    objectives_str = request.form.get('objectives', '').strip()
    objectives = [obj.strip() for obj in objectives_str.split('\n')]
    config.objectives = [LearningObjective(obj, []) for obj in objectives]

    num_questions = int(request.form.get('num_questions', DEFAULT_QUESTIONS_PER_OBJECTIVE))

    task = populate_questions(config, llm, num_questions)
    asyncio.run(task)

    session[TUTOR_CONF_SESSION_KEY] = config
    return redirect(url_for('.setup_form'))


@bp.route('/questions/update', methods=['POST'])
def update_questions() -> Response:
    """ Update the questions for one learning objective. """
    config = TutorConfig.from_session()
    obj_index = request.form.get('obj_index')
    if obj_index is None or not obj_index.isnumeric():
        abort(400)
    questions = request.form.getlist('questions[]')
    questions = [q.strip() for q in questions]
    config.objectives[int(obj_index)].questions = questions
    session[TUTOR_CONF_SESSION_KEY] = config
    return redirect(url_for('.setup_form'))


@bp.route('/create', methods=['POST'])
def create_tutor() -> Response:
    """Persist the new tutor to the database."""
    config = TutorConfig.from_session()
    config.context = request.form.get('context', '').strip()
    config.topic = request.form.get('topic', '').strip()
    objectives_str = request.form.get('objectives', '').strip()
    objectives = [obj.strip() for obj in objectives_str.split('\n')]

    config.objectives = [LearningObjective(obj, request.form.getlist(f'questions[{i}]')) for i, obj in enumerate(objectives)]

    cur_class = get_auth_class()
    class_id = cur_class.class_id

    db = get_db()
    db.execute(
        "INSERT INTO tutors (class_id, config) VALUES (?, ?)",
        [class_id, json.dumps(asdict(config))]
    )
    db.commit()
    session.pop(TUTOR_CONF_SESSION_KEY, None)
    flash(f"Tutor created for topic: {config.topic}", 'success')
    return redirect(url_for('.setup_form'))


@bp.route('/reset', methods=['POST'])
def reset_setup() -> Response:
    """Clear the in-progress tutor setup and start over."""
    session.pop(TUTOR_CONF_SESSION_KEY, None)
    return redirect(url_for('.setup_form'))
