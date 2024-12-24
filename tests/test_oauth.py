import re
from unittest.mock import MagicMock, patch
from urllib.parse import quote_plus

from flask import url_for

from gened.auth import get_auth
from gened.db import get_db


def test_login_invalid_provider(app, client):
    """Test attempting login with non-existent provider"""
    with app.test_request_context():
        login_url = url_for('oauth.login', provider_name='fake_provider')
    response = client.get(login_url)
    assert response.status_code == 404

def test_login_google(app, client):
    """Test initiating Google OAuth login"""
    with app.test_request_context():
        login_url = url_for('oauth.login', provider_name='google')
        auth_url_encoded = quote_plus(url_for('oauth.auth', provider_name='google', _external=True))

    response = client.get(login_url)
    assert response.status_code == 302
    assert response.location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert auth_url_encoded in response.location

def test_google_callback_success(app, client, mock_oauth_patch):
    """Test successful Google OAuth callback"""

    with app.test_request_context():
        auth_url = url_for('oauth.auth', provider_name='google')

    with client:  # so we can access session
        response = client.get(auth_url)

        assert response.status_code == 302
        assert response.location == '/'  # Default redirect

        # Check session is set up correctly
        sessauth = get_auth()
        assert sessauth.user
        assert sessauth.user_id
        assert sessauth.user.display_name == mock_oauth_patch.test_user['name']
        assert sessauth.user.auth_provider == 'google'
        assert sessauth.is_admin == False
        assert sessauth.cur_class is None

def test_anon_signup(app, client, mock_oauth_client):
    """Test initial login/signup with /anon option."""
    with app.test_request_context():
        login_url = url_for('oauth.login', provider_name='google')
        login_url_anon = url_for('oauth.login', provider_name='google', anon=1)
        auth_url = url_for('oauth.auth', provider_name='google')
        logout_url = url_for('auth.logout')

    # Login once w/ anon login URL to create anonymous user,
    # then a second time with the normal login URL to verify still anonymous.
    for url in [login_url_anon, login_url]:
        # First set up the session by initiating login
        client.get(url)

        # Then handle the callback
        # Patch OAuth client creation to return our mock
        # (can't use mock_oauth_patch fixture here because we want a real client for the login request above)
        with patch('gened.oauth._oauth.create_client', return_value=mock_oauth_client), client:
            response = client.get(auth_url)

            assert response.status_code == 302
            assert response.location == '/'

            # Check session is set up correctly / anonymously
            sessauth = get_auth()
            assert sessauth.user
            assert sessauth.user_id
            assert sessauth.user.display_name != mock_oauth_client.test_user['name']
            # Anonymous usernames are three capitalized words concatenated
            assert re.match(r"^(?:[A-Z][a-z]+){3}$", sessauth.user.display_name)
            assert sessauth.user.auth_provider == 'google'
            assert sessauth.is_admin == False
            assert sessauth.cur_class is None

        # Log out (so second iteration can verify still anonymous even when using non-/anon route)
        client.post(logout_url)

def test_github_callback_success(app, client, mock_oauth_patch):
    """Test successful Github OAuth callback with email fetching"""
    # Configure mock for the initial auth response to simulate how Github might
    # not provide an email address directly.
    mock_oauth_patch.authorize_access_token.return_value['userinfo']['email'] = None

    # Configure mock for the email fetch
    mock_email_response = MagicMock()
    mock_email_response.json.return_value = [
        {'email': 'github_test@example.com', 'primary': True},
        {'email': 'other@example.com', 'primary': False}
    ]
    mock_oauth_patch.get.return_value = mock_email_response

    with app.test_request_context():
        auth_url = url_for('oauth.auth', provider_name='github')

    with client:  # so we can access session
        response = client.get(auth_url)

        assert response.status_code == 302
        assert response.location == '/'  # Default redirect

        # Verify the email API was called
        mock_oauth_patch.get.assert_called_once_with('user/emails')

        # Check session is set up correctly
        sessauth = get_auth()
        assert sessauth.user
        assert sessauth.user_id
        assert sessauth.user.display_name == mock_oauth_patch.test_user['name']
        assert sessauth.user.auth_provider == 'github'
        assert sessauth.is_admin == False
        assert sessauth.cur_class is None

        # Check that correct email is in database
        db = get_db()
        row = db.execute("SELECT email FROM users WHERE id=?", [sessauth.user_id]).fetchone()
        assert row['email'] == 'github_test@example.com'

def test_microsoft_callback_success(app, client, mock_oauth_patch):
    """Test successful Microsoft OAuth callback with special claims handling"""
    with app.test_request_context():
        auth_url = url_for('oauth.auth', provider_name='microsoft')

    response = client.get(auth_url)

    assert response.status_code == 302
    assert response.location == '/'

    # Verify the special claims_options were used
    mock_oauth_patch.authorize_access_token.assert_called_once_with(claims_options={'iss': {}})

def test_callback_with_next_url(app, client, mock_oauth_client):
    """Test OAuth callback with a next URL stored in session"""
    next_target = '/something_random/'
    with app.test_request_context():
        login_url = url_for('oauth.login', provider_name='google', next=next_target)
        auth_url = url_for('oauth.auth', provider_name='google')

    # First set up the next URL by initiating login
    client.get(login_url)

    # Then handle the callback
    # Patch OAuth client creation to return our mock
    # (can't use mock_oauth_patch fixture here because we want a real client for the login request above)
    with patch('gened.oauth._oauth.create_client', return_value=mock_oauth_client):
        response = client.get(auth_url)

    assert response.status_code == 302
    assert response.location == next_target

def test_callback_failure(app, client, mock_oauth_patch):
    """Test OAuth callback when authentication fails"""
    from authlib.integrations.flask_client import OAuthError
    mock_oauth_patch.authorize_access_token.side_effect = OAuthError("Auth failed")

    with app.test_request_context():
        auth_url = url_for('oauth.auth', provider_name='google')
        login_form_url = url_for('auth.login')
    response = client.get(auth_url)

    assert response.status_code == 302
    assert response.location == login_form_url
