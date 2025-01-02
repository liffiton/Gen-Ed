# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from gened.db import get_db
from gened.llm import get_models
from gened.lti import reload_consumers

from .component_registry import register_blueprint

bp = Blueprint('admin_consumers', __name__, url_prefix='/consumer', template_folder='templates')

register_blueprint(bp)


@bp.route("/")
@bp.route("/<int:consumer_id>")
def consumer_form(consumer_id: int | None = None) -> str:
    db = get_db()
    consumer_row = db.execute("SELECT * FROM consumers WHERE id=?", [consumer_id]).fetchone()
    return render_template("admin_consumer_form.html", consumer=consumer_row, models=get_models())


@bp.route("/new")
def consumer_new() -> str:
    return render_template("admin_consumer_form.html", models=get_models())


@bp.route("/delete/<int:consumer_id>", methods=['POST'])
def consumer_delete(consumer_id: int) -> Response:
    db = get_db()

    # Check for dependencies
    classes_count = db.execute("SELECT COUNT(*) FROM classes_lti WHERE lti_consumer_id=?", [consumer_id]).fetchone()[0]

    if classes_count > 0:
        flash("Cannot delete consumer: there are related classes.", "warning")
        return redirect(url_for(".consumer_form", consumer_id=consumer_id))

    # No dependencies, proceed with deletion

    # Fetch the consumer's name
    consumer_name_row = db.execute("SELECT lti_consumer FROM consumers WHERE id=?", [consumer_id]).fetchone()
    if not consumer_name_row:
        flash("Invalid id.", "danger")
        return redirect(url_for(".consumer_form", consumer_id=consumer_id))

    consumer_name = consumer_name_row['lti_consumer']

    # Delete the row
    db.execute("DELETE FROM consumers WHERE id=?", [consumer_id])
    db.commit()
    reload_consumers()

    flash(f"Consumer '{consumer_name}' deleted.")

    return redirect(url_for("admin.admin_main.main"))


@bp.route("/update", methods=['POST'])
def consumer_update() -> Response:
    db = get_db()

    consumer_id = request.form.get("consumer_id", type=int)

    if consumer_id is None:
        # Adding a new consumer
        cur = db.execute("INSERT INTO consumers (lti_consumer, lti_secret, llm_api_key, model_id) VALUES (?, ?, ?, ?)",
                         [request.form['lti_consumer'], request.form['lti_secret'], request.form['llm_api_key'], request.form['model_id']])
        consumer_id = cur.lastrowid
        db.commit()
        flash(f"Consumer {request.form['lti_consumer']} created.")

    elif 'clear_lti_secret' in request.form:
        db.execute("UPDATE consumers SET lti_secret='' WHERE id=?", [consumer_id])
        db.commit()
        flash("Consumer secret cleared.")

    elif 'clear_llm_api_key' in request.form:
        db.execute("UPDATE consumers SET llm_api_key='' WHERE id=?", [consumer_id])
        db.commit()
        flash("Consumer API key cleared.")

    else:
        # Updating
        if request.form.get('lti_secret', ''):
            db.execute("UPDATE consumers SET lti_secret=? WHERE id=?", [request.form['lti_secret'], consumer_id])
        if request.form.get('llm_api_key', ''):
            db.execute("UPDATE consumers SET llm_api_key=? WHERE id=?", [request.form['llm_api_key'], consumer_id])
        if request.form.get('model_id', ''):
            db.execute("UPDATE consumers SET model_id=? WHERE id=?", [request.form['model_id'], consumer_id])
        db.commit()
        flash("Consumer updated.")

    # anything might have changed: reload all consumers
    reload_consumers()

    return redirect(url_for(".consumer_form", consumer_id=consumer_id))
