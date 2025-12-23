# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import (
    Blueprint,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from .access import Access, control_blueprint_access
from .auth import get_auth
from .db import get_db

bp = Blueprint('models', __name__, url_prefix="/models", template_folder='templates')

# Require login for all routes in the blueprint
control_blueprint_access(bp, Access.LOGIN)


@bp.route("/new")
def new_model() -> str:
    return render_template("models.html", model=None)

def _make_unique_model_shortname(shortname: str, owner_id: int, model_id: int = -1) -> str:
    """
    Given a shortname, current owner of the model, id of the model. Return a
    shortname that is unique within that class.
    """
    db = get_db()

    new_shortname = shortname
    i = 0

    while db.execute(" SELECT id FROM models WHERE shortname = ? AND owner_id = ? AND id != ? ", [new_shortname, owner_id, model_id]).fetchone():
        i += 1
        new_shortname = f"{shortname} ({i})"
    return new_shortname

@bp.route("/create", methods=["POST"])
def create_new_model() -> Response:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id
    assert user_id is not None

    shortname = request.form.get('shortname')
    if not shortname:
        abort(400, "shortname required")

    model = request.form.get('model')
    if not model:
        abort(400, "model required")

    custom_endpoint = request.form.get('custom_endpoint')
    if not custom_endpoint:
        abort(400, "custom_endpoint required")

    new_shortname = _make_unique_model_shortname(shortname, user_id)

    db.execute("""
        INSERT INTO models (provider_id, shortname, model, custom_endpoint, active, owner_id)
        VALUES ((SELECT id FROM llm_providers WHERE name='Custom'), ?, ?, ?, ?, ?)
    """, (new_shortname, model, custom_endpoint, 1, user_id))
    db.commit()
    flash(f"{new_shortname} added successfully!")

    return redirect(url_for("profile.main"))

@bp.route("/edit/")
@bp.route("/edit/<int:model_id>")
def models_edit(model_id: int) -> str | Response:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id

    current_model = db.execute("""
        SELECT
            *,
            (SELECT COUNT(*) FROM classes_user AS cu WHERE cu.model_id=models.id) AS "user_class_use_count"
        FROM models
        WHERE id = ? AND owner_id = ?
    """, [model_id, user_id]).fetchone()

    if current_model is None:
        flash("Invalid Id", category='warning')
        return make_response(render_template("error.html"), 400)

    return render_template("models.html", model=current_model)

@bp.route("/update/<int:model_id>", methods=["POST"])
def models_update(model_id: int) -> Response:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id
    assert user_id is not None

    shortname = request.form.get('shortname')
    if not shortname:
        abort(400, "shortname required")

    model = request.form.get('model')
    if not model:
        abort(400, "model required")

    custom_endpoint = request.form.get('custom_endpoint')
    if not custom_endpoint:
        abort(400, "custom_endpoint required")

    new_shortname = _make_unique_model_shortname(shortname, user_id, model_id)

    db.execute("""
        UPDATE models SET shortname = ?, model = ?, custom_endpoint = ?
        WHERE id = ? and owner_id = ?
    """, (new_shortname, model, custom_endpoint, model_id, user_id))
    db.commit()

    flash(f"{new_shortname} updated successfully!")

    return redirect(url_for("profile.main"))

@bp.route("/delete/<int:model_id>", methods=["POST"])
def models_delete(model_id: int) -> Response:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id

    model = db.execute("SELECT * FROM models WHERE id = ? AND owner_id = ?", [model_id, user_id]).fetchone()
    db.execute("DELETE FROM models WHERE id = ? AND owner_id = ?", [model_id, user_id])
    db.commit()
    flash(f"{model['shortname']} deleted successfully!")

    return redirect(url_for("profile.main"))
