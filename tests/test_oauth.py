import re
from unittest.mock import MagicMock, patch
from urllib.parse import quote_plus

import pytest
from authlib.integrations.flask_client import OAuthError  # type: ignore[import-untyped]
from flask import Flask, url_for

from gened.auth import get_auth
from gened.db import get_db
from tests.conftest import AppClient


def test_login_invalid_provider(app: Flask, client: AppClient) -> None:
    """Test attempting login with non-existent provider"""
    with app.test_request_context():
        login_url = url_for('oauth.login', provider_name='fake_provider')
    response = client.get(login_url)
    assert response.status_code == 404

def test_login_google(app: Flask, client: AppClient) -> None:
    """Test initiating Google OAuth login"""
    with app.test_request_context():
        login_url = url_for('oauth.login', provider_name='google')
        auth_url_encoded = quote_plus(url_for('oauth.auth', provider_name='google', _external=True))

    response = client.get(login_url)
    assert response.status_code == 302
    assert response.location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert auth_url_encoded in response.location

def test_google_callback_success(app: Flask, client: AppClient, mock_oauth_patch: MagicMock) -> None:
    """Test successful Google OAuth callback"""

    with app.test_request_context():
        auth_url = url_for('oauth.auth', provider_name='google')

    with client:  # so we can access session
        response = client.get(auth_url)

        assert response.status_code == 302
        assert response.location == '/help/'  # Default redirect (see codehelp app.config)

        # Check session is set up correctly
        sessauth = get_auth()
        assert sessauth.user
        assert sessauth.user_id
        assert sessauth.user.display_name == mock_oauth_patch.test_user['name']
        assert sessauth.user.auth_provider == 'google'
        assert sessauth.is_admin == False
        assert sessauth.cur_class is None

@pytest.mark.parametrize("anon_first", [True, False])
def test_anon_signup(app: Flask, client: AppClient, mock_oauth_client: MagicMock, anon_first: bool) -> None:
    """Test initial login/signup with /anon option
    *and* test the warning on attempt to login anonymously if already registered with personal info."""
    with app.test_request_context():
        login_url = url_for('oauth.login', provider_name='google')
        login_url_anon = url_for('oauth.login', provider_name='google', anon=1)
        auth_url = url_for('oauth.auth', provider_name='google')
        logout_url = url_for('auth.logout')

    if anon_first:  # noqa: SIM108
        # Login once w/ anon login URL to create anonymous user,
        # then a second time with the normal login URL to verify still anonymous.
        urls = [login_url_anon, login_url]
    else:
        # Login normally, then attempt anonymous login to verify no anonymization occurs and a warning is flashed
        urls = [login_url, login_url_anon]

    for url in urls:
        # First set up the session by initiating login
        client.get(url)

        # Then handle the callback
        # Patch OAuth client creation to return our mock
        # (can't use mock_oauth_patch fixture here because we want a real client for the login request above)
        with patch('gened.oauth._oauth.create_client', return_value=mock_oauth_client), client:
            response = client.get(auth_url)

            assert response.status_code == 302
            assert response.location == '/help/'  # Default redirect (see codehelp app.config)

            sessauth = get_auth()
            assert sessauth.user
            assert sessauth.user_id
            assert sessauth.user.auth_provider == 'google'
            assert sessauth.is_admin == False
            assert sessauth.cur_class is None

            if anon_first:
                # Check session is set up correctly / anonymously
                assert sessauth.user.display_name != mock_oauth_client.test_user['name']
                # Anonymous usernames are three capitalized words concatenated
                assert re.match(r"^(?:[A-Z][a-z]+){3}$", sessauth.user.display_name)
            else:
                # Check session has the user's real name, not a generated one
                assert sessauth.user.display_name == mock_oauth_client.test_user['name']
                if url == login_url_anon:
                    # Follow the redirect and check for the flashed message
                    response = client.get(response.location)
                    assert "tried to log in anonymously, but this account was already registered" in response.text

        # Log out (so second iteration tests a fresh login)
        client.post(logout_url)

def test_github_callback_success(app: Flask, client: AppClient, mock_oauth_patch: MagicMock) -> None:
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
        assert response.location == '/help/'  # Default redirect (see codehelp app.config)

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

def test_microsoft_callback_success(app: Flask, client: AppClient, mock_oauth_patch: MagicMock) -> None:
    """Test successful Microsoft OAuth callback with special claims handling"""
    with app.test_request_context():
        auth_url = url_for('oauth.auth', provider_name='microsoft')

    response = client.get(auth_url)

    assert response.status_code == 302
    assert response.location == '/help/'  # Default redirect (see codehelp app.config)

    # Verify the special claims_options were used
    mock_oauth_patch.authorize_access_token.assert_called_once_with(claims_options={'iss': {}})

def test_callback_with_next_url(app: Flask, client: AppClient, mock_oauth_client: MagicMock) -> None:
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

def test_oauth_open_redirect(app: Flask, client: AppClient, mock_oauth_client: MagicMock) -> None:
    """Ensure OAuth callback does not redirect to external domains."""
    external_url = "https://malicious.site/login"

    with app.test_request_context():
        login_url = url_for('oauth.login', provider_name='google', next=external_url)
        auth_url = url_for('oauth.auth', provider_name='google')

    # Initiate login with malicious next URL
    client.get(login_url)

    # Handle callback
    with patch('gened.oauth._oauth.create_client', return_value=mock_oauth_client):
        response = client.get(auth_url)

    assert response.status_code == 302
    assert response.location != external_url
    assert response.location == '/help/'  # Default redirect

def test_callback_failure(app: Flask, client: AppClient, mock_oauth_patch: MagicMock) -> None:
    """Test OAuth callback when authentication fails"""
    mock_oauth_patch.authorize_access_token.side_effect = OAuthError("Auth failed")

    with app.test_request_context():
        auth_url = url_for('oauth.auth', provider_name='google')
        login_form_url = url_for('auth.login')
    response = client.get(auth_url)

    # Should redirect back to login
    assert response.status_code == 302
    assert response.location == login_form_url

def test_oauth_update_user_details(app: Flask, client: AppClient, mock_oauth_patch: MagicMock) -> None:
    """Test that subsequent logins update the user's name/email if changed at provider."""
    test_email = mock_oauth_patch.test_user['email']
    with app.test_request_context():
        db = get_db()

        # Verify user does not exist initially
        user = db.execute("SELECT * FROM users WHERE email=?", [test_email]).fetchone()
        assert not user

        # First Login
        auth_url = url_for('oauth.auth', provider_name='google')

        client.get(auth_url)

        # Verify initial state of user
        user = db.execute("SELECT * FROM users WHERE email=?", [test_email]).fetchone()
        assert user['full_name'] == mock_oauth_patch.test_user['name']

        # Change Mock Data
        new_name = "Updated Name"
        mock_oauth_patch.authorize_access_token.return_value = {
            'userinfo': {
                'email': test_email,
                'name': new_name,
                'sub': mock_oauth_patch.test_user['sub'],
            }
        }

        # Second Login
        client.get(auth_url)

        # Verify DB update
        user = db.execute("SELECT * FROM users WHERE email=?", [mock_oauth_patch.test_user['email']]).fetchone()
        assert user['full_name'] == new_name
