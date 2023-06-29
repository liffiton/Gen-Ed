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
