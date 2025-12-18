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
    DataSource,
    Filters,
    get_admin_charts,
    get_registered_data_sources,
)
from gened.csv import csv_response
from gened.db import get_db
from gened.tables import Action, Col, DataTable, NumCol, UserCol

from .component_registry import register_blueprint

bp = Blueprint('admin_main', __name__, url_prefix='/', template_folder='templates')

register_blueprint(bp)


def count_activity() -> None:
    """ Count user activity per-user and per-role, and store in a temporary
    table to be used in various queries for the admin screen. """
    db = get_db()

    db.execute("""
        CREATE TEMPORARY TABLE __activity_counts AS
        SELECT
            users.id AS user_id,
            v_user_items.role_id AS role_id,  -- may be NULL due to LEFT JOIN
            COUNT(v_user_items.entry_time) AS uses,
            SUM(CASE WHEN v_user_items.entry_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS uses_1wk
        FROM users
        LEFT JOIN v_user_items ON v_user_items.user_id = users.id
        GROUP BY users.id, v_user_items.role_id
    """)


def get_consumers(_: Filters, limit: int=-1, offset: int=0) -> Cursor:
    db = get_db()
    return db.execute("""
        SELECT
            consumers.id AS id,
            consumers.lti_consumer AS consumer,
            models.shortname AS model,
            COUNT(DISTINCT classes.id) AS "#classes",
            COUNT(DISTINCT roles.id) AS "#users",
            SUM(__activity_counts.uses) AS "#uses",
            SUM(__activity_counts.uses_1wk) AS "1wk"
        FROM consumers
        LEFT JOIN models ON models.id=consumers.model_id
        LEFT JOIN classes_lti ON classes_lti.lti_consumer_id=consumers.id
        LEFT JOIN classes ON classes.id=classes_lti.class_id
        LEFT JOIN roles ON roles.class_id=classes.id
        LEFT JOIN __activity_counts ON __activity_counts.role_id=roles.id
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
            SUM(__activity_counts.uses) AS "#uses",
            SUM(__activity_counts.uses_1wk) AS "1wk"
        FROM classes
        LEFT JOIN classes_user ON classes.id=classes_user.class_id
        LEFT JOIN users AS class_owner ON classes_user.creator_user_id=class_owner.id
        LEFT JOIN models ON models.id=classes_user.model_id
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        LEFT JOIN roles ON roles.class_id=classes.id
        LEFT JOIN __activity_counts ON __activity_counts.role_id=roles.id
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
            users.query_tokens AS tokens,
            SUM(__activity_counts.uses) AS "#uses",
            SUM(__activity_counts.uses_1wk) AS "1wk"
        FROM users
        LEFT JOIN auth_providers ON auth_providers.id=users.auth_provider
        LEFT JOIN roles ON roles.user_id=users.id
        LEFT JOIN classes ON roles.class_id=classes.id
        LEFT JOIN classes_lti ON classes.id=classes_lti.class_id
        LEFT JOIN consumers ON consumers.id=classes_lti.lti_consumer_id
        LEFT JOIN __activity_counts ON __activity_counts.user_id=users.id
        WHERE {where_clause}
          AND (roles.id IS NULL OR __activity_counts.role_id=roles.id)
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


def get_data_sources(filters: Filters) -> dict[str, DataSource]:
    # set up temporary table with activity counts
    count_activity()

    data_funcs = {
        'consumers': get_consumers,
        'classes': get_classes,
        'users': get_users,
        'roles': get_roles,
    }

    datatables = {}

    datatables['consumers'] = DataTable(
        name='consumers',
        columns=[NumCol('id'), Col('consumer'), Col('model'), NumCol('#classes'), NumCol('#users'), NumCol('#uses'), NumCol('1wk')],
        link_col=0,
        link_template=filters.template_string('consumer'),
        actions=[Action("Edit consumer", icon='pencil', url=url_for('admin.admin_consumers.consumer_form'), id_col=0)],
        create_endpoint='admin.admin_consumers.consumer_new',
    )

    datatables['classes'] = DataTable(
        name='classes',
        columns=[NumCol('id'), Col('name'), Col('owner'), Col('model'), NumCol('#users'), NumCol('#uses'), NumCol('1wk')],
        link_col=0,
        link_template=filters.template_string('class'),
        actions=[Action("Administer class", icon='admin', url=url_for('classes.switch_class_handler'), id_col=0)],
    )

    datatables['users'] = DataTable(
        name='users',
        columns=[NumCol('id'), UserCol('user'), NumCol('tokens'), NumCol('#uses'), NumCol('1wk')],
        link_col=0,
        link_template=filters.template_string('user'),
    )

    datatables['roles'] = DataTable(
        name='roles',
        columns=[NumCol('id'), UserCol('user'), Col('role'), Col('class'), Col('class owner')],
        link_col=0,
        link_template=filters.template_string('role'),
    )

    built_ins = {
        table: DataSource(table_name=table, display_name=table, get_data=data_funcs[table], table=datatables[table])
        for table in ('consumers', 'classes', 'users', 'roles')
    }

    registered = get_registered_data_sources()

    return built_ins | registered


@bp.route("/api/<string:name>/")
@bp.route("/api/<string:name>/<string:kind>")
def get_data(name: str, kind: str='json') -> str | Response:
    if kind not in ['json', 'csv']:
        abort(404)

    filters = Filters.from_args()
    limit = int(request.args.get('limit', -1))
    offset = int(request.args.get('offset', 0))

    all_data_sources = get_data_sources(filters)

    if name not in all_data_sources:
        abort(404)

    source = all_data_sources[name]
    table = source.table
    table.data = source.get_data(filters, limit=limit, offset=offset).fetchall()

    if kind == 'json':
        return jsonify(table.data_for_json)
    if kind == 'csv':
        return csv_response('admin_export', name, table.data)
    return ''


@bp.route("/")
def main() -> str:
    filters = Filters.from_args(with_display=True)

    charts = []
    for generate_chart in get_admin_charts():
        charts.extend(generate_chart(filters))

    init_rows = 20  # number of rows to send in the page for each table (remainder will load asynchronously)
    limit = 1000    # maximum row number to reach in asynch request

    all_data_sources = get_data_sources(filters)
    tables = []

    for name, source in all_data_sources.items():
        data = source.get_data(filters, limit=init_rows).fetchall()
        table = source.table
        table.data = data
        table.csv_link = url_for('.get_data', name=name, kind='csv', **request.args)  # type: ignore[arg-type]
        if len(data) == init_rows:
            # we reached the limit, so there may be (is probably) more to fetch
            # but we can skip providing an ajax URL if we have less than the limit, because that must be all the data
            table.ajax_url = url_for('.get_data', name=name, kind='json', offset=init_rows, limit=limit-init_rows, **request.args)  # type: ignore[arg-type]

        tables.append(table)

    return render_template(
        "admin_main.html",
        charts=charts,
        filters=filters,
        tables=tables,
    )
