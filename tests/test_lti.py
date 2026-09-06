# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from html.parser import HTMLParser

import pytest
from flask import Flask, url_for
from oauthlib import oauth1

from gened.db import get_db
from tests.conftest import AppClient

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
    def __init__(self, consumer_key: str='', consumer_secret: str='') -> None:
        self.url = "http://localhost/lti/"
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def generate_launch_request(self, user_and_role: str, class_config: dict[str, str]=CLASS, *, message_type: str = "basic-lti-launch-request", context_id: str = "course54321", return_url: str | None = None) -> tuple[str, dict[str, str], str]:
        params = {
            "user_id": user_and_role,
            "roles": user_and_role,
            "context_id": context_id,
            "context_label": class_config['label'],
            "context_title": class_config['title'],
            "lis_person_name_given": USER['given'],
            "lis_person_name_family": USER['family'],
            "lis_person_name_full": USER['fullname'],
            "lis_person_contact_email_primary": USER['email'],
            "oauth_callback": "about:blank",
            "lti_version": "LTI-1p0",
            "lti_message_type": message_type,
        }
        if return_url is not None:
            params["content_item_return_url"] = return_url

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
def test_lti_auth_failure(client: AppClient, consumer_key: str, consumer_secret: str) -> None:
    lti = LTIConsumer(consumer_key, consumer_secret)
    uri, headers, body = lti.generate_launch_request("Instructor")
    result = client.post(uri, headers=headers, data=body)
    assert result.text == "There was an LTI communication error"


@pytest.mark.parametrize(('role', 'internal_role'), [
    ('Instructor', 'instructor'),
    ('urn:lti:role:ims/lis/TeachingAssistant', 'instructor'),  # canvas TA
    ('Student', 'student'),
])
def test_lti_auth_success(app: Flask, client: AppClient, role: str, internal_role: str) -> None:
    # key and secret match 'consumer.domain' consumer in test_data.sql
    lti = LTIConsumer('consumer.domain', 'seecrits1')

    uri, headers, body = lti.generate_launch_request(role)

    result = client.post(uri, headers=headers, data=body)
    assert "LTI communication error" not in result.text
    # success == redirect to configured post-login page...
    assert result.status_code == 302
    with app.test_request_context():
        if internal_role == 'instructor':
            assert result.location == url_for("class_config.base.config_form")
        else:
            assert result.location == url_for(app.config['DEFAULT_LOGIN_ENDPOINT'])

    result = client.get('/help/')
    assert result.status_code == 200

    # we can configure the class iff we're an instructor
    result = client.get('/instructor/config/')
    if internal_role == 'instructor':
        assert result.status_code == 200
    else:
        assert result.status_code == 403
        assert "Access denied" in result.text

    # check the profile for correct name, class name and role
    result = client.get('/profile/')
    assert result.status_code == 200
    assert USER['fullname'] in result.text
    assert USER['email'] in result.text
    assert f"{CLASS['label']} ({internal_role})" in result.text


def test_lti_class_name_change(app: Flask, client: AppClient) -> None:
    # key and secret match 'consumer.domain' consumer in test_data.sql
    lti = LTIConsumer('consumer.domain', 'seecrits1')

    role = "Student"
    internal_role = "student"
    class_config = CLASS
    uri, headers, body = lti.generate_launch_request(role, class_config=class_config)

    result = client.post(uri, headers=headers, data=body)
    assert "LTI communication error" not in result.text
    # success == redirect to configured page...
    assert result.status_code == 302
    with app.test_request_context():
        assert result.location == url_for(app.config['DEFAULT_LOGIN_ENDPOINT'])

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
    # success == redirect to configured page...
    assert result.status_code == 302
    with app.test_request_context():
        assert result.location == url_for(app.config['DEFAULT_LOGIN_ENDPOINT'])

    # check the profile for correct name, class name and role
    result = client.get('/profile/')
    assert result.status_code == 200
    assert USER['fullname'] in result.text
    assert USER['email'] in result.text
    assert f"{class_config['label']} ({internal_role})" in result.text
    assert prev_label not in result.text


def test_lti_instructor_and_students(client: AppClient) -> None:
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
    assert result.location == "/help/view/101"  # next open query ID (test_data.sql inserts max 100)
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
    result = client.get('/help/view/101')
    assert result.status_code == 400
    assert 'student_1_code' not in result.text
    assert 'Invalid id.' in result.text

    client.post('/auth/logout')

    # 7) instructor logs in again and can see student 1's query
    uri, headers, body = lti.generate_launch_request("instructor")
    client.post(uri, headers=headers, data=body)

    result = client.get('/help/view/101')
    assert result.status_code == 200
    assert 'student_1_code' in result.text
    assert 'Invalid id.' not in result.text

def test_lti_config_xml_available(client: AppClient) -> None:
    result = client.get('/lti/config.xml')
    assert result.status_code == 200
    assert result.text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<cartridge_basiclti_link')
    assert "CodeHelp" in result.text


class RadioGrab(HTMLParser):
    """ Collects the attributes of all radio-button inputs in an HTML document. """
    def __init__(self) -> None:
        super().__init__()
        self.radios: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'input':
            attrs_dict = {key: value for key, value in attrs if value is not None}
            if attrs_dict.get('type') == 'radio':
                self.radios.append(attrs_dict)


def test_lti_content_select_launch(app: Flask, client: AppClient) -> None:
    # instructor content-item-selection launch -> 302 to the select page
    # (the return URL is not passed in the redirect; the page reads it from the session)
    lti = LTIConsumer('consumer.domain', 'seecrits1')
    uri, headers, body = lti.generate_launch_request("Instructor", message_type="ContentItemSelectionRequest", return_url="https://lms.example.com/content_item")
    result = client.post(uri, headers=headers, data=body)
    assert result.status_code == 302
    with app.test_request_context():
        assert result.location == url_for("class_config.base.lti_content_select")


def test_lti_content_select_page(app: Flask, client: AppClient) -> None:
    # launch against class 1 (context_id 'ctx_id'), which has context item 'default' (id=1)
    lti = LTIConsumer('consumer.domain', 'seecrits1')
    return_url = "https://lms.example.com/content_item"
    uri, headers, body = lti.generate_launch_request("Instructor", message_type="ContentItemSelectionRequest", context_id="ctx_id", return_url=return_url)
    client.post(uri, headers=headers, data=body)

    # add a context that is not yet available; it must still be linkable, with a note
    with app.app_context():
        db = get_db()
        future_id = db.execute(
            "INSERT INTO config_items (class_id, item_type, name, class_order, available, config) VALUES (?, ?, ?, ?, ?, ?)",
            [1, 'context', 'future', 10, '2999-01-01', '{"tools":"","details":"","avoid":""}'],
        ).lastrowid
        # add a context hidden by the instructor (sentinel available date); it must
        # be flagged as hidden, not "not yet available" with the far-future date
        hidden_id = db.execute(
            "INSERT INTO config_items (class_id, item_type, name, class_order, available, config) VALUES (?, ?, ?, ?, ?, ?)",
            [1, 'context', 'hidden_ctx', 11, '9999-12-31', '{"tools":"","details":"","avoid":""}'],
        ).lastrowid
        db.commit()

    result = client.get("/instructor/config/lti_content_select")
    assert result.status_code == 200
    text = result.text
    # standalone document (no app layout) whose single form posts to the LMS return URL
    assert 'navbar' not in text
    assert f'action="{return_url}"' in text
    assert 'name="lti_message_type" value="ContentItemSelection"' in text
    assert 'name="lti_version" value="LTI-1p0"' in text
    assert text.count('name="content_items"') == 1
    # both context items appear under both of their share links
    assert 'default — Help form' in text
    assert 'default — Inquiry chat' in text
    # the not-yet-available item is offered too, flagged so it doesn't surprise the instructor
    assert 'future — Help form (not yet available; available 2999-01-01)' in text
    assert 'future — Inquiry chat (not yet available; available 2999-01-01)' in text
    # a hidden item is offered too, flagged as hidden (not "available 9999-12-31")
    assert 'hidden_ctx — Help form (hidden from students)' in text
    assert 'hidden_ctx — Inquiry chat (hidden from students)' in text

    # each option's data-ci attribute holds a valid content_items JSON document
    grab = RadioGrab()
    grab.feed(text)
    assert len(grab.radios) == 6
    payloads = {}
    for radio in grab.radios:
        assert radio['name'] == 'content_select'
        payload = json.loads(radio['data-ci'])
        assert payload['@context'] == 'http://purl.imsglobal.org/ctx/lti/v1/ContentItem'
        assert len(payload['@graph']) == 1
        payloads[radio['value']] = payload['@graph'][0]

    assert set(payloads) == {
        'context:context_help_form:1', 'context:context_inquiry_chat:1',
        f'context:context_help_form:{future_id}', f'context:context_inquiry_chat:{future_id}',
        f'context:context_help_form:{hidden_id}', f'context:context_inquiry_chat:{hidden_id}',
    }
    help_item = payloads['context:context_help_form:1']
    assert help_item['@id'] == 'gened_context_1_context_help_form'
    assert help_item['text'] == 'CodeHelp: Help form – default'  # noqa: RUF001
    assert help_item['mediaType'] == 'application/vnd.ims.lti.v1.ltilink'
    assert help_item['placementAdvice'] == {'presentationDocumentTarget': 'window'}
    assert help_item['url'] == "http://localhost/lti/?dl_table=context&dl_link=context_help_form&content_id=1"
    inquiry_item = payloads['context:context_inquiry_chat:1']
    assert inquiry_item['@id'] == 'gened_context_1_context_inquiry_chat'
    assert inquiry_item['text'] == 'CodeHelp: Inquiry chat – default'  # noqa: RUF001
    assert inquiry_item['url'] == "http://localhost/lti/?dl_table=context&dl_link=context_inquiry_chat&content_id=1"
    # deep links are built for not-yet-available items as well (launches to them are allowed)
    future_item = payloads[f'context:context_help_form:{future_id}']
    assert future_item['@id'] == f'gened_context_{future_id}_context_help_form'
    assert future_item['url'] == f"http://localhost/lti/?dl_table=context&dl_link=context_help_form&content_id={future_id}"
    # deep links are built for hidden items as well
    hidden_item = payloads[f'context:context_help_form:{hidden_id}']
    assert hidden_item['@id'] == f'gened_context_{hidden_id}_context_help_form'
    assert hidden_item['url'] == f"http://localhost/lti/?dl_table=context&dl_link=context_help_form&content_id={hidden_id}"


def test_lti_content_select_page_empty(client: AppClient) -> None:
    # launch for a context with no mapped class items -> "nothing to link yet", no form
    lti = LTIConsumer('consumer.domain', 'seecrits1')
    uri, headers, body = lti.generate_launch_request("Instructor", message_type="ContentItemSelectionRequest", context_id="ctx_no_items", return_url="https://lms.example.com/content_item")
    result = client.post(uri, headers=headers, data=body)
    assert result.status_code == 302

    result = client.get("/instructor/config/lti_content_select")
    assert result.status_code == 200
    assert 'no content to link yet' in result.text
    assert '<form' not in result.text


def test_lti_content_select_no_return_url(app: Flask, client: AppClient) -> None:
    # instructor logged in via a normal launch (no selection request in session)
    lti = LTIConsumer('consumer.domain', 'seecrits1')
    uri, headers, body = lti.generate_launch_request("Instructor")
    client.post(uri, headers=headers, data=body)
    with client.session_transaction() as sess:
        sess.pop('content_item_return_url', None)
    result = client.get("/instructor/config/lti_content_select")
    assert result.status_code == 302
    with app.test_request_context():
        assert result.location == url_for("class_config.base.config_form")


def test_lti_content_select_invalid_return_url(app: Flask, client: AppClient) -> None:
    # a non-http(s) return URL must not be rendered as the form action
    # (it would execute in the app's origin on submit)
    lti = LTIConsumer('consumer.domain', 'seecrits1')
    uri, headers, body = lti.generate_launch_request("Instructor", message_type="ContentItemSelectionRequest", return_url="javascript:alert(1)")
    client.post(uri, headers=headers, data=body)
    result = client.get("/instructor/config/lti_content_select")
    assert result.status_code == 302
    with app.test_request_context():
        assert result.location == url_for("class_config.base.config_form")
    # the warning is shown on the page the instructor lands on
    result = client.get(result.location)
    assert result.status_code == 200
    assert "did not provide a valid return URL" in result.text
    # the unusable value is cleared, so later visits see "no launch in progress"
    with client.session_transaction() as sess:
        assert 'content_item_return_url' not in sess


def test_lti_content_select_student_rejected(client: AppClient) -> None:
    # content selection is instructor-only; a student launch is rejected
    lti = LTIConsumer('consumer.domain', 'seecrits1')
    uri, headers, body = lti.generate_launch_request("Student", message_type="ContentItemSelectionRequest", return_url="https://lms.example.com/content_item")
    result = client.post(uri, headers=headers, data=body)
    assert result.status_code == 400


def test_lti_content_select_launch_missing_return_url(client: AppClient) -> None:
    # a selection request without content_item_return_url cannot complete; rejected at launch
    lti = LTIConsumer('consumer.domain', 'seecrits1')
    uri, headers, body = lti.generate_launch_request("Instructor", message_type="ContentItemSelectionRequest")
    result = client.post(uri, headers=headers, data=body)
    assert result.status_code == 400
