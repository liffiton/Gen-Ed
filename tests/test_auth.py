import pytest

from plum.auth import get_session_auth


@pytest.mark.parametrize(('username', 'password', 'status', 'message', 'is_admin'), (
    ('', '', 200, 'Invalid username or password.', False),
    ('x', '', 200, 'Invalid username or password.', False),
    ('', 'y', 200, 'Invalid username or password.', False),
    ('x', 'y', 200, 'Invalid username or password.', False),
    ('testuser', 'y', 200, 'Invalid username or password.', False),
    ('testuser', 'testpassword', 302, 'Welcome, testuser!', False),
    ('testadmin', 'testadminpassword', 302, 'Welcome, testadmin!', True),
))
def test_login(client, auth, username, password, status, message, is_admin):
    with client:  # so we can use session in get_session_auth()
        assert client.get('/auth/login').status_code == 200
        response = auth.login(username, password)
        assert response.status_code == status

        # Follow redirect if we expect one
        if status == 302:
            response = client.get(response.headers['Location'])
            assert response.status_code == 200

            # Verify session auth contains correct values for logged-in user
            sessauth = get_session_auth()
            assert sessauth['username'] == username
            assert sessauth['is_admin'] == is_admin
            assert sessauth['lti'] is None

        else:
            # Verify session auth contains correct values for non-logged-in user
            sessauth = get_session_auth()
            assert sessauth['username'] is None
            assert sessauth['is_admin'] is False
            assert sessauth['lti'] is None

        assert message in response.text


def test_logout(client, auth):
    with client:
        auth.login()  # defaults to testuser (id 11)
        sessauth = get_session_auth()
        assert sessauth['username'] == 'testuser'

        auth.logout()
        sessauth = get_session_auth()
        assert sessauth['username'] is None
        assert sessauth['is_admin'] is False
        assert sessauth['lti'] is None


@pytest.mark.parametrize(('path', 'nologin', 'withlogin', 'withadmin'), (
    ('/', 200, 200, 200),
    ('/help/', 401, 200, 200),
    ('/help/view/1', 401, (200, "Invalid id."), (200, "response1")),
    ('/tutor/', 401, 200, 200),
    ('/tutor/chat/1', 401, (200, "user_msg_1"), (200, "user_msg_1")),
    ('/tutor/chat/2', 401, (200, "Invalid id."), (200, "user_msg_2")),
    ('/admin/', 302, 302, 200),         # admin_required redirects to login
    ('/admin/get_db', 302, 302, 200),   # admin_required redirects to login
))
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
