# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio

import msgspec
from flask import (
    Blueprint,
    current_app,
    request,
)

from gened.access import Access, RequireComponent, control_blueprint_access
from gened.llm import LLM, ChatMessage, with_llm

from . import prompts
from .chat_helpers import create_guided_chat
from .data_types import (
    LearningObjective,
    ObjectivesResponse,
    QuestionsResponse,
    TutorConfig,
)

DEFAULT_OBJECTIVES = 5
DEFAULT_QUESTIONS_PER_OBJECTIVE = 4


bp = Blueprint('guided', __name__, url_prefix=None, template_folder='templates')

# Blueprint default access controls set in __init__ via availability_requirements
# Additionally require an instructor role and that the subfeature is enabled for all routes in this blueprint
control_blueprint_access(bp, Access.INSTRUCTOR, RequireComponent('tutors', feature='guided'))


@bp.route('/generate/objectives', methods=['POST'])
@with_llm(spend_token=True, is_api=True)
def generate_objectives(llm: LLM) -> bytes | tuple[dict[str, str], int]:
    """Generate learning objectives for the given topic."""
    config = TutorConfig.from_request_form(request.form)

    num_items_final = int(request.form.get('num_objectives', DEFAULT_OBJECTIVES))
    num_items_initial = max(20, num_items_final + 10)

    # Get documents marked for setup use
    setup_docs = [doc for doc in config.documents if 'setup' in doc.use_in]

    sys_prompt = prompts.tutor_setup_objectives_sys_prompt.render(
        topic=config.topic,
        learning_context=config.context,
        documents=setup_docs,
    )
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
        opt_contact = "" if "SUPPORT_EMAIL" not in current_app.config else f" to {current_app.config['SUPPORT_EMAIL']}"
        return {"error": f"The LLM returned an invalid response.\nPlease try again or report the issue{opt_contact} if it continues."}, 502

    objectives = [LearningObjective(obj, []) for obj in objectives_data]

    return msgspec.json.encode(objectives)


async def generate_questions_for_objective(config: TutorConfig, index: int, llm: LLM, num_questions: int) -> list[str]:
    context = config.context

    # Get documents marked for setup use
    setup_docs = [doc for doc in config.documents if 'setup' in doc.use_in]

    objective = config.objectives[index].name
    previous  = [obj.name for obj in config.objectives[:index]]
    following = [obj.name for obj in config.objectives[index+1:]]

    messages: list[ChatMessage] = [
        {'role': 'system', 'content': prompts.tutor_setup_questions_sys_prompt.render(learning_context=context, documents=setup_docs)},
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
    except msgspec.DecodeError as e:
        current_app.logger.error(f"Failed to parse questions from LLM for objective '{objective}'. Error: {e}. Response: {response_txt}")
        raise
    else:
        return response.questions


async def populate_questions(config: TutorConfig, llm: LLM, num_questions: int) -> None:
    """ Populate (in-place) all learning objectives in config with the given number of questions. """
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(generate_questions_for_objective(config, i, llm, num_questions))
            for i in range(len(config.objectives))
        ]

    # If we reach here, all tasks succeeded. Apply results.
    for i, task in enumerate(tasks):
        config.objectives[i].questions = task.result()


@bp.route('/generate/questions', methods=['POST'])
@with_llm(spend_token=True, is_api=True)
def generate_questions(llm: LLM) -> bytes | tuple[dict[str, str], int]:
    """Generate questions based on topic and objectives."""
    config = TutorConfig.from_request_form(request.form)

    num_questions = int(request.form.get('num_questions', DEFAULT_QUESTIONS_PER_OBJECTIVE))

    try:
        asyncio.run(populate_questions(config, llm, num_questions))
    except (msgspec.DecodeError, ExceptionGroup):
        opt_contact = "" if "SUPPORT_EMAIL" not in current_app.config else f" to {current_app.config['SUPPORT_EMAIL']}"
        return {"error": f"The LLM returned an invalid response for one or more objectives.\nPlease try again or report the issue{opt_contact} if it continues."}, 502

    return msgspec.json.encode(config.objectives)


@bp.route('/generate/opening', methods=['POST'])
@with_llm(spend_token=True, is_api=True)
def generate_opening(llm: LLM) -> str | tuple[dict[str, str], int]:
    """ Generate an opening message for the given tutor plan. """
    tutor_config = TutorConfig.from_request_form(request.form)
    chat = create_guided_chat(tutor_config, skip_db=True)

    msgs = chat.openai_messages[:]
    msgs.append({
        'role': 'user',
        'content': 'Please generate an initial message for the user.',
    })

    response, response_txt = asyncio.run(
        llm.get_completion(messages=msgs)
    )

    if 'error' in response:
        current_app.logger.error(f"Failed to generate opening message from LLM: {response}")
        opt_contact = "" if "SUPPORT_EMAIL" not in current_app.config else f" to {current_app.config['SUPPORT_EMAIL']}"
        return {"error": f"The LLM returned an invalid response.\nPlease try again or report the issue{opt_contact} if it continues."}, 502

    return response_txt
