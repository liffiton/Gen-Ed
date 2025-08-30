# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from sqlite3 import Cursor
from typing import Any, Final, Literal, TypeAlias

from markupsafe import Markup

from gened.app_data import (
    ChartData,
    DataSource,
    Filters,
)
from gened.db import get_db
from gened.llm import ChatMessage
from gened.tables import Col, DataTable, NumCol, TimeCol, UserCol

ChatMode: TypeAlias = Literal["inquiry", "guided"]

@dataclass(kw_only=True)
class ChatData:
    id: int | None = None
    user_id: int | None = None
    class_id: int | None = None
    topic: str
    context_name: str | None = None
    messages: list[ChatMessage]
    usages: list[dict[str, Any]] = field(default_factory=list)
    mode: ChatMode
    analysis: dict[str, Any] | None = None


def gen_chats_chart(filters: Filters) -> list[ChartData]:
    """ Generate chart data for CodeHelp tutor chat charts.
    Filter using same filters as set in the admin interface
    (passed in where_clause and where_params).
    """
    db = get_db()

    where_clause, where_params = filters.make_where(['consumer', 'class', 'user', 'role'])

    # https://www.sqlite.org/lang_with.html#recursive_query_examples
    usage_data = db.execute(f"""
        WITH RECURSIVE
            cnt(val) AS (VALUES(0) UNION ALL SELECT val+1 FROM cnt WHERE val<14)
        SELECT
            val AS days_since,
            COALESCE(chats, 0) AS chats
        FROM cnt
        LEFT JOIN (
        SELECT
            CAST(julianday() AS INTEGER) - CAST(julianday(chats.chat_started) AS INTEGER) AS days_since,
            COUNT(chats.id) AS chats
            FROM chats
            JOIN users ON chats.user_id=users.id
            LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
            LEFT JOIN roles ON chats.role_id=roles.id
            LEFT JOIN classes ON roles.class_id=classes.id
            LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
            LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
            WHERE days_since <= 14
            AND {where_clause}
            GROUP BY days_since
        ) ON days_since = val
        ORDER BY days_since DESC
    """, where_params).fetchall()
    days_since = [row['days_since'] for row in usage_data]
    data_chats = [row['chats'] for row in usage_data]
    charts: list[ChartData] = [
        ChartData(
            labels=days_since,
            series={'chats': data_chats},
            colors=['#66ccff'],
        ),
    ]

    return charts


def get_chats(filters: Filters, /, limit: int=-1, offset: int=0) -> Cursor:
    db = get_db()
    where_clause, where_params = filters.make_where(['consumer', 'class', 'user', 'role', 'row_id'])
    sql = f"""
        SELECT
            t.id AS id,
            json_array(users.display_name, auth_providers.name, users.display_extra) AS user,
            t.chat_started,
            t.user_id AS user_id,
            json_extract(t.chat_json, '$.topic') AS topic,
            t.chat_json AS chat_json,
            json_extract(t.chat_json, '$.analysis') AS analysis,
            classes.id AS class_id,
            (
                SELECT COUNT(*)
                FROM json_each(json_extract(t.chat_json, '$.messages'))
                WHERE json_extract(json_each.value, '$.role')='user'
            ) as "user messages"
        FROM chats AS t
        JOIN users ON t.user_id=users.id
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        LEFT JOIN roles ON UNLIKELY(t.role_id=roles.id)  -- UNLIKELY() to help query planner in older sqlite versions
        LEFT JOIN classes ON UNLIKELY(roles.class_id=classes.id)
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        WHERE {where_clause}
        ORDER BY t.id DESC
        LIMIT ?
        OFFSET ?
    """
    cur = db.execute(sql, [*where_params, limit, offset])
    return cur


def fmt_analysis(value: str) -> Markup:
    '''Format an analysis json object for display in a table cell.'''
    if not value:
        return Markup()

    obj = json.loads(value)
    #summary = obj['summary']
    progress = obj['progress']
    counts = Counter(objective['status'] for objective in progress)

    statuses = [
        ('not started', '#ebb'),
        ('moved on', '#dca'),
        ('in progress', '#add'),
        ('completed', '#ada'),
    ]
    tags = [
        Markup("<span class='tag m-0' style='background: {}; color: {}'>{}</span>").format(
            color if counts[status] else '#ddd',
            'inherit' if counts[status] else '#999',
            counts[status]
        )
        for status, color in statuses
    ]
    title = Markup("&#13;").join(Markup("{}: {}").format(status, counts[status]) for status, _ in statuses if counts[status])

    return Markup("<div class='tags has-addons' title='{}'>").format(title) + Markup("").join(tags) + Markup("</div>")


@dataclass(frozen=True, kw_only=True)
class AnalysisCol(Col):
    kind: Final = 'html'
    prerender: Final[Callable[[str], str]] = fmt_analysis

chats_data_source = DataSource(
    table_name='chats',
    display_name='chats',
    get_data=get_chats,
    table=DataTable(
        name='chats',
        columns=[NumCol('id'), UserCol('user'), TimeCol('chat_started'), Col('topic'), NumCol('user messages'), AnalysisCol('analysis')],
        link_col=0,
        link_template='/tutor/${value}',
    ),
    time_col='chat_started',
    requires_experiment='chats_experiment',
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
