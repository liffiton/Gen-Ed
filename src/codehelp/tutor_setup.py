# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from dataclasses import dataclass, field
from typing import Any, Self

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.wrappers.response import Response

from gened.auth import get_auth_class, instructor_required
from gened.db import get_db

bp = Blueprint('tutor_setup', __name__, url_prefix='/tutor-setup', template_folder='templates')

@bp.before_request
@instructor_required
def before_request() -> None:
    """ Apply decorator to protect all blueprint endpoints. """


@dataclass
class LearningObjective:
    name: str
    desc: str
    questions: list[str]

@dataclass
class TutorConfig:
    topic: str = ""
    objectives: list[LearningObjective] = field(default_factory=list)

    @classmethod
    def from_dict(cls, dictionary: dict[str, Any]) -> Self:
        obj = cls(**dictionary)
        obj.objectives = [LearningObjective(**obj) for obj in dictionary.get('objectives', [])]
        return obj


@bp.route('/', methods=['GET'])
def setup_form() -> str:
    """Display the tutor setup form."""
    config = TutorConfig.from_dict(session.get('tutor_setup', {}))
    return render_template(
        'tutor_setup_form.html',
        tutorconf=config,
        has_questions=any(obj.questions for obj in config.objectives)
    )


@bp.route('/objectives/generate', methods=['POST'])
def generate_objectives() -> Response:
    """Stub: generate learning objectives for the given topic."""
    topic = request.form.get('topic', '').strip()
    objectives = [
        LearningObjective(f"Objective {i} for {topic}", "", [])
        for i in range(1, 4)
    ]
    config = TutorConfig(topic, objectives)

    session['tutor_setup'] = config
    return redirect(url_for('tutor_setup.setup_form'))


@bp.route('/questions/generate', methods=['POST'])
def generate_questions() -> Response:
    """Stub: generate questions based on topic and objectives."""
    topic = request.form.get('topic', '').strip()
    objectives = request.form.get('objectives', '').strip().split('\n')
    config = TutorConfig(topic, [LearningObjective(obj, "", []) for obj in objectives])
    for obj in config.objectives:
        obj.questions = [f"Question {i} about {obj.name}" for i in range(1, 5)]

    session['tutor_setup'] = config
    return redirect(url_for('tutor_setup.setup_form'))


@bp.route('/questions/update', methods=['POST'])
def update_questions() -> Response:
    """ Update the questions for one learning objective. """
    config = TutorConfig.from_dict(session.get('tutor_setup', {}))
    obj_index = request.form.get('obj_index')
    if obj_index is None or not obj_index.isnumeric():
        abort(400)
    questions = request.form.get('questions', '').strip().split('\n')
    config.objectives[int(obj_index)].questions = questions
    session['tutor_setup'] = config
    return redirect(url_for('tutor_setup.setup_form'))


@bp.route('/create', methods=['POST'])
def create_tutor() -> Response:
    """Persist the new tutor to the database."""
    config = TutorConfig.from_dict(session.get('tutor_setup', {}))
    name = config.topic
    cur_class = get_auth_class()
    class_id = cur_class.class_id
    db = get_db()
    db.execute(
        "INSERT INTO tutors (name, class_id, config) VALUES (?, ?, ?)",
        [name, class_id, json.dumps(config)]
    )
    db.commit()
    session.pop('tutor_setup', None)
    flash(f"Tutor '{name}' created.", 'success')
    return redirect(url_for('tutor_setup.setup_form'))


@bp.route('/reset', methods=['POST'])
def reset_setup() -> Response:
    """Clear the in-progress tutor setup and start over."""
    session.pop('tutor_setup', None)
    return redirect(url_for('tutor_setup.setup_form'))
