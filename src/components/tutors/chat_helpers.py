# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import msgspec

from components.code_contexts import ContextConfig
from gened.auth import get_auth
from gened.db import get_db

from . import prompts
from .data_types import (
    ChatData,
    ChatMode,
    GuidedAnalysis,
    GuidedObjectiveProgress,
    TutorConfig,
)


def create_guided_chat(tutor_config: TutorConfig, *, skip_db: bool = False) -> ChatData:
    auth = get_auth()

    # Get documents marked for use in chat
    chat_docs = [doc for doc in tutor_config.documents if 'chat' in doc.use_in]

    tikz_enabled = 'tikz_experiment' in auth.class_experiments
    sys_prompt = prompts.guided_sys_msg_tpl.render(tutor_config=tutor_config, documents=chat_docs, tikz_enabled=tikz_enabled)

    chat = _create_chat(tutor_config.topic, context_name=None, sys_prompt=sys_prompt, mode="guided")

    chat.analysis = GuidedAnalysis(
        summary = "",
        progress = [
            GuidedObjectiveProgress(obj.name, "not started")
            for obj in tutor_config.objectives
        ],
    )

    if not skip_db:
        chat = _save_chat(chat)

    return chat


def create_inquiry_chat(topic: str, context: ContextConfig | None, *, skip_db: bool = False) -> ChatData:
    auth = get_auth()

    context_name = context.name if context else None
    context_string = context.prompt_str() if context else None

    tikz_enabled = 'tikz_experiment' in auth.class_experiments
    sys_prompt = prompts.inquiry_sys_msg_tpl.render(topic=topic, context=context_string, tikz_enabled=tikz_enabled)

    chat = _create_chat(topic, context_name, sys_prompt, "inquiry")

    if not skip_db:
        chat = _save_chat(chat)

    return chat


def _create_chat(topic: str, context_name: str | None, sys_prompt: str, mode: ChatMode) -> ChatData:
    auth = get_auth()
    user_id = auth.user_id
    class_id = auth.cur_class.class_id if auth.cur_class else None

    chat_data = ChatData(
        user_id=user_id,
        class_id=class_id,
        topic=topic,
        context_name=context_name,
        messages=[{"role": "system", "content": sys_prompt}],
        usages=[],
        mode=mode,
    )

    return chat_data


def _save_chat(chat_data: ChatData) -> ChatData:
    """ Record the given chat in the database, updating its id attribute with the new row id. """
    auth = get_auth()
    user_id = auth.user_id
    role_id = auth.cur_class.role_id if auth.cur_class else None

    db = get_db()
    cur = db.execute(
        "INSERT INTO chats (user_id, role_id, chat_json) VALUES (?, ?, ?)",
        [user_id, role_id, msgspec.json.encode(chat_data).decode()]
    )
    new_row_id = cur.lastrowid

    db.commit()

    assert new_row_id is not None
    return msgspec.structs.replace(chat_data, id=new_row_id)
