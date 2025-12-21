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

from . import admin
from .db import get_db
from .tables import Action, Col, DataTable, DataTableSpec, NumCol

# ### Admin routes ###
# Auth requirements covered by admin.before_request()
bp_admin = Blueprint('admin_experiments', __name__, url_prefix='/experiments', template_folder='templates')

# Register the experiments admin component.
admin.register_blueprint(bp_admin)
admin.register_navbar_item("admin_experiments.experiments_view", "Experiments")


@bp_admin.route("/")
def experiments_view() -> str:
    db = get_db()
    experiments = db.execute("""
        SELECT *, (SELECT COUNT(*) FROM experiment_class WHERE experiment_id=id) AS "#classes" FROM experiments
    """).fetchall()

    table_spec = DataTableSpec(
        name='experiments',
        columns=[NumCol('id'), Col('name'), Col('description'), NumCol('#classes')],
        actions=[Action("Edit experiment", icon='pencil', url=url_for('.experiment_form'), id_col=0)],
        link_col=0,
        link_template=url_for('.experiment_form') + '${value}',
        create_endpoint='.experiment_new',
    )
    table = DataTable(spec=table_spec, data=experiments)

    return render_template("admin_experiments.html", experiments=table)

@bp_admin.route("/new")
def experiment_new() -> str:
    return render_template("admin_experiment_form.html")

@bp_admin.route("/edit/")
@bp_admin.route("/edit/<int:exp_id>")
def experiment_form(exp_id: int) -> str:
    db = get_db()
    experiment = db.execute("SELECT * FROM experiments WHERE id=?", [exp_id]).fetchone()
    classes = db.execute("SELECT id, name FROM classes ORDER BY name").fetchall()
    classes = [dict(row) for row in classes]  # so we can tojson it in the template
    assigned_classes = db.execute("SELECT class_id AS id, classes.name FROM experiment_class JOIN classes ON experiment_class.class_id=classes.id WHERE experiment_id=? ORDER BY name", [exp_id]).fetchall()
    assigned_classes = [dict(row) for row in assigned_classes]
    return render_template("admin_experiment_form.html", experiment=experiment, classes=classes, assigned_classes=assigned_classes)

@bp_admin.route("/update", methods=['POST'])
def experiment_update() -> Response:
    db = get_db()

    exp_id = request.form.get("exp_id", type=int)

    if exp_id is None:
        # Adding a new experiment
        cur = db.execute("INSERT INTO experiments (name, description) VALUES (?, ?)",
                         [request.form['name'], request.form['description']])
        exp_id = cur.lastrowid
        db.commit()
        flash(f"Experiment {request.form['name']} created.")
    else:
        # Updating
        db.execute("UPDATE experiments SET name=?, description=? WHERE id=?",
                   [request.form['name'], request.form['description'], exp_id])
        db.commit()
        flash("Experiment updated.")

    # Update assigned classes
    db.execute("DELETE FROM experiment_class WHERE experiment_id=?", [exp_id])
    for class_id in request.form.getlist('assigned_classes'):
        db.execute("INSERT INTO experiment_class (experiment_id, class_id) VALUES (?, ?)",
                   [exp_id, class_id])
    db.commit()

    return redirect(url_for(".experiment_form", exp_id=exp_id))

@bp_admin.route("/delete/<int:exp_id>", methods=['POST'])
def experiment_delete(exp_id: int) -> Response:
    db = get_db()

    # Delete the experiment and its class assignments
    db.execute("DELETE FROM experiment_class WHERE experiment_id=?", [exp_id])
    db.execute("DELETE FROM experiments WHERE id=?", [exp_id])
    db.commit()

    flash("Experiment deleted.")

    return redirect(url_for(".experiments_view"))
