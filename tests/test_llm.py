from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from gened.db import get_db
from gened.llm import (
    ClassDisabledError,
    NoKeyFoundError,
    NoTokensError,
    get_llm,
    with_llm,
)
from tests.conftest import AppClient


@pytest.fixture
def mock_auth() -> Generator[MagicMock, None, None]:
    """Fixture to mock get_auth in gened.llm."""
    with patch('gened.llm.get_auth') as m:
        auth = MagicMock()
        m.return_value = auth
        yield auth


def test_get_llm_system_override(app: Flask, mock_auth: MagicMock) -> None:
    with app.app_context():
        mock_auth.user_id = 21
        mock_auth.cur_class.class_id = 1

        # Even in a class, use_system_key should return system config
        llm = get_llm(use_system_key=True, spend_token=False)
        assert llm.shortname == app.config['SYSTEM_MODEL_SHORTNAME']
        assert llm.api_key == app.config['SYSTEM_API_KEY']


def test_get_llm_local_user(app: Flask, mock_auth: MagicMock) -> None:
    with app.app_context():
        # User 11 is 'local' in test_data.sql
        mock_auth.user_id = 11
        mock_auth.cur_class = None
        mock_auth.user.auth_provider = "local"

        llm = get_llm(use_system_key=False, spend_token=False)
        assert llm.shortname == app.config['SYSTEM_MODEL_SHORTNAME']
        assert llm.api_key == app.config['SYSTEM_API_KEY']


@pytest.mark.parametrize(("class_id", "expected_key"), [
    (1, 'keeeez1'),  # LTI class from test_data.sql
    (2, 'nope'),     # User class from test_data.sql
])
def test_get_llm_class_success(app: Flask, mock_auth: MagicMock, class_id: int, expected_key: str) -> None:
    with app.app_context():
        mock_auth.user_id = 21 # lti user
        mock_auth.cur_class.class_id = class_id

        llm = get_llm(use_system_key=False, spend_token=False)
        assert llm.api_key == expected_key

def test_get_llm_class_disabled(app: Flask, mock_auth: MagicMock) -> None:
    with app.app_context():
        db = get_db()
        db.execute("UPDATE classes SET enabled=0 WHERE id=1")
        db.commit()

        mock_auth.user_id = 21
        mock_auth.cur_class.class_id = 1

        with pytest.raises(ClassDisabledError):
            get_llm(use_system_key=False, spend_token=False)


def test_get_llm_no_key_found_lti(app: Flask, mock_auth: MagicMock) -> None:
    """Test that a non-creator (e.g. LTI user) gets NoKeyFoundError if class has no key."""
    with app.app_context():
        db = get_db()
        # Class 1 is LTI. Set consumer key to NULL.
        db.execute("UPDATE consumers SET llm_api_key=NULL WHERE id=1")
        db.commit()

        mock_auth.user_id = 21  # ltiuser1 (not creator)
        mock_auth.cur_class.class_id = 1

        with pytest.raises(NoKeyFoundError):
            get_llm(use_system_key=False, spend_token=False)


def test_get_llm_no_key_found_student(app: Flask, mock_auth: MagicMock) -> None:
    """Test that a student (non-creator) gets NoKeyFoundError in a User class with no key."""
    with app.app_context():
        db = get_db()
        # Class 2 is User class created by testuser(11).
        # Set class key to NULL.
        db.execute("UPDATE classes_user SET llm_api_key=NULL WHERE class_id=2")
        db.commit()

        mock_auth.user_id = 12  # testadmin (student in class 2)
        mock_auth.cur_class.class_id = 2

        with pytest.raises(NoKeyFoundError):
            get_llm(use_system_key=False, spend_token=False)


def test_get_llm_creator_fallthrough(app: Flask, mock_auth: MagicMock) -> None:
    """Test that the creator of a class falls through to tokens if the class has no key."""
    with app.app_context():
        db = get_db()
        # Class 2 is User class created by testuser(11).
        db.execute("UPDATE classes_user SET llm_api_key=NULL WHERE class_id=2")
        db.execute("UPDATE users SET query_tokens=5 WHERE id=11")
        db.commit()

        mock_auth.user_id = 11  # creator of class 2
        mock_auth.cur_class.class_id = 2
        mock_auth.user.auth_provider = "demo"  # use tokens
        mock_auth.user.query_tokens = 5

        # Should not raise NoKeyFoundError, but fall through to tokens
        llm = get_llm(use_system_key=False, spend_token=True)
        assert llm.api_key == app.config['SYSTEM_API_KEY']
        assert llm.tokens_remaining == 4

        new_tokens = db.execute("SELECT query_tokens FROM users WHERE id=11").fetchone()[0]
        assert new_tokens == 4

def test_get_llm_no_tokens(app: Flask, mock_auth: MagicMock) -> None:
    with app.app_context():
        db = get_db()
        db.execute("UPDATE users SET query_tokens=0 WHERE id=21")
        db.commit()

        mock_auth.user_id = 21
        mock_auth.cur_class = None
        mock_auth.user.query_tokens = 0

        with pytest.raises(NoTokensError):
            get_llm(use_system_key=False, spend_token=False)


@pytest.mark.parametrize(("spend_token", "expected_tokens"), [
    (True, 9),  # decrement 10 to 9
    (False, 10),  # retain original 10 tokens
])
def test_get_llm_token_decrement(app: Flask, mock_auth: MagicMock, spend_token: bool, expected_tokens: int) -> None:
    with app.app_context():
        db = get_db()
        db.execute("UPDATE users SET query_tokens=10 WHERE id=21")
        db.commit()

        mock_auth.user_id = 21
        mock_auth.cur_class = None
        mock_auth.user.auth_provider = "demo"
        mock_auth.user.query_tokens = 10

        llm = get_llm(use_system_key=False, spend_token=spend_token)
        assert llm.tokens_remaining == expected_tokens
        tokens_in_db = db.execute("SELECT query_tokens FROM users WHERE id=21").fetchone()[0]
        assert tokens_in_db == expected_tokens


# --- Integration tests via decorator ---

@pytest.fixture
def test_route_app(app: Flask) -> Flask:
    @app.route('/test/llm_decorator')
    @with_llm(spend_token=True)
    def test_route(llm: Any) -> str:
        return f"Success: {llm.api_key}"
    return app


def test_decorator_class_disabled(test_route_app: Flask, client: AppClient) -> None:
    client.login('testuser', 'testpassword')
    client.get('/classes/switch/2')

    with test_route_app.app_context():
        db = get_db()
        db.execute("UPDATE classes SET enabled=0 WHERE id=2")
        db.commit()

    response = client.get('/test/llm_decorator')
    assert response.status_code == 400
    assert "archived or disabled" in response.text

def test_decorator_no_key(test_route_app: Flask, client: AppClient) -> None:
    # Login as a student in class 2 (testadmin/testadminpassword)
    # They are NOT the creator of class 2 (testuser is).
    client.login('testadmin', 'testadminpassword')
    client.get('/classes/switch/2')

    with test_route_app.app_context():
        db = get_db()
        db.execute("UPDATE classes_user SET llm_api_key=NULL WHERE class_id=2")
        db.commit()

    response = client.get('/test/llm_decorator')
    assert response.status_code == 400
    assert "No API key set" in response.text


# *no tokens left* case covered in test_demo_links:test_valid_demo_link


@pytest.mark.usefixtures("test_route_app")
def test_decorator_success(client: AppClient) -> None:
    client.login('testuser', 'testpassword')
    client.get('/classes/switch/2')

    response = client.get('/test/llm_decorator')
    assert response.status_code == 200
    assert "Success: nope" in response.text
