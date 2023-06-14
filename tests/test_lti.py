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
    def __init__(self, url, consumer_key='', consumer_secret=''):
        self.url = url
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def generate_launch_request(self, roles):
        params = {
            "user_id": "user54321",
            "roles": roles,
            "context_id": "course54321",
            "context_label": CLASS['label'],
            "context_title": CLASS['title'],
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


def test_lti_auth_bad_communication(client):
    lti_unconfigured = LTIConsumer('http://localhost/lti/')  # no consumer, secret set; invalid LTI communication
    uri, headers, body = lti_unconfigured.generate_launch_request("Instructor")
    result = client.post(uri, headers=headers, data=body)
    assert result.text == "There was an LTI communication error"


def test_lti_auth_bad_consumer(client):
    # Consumer not registered in app
    lti_unconfigured = LTIConsumer('http://localhost/lti/', 'invalid_consumer.domain', 'secret')

    uri, headers, body = lti_unconfigured.generate_launch_request("Instructor")
    result = client.post(uri, headers=headers, data=body)
    assert result.text == "There was an LTI communication error"


def test_lti_auth_bad_secret(client):
    # Incorrect secret for that consumer as configured in the database (test_data.sql)
    lti_unconfigured = LTIConsumer('http://localhost/lti/', 'consumer.domain', 'wrong_secret')

    uri, headers, body = lti_unconfigured.generate_launch_request("Instructor")
    result = client.post(uri, headers=headers, data=body)
    assert result.text == "There was an LTI communication error"


def test_lti_auth_instructor(client):
    # key and secret match 'consumer.domain' consumer in test_data.sql
    lti = LTIConsumer('http://localhost/lti/', 'consumer.domain', 'seecrits1')

    uri, headers, body = lti.generate_launch_request("Instructor")

    result = client.post(uri, headers=headers, data=body)
    assert result.text != "There was an LTI communication error"
    assert result.status_code == 302  # success == redirect to help page...
    assert result.location == '/help/'

    result = client.get('/help/')
    assert result.status_code == 302  # ... but the class is not configured, so another redirect to the instructor config page
    assert result.location == '/instructor/config'

    result = client.post(
        '/instructor/config/set',
        data={'class_id': 2, 'default_lang': 1, 'avoid': ''},
        follow_redirects=True
    )
    assert "Configuration set!" in result.text

    result = client.get('/help/')
    assert result.status_code == 200  # ... and now it should work!
    assert USER['fullname'] in result.text

    result = client.get('/profile/')
    assert result.status_code == 200
    assert f"{CLASS['label']} (instructor)" in result.text


def test_lti_auth_student(client):
    # key and secret match 'consumer.domain' consumer in test_data.sql
    lti = LTIConsumer('http://localhost/lti/', 'consumer.domain', 'seecrits1')

    uri, headers, body = lti.generate_launch_request("Student")

    result = client.post(uri, headers=headers, data=body)
    assert result.text != "There was an LTI communication error"
    assert result.status_code == 302  # success == redirect to help page...
    assert result.location == '/help/'

    result = client.get('/help/')
    assert result.status_code == 200
    assert USER['fullname'] in result.text

    result = client.get('/profile/')
    assert result.status_code == 200
    assert f"{CLASS['label']} (student)" in result.text
