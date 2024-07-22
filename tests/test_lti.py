# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from oauthlib import oauth1

CLASS = {
    'label': "CS799-S23",
    'title': "CS799-S23+-+Advanced+LTI+Testing",
}

USER = {
    'given': "Tester",
    'family': "McTestson",
    'fullname': "Tester McTestson",
    'email': "tmctest@university.edu",
}


class LTIConsumer:
    def __init__(self, consumer_key='', consumer_secret=''):
        self.url = "http://localhost/lti/"
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def generate_launch_request(self, user_and_role, class_config=CLASS):
        params = {
            "user_id": user_and_role,
            "roles": user_and_role,
            "context_id": "course54321",
            "context_label": class_config['label'],
            "context_title": class_config['title'],
            "lis_person_name_given": USER['given'],
            "lis_person_name_family": USER['family'],
            "lis_person_name_full": USER['fullname'],
            "lis_person_contact_email_primary": USER['email'],
            "oauth_callback": "about:blank",
            "lti_version": "LTI-1p0",
            "lti_message_type": "basic-lti-launch-request",
        }

        headers = {'Content-Type': oauth1.rfc5849.CONTENT_TYPE_FORM_URLENCODED}

        client = oauth1.Client(
            self.consumer_key,
            self.consumer_secret,
            signature_type=oauth1.SIGNATURE_TYPE_BODY,
        )

        uri, headers, body = client.sign(
            self.url,
            http_method='POST',
            body=params,
            headers=headers
        )

        return uri, headers, body


@pytest.mark.parametrize(('consumer_key', 'consumer_secret'), [
    ('', ''),   # no consumer, no secret: invalid LTI communication
    ('invalid_consumer.domain', 'secret'),   # consumer not registered in app
    ('consumer.domain', 'wrong_secret'),   # consumer registered (see test_data.sql), but wrong secret provided
])
def test_lti_auth_failure(client, consumer_key, consumer_secret):
    lti = LTIConsumer(consumer_key, consumer_secret)
    uri, headers, body = lti.generate_launch_request("Instructor")
    result = client.post(uri, headers=headers, data=body)
    assert result.text == "There was an LTI communication error"


@pytest.mark.parametrize(('role', 'internal_role'), [
    ('Instructor', 'instructor'),
    ('urn:lti:role:ims/lis/TeachingAssistant', 'instructor'),  # canvas TA
    ('Student', 'student'),
])
def test_lti_auth_success(client, role, internal_role):
    # key and secret match 'consumer.domain' consumer in test_data.sql
    lti = LTIConsumer('consumer.domain', 'seecrits1')

    uri, headers, body = lti.generate_launch_request(role)

    result = client.post(uri, headers=headers, data=body)
    assert "LTI communication error" not in result.text
    # success == redirect to help page...
    assert result.status_code == 302
    if internal_role == 'instructor':
        assert result.location == '/instructor/config/'
    else:
        assert result.location == '/help/'

    result = client.get('/help/')
    assert result.status_code == 200

    # we can configure the class iff we're an instructor
    result = client.get('/instructor/config/')
    if internal_role == 'instructor':
        assert result.status_code == 200
    else:
        assert result.status_code == 302  # redirect to login (as non-instructor)

    # check the profile for correct name, class name and role
    result = client.get('/profile/')
    assert result.status_code == 200
    assert USER['fullname'] in result.text
    assert USER['email'] in result.text
    assert f"{CLASS['label']} ({internal_role})" in result.text


def test_lti_class_name_change(client):
    # key and secret match 'consumer.domain' consumer in test_data.sql
    lti = LTIConsumer('consumer.domain', 'seecrits1')

    role = "Student"
    internal_role = "student"
    class_config = CLASS
    uri, headers, body = lti.generate_launch_request(role, class_config=class_config)

    result = client.post(uri, headers=headers, data=body)
    assert "LTI communication error" not in result.text
    # success == redirect to help page...
    assert result.status_code == 302
    assert result.location == '/help/'

    result = client.get('/help/')
    assert result.status_code == 200

    # check the profile for correct name, class name and role
    result = client.get('/profile/')
    assert result.status_code == 200
    assert USER['fullname'] in result.text
    assert USER['email'] in result.text
    assert f"{class_config['label']} ({internal_role})" in result.text

    # log out, then log in with a different class name to verify the name changes
    client.post('/auth/logout')

    prev_label = class_config['label']
    class_config['label'] = "Completely Different"
    uri, headers, body = lti.generate_launch_request(role, class_config=class_config)

    result = client.post(uri, headers=headers, data=body)
    assert "LTI communication error" not in result.text
    # success == redirect to help page...
    assert result.status_code == 302
    assert result.location == '/help/'

    # check the profile for correct name, class name and role
    result = client.get('/profile/')
    assert result.status_code == 200
    assert USER['fullname'] in result.text
    assert USER['email'] in result.text
    assert f"{class_config['label']} ({internal_role})" in result.text
    assert prev_label not in result.text


def test_lti_instructor_and_students(client):
    # key and secret match 'consumer.domain' consumer in test_data.sql
    lti = LTIConsumer('consumer.domain', 'seecrits1')

    # 1) instructor logs in
    uri, headers, body = lti.generate_launch_request("instructor")
    client.post(uri, headers=headers, data=body)

    # 2) instructor can access the course help page
    result = client.get('/help/')
    assert result.status_code == 200
    assert USER['fullname'] in result.text

    client.post('/auth/logout')

    # 3) student 1 logs in, can access help page
    uri, headers, body = lti.generate_launch_request("student_1")
    client.post(uri, headers=headers, data=body)

    result = client.get('/help/')
    assert result.status_code == 200

    # 4) student 1 makes a query
    result = client.post('/help/request', data={'code': 'student_1_code', 'error': 'error', 'issue': 'issue'})
    assert result.status_code == 302
    assert result.location == "/help/view/5"  # next open query ID (test_data.sql inserts up to 4)
    result = client.get(result.location)
    assert result.status_code == 200
    assert 'student_1_code' in result.text

    client.post('/auth/logout')

    # 5) student 2 logs in
    uri, headers, body = lti.generate_launch_request("student_2")
    client.post(uri, headers=headers, data=body)

    result = client.get('/help/')
    assert result.status_code == 200

    # 6) student 2 cannot see student 1's query
    result = client.get('/help/view/5')
    assert result.status_code == 400
    assert 'student_1_code' not in result.text
    assert 'Invalid id.' in result.text

    client.post('/auth/logout')

    # 7) instructor logs in again and can see student 1's query
    uri, headers, body = lti.generate_launch_request("instructor")
    client.post(uri, headers=headers, data=body)

    result = client.get('/help/view/5')
    assert result.status_code == 200
    assert 'student_1_code' in result.text
    assert 'Invalid id.' not in result.text
