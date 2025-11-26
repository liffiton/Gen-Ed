# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from sqlite3 import Row

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from markupsafe import Markup
from werkzeug.wrappers.response import Response

from gened.data_deletion import UserHasCreatedClassesError, delete_user_data
from gened.db import get_db
from gened.redir import safe_redirect
from gened.tables import BoolCol, Col, DataTable, NumCol, UserCol

from .component_registry import register_blueprint, register_navbar_item


def get_candidates() -> tuple[list[Row], int]:
    if 'pruning_candidates' not in g:
        db = get_db()
        retention_time_days = current_app.config['RETENTION_TIME_DAYS']
        g.pruning_candidates = db.execute("""
            SELECT
                id,
                json_array(display_name, auth_provider, display_extra) AS user,
                created AS "user created",
                last_query_time AS "last query",
                last_role_created_time AS "last role created",
                last_class_created_time AS "last class created",
                last_activity AS "last activity",
                CAST(JULIANDAY(DATE('now')) - JULIANDAY(last_activity) AS INTEGER) AS "days since",
                delete_status = 'whitelisted' AS "whitelist?"
            FROM v_user_activity
            WHERE "last activity" < DATE('now', ?)
        """, [f"-{retention_time_days} days"]).fetchall()

    num_candidates = sum(not row['whitelist?'] for row in g.pruning_candidates)
    return g.pruning_candidates, num_candidates


def render_link() -> Markup:
    _, num_candidates = get_candidates()
    if num_candidates:
        return Markup("Pruning <span style='font-size: 50%;' class='tag is-rounded is-danger px-1 py-0 ml-1'>{}</span>").format(num_candidates)
    else:
        return Markup("Pruning")


bp = Blueprint('admin_pruning', __name__, url_prefix='/pruning', template_folder='templates')

register_blueprint(bp)
register_navbar_item("admin_pruning.pruning_view", render_link)


@bp.route("/")
def pruning_view() -> str:
    pruning_candidates, num_candidates = get_candidates()
    num_whitelisted = len(pruning_candidates) - num_candidates

    candidates = DataTable(
        name='candidates',
        columns=[NumCol('id'), UserCol('user'), Col('user created'), Col('last query'), Col('last role created'), Col('last class created'), Col('last activity'), NumCol('days since'), BoolCol('whitelist?', url=url_for('.set_whitelist'), reload=True)],
        data=pruning_candidates,
    )

    return render_template("admin_pruning.html", candidates=candidates, num_candidates=num_candidates, num_whitelisted=num_whitelisted)

@bp.route("/set_whitelist", methods=['POST'])  # just for url_for in the Javascript code
@bp.route("/set_whitelist/<int:user_id>/<int(min=0, max=1):bool_whitelist>", methods=['POST'])
def set_whitelist(user_id: int, bool_whitelist: int) -> str:
    db = get_db()

    # cannot already be deleted
    current = db.execute("SELECT delete_status FROM users WHERE id=?", [user_id]).fetchone()
    assert current['delete_status'] in ('', 'whitelisted')

    new_status = 'whitelisted' if bool_whitelist else ''
    db.execute("UPDATE users SET delete_status=? WHERE id=?", [new_status, user_id])
    db.commit()
    return "okay"


@bp.route("/delete/", methods=['POST'])
def prune_users() -> Response:
    if request.form.get('confirm_delete') != 'DELETE':
        flash("Data deletion requires confirmation. Please type DELETE to confirm.", "warning")
        return safe_redirect(request.referrer, default_endpoint=".pruning_view")

    user_ids = [int(x) for x in request.form.getlist('user_ids')]

    db = get_db()

    count = 0
    for user_id in user_ids:
        # Check whitelist status before deleting to handle race conditions
        # (e.g. user was whitelisted after page load).
        user = db.execute("SELECT delete_status FROM users WHERE id = ?", [user_id]).fetchone()

        if not user:
            current_app.logger.warning(f"Skipped pruning of non-existent user {user_id}")
            continue

        if user['delete_status'] == 'whitelisted':
            current_app.logger.warning(f"Skipped pruning of whitelisted user {user_id}")
            continue

        try:
            delete_user_data(user_id)
            count += 1
        except UserHasCreatedClassesError:
            current_app.logger.warning(f"Skipped pruning of class-owner user {user_id}")
            continue

    flash(f'Successfully deleted {count} user(s)', 'success')
    return redirect(url_for('.pruning_view'))
