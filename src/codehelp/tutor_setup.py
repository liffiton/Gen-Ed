# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.wrappers.response import Response

from gened.auth import get_auth_class, instructor_required
from gened.db import get_db

bp = Blueprint('tutor_setup', __name__, url_prefix='/tutor-setup', template_folder='templates')

@bp.before_request
@instructor_required
def before_request() -> None:
    """ Apply decorator to protect all blueprint endpoints. """


@bp.route('/', methods=['GET'])
def setup_form() -> str:
    """Display the tutor setup form."""
    data = session.get('tutor_setup', {})
    topic = data.get('topic', '')
    objectives = data.get('objectives', '')
    questions = data.get('questions', '')
    return render_template(
        'tutor_setup_form.html',
        topic=topic,
        objectives=objectives,
        questions=questions,
    )

@bp.route('/objectives', methods=['POST'])
def generate_objectives() -> Response:
    """Stub: generate learning objectives for the given topic."""
    topic = request.form.get('topic', '').strip()
    objectives = "\n".join([
        f"Objective 1 for {topic}",
        f"Objective 2 for {topic}",
        f"Objective 3 for {topic}",
    ])
    session['tutor_setup'] = {'topic': topic, 'objectives': objectives, 'questions': ''}
    return redirect(url_for('tutor_setup.setup_form'))

@bp.route('/reset', methods=['POST'])
def reset_setup() -> Response:
    """Clear the in-progress tutor setup and start over."""
    session.pop('tutor_setup', None)
    return redirect(url_for('tutor_setup.setup_form'))

@bp.route('/questions', methods=['POST'])
def generate_questions() -> Response:
    """Stub: generate questions based on topic and objectives."""
    topic = request.form.get('topic', '').strip()
    objectives = request.form.get('objectives', '').strip()
    questions = "\n".join([
        f"Question 1 about {topic}",
        f"Question 2 about {topic}",
        f"Question 3 about {topic}",
    ])
    session['tutor_setup'] = {'topic': topic, 'objectives': objectives, 'questions': questions}
    return redirect(url_for('tutor_setup.setup_form'))

@bp.route('/create', methods=['POST'])
def create_tutor() -> Response:
    """Persist the new tutor to the database."""
    data = session.get('tutor_setup', {})
    name = data.get('topic', '')
    objectives = data.get('objectives', '')
    questions = data.get('questions', '')
    cur_class = get_auth_class()
    class_id = cur_class.class_id
    config = {'objectives': objectives, 'questions': questions}
    db = get_db()
    db.execute(
        "INSERT INTO tutors (name, class_id, config) VALUES (?, ?, ?)",
        [name, class_id, json.dumps(config)]
    )
    db.commit()
    session.pop('tutor_setup', None)
    flash(f"Tutor '{name}' created.", 'success')
    return redirect(url_for('tutor_setup.setup_form'))
