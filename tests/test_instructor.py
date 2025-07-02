# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Flask

from gened.db import get_db
from tests.conftest import AppClient


def test_instructor_view(instructor: AppClient) -> None:
    response = instructor.get('/instructor/')
    assert response.status_code == 200

    # users in the Users table
    assert "testuser" in response.text    # the instructor's name
    assert "testadmin" in response.text   # registered as a student in this class
    assert "testinstructor" not in response.text  # also registered as a student, but not displayed by that name
    assert "instructor@example.com" in response.text  # 'testinstructor's displayed name

    # queries in the Queries table
    for prefix in 'code', 'error', 'issue':
        assert f"{prefix}01" not in response.text
        assert f"{prefix}02" not in response.text
        assert f"{prefix}11" in response.text
        assert f"{prefix}12" in response.text
        assert f"{prefix}13" in response.text
        assert f"{prefix}21" in response.text
        assert f"{prefix}22" in response.text

    # now filter to one user (testinstructor)
    response = instructor.get('/instructor/?user=13')
    assert response.status_code == 200
    for prefix in 'code', 'error', 'issue':
        assert f"{prefix}01" not in response.text
        assert f"{prefix}02" not in response.text
        assert f"{prefix}11" in response.text
        assert f"{prefix}12" in response.text
        assert f"{prefix}13" in response.text
        assert f"{prefix}21" not in response.text
        assert f"{prefix}22" not in response.text


def test_set_role_active(app: Flask, instructor: AppClient) -> None:
    # Test successful deactivation (deactivating testadmin in the course)
    response = instructor.post('/instructor/role/set_active/5/0')
    assert response.status_code == 200
    assert response.data == b'okay'

    # Verify database update
    with app.app_context():
        db = get_db()
        active_status = db.execute('SELECT active FROM roles JOIN users ON roles.user_id=users.id WHERE users.auth_name="testadmin"').fetchone()['active']
        assert active_status == 0

    # Test successful activation
    response = instructor.post('/instructor/role/set_active/5/1')
    assert response.status_code == 200
    assert response.data == b'okay'

    # Verify database update
    with app.app_context():
        db = get_db()
        active_status = db.execute('SELECT active FROM roles JOIN users ON roles.user_id=users.id WHERE users.auth_name="testadmin"').fetchone()['active']
        assert active_status == 1

    # Test class instructor (testuser, role 4) trying to deactivate themselves
    response = instructor.post('/instructor/role/set_active/4/0')
    assert response.status_code == 200
    assert b'okay' not in response.data
    assert response.data == b'You cannot make yourself inactive.'

    # Test invalid role_id
    response = instructor.post('/instructor/role/set_active/999/0')
    assert response.status_code == 200
    assert response.data == b'okay'  # It doesn't fail, just doesn't update anything

    # Test invalid bool_active value
    response = instructor.post('/instructor/role/set_active/4/2')
    assert response.status_code == 404  # Not Found, as it doesn't match the route (0 or 1 only for the new state)

    # Test non-instructor access
    client = AppClient(app.test_client())
    client.login('testuser2', 'testuser2password')
    response = client.post('/instructor/role/set_active/5/0')
    assert response.status_code == 302  # Redirect to login
    assert response.location.startswith('/auth/login?')


def test_set_role_instructor(app: Flask, instructor: AppClient) -> None:
    # Test successful change to instructor for testadmin (starts as student)
    response = instructor.post('/instructor/role/set_instructor/5/1')
    assert response.status_code == 200
    assert response.data == b'okay'

    # Verify database update
    with app.app_context():
        db = get_db()
        role = db.execute('SELECT role FROM roles JOIN users ON roles.user_id=users.id WHERE users.auth_name="testadmin"').fetchone()['role']
        assert role == 'instructor'

    # Test successful change back to student
    response = instructor.post('/instructor/role/set_instructor/5/0')
    assert response.status_code == 200
    assert response.data == b'okay'

    # Verify database update
    with app.app_context():
        db = get_db()
        role = db.execute('SELECT role FROM roles JOIN users ON roles.user_id=users.id WHERE users.auth_name="testadmin"').fetchone()['role']
        assert role == 'student'

    # Test instructor trying to change their own role
    response = instructor.post('/instructor/role/set_instructor/4/0')
    assert response.status_code == 200
    assert b'okay' not in response.data
    assert response.data == b'You cannot change your own role.'

    # Test invalid role_id
    response = instructor.post('/instructor/role/set_instructor/999/1')
    assert response.status_code == 200
    assert response.data == b'okay'  # It doesn't fail, just doesn't update anything

    # Test invalid bool_instructor value
    response = instructor.post('/instructor/role/set_instructor/4/2')
    assert response.status_code == 404  # Not Found, as it doesn't match the route

    # Test non-instructor access
    client = AppClient(app.test_client())
    client.login('testuser2', 'testuser2password')
    response = client.post('/instructor/role/set_instructor/5/1')
    assert response.status_code == 302  # Redirect to login
    assert response.location.startswith('/auth/login?')
