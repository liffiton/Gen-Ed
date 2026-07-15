# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from sqlite3 import Cursor
from typing import Final

import msgspec
from flask import current_app
from markupsafe import Markup

from gened.access import RequireComponent
from gened.app_data import (
    ChartData,
    DataSource,
    Filters,
)
from gened.class_config.types import ConfigShareLink, ConfigTable
from gened.db import get_db
from gened.tables import Col, DataTableSpec, NumCol, TimeCol, UserCol

from .data_types import GuidedAnalysis, ObjectiveStatus, TutorConfig
from .guided import bp as guided_bp

# To register the configuration UI inside gened's class_config module
guided_tutor_config_table = ConfigTable(
    config_item_class=TutorConfig,
    name='guided_tutor',
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
    extra_routes=guided_bp,
    availability_requirements=(RequireComponent('tutors', feature='guided'), ),
)


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
    """, where_params).fetchall()  # noqa: S608 -- where_clause is generated safely
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
        LEFT JOIN roles ON t.role_id=roles.id
        LEFT JOIN classes ON roles.class_id=classes.id
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        WHERE {where_clause}
        ORDER BY t.id DESC
        LIMIT ?
        OFFSET ?
    """  # noqa: S608 -- where_clause is generated safely
    cur = db.execute(sql, [*where_params, limit, offset])
    return cur


def fmt_analysis(value: str) -> Markup:
    '''Format an analysis json object for display in a table cell.'''
    if not value:
        return Markup()

    try:
        analysis = msgspec.json.decode(value, type=GuidedAnalysis)
        #summary = analysis.summary
        progress = analysis.progress
        counts = Counter(objective.status for objective in progress)
    except (msgspec.DecodeError, TypeError) as e:
        current_app.logger.error(e)
        return Markup("parse error")

    statuses: list[tuple[ObjectiveStatus, str]] = [
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
    display_name='Chats',
    get_data=get_chats,
    table_spec=DataTableSpec(
        columns=[NumCol('id'), UserCol('user'), TimeCol('chat_started'), Col('topic'), NumCol('user messages'), AnalysisCol('analysis')],
        link_col=0,
        link_template='/tutor/${value}',
    ),
    time_col='chat_started',
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
