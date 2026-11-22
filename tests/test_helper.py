# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from flask import Flask

from gened.db import get_db
from tests.conftest import AppClient


@pytest.mark.use_real_openai
def test_openai_exception(client: AppClient) -> None:
    """ Check that we raise the correct OpenAI exception if we have an invalid API key.
    NOTE that this is using base_app, and so openai is *not* monkey-patched.
    Requests go to the actual OpenAI endpoint.
    """
    client.login()

    response = client.post('/help/request', data={'code': 'code', 'error': 'error', 'issue': 'issue'})

    assert response.status_code == 302         # expect a redirect
    assert "/help/view/" in response.location  # to a query result view

    # follow the redirect to the query view
    response = client.get(response.location)
    # ensure error message is present in query view
    assert "notification is-danger" in response.text
    assert "Error (AuthenticationError)" in response.text
    assert "The API key set by the instructor for this class is invalid" in response.text


@pytest.mark.parametrize(('context_name'), ['default', 'default2', 'default3'])
def test_saved_context(client: AppClient, context_name: str) -> None:
    """ Check that previously-used context is auto-selected in help interface. """
    client.login()

    response = client.get('/classes/switch/2')  # switch to class 2 (where contexts are configured and this user has a role)
    assert response.status_code == 302

    response = client.get("/help/")
    assert "selected>" not in response.text  # no previously used context yet

    client.post('/help/request', data={'context': context_name, 'code': 'code', 'error': 'error', 'issue': 'issue'})

    response = client.get("/help/")
    assert f"selected>{context_name}" in response.text


def test_context_description_shows_tools_and_details_but_hides_avoid(client: AppClient) -> None:
    """The student-facing context description omits the instructor's avoid terms."""
    client.login()
    response = client.get('/classes/switch/2')
    assert response.status_code == 302

    response = client.get('/help/')
    assert response.status_code == 200
    assert 'Python2' in response.text
    assert 'details2' in response.text
    assert 'avoid2' not in response.text


def test_query_records_rendered_context(app: Flask, client: AppClient) -> None:
    """The context string stored with a query includes the full prompt text."""
    client.login()
    response = client.get('/classes/switch/2')
    assert response.status_code == 302

    response = client.post('/help/request', data={
        'context': 'default2',
        'code': 'code',
        'error': 'error',
        'issue': 'issue',
    })
    assert response.status_code == 302

    with app.app_context():
        row = get_db().execute(
            """
            SELECT cs.ctx_str
            FROM code_queries AS q
            JOIN context_strings AS cs ON cs.id = q.context_string_id
            WHERE q.user_id = ? AND q.context_name = ?
            ORDER BY q.id DESC
            LIMIT 1
            """,
            [11, 'default2'],
        ).fetchone()
    assert row is not None
    context_string = row['ctx_str']
    assert 'Python2' in context_string
    assert 'details2' in context_string
    assert 'avoid2' in context_string
    assert 'Environment and tools' in context_string
    assert 'Keywords and concepts to avoid' in context_string


@pytest.mark.parametrize(('username', 'password'), [
    ('testuser', 'testpassword'),
    ('testadmin', 'testadminpassword'),
])
def test_query(client: AppClient, username: str, password: str) -> None:
    client.login(username, password)

    results = []

    for i in range(10):
        code = f"some very long test code to overflow the truncate limit in the query history and ensure this number is only in the main page: {i}"
        response = client.post(
            '/help/request',
            data={'code': code, 'error': 'test error', 'issue': 'test_issue'}
        )
        results.append((code, response.location))

    for code, path in results:
        response = client.get(path)
        assert code in response.text
