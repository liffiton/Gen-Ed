import os
from pathlib import Path
import tempfile

import pytest
from dotenv import find_dotenv, load_dotenv

from plum.admin import reload_consumers
from plum.db import get_db, init_db
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
    # Mock get_completion() to not hit OpenAI's API
    async def mock_completion(*args, **kwargs):
        prompt = kwargs['prompt'] if 'prompt' in kwargs else args[1]
        txt = f"Mocked completion with {prompt=}"
        return {'main': txt}, txt
    monkeypatch.setattr(codehelp.helper, 'get_completion', mock_completion)

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
