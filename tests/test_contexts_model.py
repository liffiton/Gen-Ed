# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
import sqlite3

import pytest
from flask import Flask
from werkzeug.datastructures import ImmutableMultiDict

from components.learning_contexts.model import ContextConfig


def _make_row(name: str, config: str) -> sqlite3.Row:
    """Build an sqlite row shaped like a config_items row."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    row: sqlite3.Row | None = conn.execute(
        "SELECT 1 AS id, ? AS name, ? AS config",
        (name, config),
    ).fetchone()
    conn.close()
    assert row is not None
    return row


def test_initial_context_has_defaults() -> None:
    item = ContextConfig.initial()
    assert item.name == ''
    assert item.details == ''
    assert item.guidance == ''
    assert item.avoid == ''
    assert item.row_id is None


def test_from_request_form_reads_all_fields() -> None:
    form: ImmutableMultiDict[str, str] = ImmutableMultiDict([
        ('name', 'Test Context'),
        ('details', 'Some **details**'),
        ('guidance', 'Use Socratic questioning.'),
        ('avoid', 'eval()\nzfill()'),
    ])
    item = ContextConfig.from_request_form(form)
    assert item.name == 'Test Context'
    assert item.details == 'Some **details**'
    assert item.guidance == 'Use Socratic questioning.'
    assert item.avoid == 'eval()\nzfill()'


def test_from_request_form_defaults_missing_optional_fields() -> None:
    form: ImmutableMultiDict[str, str] = ImmutableMultiDict([('name', 'Only Name')])
    item = ContextConfig.from_request_form(form)
    assert item.name == 'Only Name'
    assert item.details == ''
    assert item.guidance == ''
    assert item.avoid == ''


def test_to_json_includes_config_and_excludes_row_id() -> None:
    item = ContextConfig(
        name='Test',
        details='Details',
        guidance='Guidance',
        avoid='eval()',
        row_id=42,
    )
    data = json.loads(item.to_json())
    assert data == {
        'name': 'Test',
        'details': 'Details',
        'guidance': 'Guidance',
        'avoid': 'eval()',
    }


def test_to_json_writes_all_content_keys_even_when_empty() -> None:
    data = json.loads(ContextConfig(name='Test').to_json())
    assert data == {
        'name': 'Test',
        'details': '',
        'guidance': '',
        'avoid': '',
    }


def test_from_row_loads_legacy_tools_json_with_defaults() -> None:
    """Old JSON loads, but `tools` is silently dropped; defaults fill missing keys."""
    row = _make_row(
        'Legacy Context',
        '{"name": "Ignored", "tools": "Python\\nFlask", "details": "Legacy details", "avoid": "eval()"}',
    )
    item = ContextConfig.from_row(row)
    assert item.name == 'Legacy Context'
    assert item.details == 'Legacy details'
    assert item.guidance == ''
    assert item.avoid == 'eval()'
    assert not hasattr(item, 'tools')


@pytest.mark.parametrize('config', ['{}', '{"avoid": "eval()"}'])
def test_from_row_fills_missing_content_keys(config: str) -> None:
    item = ContextConfig.from_row(_make_row('Sparse', config))
    assert item.name == 'Sparse'
    assert item.details == ''
    assert item.guidance == ''
    assert item.avoid == ('eval()' if 'avoid' in config else '')


@pytest.mark.parametrize(('avoid', 'expected'), [
    ('eval()', 'eval()'),
    ('eval()\r\nzfill()\r\n', 'eval(); zfill()'),
    ('\r\neval()\r\n\r\n  zfill()  \r\n\r\n', 'eval(); zfill()'),
])
def test_prompt_str_formats_avoid_as_joined_list(avoid: str, expected: str) -> None:
    item = ContextConfig(name='Test', avoid=avoid)
    prompt = item.prompt_str()
    assert 'Terms and concepts to avoid' in prompt
    assert f'<avoid>{expected}</avoid>' in prompt


def test_prompt_str_name_only() -> None:
    assert ContextConfig(name='Python').prompt_str() == 'Python'


@pytest.mark.parametrize(('details', 'guidance', 'avoid'), [
    ('', '', ''),
    ('   ', '\r\n\t', '\n \n'),
])
def test_prompt_str_whitespace_only_content_uses_name_only(
    details: str,
    guidance: str,
    avoid: str,
) -> None:
    item = ContextConfig(name='Python', details=details, guidance=guidance, avoid=avoid)
    assert item.prompt_str() == 'Python'


def test_prompt_str_includes_content_in_order() -> None:
    item = ContextConfig(
        name='Python',
        details='Some **details**',
        guidance='Use Socratic questioning.',
        avoid='eval()\nzfill()',
    )
    prompt = item.prompt_str()
    assert 'Context name: <name>Python</name>' in prompt
    assert 'Details: <details>Some **details**</details>' in prompt
    assert 'General guidance: <guidance>Use Socratic questioning.</guidance>' in prompt
    assert (
        'Terms and concepts to avoid (do not mention these terms or concepts in your response at all): '
        '<avoid>eval(); zfill()</avoid>'
    ) in prompt
    assert prompt.index('Details:') < prompt.index('General guidance:') < prompt.index('Terms and concepts')


def test_prompt_str_omits_empty_fields() -> None:
    item = ContextConfig(name='Python', details='', guidance='Guidance only', avoid='')
    prompt = item.prompt_str()
    assert 'Details:' not in prompt
    assert 'General guidance: <guidance>Guidance only</guidance>' in prompt
    assert 'Terms and concepts to avoid' not in prompt


def test_desc_html_renders_only_details(app: Flask) -> None:
    item = ContextConfig(
        name='Python',
        details='Some **details**',
        guidance='secret-guidance-term',
        avoid='secret-avoid-term',
    )
    with app.app_context():
        description = item.desc_html()
    assert '<strong>details</strong>' in description
    assert 'Details:' not in description
    assert 'secret-guidance-term' not in description
    assert 'secret-avoid-term' not in description


@pytest.mark.parametrize('details', ['', '   ', '\r\n\t'])
def test_desc_html_empty_for_missing_or_whitespace_details(app: Flask, details: str) -> None:
    item = ContextConfig(name='Python', details=details)
    with app.app_context():
        assert item.desc_html() == ''
