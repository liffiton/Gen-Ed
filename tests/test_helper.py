import pytest


@pytest.mark.parametrize(('lang_id'), (0, 2, 4, 6))
def test_saved_language(app, client, auth, lang_id):
    """ Check that previously-used language is auto-selected in help interface. """
    auth.login()

    response = client.get("/help/")
    assert "selected" not in response.text  # no previously used language yet

    client.post('/help/request', data={'lang_id': lang_id, 'code': 'code', 'error': 'error', 'issue': 'issue'})

    response = client.get("/help/")
    language = app.config['LANGUAGES'][lang_id].capitalize()
    assert f"selected>{language}" in response.text


@pytest.mark.parametrize(('username', 'password'), (
    ('testuser', 'testpassword'),
    ('testadmin', 'testadminpassword'),
))
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
