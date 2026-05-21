# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest
from flask import Flask

from gened.class_config.types import RegistrationLink
from gened.db import get_db
from tests.conftest import AppClient


def _test_user_class_link(client: AppClient, link_url: str, status: int, result: str | None = None) -> None:
    response = client.get(link_url)
    assert response.status_code == status

    if status == 302:
        assert response.location == result
    elif status == 200:
        assert result is not None
        assert result in response.text


@pytest.mark.parametrize(('link_ident', 'status_nologin', 'status_login', 'result'), [
    ('invalid_link', 404, 404, None),
    ('reg_disabled', 302, 200, 'Registration is not active for this class.'),
    ('reg_expired', 302, 200, 'Registration is not active for this class.'),
    ('reg_enabled', 302, 302, '/classes/home'),
])
def test_user_class_link_v1(
    client: AppClient,
    link_ident: str,
    status_nologin: int,
    status_login: int,
    result: str | None
) -> None:
    # test v1 links
    path = f"/classes/access/{link_ident}"

    # reg/access links should redirect if valid but not logged in.
    _test_user_class_link(client, path, status_nologin, f"/auth/login?next={path}?")

    # if logged in, should get parameterized result
    client.login('testuser2', 'testuser2password')  # log in as testuser2, not connected to any existing classes
    _test_user_class_link(client, path, status_login, result)


@pytest.mark.parametrize('class_id', [-1, 1, 4], ids=['invalid_id', 'lti_class', 'v1_only_class'])
@pytest.mark.parametrize('hash_suffix', ['', 'XXX'], ids=['no_hash', 'bad_hash'])
@pytest.mark.parametrize('logged_in', [False, True], ids=['logged_out', 'logged_in'])
def test_user_class_link_v2_invalid(
    client: AppClient,
    class_id: int,
    hash_suffix: str,
    logged_in: bool,
) -> None:
    """Invalid v2 links always return 404 regardless of login state.

    -1: nonexistent class ID
     1: valid class but LTI (no classes_user row)
     4: valid class but uses a v1 link key
    """
    if logged_in:
        client.login('testuser2', 'testuser2password')

    path = f"/classes/access/{class_id}/{hash_suffix}"
    _test_user_class_link(client, path, 404)


@pytest.mark.parametrize(('class_id', 'status_nologin', 'status_login', 'result'), [
    (6, 302, 200, 'Registration is not active for this class.'),  # disabled v2 class
    (7, 302, 200, 'Registration is not active for this class.'),  # expired v2 class
    (8, 302, 302, '/classes/home'),  # enabled v2 class
    (9, 302, 302, '/classes/home'),  # enabled v2 class w/ anonymous login
])
def test_user_class_link_v2(
    app: Flask,
    client: AppClient,
    class_id: int,
    status_nologin: int,
    status_login: int,
    result: str | None
) -> None:
    # test v2 links

    # get a valid RegistrationLink to get a functioning URL
    with app.test_request_context():
        db = get_db()
        row = db.execute("""
            SELECT classes.id, classes.name, classes_user.link_key,
                   classes_user.link_reg_expires, classes_user.link_anon_login
            FROM classes
            JOIN classes_user ON classes.id = classes_user.class_id
            WHERE classes.id = ?
        """, [class_id]).fetchone()

        link = RegistrationLink.from_row(row)
        url = link.get_url()
        path = link.get_url(external=False)

    # link with invalid hash (whether originally valid or not))
    invalid_url = url + "X"  # one character added to the hash
    _test_user_class_link(client, invalid_url, 404)

    # reg/access links should redirect if valid but not logged in.
    _test_user_class_link(client, url, status_nologin, f"/auth/login?{'anon=1&' if link.anon_login else ''}next={path}?")

    # if logged in, should get parameterized result
    client.login('testuser2', 'testuser2password')  # log in as testuser2, not connected to any existing classes
    _test_user_class_link(client, url, status_login, result)


def _create_user_class(client: AppClient, class_name: str) -> str:
    response = client.post(
        "/classes/create/",
        data={'class_name': class_name, 'llm_api_key': "none"}
    )

    assert response.status_code == 302
    assert response.location == "/instructor/config/"

    response = client.get(response.location)
    match = re.search(r"(https?:\/\/\S+\/classes\/access\/\S+)", response.text)
    assert match is not None
    assert match.group(1)

    class_access_link = match.group(1)
    return class_access_link


def test_user_class_creation(client: AppClient) -> None:
    client.login()  # only works if logged in
    class_access_link = _create_user_class(client, "Test Class")
    _test_user_class_link(client, class_access_link, 302, '/classes/home')


def test_user_class_usage(app: Flask) -> None:
    instructor_client = AppClient(app.test_client())
    user_client = AppClient(app.test_client())

    # 1) instructor logs in, creates the course
    instructor_client.login('testinstructor', 'testinstructorpassword')
    access_link = _create_user_class(instructor_client, "Instructor's Test Class")
    assert access_link

    # 2) user logs in, cannot access the course yet
    user_client.login('testuser', 'testpassword')
    _test_user_class_link(user_client, access_link, 200, 'Registration is not active for this class.')

    # 3) instructor enables/activates the course
    result = instructor_client.post(
        '/instructor/config/save/access',
        data={
            'class_enabled': 'on',
            'is_user_class': 'true',
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
    _test_user_class_link(user_client, access_link, 302, '/classes/home')
    result = user_client.get('/help/')
    assert result.status_code == 200

    # 5) instructor cannot yet see a query
    result = instructor_client.get('/help/view/101')
    assert result.status_code == 400
    assert 'Invalid id.' in result.text

    # 6) user makes a query
    result = user_client.post('/help/request', data={'code': 'student_1_code', 'error': 'error', 'issue': 'issue'})
    assert result.status_code == 302
    assert result.location == "/help/view/101"  # next open query ID (test_data.sql inserts max 100)
    result = user_client.get(result.location)
    assert result.status_code == 200
    assert 'student_1_code' in result.text

    # 7) instructor can see user's query
    result = instructor_client.get('/help/view/101')
    assert result.status_code == 200
    assert 'student_1_code' in result.text
    assert 'Invalid id.' not in result.text

    # 8) instructor can see user's query in instructor view as well
    result = instructor_client.get('/instructor/')
    assert result.status_code == 200
    assert 'student_1_code' in result.text

    # 9) instructor disables link registration
    result = instructor_client.post(
        '/instructor/config/save/access',
        data={
            'class_enabled': 'on',
            'is_user_class': 'true',
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
    user_client.logout()
    user_client.login('testuser2', 'testuser2password')
    _test_user_class_link(user_client, access_link, 200, 'Registration is not active for this class.')

    # 11) but the first user still can
    user_client.logout()
    user_client.login('testuser', 'testpassword')
    _test_user_class_link(user_client, access_link, 302, '/classes/home')
    result = user_client.get('/help/')
    assert result.status_code == 200
