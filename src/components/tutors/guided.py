# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
from typing import Any, Self

import msgspec
from flask import (
    Blueprint,
    current_app,
    request,
)
from markupsafe import Markup
from werkzeug.datastructures import ImmutableMultiDict

from gened.access import Access, RequireComponent, control_blueprint_access
from gened.class_config.types import ConfigItem, ConfigShareLink, ConfigTable
from gened.llm import LLM, ChatMessage, with_llm

from . import prompts

DEFAULT_OBJECTIVES = 5
DEFAULT_QUESTIONS_PER_OBJECTIVE = 4


bp = Blueprint('guided', __name__, url_prefix=None, template_folder='templates')

# Blueprint default access controls set in __init__ via availability_requirements
# Additionally require an instructor role and that the subfeature is enabled for all routes in this blueprint
control_blueprint_access(bp, Access.INSTRUCTOR, RequireComponent('tutors', feature='guided'))


class ObjectivesResponse(msgspec.Struct):
    """LLM response for objective generation."""
    objectives: list[str]


class QuestionsResponse(msgspec.Struct):
    """LLM response for question generation."""
    questions: list[str]


class LearningObjective(msgspec.Struct):
    name: str
    questions: list[str] = []


class TutorConfig(ConfigItem):
    topic: str = ""
    context: str = ""
    document_filename: str = ""
    document_text: str = ""
    objectives: list[LearningObjective] = []  # noqa: RUF012 - ConfigItem is a msgspec.Struct, so this is okay

    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, Any]) -> Self:
        """
        Populates a TutorConfig from the given form.
        """
        config = cls.initial()
        if 'row_id' in form:
            config.row_id = int(form['row_id'])
        config.name = form.get('name', '').strip()
        config.topic = form.get('topic', '').strip()
        config.context = form.get('context', '').strip()
        config.document_filename = form.get('document_filename', '').strip()
        config.document_text = form.get('document_text', '').strip()
        objective_names = form.getlist('objectives')
        config.objectives = [LearningObjective(obj, form.getlist(f'questions[{i}]')) for i, obj in enumerate(objective_names)]
        return config


# To register the configuration UI inside gened's class_config module
guided_tutor_config_table = ConfigTable(
    config_item_class=TutorConfig,
    name='guided_tutor',
    db_table_name='tutors',
    display_name='focused tutor',
    display_name_plural='focused tutors',
    help_text=Markup("<p>Instructors can design Focused Tutors for students with pre-defined learning objectives and assessment questions (e.g., to be used as reinforcement and/or low-stakes assessments following a reading or video).</p>"),
    edit_form_template='guided_tutor_edit_form.html',
    share_links=[
        ConfigShareLink(
            'Focused tutor chat',
            'tutors.new_chat_form',
            {'class_id', 'tutor_name'},
        ),
    ],
    extra_routes=bp,
    availability_requirements=(RequireComponent('tutors', feature='guided'), ),
)


@bp.route('/objectives/generate', methods=['POST'])
@with_llm(spend_token=True, is_api=True)
def generate_objectives(llm: LLM) -> bytes:
    """Generate learning objectives for the given topic."""
    config = TutorConfig.from_request_form(request.form)

    num_items_final = int(request.form.get('num_objectives', DEFAULT_OBJECTIVES))
    num_items_initial = max(20, num_items_final + 10)

    sys_prompt = prompts.tutor_setup_objectives_sys_prompt.render(topic=config.topic, learning_context=config.context, document=config.document_text)
    user_prompts = [
        prompts.tutor_setup_objectives_prompt1.render(num_items=num_items_initial),
        prompts.tutor_setup_objectives_prompt2.render(num_items=num_items_final),
    ]

    _response, response_txt = asyncio.run(
        llm.get_multi_completion(
            sys_prompt=sys_prompt,
            user_prompts=user_prompts,
            extra_args={
                'response_format': {'type': 'json_object'},
            },
        )
    )

    try:
        response = msgspec.json.decode(response_txt, type=ObjectivesResponse)
        objectives_data = response.objectives
    except msgspec.DecodeError as e:
        current_app.logger.error(f"Failed to parse objectives from LLM. Error: {e}. Response: {response_txt}")
        raise

    objectives = [LearningObjective(obj, []) for obj in objectives_data]

    return msgspec.json.encode(objectives)


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
    _response, response_txt = await llm.get_completion(
        messages=messages,
        extra_args={
            'response_format': {'type': 'json_object'},
        },
    )

    try:
        response = msgspec.json.decode(response_txt, type=QuestionsResponse)
        data = response.questions
    except msgspec.DecodeError as e:
        current_app.logger.error(f"Failed to parse questions from LLM for objective '{objective}'. Error: {e}. Response: {response_txt}")
        raise

    config.objectives[index].questions = data


async def populate_questions(config: TutorConfig, llm: LLM, num_questions: int) -> None:
    """ Populate (in-place) all learning objectives in config with the given number of questions. """
    # TaskGroup is 3.11+ (TODO: switch after 3.10 eol)
    #async with asyncio.TaskGroup() as tg:
    #    for i in range(len(config.objectives)):
    #        tg.create_task(generate_questions_for_objective(config, i, llm, num_questions))
    tasks = [
        asyncio.create_task(generate_questions_for_objective(config, i, llm, num_questions))
        for i in range(len(config.objectives))
    ]
    await asyncio.gather(*tasks)


@bp.route('/questions/generate', methods=['POST'])
@with_llm(spend_token=True, is_api=True)
def generate_questions(llm: LLM) -> bytes:
    """Generate questions based on topic and objectives."""
    config = TutorConfig.from_request_form(request.form)

    num_questions = int(request.form.get('num_questions', DEFAULT_QUESTIONS_PER_OBJECTIVE))

    task = populate_questions(config, llm, num_questions)
    asyncio.run(task)

    return msgspec.json.encode(config.objectives)
