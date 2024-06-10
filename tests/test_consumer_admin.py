# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only


def test_create_consumer(client, auth):
    auth.login('testadmin', 'testadminpassword')
    response = client.post(
        '/admin/consumer/update',
        data={
            'lti_consumer': 'test_consumer',
            'lti_secret': 'test_secret',
            'openai_key': 'test_openai_key',
            'model_id': 1
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Consumer test_consumer created." in response.data
    assert len(response.history) == 1  # one redirect
    assert response.request.path == '/admin/consumer/3'
    assert b"test_secret" in response.data


def test_edit_consumer(client, auth):
    auth.login('testadmin', 'testadminpassword')
    response = client.post(
        '/admin/consumer/update',
        data={
            'consumer_id': 1,
            'lti_secret': 'new_secret',
            'openai_key': 'new_openai_key',
            'model_id': 2
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert len(response.history) == 1  # one redirect
    assert response.request.path == '/admin/consumer/1'
    assert b"Consumer updated." in response.data


def test_delete_consumer_with_dependencies(client, auth):
    auth.login('testadmin', 'testadminpassword')
    response = client.post(
        '/admin/consumer/delete/1',
        follow_redirects=True
    )
    assert response.status_code == 200
    assert len(response.history) == 1  # one redirect
    assert response.request.path == '/admin/consumer/1'
    assert b"Cannot delete consumer: there are related classes." in response.data


def test_delete_consumer_with_no_classes(client, auth):
    auth.login('testadmin', 'testadminpassword')
    response = client.post(
        '/admin/consumer/delete/2',
        follow_redirects=True
    )
    assert response.status_code == 200
    assert len(response.history) == 1  # one redirect
    assert response.request.path == '/admin/'
    assert b"Consumer &#39;consumer.otherdomain&#39; deleted." in response.data


def test_delete_consumer_invalid(client, auth):
    auth.login('testadmin', 'testadminpassword')
    response = client.post(
        '/admin/consumer/delete/3',
        follow_redirects=True
    )
    assert response.status_code == 200
    assert len(response.history) == 1  # one redirect
    assert response.request.path == '/admin/consumer/3'
    assert b"Invalid id." in response.data
    assert b"deleted." not in response.data
