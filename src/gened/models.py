# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    make_response
)
from werkzeug.wrappers.response import Response

from .auth import get_auth, login_required
from .db import get_db

bp = Blueprint('models', __name__, url_prefix="/models", template_folder='templates')

@login_required
@bp.route("/new")
def new_model() -> str:
    return render_template("custom_model.html", model=None)



@login_required
@bp.route("/create", methods=["POST"])
def create_new_model() -> Response:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id

    shortname = request.form.get('shortname')
    model = request.form.get('model')
    custom_endpoint = request.form.get('custom_endpoint')

    db.execute("""
        INSERT INTO models (provider_id, shortname, model, custom_endpoint, active, scope, owner_id)
        VALUES ((SELECT id FROM llm_providers WHERE name='Custom'), ?, ?, ?, ?, ?, ?)
    """, (shortname, model, custom_endpoint, 1, 'user', user_id))
    db.commit()
    flash("Model added successfully!")

    return redirect(url_for("profile.main"))

@login_required
@bp.route("/edit/<int:model_id>")
def models_edit(model_id: int) -> str | Response:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id

    current_model = db.execute("""
        SELECT * FROM models WHERE id = ? AND owner_id = ?
    """, [model_id, user_id]).fetchone()

    if current_model is None:
        flash("Invalid Id", category='warning')
        return make_response(render_template("error.html"), 400)

    return render_template("custom_model.html", model=current_model)

@login_required
@bp.route("/update/<int:model_id>", methods=["POST"])
def models_update(model_id: int) -> Response:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id

    shortname = request.form.get('shortname')
    model = request.form.get('model')
    custom_endpoint = request.form.get('custom_endpoint')   

    db.execute("""
    UPDATE models SET shortname = ?, model = ?, custom_endpoint = ?
    WHERE id = ? and owner_id = ?
    """, (shortname, model, custom_endpoint, model_id, user_id))
    db.commit()

    flash("Model updated successfully!")

    return redirect(url_for("profile.main"))

@login_required
@bp.route("/delete/<int:model_id>", methods=["POST"])
def models_delete(model_id: int) -> Response:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id
    
    db.execute("DELETE FROM models WHERE id = ? AND owner_id = ?", [model_id, user_id])
    db.commit()
    flash("Model deleted successfully!")

    return redirect(url_for("profile.main"))