# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from sqlite3 import Cursor

from gened.app_data import (
    ChartData,
    DataSource,
    Filters,
)
from gened.db import get_db
from gened.tables import Col, DataTable, NumCol, ResponseCol, TimeCol, UserCol


def gen_query_charts(filters: Filters) -> list[ChartData]:
    """ Generate chart data for CodeHelp query charts.
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
            COALESCE(queries, 0) AS queries,
            COALESCE(errors, 0) AS errors,
            COALESCE(insufficient, 0) AS insufficient
        FROM cnt
        LEFT JOIN (
        SELECT
            CAST(julianday() AS INTEGER) - CAST(julianday(queries.query_time) AS INTEGER) AS days_since,
            COUNT(queries.id) AS queries,
            SUM(json_extract(queries.response_json, '$[0].error') IS NOT NULL) AS errors,
            SUM(json_extract(queries.response_text, '$.insufficient') IS NOT NULL) AS insufficient
            FROM queries
            JOIN users ON queries.user_id=users.id
            LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
            LEFT JOIN roles ON queries.role_id=roles.id
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
    data_queries = [row['queries'] for row in usage_data]
    data_errors = [row['errors'] for row in usage_data]
    data_insuff = [row['insufficient'] for row in usage_data]
    data_error_rate = [(err / total) if total else 0 for err, total in zip(data_errors, data_queries, strict=True)]
    data_insuff_rate = [(insuff / total) if total else 0 for insuff, total in zip(data_insuff, data_queries, strict=True)]
    charts: list[ChartData] = [
        ChartData(
            labels=days_since,
            series={'queries': data_queries, 'errors': data_errors, 'insufficient': data_insuff},
            colors=['#66ccff', '#ff0000', '#ffcc00'],
        ),
        ChartData(
            labels=days_since,
            series={'error rate': data_error_rate, 'insufficient rate': data_insuff_rate},
            colors=['#ff0000', '#ffcc00'],
        ),
    ]

    return charts


def get_queries(filters: Filters, /, limit: int=-1, offset: int=0) -> Cursor:
    db = get_db()
    where_clause, where_params = filters.make_where(['consumer', 'class', 'user', 'role', 'row_id'])
    sql = f"""
        SELECT
            t.id AS id,
            json_array(users.display_name, auth_providers.name, users.display_extra) AS user,
            t.query_time AS time,
            t.context_name AS context,
            t.code AS code,
            t.error AS error,
            t.issue AS issue,
            t.response_text AS response,
            t.helpful AS helpful,
            t.helpful_emoji AS helpful_emoji,
            t.user_id AS user_id,
            t.context_string_id AS context_string_id,
            classes.id AS class_id,
            t.topics_json AS topics_json
        FROM queries AS t
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
    """
    cur = db.execute(sql, [*where_params, limit, offset])
    return cur

queries_table = DataTable(
    name='queries',
    columns=[NumCol('id'), UserCol('user'), TimeCol('time'), Col('context'), Col('code'), Col('error'), Col('issue'), ResponseCol('response'), Col('helpful_emoji', align='center')],
    link_col=0,
    link_template="/help/view/${value}",
)

queries_data_source = DataSource(
    'queries',
    'queries',
    get_queries,
    queries_table,
    time_col='query_time',
)


class QueriesDeletionHandler:
    """Personal data deletion for the queries component."""

    @staticmethod
    def delete_user_data(user_id: int) -> None:
        """Delete/Anonymize personal data for a user while preserving non-personal data for analysis."""
        db = get_db()

        # Anonymize personal data in queries
        db.execute("""
            UPDATE queries
            SET code = CASE
                    WHEN code IS NOT NULL THEN '[deleted]'
                    ELSE NULL
                END,
                error = CASE
                    WHEN error IS NOT NULL THEN '[deleted]'
                    ELSE NULL
                END,
                issue = '[deleted]',
                context_name = '[deleted]',
                context_string_id = NULL,
                user_id = -1
            WHERE user_id = ?
        """, [user_id])

    @staticmethod
    def delete_class_data(class_id: int) -> None:
        """Delete/Anonymize personal data for a class while preserving non-personal data for analysis."""
        db = get_db()

        # Anonymize personal data in queries
        db.execute("""
            UPDATE queries
            SET code = CASE
                    WHEN code IS NOT NULL THEN '[deleted]'
                    ELSE NULL
                END,
                error = CASE
                    WHEN error IS NOT NULL THEN '[deleted]'
                    ELSE NULL
                END,
                issue = '[deleted]',
                context_name = '[deleted]',
                context_string_id = NULL,
                user_id = -1
            WHERE role_id IN (
                SELECT id FROM roles WHERE class_id = ?
            )
        """, [class_id])
