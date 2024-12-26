# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from sqlite3 import Row
from urllib.parse import urlencode

from flask import (
    render_template,
    request,
)
from werkzeug.wrappers.response import Response

from gened.csv import csv_response
from gened.db import get_db

from . import bp as bp_admin


@dataclass(frozen=True)
class ChartData:
    labels: list[str | int | float]
    series: dict[str, list[int | float]]
    colors: list[str]


# A module-level list of registered charts for the main admin page.  Updated by register_admin_chart()
_admin_chart_generators: list[Callable[[str, list[str]], list[ChartData]]] = []


def register_admin_chart(generator_func: Callable[[str, list[str]], list[ChartData]]) -> None:
    _admin_chart_generators.append(generator_func)


@dataclass(frozen=True)
class FilterSpec:
    name: str
    column: str
    display_query: str

_available_filter_specs = [
    FilterSpec('consumer', 'consumers.id', 'SELECT lti_consumer FROM consumers WHERE id=?'),
    FilterSpec('class', 'classes.id', 'SELECT name FROM classes WHERE id=?'),
    FilterSpec('user', 'users.id', 'SELECT display_name FROM users WHERE id=?'),
    FilterSpec('role', 'roles.id', """
        SELECT printf("%s (%s:%s)", users.display_name, role_class.name, roles.role)
        FROM roles
        LEFT JOIN users ON users.id=roles.user_id
        LEFT JOIN classes AS role_class ON role_class.id=roles.class_id
        WHERE roles.id=?
    """),
]


@dataclass(frozen=True)
class Filter:
    spec: FilterSpec
    value: str
    display_value: str


class Filters:
    def __init__(self) -> None:
        self._filters: list[Filter] = []

    def __iter__(self) -> Iterator[Filter]:
        return self._filters.__iter__()

    def add(self, spec: FilterSpec, value: str, display_value: str) -> None:
        self._filters.append(Filter(spec, value, display_value))

    def make_where(self, selected: list[str]) -> tuple[str, list[str]]:
        filters = [f for f in self._filters if f.spec.name in selected]
        if not filters:
            return "1", []
        else:
            return (
                " AND ".join(f"{f.spec.column}=?" for f in filters),
                [f.value for f in filters]
            )

    def filter_string(self) -> str:
        filter_dict = {f.spec.name: f.value for f in self._filters}
        return f"?{urlencode(filter_dict)}"

    def filter_string_without(self, exclude_name: str) -> str:
        filter_dict = {f.spec.name: f.value for f in self._filters if f.spec.name != exclude_name}
        return f"?{urlencode(filter_dict)}"

    def template_string(self, selected_name: str) -> str:
        '''
        Return a string that will be used to create a link URL for each row in
        a table.  This string is passed to a Javascript function as
        `{{template_string}}`, to be used with string interpolation in
        Javascript.  Therefore, it should contain "${{value}}" as a placeholder
        for the value -- it is rendered by Python's f-string interpolation as
        "${value}" in the page source, suitable for Javascript string
        interpolation.
        '''
        return self.filter_string_without(selected_name) + f"&{selected_name}=${{value}}"


def get_queries_filtered(where_clause: str, where_params: list[str], queries_limit: int | None = None) -> list[Row]:
    db = get_db()
    sql = f"""
        SELECT
            queries.*,
            users.id AS user_id,
            users.display_name,
            users.email,
            users.auth_name,
            auth_providers.name AS auth_provider
        FROM queries
        JOIN users ON queries.user_id=users.id
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        LEFT JOIN roles ON queries.role_id=roles.id
        LEFT JOIN classes ON roles.class_id=classes.id
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        WHERE {where_clause}
        ORDER BY queries.id DESC
    """
    if queries_limit is not None:
        sql += f"LIMIT {int(queries_limit)}"
    queries = db.execute(sql, [*where_params]).fetchall()
    return queries


@bp_admin.route("/csv/queries/")
def get_queries_csv() -> str | Response:
    filters = Filters()

    for spec in _available_filter_specs:
        if spec.name in request.args:
            value = request.args[spec.name]
            filters.add(spec, value, "dummy value")  # display value not used in CSV export

    # queries, filtered by consumer, class, user, and role
    where_clause, where_params = filters.make_where(['consumer', 'class', 'user', 'role'])
    queries = get_queries_filtered(where_clause, where_params)

    return csv_response('admin_export', 'queries', queries)


@bp_admin.route("/")
def main() -> str:
    db = get_db()
    filters = Filters()

    for spec in _available_filter_specs:
        if spec.name in request.args:
            value = request.args[spec.name]
            # bit of a hack to have a single SQL query cover all different filters...
            display_row = db.execute(spec.display_query, [value]).fetchone()
            display_value = display_row[0]
            filters.add(spec, value, display_value)

    # all consumers
    consumers = db.execute("""
        SELECT
            consumers.*,
            models.shortname AS model,
            COUNT(queries.id) AS num_queries,
            COUNT(DISTINCT classes.id) AS num_classes,
            COUNT(DISTINCT roles.id) AS num_users,
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS num_recent_queries
        FROM consumers
        LEFT JOIN models ON models.id=consumers.model_id
        LEFT JOIN classes_lti ON classes_lti.lti_consumer_id=consumers.id
        LEFT JOIN classes ON classes.id=classes_lti.class_id
        LEFT JOIN roles ON roles.class_id=classes.id
        LEFT JOIN queries ON queries.role_id=roles.id
        GROUP BY consumers.id
        ORDER BY num_recent_queries DESC, consumers.id DESC
    """).fetchall()

    # classes, filtered by consumer
    where_clause, where_params = filters.make_where(['consumer'])
    classes = db.execute(f"""
        SELECT
            classes.id,
            classes.name,
            COALESCE(consumers.lti_consumer, class_owner.display_name) AS owner,
            models.shortname AS model,
            COUNT(DISTINCT roles.id) AS num_users,
            COUNT(queries.id) AS num_queries,
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS num_recent_queries
        FROM classes
        LEFT JOIN classes_user ON classes.id=classes_user.class_id
        LEFT JOIN users AS class_owner ON classes_user.creator_user_id=class_owner.id
        LEFT JOIN models ON models.id=classes_user.model_id
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        LEFT JOIN roles ON roles.class_id=classes.id
        LEFT JOIN queries ON queries.role_id=roles.id
        WHERE {where_clause}
        GROUP BY classes.id
        ORDER BY num_recent_queries DESC, classes.id DESC
    """, where_params).fetchall()

    # users, filtered by consumer and class
    where_clause, where_params = filters.make_where(['consumer', 'class'])
    users = db.execute(f"""
        SELECT
            users.id,
            users.display_name,
            users.email,
            users.auth_name,
            auth_providers.name AS auth_provider,
            users.query_tokens,
            COUNT(queries.id) AS num_queries,
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS num_recent_queries
        FROM users
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        LEFT JOIN roles ON roles.user_id=users.id
        LEFT JOIN classes ON roles.class_id=classes.id
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        LEFT JOIN queries ON queries.user_id=users.id
        WHERE {where_clause}
        GROUP BY users.id
        ORDER BY num_recent_queries DESC, users.id DESC
    """, where_params).fetchall()

    # roles, filtered by consumer, class, and user
    where_clause, where_params = filters.make_where(['consumer', 'class', 'user'])
    roles = db.execute(f"""
        SELECT
            roles.*,
            users.display_name,
            users.email,
            users.auth_name,
            classes.name AS class_name,
            COALESCE(consumers.lti_consumer, class_owner.display_name) AS class_owner,
            auth_providers.name AS auth_provider
        FROM roles
        LEFT JOIN users ON users.id=roles.user_id
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        LEFT JOIN classes ON roles.class_id=classes.id
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN classes_user ON classes.id=classes_user.class_id
        LEFT JOIN users AS class_owner ON classes_user.creator_user_id=class_owner.id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        WHERE {where_clause}
        ORDER BY roles.id DESC
    """, where_params).fetchall()

    # queries, filtered by consumer, class, user, and role
    where_clause, where_params = filters.make_where(['consumer', 'class', 'user', 'role'])
    queries = get_queries_filtered(where_clause, where_params, queries_limit=200)

    charts = []
    for generate_chart in _admin_chart_generators:
        charts.extend(generate_chart(where_clause, where_params))

    # 'admin.html' should be defined in each individual application
    return render_template("admin.html", charts=charts, consumers=consumers, classes=classes, users=users, roles=roles, queries=queries, filters=filters)
