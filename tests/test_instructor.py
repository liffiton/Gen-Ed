# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Flask
from flask.testing import FlaskClient

from gened.db import get_db
from tests.conftest import AuthActions


def test_set_role_active(app: Flask, instructor: tuple[FlaskClient, AuthActions]) -> None:
    client, auth = instructor

    # Test successful deactivation (deactivating testadmin in the course)
    response = client.post('/instructor/role/set_active/5/0')
    assert response.status_code == 200
    assert response.data == b'okay'

    # Verify database update
    with app.app_context():
        db = get_db()
        active_status = db.execute('SELECT active FROM roles JOIN users ON roles.user_id=users.id WHERE users.auth_name="testadmin"').fetchone()['active']
        assert active_status == 0

    # Test successful activation
    response = client.post('/instructor/role/set_active/5/1')
    assert response.status_code == 200
    assert response.data == b'okay'

    # Verify database update
    with app.app_context():
        db = get_db()
        active_status = db.execute('SELECT active FROM roles JOIN users ON roles.user_id=users.id WHERE users.auth_name="testadmin"').fetchone()['active']
        assert active_status == 1

    # Test class instructor (testuser, role 4) trying to deactivate themselves
    response = client.post('/instructor/role/set_active/4/0')
    assert response.status_code == 200
    assert b'okay' not in response.data
    assert response.data == b'You cannot make yourself inactive.'

    # Test invalid role_id
    response = client.post('/instructor/role/set_active/999/0')
    assert response.status_code == 200
    assert response.data == b'okay'  # It doesn't fail, just doesn't update anything

    # Test invalid bool_active value
    response = client.post('/instructor/role/set_active/4/2')
    assert response.status_code == 404  # Not Found, as it doesn't match the route (0 or 1 only for the new state)

    # Test non-instructor access
    auth.logout()
    auth.login('testuser2', 'testuser2password')
    response = client.post('/instructor/role/set_active/5/0')
    assert response.status_code == 302  # Redirect to login
    assert response.location.startswith('/auth/login?')


def test_set_role_instructor(app: Flask, instructor: tuple[FlaskClient, AuthActions]) -> None:
    client, auth = instructor

    # Test successful change to instructor for testadmin (starts as student)
    response = client.post('/instructor/role/set_instructor/5/1')
    assert response.status_code == 200
    assert response.data == b'okay'

    # Verify database update
    with app.app_context():
        db = get_db()
        role = db.execute('SELECT role FROM roles JOIN users ON roles.user_id=users.id WHERE users.auth_name="testadmin"').fetchone()['role']
        assert role == 'instructor'

    # Test successful change back to student
    response = client.post('/instructor/role/set_instructor/5/0')
    assert response.status_code == 200
    assert response.data == b'okay'

    # Verify database update
    with app.app_context():
        db = get_db()
        role = db.execute('SELECT role FROM roles JOIN users ON roles.user_id=users.id WHERE users.auth_name="testadmin"').fetchone()['role']
        assert role == 'student'

    # Test instructor trying to change their own role
    response = client.post('/instructor/role/set_instructor/4/0')
    assert response.status_code == 200
    assert b'okay' not in response.data
    assert response.data == b'You cannot change your own role.'

    # Test invalid role_id
    response = client.post('/instructor/role/set_instructor/999/1')
    assert response.status_code == 200
    assert response.data == b'okay'  # It doesn't fail, just doesn't update anything

    # Test invalid bool_instructor value
    response = client.post('/instructor/role/set_instructor/4/2')
    assert response.status_code == 404  # Not Found, as it doesn't match the route

    # Test non-instructor access
    auth.logout()
    auth.login('testuser2', 'testuser2password')
    response = client.post('/instructor/role/set_instructor/5/1')
    assert response.status_code == 302  # Redirect to login
    assert response.location.startswith('/auth/login?')
