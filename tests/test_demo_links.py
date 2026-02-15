# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from gened.db import get_db
from tests.conftest import AppClient


@pytest.mark.parametrize(('link_name', 'message'), [
    ('does_not_exist', 'Invalid demo link.'),
    ('test_disabled', 'Demo link disabled.'),
    ('test_expired', 'Demo link expired.'),
])
def test_invalid_demo_link(client: AppClient, link_name: str, message: str) -> None:
    """ Accessing an invalid demo link should return an error. """
    response = client.get(f"/demo/{link_name}")
    assert message in response.text

    response = client.get("/help/")
    assert response.status_code == 302   # /help/ redirects to login in all of these cases


def test_valid_demo_link(client: AppClient) -> None:
    """ Accessing a valid demo link should log the user in and allow posting a request. """
    response = client.get("/demo/test_valid")
    assert "Invalid demo link." not in response.text
    assert response.status_code == 302
    assert response.location == "/"

    # test_data.sql assigns 3 tokens
    response = client.get("/help/")

    # Try 5 queries, verifying the tokens work (test_data.sql assigns 3 for this demo link)
    for i in range(5):
        response1 = client.get("/help/")
        test_code = f"_test_code_{i}_"
        response2 = client.post(
            '/help/request',
            data={'code': test_code, 'error': f'_test_error_{i}_', 'issue': f'_test_issue_{i}_'}
        )
        if i < 3:
            assert response1.status_code == 200   # unauthorized in all of these cases
            assert f"{3-i} queries remaining." in response1.text
            # successful requests should redirect to a response page with the same items
            assert response2.status_code == 302   # redirect
            response3 = client.get(response2.location)
            assert test_code in response3.text
            assert f'_test_error_{i}_' in response3.text
            assert f'_test_issue_{i}_' in response3.text
        else:
            assert response1.status_code == 200   # unauthorized in all of these cases
            assert "You have used all of your free queries." in response1.text
            # those without tokens remaining return an error page directly
            assert response2.status_code == 200
            assert "You have used all of your free queries." in response2.text
            assert test_code not in response2.text
            assert '_test_error_' not in response2.text
            assert '_test_issue_' not in response2.text


def test_logged_in(client: AppClient) -> None:
    client.login()
    response = client.get("/demo/test_valid")
    assert "Invalid demo link." not in response.text
    assert "You are already logged in." in response.text


def test_instructor_demo_link(client: AppClient) -> None:
    """Test that instructor demo links create a class and allow LLM access via tokens."""
    app = client.application

    # Access the link
    response = client.get("/demo/test_instructor", follow_redirects=True)
    assert response.status_code == 200

    # Verify the class and role are correctly set up in the database
    with app.app_context():
        db = get_db()
        # Find the newly created demo user
        user_row = db.execute("SELECT id, last_class_id FROM users WHERE auth_provider=3 ORDER BY created DESC LIMIT 1").fetchone()
        user_id = user_row['id']
        class_id = user_row['last_class_id']
        assert class_id is not None

        # Verify the class has no key but the user is an instructor
        class_user_row = db.execute("SELECT llm_api_key FROM classes_user WHERE class_id=?", [class_id]).fetchone()
        assert class_user_row['llm_api_key'] is None

        role_row = db.execute("SELECT role FROM roles WHERE user_id=? AND class_id=?", [user_id, class_id]).fetchone()
        assert role_row['role'] == 'instructor'

    # Try an LLM action that spends a token (e.g. /help/request)
    # The user should have 5 tokens initially.
    client.post('/help/request', data={'code': 'c', 'error': 'e', 'issue': 'i'})

    with app.app_context():
        db = get_db()
        tokens = db.execute("SELECT query_tokens FROM users WHERE id=?", [user_id]).fetchone()['query_tokens']
        assert tokens == 4
