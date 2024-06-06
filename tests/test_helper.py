# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest


@pytest.mark.use_real_openai()
def test_openai_exception(client, auth):
    """ Check that we raise the correct OpenAI exception if we have an invalid API key.
    NOTE that this is using base_app, and so openai is *not* monkey-patched.
    Requests go to the actual OpenAI endpoint.
    """
    auth.login()

    response = client.post('/help/request', data={'lang_id': 0, 'code': 'code', 'error': 'error', 'issue': 'issue'})

    assert response.status_code == 302         # expect a redirect
    assert "/help/view/" in response.location  # to a query result view

    # follow the redirect to the query view
    response = client.get(response.location)
    # ensure error message is present in query view
    assert "notification is-danger" in response.text
    assert "Error (AuthenticationError)" in response.text
    assert "The API key set by the instructor for this class is invalid" in response.text


@pytest.mark.parametrize(('lang_id'), [0, 1, 2])
def test_saved_language(app, client, auth, lang_id):
    """ Check that previously-used language is auto-selected in help interface. """
    auth.login()

    response = client.get("/help/")
    assert "selected" not in response.text  # no previously used language yet

    client.post('/help/request', data={'lang_id': lang_id, 'code': 'code', 'error': 'error', 'issue': 'issue'})

    response = client.get("/help/")
    language = app.config['DEFAULT_LANGUAGES'][lang_id]
    assert f"selected>{language}" in response.text


@pytest.mark.parametrize(('username', 'password'), [
    ('testuser', 'testpassword'),
    ('testadmin', 'testadminpassword'),
])
def test_query(client, auth, username, password):
    auth.login(username, password)

    results = []

    for i in range(10):
        code = f"some very long test code to overflow the truncate limit in the query history and ensure this number is only in the main page: {i}"
        response = client.post(
            '/help/request',
            data={'lang_id': 1, 'code': code, 'error': 'test error', 'issue': 'test_issue'}
        )
        results.append((code, response.location))

    for code, path in results:
        response = client.get(path)
        assert code in response.text
