# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from sqlite3 import Row

from flask import Blueprint, current_app, render_template
from markupsafe import Markup

from gened.db import get_db

from .component_registry import register_blueprint, register_navbar_item


def get_candidates() -> list[Row]:
    db = get_db()
    retention_time_days = current_app.config['RETENTION_TIME_DAYS']
    candidates = db.execute("""
        SELECT id, display_name, query_time, created, latest FROM (
            SELECT users.id, users.display_name, MAX(queries.id), queries.query_time, users.created, COALESCE(queries.query_time, users.created) AS latest
            FROM users
            LEFT JOIN queries ON queries.user_id=users.id
            WHERE NOT users.is_admin
            AND users.id != -1
            GROUP BY users.id
        )
        WHERE latest < DATE('now', ?)
    """, [f"-{retention_time_days} days"]).fetchall()

    return candidates


def render_link() -> Markup:
    if get_candidates():
        return Markup("Pruning<span style='font-size: 50%'>🔴</span>")
    else:
        return Markup("Pruning")


bp = Blueprint('admin_pruning', __name__, url_prefix='/pruning', template_folder='templates')

register_blueprint(bp)
register_navbar_item("admin_pruning.pruning_view", render_link)


@bp.route("/")
def pruning_view() -> str:
    pruning_candidates = get_candidates()

    return render_template("admin_pruning.html", candidates=pruning_candidates)
