# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from sqlite3 import Cursor

from gened.app_data import (
    Filters,
    register_data,
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
            queries.assignment AS assignment,
            queries.topics AS topics,
            queries.response_text AS response,
            queries.user_id AS user_id,
            classes.id AS class_id
        FROM queries
        JOIN users ON queries.user_id=users.id
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        LEFT JOIN roles ON UNLIKELY(queries.role_id=roles.id)  -- UNLIKELY() to help query planner in older sqlite versions
        LEFT JOIN classes ON UNLIKELY(roles.class_id=classes.id)
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
    columns=[NumCol('id'), UserCol('user'), TimeCol('time'), Col('assignment'), Col('topics'), ResponseCol('response')],
    link_col=0,
    link_template="/ideas/view/${value}",
)


def register_with_gened() -> None:
    """ Register admin functionality with the main gened admin module."""
    register_data('queries', get_queries, queries_table)
