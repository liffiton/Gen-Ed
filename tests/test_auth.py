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
    assert 'name="username"' in response.text
    assert 'name="password"' in response.text
    assert 'type="submit"' in response.text


def check_login(
        client,    # fixture
        auth,      # fixture
        username,  # login username
        password,  # login password
        next_url=None,   # value for 'next' form parameter
        status=200,      # expected response status code
        message=None,    # expected text in response
        redir_tgt=None,  # expected target for redirect response
        is_admin=False,  # expected value of is_admin in session auth
    ):
    with client:  # so we can use session in get_auth()
        response = auth.login(username, password, next_url)
        assert response.status_code == status

        # Follow redirect if we expect one
        if status == 302:
            target = response.headers['Location']
            assert target == redir_tgt
            response = client.get(target)
            assert response.status_code == 200

            # Verify session auth contains correct values for logged-in user
            sessauth = get_auth()
            assert sessauth['user_id']
            assert sessauth['display_name'] == username
            assert sessauth['is_admin'] == is_admin
            assert sessauth['class_id'] is None
            assert sessauth['role_id'] is None
            assert 'auth_provider' in sessauth
            assert sessauth['auth_provider'] == 'local'

        else:
            # Verify session auth contains correct values for non-logged-in user
            sessauth = get_auth()
            assert sessauth['user_id'] is None
            assert sessauth['is_admin'] is False
            assert sessauth['role'] is None
            assert 'display_name' not in sessauth
            assert 'class_id' not in sessauth
            assert 'role_id' not in sessauth
            assert 'auth_provider' not in sessauth

        assert message in response.text


def test_newuser_command(app, runner, client, auth):
    username = "_newuser_"
    check_login(client, auth, username, 'x', message="Invalid username or password.")
    auth.logout()

    with app.app_context():
        cmd_result = runner.invoke(args=['newuser', username])
        password = re.search(r'password: (\w+)\b', cmd_result.output).group(1)

    check_login(client, auth, username, password, status=302, redir_tgt="/help/", message="_newuser_")
    auth.logout()
    check_login(client, auth, 'x', password, message="Invalid username or password.")
    auth.logout()
    check_login(client, auth, username, 'x', message="Invalid username or password.")


@pytest.mark.parametrize(('username', 'password'), [
    ('', ''),
    ('x', ''),
    ('', 'y'),
    ('x', 'y'),
    ('testuser', 'y'),
    ('testadmin', 'y'),
])
def test_invalid_login(client, auth, username, password):
    check_login(client, auth, username, password, status=200, message="Invalid username or password.")


@pytest.mark.parametrize(('username', 'password', 'next_url', 'is_admin'), [
    ('testuser', 'testpassword', '/profile/', False),
    ('testadmin', 'testadminpassword', '/admin/', True),
])
def test_valid_login(client, auth, username, password, next_url, is_admin):
    # Test with the next URL specified
    check_login(client, auth, username, password, next_url=next_url, status=302, redir_tgt=next_url, message=username, is_admin=is_admin)
    auth.logout()
    # Test with no next URL specified: should redirect to /help
    check_login(client, auth, username, password, next_url=None, status=302, redir_tgt="/help/", message=username, is_admin=is_admin)
    auth.logout()
    # Test with an unsafe next URL specified: should redirect to /help
    check_login(client, auth, username, password, next_url="https://malicious.site/", status=302, redir_tgt="/help/", message=username, is_admin=is_admin)
    auth.logout()


def test_logout(client, auth):
    with client:
        auth.login()  # defaults to testuser (id 11)
        sessauth = get_auth()
        assert sessauth['display_name'] == 'testuser'

        response = auth.logout()
        assert response.status_code == 302
        assert response.location == "/auth/login"

        sessauth = get_auth()
        assert sessauth['user_id'] is None
        assert sessauth['is_admin'] is False
        assert 'display_name' not in sessauth
        assert 'class_id' not in sessauth
        assert 'role_id' not in sessauth
        assert 'auth_provider' not in sessauth

        # Check if the user can access the login page and see the flashed message after logout
        response = client.get(response.location)
        assert response.status_code == 200
        assert "You have been logged out." in response.text


@pytest.mark.parametrize(('path', 'nologin', 'withlogin', 'withadmin'), [
    ('/', 200, 200, 200),
    ('/profile/', 302, (200, "0 total, 0 in the past week"), (200, "0 total, 0 in the past week")),
    ('/help/', 302, 200, 200),
    ('/help/view/1', 302, (400, "Invalid id."), (200, "response1")),
    ('/tutor/', 404, 200, 404),
    ('/tutor/chat/1', 404, (200, "user_msg_1"), 404),
    ('/tutor/chat/2', 404, (200, "user_msg_2"), 404),
    ('/tutor/chat/3', 404, (400, "Invalid id."), 404),
    ('/tutor/chat/999', 404, (400, "Invalid id."), 404),
    ('/admin/', 302, 302, 200),         # admin_required redirects to login
    ('/admin/get_db', 302, 302, 200),   # admin_required redirects to login
])
def test_auth_required(client, auth, path, nologin, withlogin, withadmin):
    response = client.get(path)
    assert response.status_code == nologin

    auth.login()  # defaults to testuser (id 11)
    client.get('/classes/switch/2')  # switch to class 2 (where the chats are registered)

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
