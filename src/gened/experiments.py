# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from .admin import bp as bp_admin
from .admin import register_admin_link
from .auth import get_auth
from .db import get_db


# Functions for controlling access to experiments based on the current class
def current_class_in_experiment(experiment_name: str) -> bool:
    """ Return True if the current active class is registered in the specified experiment,
        False otherwise.
    """
    db = get_db()
    experiment_class_rows = db.execute("SELECT experiment_class.class_id FROM experiments JOIN experiment_class ON experiment_class.experiment_id=experiments.id WHERE experiments.name=?", [experiment_name]).fetchall()
    experiment_class_ids = [row['class_id'] for row in experiment_class_rows]
    auth = get_auth()
    return 'class_id' in auth and auth['class_id'] in experiment_class_ids

# Decorator for routes designated as part of an experiment
# For decorator type hints
P = ParamSpec('P')
R = TypeVar('R')
def experiment_required(experiment_name: str) -> Callable[[Callable[P, R]], Callable[P, Response | R]]:
    '''404 if the current class is not registered in the specified experiment.'''
    def decorator(f: Callable[P, R]) -> Callable[P, Response | R]:
        @wraps(f)
        def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Response | R:
            if not current_class_in_experiment(experiment_name):
                return abort(404)
            else:
                return f(*args, **kwargs)
        return decorated_function
    return decorator


# ### Admin routes ###
# Auth requirements covered by admin.before_request()

@register_admin_link("Experiments")
@bp_admin.route("/experiments/")
def experiments_view() -> str:
    db = get_db()
    experiments = db.execute("SELECT *, (SELECT COUNT(*) FROM experiment_class WHERE experiment_id=id) AS count FROM experiments").fetchall()
    return render_template("admin_experiments.html", experiments=experiments)

@bp_admin.route("/experiment/new")
def experiment_new() -> str:
    return render_template("experiment_form.html")

@bp_admin.route("/experiment/<int:exp_id>")
def experiment_form(exp_id: int) -> str:
    db = get_db()
    experiment = db.execute("SELECT * FROM experiments WHERE id=?", [exp_id]).fetchone()
    classes = db.execute("SELECT id, name FROM classes ORDER BY name").fetchall()
    classes = [dict(row) for row in classes]  # so we can tojson it in the template
    assigned_classes = db.execute("SELECT class_id AS id, classes.name FROM experiment_class JOIN classes ON experiment_class.class_id=classes.id WHERE experiment_id=? ORDER BY name", [exp_id]).fetchall()
    assigned_classes = [dict(row) for row in assigned_classes]
    return render_template("experiment_form.html", experiment=experiment, classes=classes, assigned_classes=assigned_classes)

@bp_admin.route("/experiment/update", methods=['POST'])
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

@bp_admin.route("/experiment/delete/<int:exp_id>", methods=['POST'])
def experiment_delete(exp_id: int) -> Response:
    db = get_db()

    # Delete the experiment and its class assignments
    db.execute("DELETE FROM experiment_class WHERE experiment_id=?", [exp_id])
    db.execute("DELETE FROM experiments WHERE id=?", [exp_id])
    db.commit()

    flash("Experiment deleted.")

    return redirect(url_for(".experiments_view"))
