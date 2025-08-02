# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from sqlite3 import Cursor

from gened.app_data import (
    DataSource,
    Filters,
)
from gened.db import get_db
from gened.tables import Col, DataTable, NumCol, ResponseCol, TimeCol, UserCol


def get_queries(filters: Filters, limit: int=-1, offset: int=0) -> Cursor:
    db = get_db()
    where_clause, where_params = filters.make_where(['consumer', 'class', 'user', 'role', 'query'])
    sql = f"""
        SELECT
            queries.id AS id,
            json_array(users.display_name, auth_providers.name, users.display_extra) AS user,
            queries.query_time AS time,
            queries.writing AS writing,
            queries.response_text AS response,
            queries.user_id AS user_id,
            classes.id AS class_id
        FROM queries
        JOIN users ON queries.user_id=users.id
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        LEFT JOIN roles ON queries.role_id=roles.id
        LEFT JOIN classes ON roles.class_id=classes.id
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        WHERE {where_clause}
        ORDER BY queries.id DESC
        LIMIT ?
        OFFSET ?
    """
    cur = db.execute(sql, [*where_params, limit, offset])
    return cur


queries_table = DataTable(
    name='queries',
    columns=[NumCol('id'), UserCol('user'), TimeCol('time'), Col('writing'), ResponseCol('response')],
    link_col=0,
    link_template="/check/view/${value}",
)

queries_data_source = DataSource(
    'queries',
    'queries',
    get_queries,
    queries_table,
)


class LangDeletionHandler:
    """Handler for deleting user data."""

    @staticmethod
    def delete_user_data(user_id: int) -> None:
        """Delete/Anonymize personal data for a user while preserving non-personal data for analysis."""
        db = get_db()

        # Delete queries
        db.execute("""
            DELETE queries
            WHERE user_id = ?
        """, [user_id])

    @staticmethod
    def delete_class_data(class_id: int) -> None:
        """Delete/Anonymize personal data for a class while preserving non-personal data for analysis."""
        db = get_db()

        # Delete queries
        db.execute("""
            DELETE FROM queries
            WHERE role_id IN (
                SELECT id FROM roles WHERE class_id = ?
            )
        """, [class_id])
