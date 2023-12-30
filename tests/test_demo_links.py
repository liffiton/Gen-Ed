# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

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
    assert response.status_code == 302   # /help/ redirects to login in all of these cases


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
        if i < 3:
            # successful requests should redirect to a response page with the same items
            assert response.status_code == 302   # redirect
            response = client.get(response.location)
            assert test_code in response.text
            assert '_test_error_' in response.text
            assert '_test_issue_' in response.text
        else:
            # those without tokens remaining return an error page directly
            assert response.status_code == 200
            assert "You have used all of your free tokens." in response.text
            assert test_code not in response.text
            assert '_test_error_' not in response.text
            assert '_test_issue_' not in response.text


def test_logged_in(auth, client):
    auth.login()
    response = client.get("/demo/test_valid")
    assert "Invalid demo link." not in response.text
    assert "You are already logged in." in response.text
