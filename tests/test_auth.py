# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest
from gened.auth import get_auth


def test_login_page(client):
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert "Username:" in response.text
    assert "Password:" in response.text


def check_login(client, auth, username, password, status, message, is_admin):
    with client:  # so we can use session in get_auth()
        response = auth.login(username, password)
        assert response.status_code == status

        # Follow redirect if we expect one
        if status == 302:
            response = client.get(response.headers['Location'])
            assert response.status_code == 200

            # Verify session auth contains correct values for logged-in user
            sessauth = get_auth()
            assert sessauth['user_id']
            assert sessauth['display_name'] == username
            assert sessauth['is_admin'] == is_admin
            assert sessauth['class_id'] is None

        else:
            # Verify session auth contains correct values for non-logged-in user
            sessauth = get_auth()
            assert sessauth['user_id'] is None
            assert sessauth['role_id'] is None
            assert sessauth['is_admin'] is False
            assert 'display_name' not in sessauth
            assert 'class_id' not in sessauth

        assert message in response.text


def test_newuser_command(app, runner, client, auth):
    username = "_newuser_"
    check_login(client, auth, username, 'x', 200, "Invalid username or password.", False)
    auth.logout()

    with app.app_context():
        cmd_result = runner.invoke(args=['newuser', username])
        password = re.search(r'password: (\w+)\b', cmd_result.output).group(1)

    check_login(client, auth, username, password, 302, "_newuser_", False)
    auth.logout()
    check_login(client, auth, 'x', password, 200, "Invalid username or password.", False)
    auth.logout()
    check_login(client, auth, username, 'x', 200, "Invalid username or password.", False)


@pytest.mark.parametrize(('username', 'password', 'status', 'message', 'is_admin'), [
    ('', '', 200, 'Invalid username or password.', False),
    ('x', '', 200, 'Invalid username or password.', False),
    ('', 'y', 200, 'Invalid username or password.', False),
    ('x', 'y', 200, 'Invalid username or password.', False),
    ('testuser', 'y', 200, 'Invalid username or password.', False),
    ('testuser', 'testpassword', 302, 'testuser', False),
    ('testadmin', 'testadminpassword', 302, 'testadmin', True),
])
def test_login(client, auth, username, password, status, message, is_admin):
    check_login(client, auth, username, password, status, message, is_admin)


def test_logout(client, auth):
    with client:
        auth.login()  # defaults to testuser (id 11)
        sessauth = get_auth()
        assert sessauth['display_name'] == 'testuser'

        auth.logout()
        sessauth = get_auth()
        assert sessauth['user_id'] is None
        assert sessauth['role_id'] is None
        assert sessauth['is_admin'] is False
        assert 'display_name' not in sessauth
        assert 'class_id' not in sessauth


@pytest.mark.parametrize(('path', 'nologin', 'withlogin', 'withadmin'), [
    ('/', 200, 200, 200),
    ('/profile/', 302, (200, "0 total, 0 in the past week"), (200, "0 total, 0 in the past week")),
    ('/help/', 302, 200, 200),
    ('/help/view/1', 302, (200, "Invalid id."), (200, "response1")),
    ('/tutor/', 404, 200, 200),
    ('/tutor/chat/1', 404, (200, "user_msg_1"), (200, "user_msg_1")),
    ('/tutor/chat/2', 404, (200, "Invalid id."), (200, "user_msg_2")),
    ('/admin/', 302, 302, 200),         # admin_required redirects to login
    ('/admin/get_db', 302, 302, 200),   # admin_required redirects to login
])
def test_auth_required(client, auth, path, nologin, withlogin, withadmin):
    response = client.get(path)
    assert response.status_code == nologin

    auth.login()  # defaults to testuser (id 11)
    response = client.get(path)
    if isinstance(withlogin, tuple):
        assert response.status_code == withlogin[0]
        assert withlogin[1] in response.text
    else:
        assert response.status_code == withlogin
        if withlogin == 302:
            assert response.location.startswith('/auth/login')

    auth.logout()
    response = client.get(path)
    assert response.status_code == nologin

    auth.login('testadmin', 'testadminpassword')
    response = client.get(path)
    if isinstance(withadmin, tuple):
        assert response.status_code == withadmin[0]
        assert withadmin[1] in response.text
    else:
        assert response.status_code == withadmin

    auth.logout()
    response = client.get(path)
    assert response.status_code == nologin
