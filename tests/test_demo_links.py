import pytest


@pytest.mark.parametrize('link_name,message', [
    ('does_not_exist', 'Invalid demo link.'),
    ('test_disabled', 'Demo link disabled.'),
    ('test_expired', 'Demo link expired.'),
])
def test_invalid_demo_link(client, link_name, message):
    """ Accessing an invalid demo link should return an error. """
    response = client.get(f"/demo/{link_name}")
    assert message in response.text

    response = client.get("/help/")
    assert response.status_code == 401   # unauthorized in all of these cases


def test_valid_demo_link(client):
    """ Accessing a valid demo link should log the user in and allow posting a request. """
    response = client.get("/demo/test_valid")
    assert "Invalid demo link." not in response.text

    response = client.get("/help/")
    assert response.status_code == 200   # unauthorized in all of these cases

    response = client.post(
        '/help/request',
        data={'lang_id': 1, 'code': 'test code', 'error': 'test error', 'issue': 'test_issue'}
    )
    assert response.status_code == 302   # redirect

    response = client.get(response.location)
    assert response.status_code == 200
    assert 'test code' in response.text


def test_logged_in(auth, client):
    auth.login()
    response = client.get("/demo/test_valid")
    assert "Invalid demo link." not in response.text
    assert "You are already logged in." in response.text
