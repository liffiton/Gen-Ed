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
def test_saved_context(app, client, auth, context_name):
    """ Check that previously-used context is auto-selected in help interface. """
    auth.login()

    response = client.get('/classes/switch/2')  # switch to class 2 (where contexts are configured and this user has a role)
    assert response.status_code == 302

    response = client.get("/help/")
    assert "selected>" not in response.text  # no previously used context yet

    client.post('/help/request', data={'context': context_name, 'code': 'code', 'error': 'error', 'issue': 'issue'})

    response = client.get("/help/")
    assert f"selected>{context_name}" in response.text


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
            data={'code': code, 'error': 'test error', 'issue': 'test_issue'}
        )
        results.append((code, response.location))

    for code, path in results:
        response = client.get(path)
        assert code in response.text
