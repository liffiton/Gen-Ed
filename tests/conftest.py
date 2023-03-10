import os
import tempfile

import pytest
from codehelp import create_app
from shared.db import get_db, init_db


# Load test DB data
with open(os.path.join(os.path.dirname(__file__), 'test_data.sql'), 'rb') as f:
    _test_data_sql = f.read().decode('utf8')


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()

    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
    })

    with app.app_context():
        init_db()
        get_db().executescript(_test_data_sql)

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class AuthActions(object):
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
