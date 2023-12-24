import re

import pytest


def test_not_logged_in(client):
    # reg/access links should not work if not logged in.
    response = client.get("/classes/access/reg_enabled")
    assert response.status_code == 302
    assert response.location == "/auth/login?next=/classes/access/reg_enabled?"


@pytest.mark.parametrize('link_name,status,result', [
    ('invalid_link', 404, None),
    ('reg_disabled', 200, 'Registration is not active for this class.'),
    ('reg_expired', 200, 'Registration is not active for this class.'),
    ('reg_enabled', 302, '/'),
])
def test_user_class_link(auth, client, link_name, status, result):
    auth.login()  # reg/access links only work if logged in

    response = client.get(f"/classes/access/{link_name}")
    assert response.status_code == status

    if status == 302:
        assert response.location == result
    elif status == 200:
        assert result in response.text


def _create_user_class(client, class_name):
    response = client.post(
        "/classes/create/",
        data={'class_name': class_name, 'openai_key': "none"}
    )

    assert response.status_code == 302
    assert response.location == "/instructor/config/"

    response = client.get(response.location)
    match = re.search(r"https?:\/\/\S+\/classes\/access\/(\w+)", response.text)
    assert match is not None
    assert match.group(1)

    class_access_link_name = match.group(1)
    return class_access_link_name


def test_user_class_creation(auth, client):
    auth.login()  # only works if logged in
    class_access_link_name = _create_user_class(client, "Test Class")
    test_user_class_link(auth, client, class_access_link_name, 302, '/')
