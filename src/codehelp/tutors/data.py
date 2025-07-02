from dataclasses import dataclass
from sqlite3 import Cursor
from typing import Any, Literal, TypeAlias

from flask import Flask, url_for

from gened.app_data import (
    Filters,
    register_data,
)
from gened.db import get_db
from gened.llm import ChatMessage
from gened.tables import Col, DataTable, NumCol, ResponseCol, TimeCol, UserCol

ChatMode: TypeAlias = Literal["inquiry", "guided"]

@dataclass
class ChatData:
    topic: str
    context_name: str | None
    messages: list[ChatMessage]
    mode: ChatMode
    analysis: dict[str, Any] | None = None


def get_chats(filters: Filters, /, limit: int=-1, offset: int=0) -> Cursor:
    db = get_db()
    where_clause, where_params = filters.make_where(['consumer', 'class', 'user', 'role', 'chat'])
    sql = f"""
        SELECT
            chats.id AS id,
            json_array(users.display_name, auth_providers.name, users.display_extra) AS user,
            chats.chat_started,
            chats.user_id AS user_id,
            classes.id AS class_id
        FROM chats
        JOIN users ON chats.user_id=users.id
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        LEFT JOIN roles ON UNLIKELY(chats.role_id=roles.id)  -- UNLIKELY() to help query planner in older sqlite versions
        LEFT JOIN classes ON UNLIKELY(roles.class_id=classes.id)
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        WHERE {where_clause}
        ORDER BY chats.id DESC
        LIMIT ?
        OFFSET ?
    """
    cur = db.execute(sql, [*where_params, limit, offset])
    return cur


def register_with_gened() -> None:
    chats_table = DataTable(
        name='chats',
        columns=[NumCol('id'), UserCol('user'), TimeCol('chat_started')],
        link_col=0,
        link_template='/tutor/chat/$value',
    )
    register_data('chats', get_chats, chats_table)
