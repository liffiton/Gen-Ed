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

    # Try 5 queries, verifying the tokens work (test_data.sql assigns 3 for this demo link)
    for i in range(5):
        test_code = f"_test_code_{i}_"
        response = client.post(
            '/help/request',
            data={'lang_id': 1, 'code': test_code, 'error': '_test_error_', 'issue': '_test_issue_'}
        )
        assert response.status_code == 302   # redirect
        response = client.get(response.location)
        assert response.status_code == 200
        assert '_test_error_' in response.text and '_test_issue_' in response.text
        if i < 3:
            assert test_code in response.text
        else:
            assert test_code not in response.text


def test_logged_in(auth, client):
    auth.login()
    response = client.get("/demo/test_valid")
    assert "Invalid demo link." not in response.text
    assert "You are already logged in." in response.text
