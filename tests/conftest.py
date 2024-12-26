# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import openai
import pytest
from dotenv import find_dotenv, load_dotenv

import codehelp
from gened.db import get_db, init_db
from gened.lti import reload_consumers
from gened.testing.mocks import mock_async_completion, mock_completion

# Load test DB data
test_sql = Path(__file__).parent / 'test_data.sql'
with test_sql.open('rb') as f:
    _test_data_sql = f.read().decode('utf8')


@pytest.fixture(scope='session', autouse=True)
def _load_env():
    env_file = find_dotenv('.env.test')
    load_dotenv(env_file)


@pytest.fixture
def app(monkeypatch, request):
    """ Provides an application object and by default monkey patches openai to
    *not* send requests: the most common case for testing.

    If used in a test decorated with @pyest.mark.use_real_openai, then it will
    *not* patch openai, and requests in that test will go to the real OpenAI
    endpoint.
    """
    if "use_real_openai" not in request.keywords:  # the default is that the marker is *not* used
        # Mock OpenAI completions to not hit OpenAI's API  (0 delay for testing)
        monkeypatch.setattr(openai.resources.chat.Completions, "create", mock_completion(0.0))
        monkeypatch.setattr(openai.resources.chat.AsyncCompletions, "create", mock_async_completion(0.0))

    # Create a temporary app root with instance directory
    with tempfile.TemporaryDirectory() as temp_dir:
        instance_path = Path(temp_dir)

        # Create database in the instance directory
        db_path = instance_path / 'test.db'

        app = codehelp.create_app(
            test_config={
                'TESTING': True,
                'DATABASE': str(db_path),
                'OPENAI_API_KEY': 'invalid',  # ensure an invalid API key for testing
            },
            instance_path=instance_path,
        )

        with app.app_context():
            init_db()
            get_db().executescript(_test_data_sql)
            reload_consumers()  # reload consumers from now-initialized DB

        yield app
        # Directory cleanup happens automatically when the context manager exits


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class AuthActions:
    def __init__(self, client):
        self._client = client

    def login(self, username='testuser', password='testpassword', next_url=''):
        return self._client.post(
            '/auth/local_login',
            data={'username': username, 'password': password, 'next': next_url}
        )

    def logout(self):
        return self._client.post('/auth/logout')


@pytest.fixture
def auth(client):
    return AuthActions(client)


TEST_OAUTH_USER = {
    'email': 'test@example.com',
    'name': 'Test OAuth User',
    'sub': '12345',  # OpenID Connect ID
    'id': '54321',   # Github ID
}

@pytest.fixture
def mock_oauth_client(app):
    """Create a mock OAuth client that can be configured per-test"""
    mock_oauth_client = MagicMock()
    mock_oauth_client.test_user = TEST_OAUTH_USER
    mock_oauth_client.authorize_access_token.return_value = {
        'userinfo': TEST_OAUTH_USER
    }
    return mock_oauth_client

@pytest.fixture
def mock_oauth_patch(mock_oauth_client):
    # Patch OAuth client creation to return our mock
    with patch('gened.oauth._oauth.create_client', return_value=mock_oauth_client):
        yield mock_oauth_client
