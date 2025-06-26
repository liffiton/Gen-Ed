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
from werkzeug.wrappers.response import Response

from gened.auth import get_auth_class, instructor_required
from gened.db import get_db
from gened.experiments import experiment_required
from gened.llm import LLM, ChatMessage, with_llm

from . import prompts

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
    objectives: list[LearningObjective] = field(default_factory=list)

    @classmethod
    def from_dict(cls, dictionary: dict[str, Any]) -> Self:
        try:
            obj = cls(**dictionary)
            obj.objectives = [LearningObjective(**obj) for obj in dictionary.get('objectives', [])]
            return obj
        except TypeError:
            return cls()


@bp.route('/new', methods=['GET'])
def setup_form() -> str:
    """Display the tutor setup form."""
    config = TutorConfig.from_dict(session.get('tutor_config', {}))
    return render_template(
        'tutor_setup_form.html',
        tutorconf=config,
        has_questions=any(obj.questions for obj in config.objectives)
    )


@bp.route('/objectives/generate', methods=['POST'])
@with_llm(spend_token=False)
def generate_objectives(llm: LLM) -> Response:
    """Generate learning objectives for the given topic."""
    context = request.form.get('context', '').strip()
    topic = request.form.get('topic', '').strip()
    num_items_initial = 30
    num_items_final = DEFAULT_OBJECTIVES

    sys_prompt = prompts.tutor_setup_objectives_sys_prompt.render(learning_context=context)
    user_prompts = [
        prompts.tutor_setup_objectives_prompt1.render(topic=topic, num_items=num_items_initial),
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
    config = TutorConfig(context, topic, [LearningObjective(obj, []) for obj in objectives])

    session['tutor_config'] = config
    return redirect(url_for('.setup_form'))


async def generate_questions_from_objective(llm: LLM, context: str, objectives: list[str], index: int) -> list[str]:
    objective = objectives[index]
    previous = objectives[:index]
    following = objectives[index+1:]

    messages: list[ChatMessage] = [
        {'role': 'system', 'content': prompts.tutor_setup_questions_sys_prompt.render(learning_context=context)},
        {'role': 'user', 'content': prompts.tutor_setup_questions_prompt.render(objective=objective, previous=previous, following=following, num_items=DEFAULT_QUESTIONS_PER_OBJECTIVE)},
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
    return data


async def populate_questions(llm: LLM, context: str, objectives: list[str]) -> list[LearningObjective]:
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(generate_questions_from_objective(llm, context, objectives, i))
            for i in range(len(objectives))
        ]

    return [LearningObjective(obj, task.result()) for obj, task in zip(objectives, tasks, strict=True)]


@bp.route('/questions/generate', methods=['POST'])
@with_llm(spend_token=False)
def generate_questions(llm: LLM) -> Response:
    """Generate questions based on topic and objectives."""
    context = request.form.get('context', '').strip()
    topic = request.form.get('topic', '').strip()
    objectives_str = request.form.get('objectives', '').strip()
    objectives = [obj.strip() for obj in objectives_str.split('\n')]

    objectives_with_questions = asyncio.run(populate_questions(llm, context, objectives))

    config = TutorConfig(context, topic, objectives_with_questions)

    session['tutor_config'] = config
    return redirect(url_for('.setup_form'))


@bp.route('/questions/update', methods=['POST'])
def update_questions() -> Response:
    """ Update the questions for one learning objective. """
    config = TutorConfig.from_dict(session.get('tutor_config', {}))
    obj_index = request.form.get('obj_index')
    if obj_index is None or not obj_index.isnumeric():
        abort(400)
    questions = request.form.getlist('questions[]')
    questions = [q.strip() for q in questions]
    config.objectives[int(obj_index)].questions = questions
    session['tutor_config'] = config
    return redirect(url_for('.setup_form'))


@bp.route('/create', methods=['POST'])
def create_tutor() -> Response:
    """Persist the new tutor to the database."""
    context = request.form.get('context', '').strip()
    topic = request.form.get('topic', '').strip()
    objectives_str = request.form.get('objectives', '').strip()
    objectives = [obj.strip() for obj in objectives_str.split('\n')]

    config = TutorConfig(
        context,
        topic,
        [LearningObjective(obj, request.form.getlist(f'questions[{i}]')) for i, obj in enumerate(objectives)]
    )

    cur_class = get_auth_class()
    class_id = cur_class.class_id

    db = get_db()
    db.execute(
        "INSERT INTO tutors (class_id, config) VALUES (?, ?)",
        [class_id, json.dumps(asdict(config))]
    )
    db.commit()
    session.pop('tutor_config', None)
    flash(f"Tutor created for topic: {topic}", 'success')
    return redirect(url_for('.setup_form'))


@bp.route('/reset', methods=['POST'])
def reset_setup() -> Response:
    """Clear the in-progress tutor setup and start over."""
    session.pop('tutor_config', None)
    return redirect(url_for('.setup_form'))
