# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest

from tests.conftest import AuthActions


def test_not_logged_in(client):
    # reg/access links should not work if not logged in.
    response = client.get("/classes/access/reg_enabled")
    assert response.status_code == 302
    assert response.location == "/auth/login?next=/classes/access/reg_enabled?"


def _test_user_class_link(client, link_name, status, result):
    response = client.get(f"/classes/access/{link_name}")
    assert response.status_code == status

    if status == 302:
        assert response.location == result
    elif status == 200:
        assert result in response.text


@pytest.mark.parametrize(('link_name', 'status', 'result'), [
    ('invalid_link', 404, None),
    ('reg_disabled', 200, 'Registration is not active for this class.'),
    ('reg_expired', 200, 'Registration is not active for this class.'),
    ('reg_enabled', 302, '/'),
])
def test_user_class_link(auth, client, link_name, status, result):
    auth.login('testuser2', 'testuser2password')  # log in a testuser2, not connected to any existing classes
    _test_user_class_link(client, link_name, status, result)


def _create_user_class(client, class_name):
    response = client.post(
        "/classes/create/",
        data={'class_name': class_name, 'openai_key': "none"}
    )

    assert response.status_code == 302
    assert response.location == "/instructor/config/"

    response = client.get(response.location)
    match = re.search(r"https?:\/\/\S+\/classes\/access\/(\S+)", response.text)
    assert match is not None
    assert match.group(1)

    class_access_link_name = match.group(1)
    return class_access_link_name


def test_user_class_creation(auth, client):
    auth.login()  # only works if logged in
    class_access_link_name = _create_user_class(client, "Test Class")
    _test_user_class_link(client, class_access_link_name, 302, '/')


def test_user_class_usage(app):
    instructor_client = app.test_client()
    instructor_auth = AuthActions(instructor_client)

    user_client = app.test_client()
    user_auth = AuthActions(user_client)

    # 1) instructor logs in, creates the course
    instructor_auth.login('testinstructor', 'testinstructorpassword')
    access_link_name = _create_user_class(instructor_client, "Instructor's Test Class")
    assert access_link_name

    # 2) user logs in, cannot access the course yet
    user_auth.login('testuser', 'testpassword')
    _test_user_class_link(user_client, access_link_name, 200, 'Registration is not active for this class.')

    # 3) instructor enables/activates the course
    result = instructor_client.post(
        '/instructor/user_class/set',
        data={
            'class_enabled': 'on',
            'link_reg_active_present': 'true',
            'link_reg_active': 'enabled',
            'save_access_form': '',
        },
        headers={
            'Referer': 'http://localhost/instructor/config'
        },
        follow_redirects=True
    )
    assert "Class access configuration updated." in result.text

    # 4) user can now access the course
    _test_user_class_link(user_client, access_link_name, 302, '/')
    result = user_client.get('/help/')
    assert result.status_code == 200

    # 5) instructor cannot yet see a query
    result = instructor_client.get('/help/view/5')
    assert result.status_code == 400
    assert 'Invalid id.' in result.text

    # 6) user makes a query
    result = user_client.post('/help/request', data={'code': 'student_1_code', 'error': 'error', 'issue': 'issue'})
    assert result.status_code == 302
    assert result.location == "/help/view/5"  # next open query ID (test_data.sql inserts up to 4)
    result = user_client.get(result.location)
    assert result.status_code == 200
    assert 'student_1_code' in result.text

    # 7) instructor can see user's query
    result = instructor_client.get('/help/view/5')
    assert result.status_code == 200
    assert 'student_1_code' in result.text
    assert 'Invalid id.' not in result.text

    # 8) instructor can see user's query in instructor view as well
    result = instructor_client.get('/instructor/')
    assert result.status_code == 200
    assert 'student_1_code' in result.text

    # 9) instructor disables link registration
    result = instructor_client.post(
        '/instructor/user_class/set',
        data={
            'class_enabled': 'on',
            'link_reg_active_present': 'true',
            'link_reg_active': 'disabled',
            'save_access_form': '',
        },
        headers={
            'Referer': 'http://localhost/instructor/config'
        },
        follow_redirects=True
    )
    assert "Class access configuration updated." in result.text

    # 10) another user now cannot access the course
    user_auth.logout()
    user_auth.login('testuser2', 'testuser2password')
    _test_user_class_link(user_client, access_link_name, 200, 'Registration is not active for this class.')

    # 11) but the first user still can
    user_auth.logout()
    user_auth.login('testuser', 'testpassword')
    _test_user_class_link(user_client, access_link_name, 302, '/')
    result = user_client.get('/help/')
    assert result.status_code == 200
