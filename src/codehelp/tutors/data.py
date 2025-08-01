from dataclasses import dataclass
from sqlite3 import Cursor
from typing import Any, Literal, TypeAlias

from gened.app_data import (
    DataSource,
    Filters,
)
from gened.db import get_db
from gened.llm import ChatMessage
from gened.tables import DataTable, NumCol, TimeCol, UserCol

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
            classes.id AS class_id,
            (
                SELECT COUNT(*)
                FROM json_each(json_extract(chats.chat_json, '$.messages'))
                WHERE json_extract(json_each.value, '$.role')='user'
            ) as "user messages"
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


chats_table = DataTable(
    name='chats',
    columns=[NumCol('id'), UserCol('user'), TimeCol('chat_started'), NumCol('user messages')],
    link_col=0,
    link_template='/tutor/${value}',
)

chats_data_source = DataSource(
    'chats',
    get_chats,
    chats_table,
)


class TutorsDeletionHandler:
    """Personal data deletion for the tutors component."""

    @staticmethod
    def delete_user_data(user_id: int) -> None:
        """Delete/Anonymize personal data for a user while preserving non-personal data for analysis."""
        db = get_db()

        # Anonymize personal data in chats
        db.execute("""
            UPDATE chats
            SET chat_json = '{}',
                user_id = -1
            WHERE user_id = ?
        """, [user_id])

    @staticmethod
    def delete_class_data(class_id: int) -> None:
        """Delete/Anonymize personal data for a class while preserving non-personal data for analysis."""
        db = get_db()

        # Anonymize personal data in chats
        db.execute("""
            UPDATE chats
            SET chat_json = '{}',
                user_id = -1
            WHERE role_id IN (
                SELECT id FROM roles WHERE class_id = ?
            )
        """, [class_id])
