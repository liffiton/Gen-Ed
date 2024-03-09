# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
from pathlib import Path
import tempfile

import openai
import pytest
from dotenv import find_dotenv, load_dotenv

from gened.admin import reload_consumers
from gened.db import get_db, init_db
from gened.openai import mock_async_completion, mock_completion
import codehelp


# Load test DB data
test_sql = Path(__file__).parent / 'test_data.sql'
with test_sql.open('rb') as f:
    _test_data_sql = f.read().decode('utf8')


@pytest.fixture(scope='session', autouse=True)
def load_env():
    env_file = find_dotenv('.env.test')
    load_dotenv(env_file)


@pytest.fixture
def app(monkeypatch):
    # Mock OpenAI completions to not hit OpenAI's API  (0 delay for testing)
    monkeypatch.setattr(openai.resources.chat.Completions, "create", mock_completion(0.0))
    monkeypatch.setattr(openai.resources.chat.AsyncCompletions, "create", mock_async_completion(0.0))

    # Create an app and initialize the DB
    db_fd, db_path = tempfile.mkstemp()

    app = codehelp.create_app(
        test_config={
            'TESTING': True,
            'DATABASE': db_path,
        },
        instance_path=Path(db_path).absolute().parent,
    )

    with app.app_context():
        init_db()
        get_db().executescript(_test_data_sql)
        reload_consumers()  # reload consumers from now-initialized DB

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class AuthActions:
    def __init__(self, client):
        self._client = client

    def login(self, username='testuser', password='testpassword'):
        return self._client.post(
            '/auth/login',
            data={'username': username, 'password': password, 'next': ''}
        )

    def logout(self):
        return self._client.post('/auth/logout')


@pytest.fixture
def auth(client):
    return AuthActions(client)
