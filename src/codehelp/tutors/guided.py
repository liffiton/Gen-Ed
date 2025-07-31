# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import dataclasses
import json
from dataclasses import dataclass
from typing import Any, Self

from cachelib.simple import SimpleCache
from flask import (
    Blueprint,
    abort,
    flash,
    request,
)
from pypdf import PdfReader
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.wrappers.response import Response

from gened.auth import get_auth, get_auth_class, instructor_required
from gened.class_config import ConfigItem
from gened.experiments import experiment_required
from gened.llm import LLM, ChatMessage, with_llm
from gened.redir import safe_redirect

from . import prompts

DEFAULT_OBJECTIVES = 5
DEFAULT_QUESTIONS_PER_OBJECTIVE = 4


# Use a simple memory-based cache for storing draft tutor configurations.
# NOTE that this will be cleared if the server restarts.
_tutor_config_cache = SimpleCache(default_timeout=60*60*24*5)  # 5 days


bp = Blueprint('guided', __name__, url_prefix=None, template_folder='templates')

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
class TutorConfig(ConfigItem):
    topic: str = ""
    context: str = ""
    document_filename: str = ""
    document_text: str = ""
    objectives: list[LearningObjective] = dataclasses.field(default_factory=list)

    @classmethod
    def from_cache(cls) -> Self:
        obj: Self | None = _tutor_config_cache.get(_cache_key())
        if obj is None:
            obj = cls(name='')
        return obj

    @classmethod
    def initial(cls) -> Self:
        return cls.from_cache()

    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, Any]) -> Self:
        """
        Loads a stored object from the cache first for the document data, and
        populates everything *else* from the given form.
        """
        config = cls.from_cache()
        config.name = form.get('name', '').strip()
        config.topic = form.get('topic', '').strip()
        config.context = form.get('context', '').strip()
        objectives_str = form.get('objectives', '').strip()
        objectives_split = [obj.strip() for obj in objectives_str.split('\n')] if objectives_str else []
        config.objectives = [LearningObjective(obj, form.getlist(f'questions[{i}]')) for i, obj in enumerate(objectives_split)]
        return config


def _cache_key() -> str:
    auth = get_auth()
    assert auth.user_id is not None
    cur_class = get_auth_class()
    return f"guided_tutor_config_{auth.user_id}_{cur_class.class_id}"


def _save_to_cache(config: TutorConfig) -> None:
    _tutor_config_cache.set(_cache_key(), config)


def _delete_cached_config() -> None:
    _tutor_config_cache.delete(_cache_key())


@bp.route('/objectives/generate', methods=['POST'])
@with_llm(spend_token=False)
def generate_objectives(llm: LLM) -> Response:
    """Generate learning objectives for the given topic."""
    config = TutorConfig.from_request_form(request.form)

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

    _save_to_cache(config)

    return safe_redirect(request.referrer, default_endpoint='profile.main')


@bp.route('/document/upload', methods=['POST'])
def upload_document() -> Response:
    """Upload a document and extract its text."""
    # first, save whatever might have been included in the form along with the file
    config = TutorConfig.from_request_form(request.form)
    _save_to_cache(config)

    if 'document_file' not in request.files:
        return safe_redirect(request.referrer, default_endpoint='profile.main')

    pdf_file = request.files['document_file']
    if pdf_file.filename:
        pdf_file.seek(0, 2)  # 2 = SEEK_END
        file_size = pdf_file.tell()
        pdf_file.seek(0)
        if file_size > 1 * 1024 * 1024:
            flash("Uploaded file is too large (max 1MB).", "danger")
            return safe_redirect(request.referrer, default_endpoint='profile.main')

        try:
            reader = PdfReader(pdf_file)  # type: ignore[arg-type]
            text = "\n\n".join(page.extract_text() for page in reader.pages)
        except Exception as e:
            flash(f"Error reading PDF: {e}", "danger")
        else:
            config = TutorConfig.from_cache()
            config.document_text = text
            config.document_filename = pdf_file.filename
            _save_to_cache(config)

    return safe_redirect(request.referrer, default_endpoint='profile.main')


@bp.route('/document/remove', methods=['POST'])
def remove_document() -> Response:
    """Remove an uploaded document."""
    config = TutorConfig.from_cache()
    config.document_filename = ""
    config.document_text = ""
    _save_to_cache(config)
    return safe_redirect(request.referrer, default_endpoint='profile.main')


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
    config = TutorConfig.from_request_form(request.form)

    num_questions = int(request.form.get('num_questions', DEFAULT_QUESTIONS_PER_OBJECTIVE))

    task = populate_questions(config, llm, num_questions)
    asyncio.run(task)

    _save_to_cache(config)
    return safe_redirect(request.referrer, default_endpoint='profile.main')


@bp.route('/questions/update', methods=['POST'])
def update_questions() -> Response:
    """ Update the questions for one learning objective. """
    config = TutorConfig.from_cache()
    obj_index = request.form.get('obj_index')
    if obj_index is None or not obj_index.isnumeric():
        abort(400)
    questions = request.form.getlist('questions[]')
    questions = [q.strip() for q in questions]
    config.objectives[int(obj_index)].questions = questions
    _save_to_cache(config)
    return safe_redirect(request.referrer, default_endpoint='profile.main')


@bp.route('/reset', methods=['POST'])
def reset_setup() -> Response:
    """Clear the in-progress tutor setup and start over."""
    _delete_cached_config()
    return safe_redirect(request.referrer, default_endpoint='profile.main')
