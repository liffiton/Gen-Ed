# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from sqlite3 import Cursor

from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from gened.app_data import (
    Filters,
    get_admin_charts,
    get_data_sources,
)
from gened.csv import csv_response
from gened.db import get_db
from gened.tables import Col, DataTable, NumCol, UserCol

from .component_registry import register_blueprint

bp = Blueprint('admin_main', __name__, url_prefix='/', template_folder='templates')

register_blueprint(bp)


def get_consumers(_: Filters | None, limit: int=-1, offset: int=0) -> Cursor:
    db = get_db()
    return db.execute("""
        SELECT
            consumers.id AS id,
            consumers.lti_consumer AS consumer,
            models.shortname AS model,
            COUNT(DISTINCT classes.id) AS "#classes",
            COUNT(DISTINCT roles.id) AS "#users",
            COUNT(queries.id) AS "#queries",
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS "1wk"
        FROM consumers
        LEFT JOIN models ON models.id=consumers.model_id
        LEFT JOIN classes_lti ON classes_lti.lti_consumer_id=consumers.id
        LEFT JOIN classes ON classes.id=classes_lti.class_id
        LEFT JOIN roles ON roles.class_id=classes.id
        LEFT JOIN queries ON queries.role_id=roles.id
        GROUP BY consumers.id
        ORDER BY "1wk" DESC, consumers.id DESC
        LIMIT ?
        OFFSET ?
    """, [limit, offset])


def get_classes(filters: Filters, limit: int=-1, offset: int=0) -> Cursor:
    db = get_db()
    where_clause, where_params = filters.make_where(['consumer'])
    return db.execute(f"""
        SELECT
            classes.id AS id,
            classes.name AS name,
            COALESCE(consumers.lti_consumer, class_owner.display_name) AS owner,
            models.shortname AS model,
            COUNT(DISTINCT roles.id) AS "#users",
            COUNT(queries.id) AS "#queries",
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS "1wk"
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
        ORDER BY "1wk" DESC, classes.id DESC
        LIMIT ?
        OFFSET ?
    """, [*where_params, limit, offset])


def get_users(filters: Filters, limit: int=-1, offset: int=0) -> Cursor:
    db = get_db()
    where_clause, where_params = filters.make_where(['consumer', 'class'])
    return db.execute(f"""
        SELECT
            users.id AS id,
            json_array(users.display_name, auth_providers.name, users.display_extra) AS user,
            COUNT(queries.id) AS "#queries",
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS "1wk",
            users.query_tokens AS tokens
        FROM users
        LEFT JOIN auth_providers ON auth_providers.id=users.auth_provider
        LEFT JOIN roles ON roles.user_id=users.id
        LEFT JOIN classes ON roles.class_id=classes.id
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        LEFT JOIN queries ON queries.user_id=users.id
        WHERE {where_clause}
        GROUP BY users.id
        ORDER BY "1wk" DESC, users.id DESC
        LIMIT ?
        OFFSET ?
    """, [*where_params, limit, offset])


def get_roles(filters: Filters, limit: int=-1, offset: int=0) -> Cursor:
    db = get_db()
    where_clause, where_params = filters.make_where(['consumer', 'class', 'user'])
    return db.execute(f"""
        SELECT
            roles.id AS id,
            json_array(users.display_name, auth_providers.name, users.display_extra) AS user,
            roles.role AS role,
            classes.name AS class,
            COALESCE(consumers.lti_consumer, class_owner.display_name) AS "class owner"
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
        LIMIT ?
        OFFSET ?
    """, [*where_params, limit, offset])


@bp.route("/api/<string:table>/")
@bp.route("/api/<string:table>/<string:kind>")
def get_data(table: str, kind: str='json') -> str | Response:
    if kind not in ['json', 'csv']:
        return abort(404)

    data_source_map = {
        'consumers': get_consumers,
        'classes': get_classes,
        'users': get_users,
        'roles': get_roles,
    }

    data_source_map |= {name: source.function for name, source in get_data_sources().items()}

    if table not in data_source_map:
        return abort(404)

    filters = Filters.from_args()
    limit = int(request.args.get('limit', -1))
    offset = int(request.args.get('offset', 0))

    data_func = data_source_map[table]
    data = data_func(filters, limit=limit, offset=offset).fetchall()

    if kind == 'json':
        return jsonify([dict(row) for row in data])
    if kind == 'csv':
        return csv_response('admin_export', table, data)
    return ''


@bp.route("/")
def main() -> str:
    filters = Filters.from_args(with_display=True)

    charts = []
    for generate_chart in get_admin_charts():
        charts.extend(generate_chart(filters))

    init_rows = 20  # number of rows to send in the page for each table

    consumers = DataTable(
        name='consumers',
        columns=[NumCol('id'), Col('consumer'), Col('model'), NumCol('#classes'), NumCol('#queries'), NumCol('1wk')],
        link_col=0,
        link_template=filters.template_string('consumer'),
        extra_links=[{'icon': "pencil", 'text': "Edit consumer", 'handler': "admin.admin_consumers.consumer_form", 'param': "consumer_id"}],
        create_endpoint='admin.admin_consumers.consumer_new',
        ajax_url=url_for('.get_data', table='consumers', offset=init_rows, **request.args),  # type: ignore[arg-type]
        data=get_consumers(None, limit=init_rows).fetchall(),
    )

    classes = DataTable(
        name='classes',
        columns=[NumCol('id'), Col('name'), Col('owner'), Col('model'), NumCol('#users'), NumCol('#queries'), NumCol('1wk')],
        link_col=0,
        link_template=filters.template_string('class'),
        extra_links=[{'icon': "admin", 'text': "Administer class", 'handler': "classes.switch_class_handler", 'param': "class_id"}],
        ajax_url=url_for('.get_data', table='classes', offset=init_rows, **request.args),  # type: ignore[arg-type]
        data=get_classes(filters, limit=init_rows).fetchall(),
    )

    users = DataTable(
        name='users',
        columns=[NumCol('id'), UserCol('user'), NumCol('#queries'), NumCol('1wk'), NumCol('tokens')],
        link_col=0,
        link_template=filters.template_string('user'),
        ajax_url=url_for('.get_data', table='users', offset=init_rows, **request.args),  # type: ignore[arg-type]
        data=get_users(filters, limit=init_rows).fetchall(),
    )

    roles = DataTable(
        name='roles',
        columns=[NumCol('id'), UserCol('user'), Col('role'), Col('class'), Col('class owner')],
        link_col=0,
        link_template=filters.template_string('role'),
        ajax_url=url_for('.get_data', table='roles', offset=init_rows, **request.args),  # type: ignore[arg-type]
        data=get_roles(filters, limit=init_rows).fetchall(),
    )

    tables = [
        consumers,
        classes,
        users,
        roles,
    ]

    for name, source in get_data_sources().items():
        table = source.table
        table.data = source.function(filters, limit=init_rows).fetchall()
        table.csv_link = url_for('.get_data', table=name, kind='csv', **request.args)  # type: ignore[arg-type]
        table.ajax_url = url_for('.get_data', table=name, kind='json', offset=init_rows, limit=1000-init_rows, **request.args)  # type: ignore[arg-type]

        tables.append(table)

    return render_template(
        "admin_main.html",
        charts=charts,
        filters=filters,
        tables=tables,
    )
