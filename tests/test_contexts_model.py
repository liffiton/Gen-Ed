# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json

import pytest
from flask import Flask
from werkzeug.datastructures import ImmutableMultiDict

from components.code_contexts.model import ContextConfig


def test_initial_context_has_defaults() -> None:
    item = ContextConfig.initial()
    assert item.name == ''
    assert item.tools == ''
    assert item.details == ''
    assert item.avoid == ''
    assert item.row_id is None


def test_from_request_form_reads_all_fields() -> None:
    form: ImmutableMultiDict[str, str] = ImmutableMultiDict([
        ('name', 'Test Context'),
        ('tools', 'Python\nFlask'),
        ('details', 'Some **details**'),
        ('avoid', 'eval()\nzfill()'),
    ])
    item = ContextConfig.from_request_form(form)
    assert item.name == 'Test Context'
    assert item.tools == 'Python\nFlask'
    assert item.details == 'Some **details**'
    assert item.avoid == 'eval()\nzfill()'


def test_from_request_form_defaults_missing_optional_fields() -> None:
    form: ImmutableMultiDict[str, str] = ImmutableMultiDict([('name', 'Only Name')])
    item = ContextConfig.from_request_form(form)
    assert item.name == 'Only Name'
    assert item.tools == ''
    assert item.details == ''
    assert item.avoid == ''


def test_to_json_includes_config_and_excludes_row_id() -> None:
    item = ContextConfig(name='Test', tools='Python', details='Details', avoid='eval()', row_id=42)
    data = json.loads(item.to_json())
    assert data == {
        'name': 'Test',
        'tools': 'Python',
        'details': 'Details',
        'avoid': 'eval()',
    }


@pytest.mark.parametrize(('tools', 'avoid', 'expected_tools', 'expected_avoid'), [
    ('Python\nFlask', 'eval()', 'Python; Flask', 'eval()'),
    ('Python\r\nFlask\r\n', 'eval()\r\nzfill()\r\n', 'Python; Flask', 'eval(); zfill()'),
    ('', '', '', ''),
])
def test_prompt_str_formats_lists(tools: str, avoid: str, expected_tools: str, expected_avoid: str) -> None:
    item = ContextConfig(name='Test', tools=tools, details='', avoid=avoid)
    prompt = item.prompt_str()
    if expected_tools:
        assert f'Environment and tools: <tools>{expected_tools}</tools>' in prompt
    else:
        assert 'Environment and tools:' not in prompt
    if expected_avoid:
        assert 'Keywords and concepts to avoid' in prompt
        assert f'<avoid>{expected_avoid}</avoid>' in prompt
    else:
        assert 'Keywords and concepts to avoid' not in prompt


def test_prompt_str_name_only() -> None:
    assert ContextConfig(name='Python').prompt_str() == 'Python'


def test_prompt_str_includes_details_and_avoid() -> None:
    item = ContextConfig(name='Python', details='Some **details**', avoid='eval()')
    prompt = item.prompt_str()
    assert 'Context name: <name>Python</name>' in prompt
    assert 'Details: <details>Some **details**</details>' in prompt
    assert 'Keywords and concepts to avoid' in prompt
    assert 'eval()' in prompt


def test_desc_html_shows_tools_and_details_but_not_avoid(app: Flask) -> None:
    item = ContextConfig(name='Python', tools='Python\nFlask', details='Some **details**', avoid='secret-avoid-term')
    with app.app_context():
        description = item.desc_html()
    assert 'Python; Flask' in description
    assert '<strong>details</strong>' in description
    assert 'secret-avoid-term' not in description


@pytest.mark.parametrize(('tools', 'details'), [
    ('', ''),
    ('Python', ''),
    ('', 'Details'),
])
def test_desc_html_omits_empty_fields(app: Flask, tools: str, details: str) -> None:
    item = ContextConfig(name='Python', tools=tools, details=details)
    with app.app_context():
        description = item.desc_html()
    if tools:
        assert 'Environment & tools:' in description
    else:
        assert 'Environment & tools:' not in description
    if details:
        assert 'Details:' in description
    else:
        assert 'Details:' not in description
    if not tools and not details:
        assert description.strip() == ''
