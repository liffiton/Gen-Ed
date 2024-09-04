# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from dataclasses import asdict, dataclass
from sqlite3 import Row

from flask import current_app
from gened.auth import get_auth
from gened.db import get_db
from jinja2 import Environment
from typing_extensions import Self
from werkzeug.datastructures import ImmutableMultiDict


def _default_langs() -> list[str]:
    langs: list[str] = current_app.config['DEFAULT_LANGUAGES']  # declaration keeps mypy happy
    return langs

jinja_env_prompt = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,  # noqa: S701 - no need to escape for the LLM
)
jinja_env_html = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=True,
)


@dataclass(frozen=True)
class ContextConfig:
    name: str
    tools: str = ''
    details: str = ''
    avoid: str = ''
    template: str = "context_edit_form.html"

    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, str]) -> Self:
        """ Instantiate a context object from a request form. """
        return cls(
            name=form['name'],
            tools=form.get('tools', ''),
            details=form.get('details', ''),
            avoid=form.get('avoid', ''),
        )

    # Instantiate from an SQLite row (implemented here) (requires correct field
    # names in the row and in its 'config' entry JSON)
    @classmethod
    def from_row(cls, row: Row) -> Self:
        """ Instantiate a context object from an SQLite row.
            (Requires correct field names in the row and in its 'config' JSON column.)
        """
        attrs = json.loads(row['config'])
        attrs['name'] = row['name']
        return cls(**attrs)

    # Dump config data (all but name and template) to JSON (implemented here)
    def to_json(self) -> str:
        filtered_attrs = {k: v for k, v in asdict(self).items() if k not in ('name', 'template')}
        return json.dumps(filtered_attrs)

    @staticmethod
    def _list_fmt(s: str) -> str:
        if s:
            return '; '.join(s.splitlines())
        else:
            return ''

    def prompt_str(self) -> str:
        """ Convert this context into a string to be used in an LLM prompt. """
        # if nothing is provided but a name, use just that name by itself
        if not self.tools and not self.details and not self.avoid:
            return self.name

        template = jinja_env_prompt.from_string("""\
Context name: <name>{{ name }}</name>
{% if tools %}
Environment and tools: <tools>{{ tools }}</tools>
{% endif %}
{% if details %}
Details: <details>{{ details }}</details>
{% endif %}
{% if avoid %}
Keywords and concepts to avoid (do not mention these in your response at all): <avoid>{{ avoid }}</avoid>
{% endif %}
""")
        return template.render(name=self.name, tools=self._list_fmt(self.tools), details=self.details, avoid=self._list_fmt(self.avoid))

    def desc_html(self) -> str:
        """ Convert this context into a description for users in HTML.

        Does not include the avoid set (not necessary to show students).
        """
        template = jinja_env_html.from_string("""\
{% if tools %}
<p><b>Environment & tools:</b> {{ tools }}</p>
{% endif %}
{% if details %}
<p><b>Details:</b></p>
{{ details | markdown }}
{% endif %}
""")
        return template.render(tools=self._list_fmt(self.tools), details=self.details, avoid=self._list_fmt(self.avoid))


### Helper functions for using contexts

def get_available_contexts() -> list[ContextConfig]:
    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']
    # Only return contexts that are available:
    #   current date anywhere on earth (using UTC+12) is at or after the saved date
    context_rows = db.execute("SELECT * FROM contexts WHERE class_id=? AND available <= date('now', '+12 hours') ORDER BY class_order ASC", [class_id]).fetchall()

    return [ContextConfig.from_row(row) for row in context_rows]


def get_context_config_by_id(ctx_id: int) -> ContextConfig | None:
    """ Return a context object of the given class based on the specified id
        or return None if no context exists with that name.
    """
    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']  # just for extra safety: double-check that the context is in the current class

    context_row = db.execute("SELECT * FROM contexts WHERE class_id=? AND id=?", [class_id, ctx_id]).fetchone()

    if not context_row:
        return None

    return ContextConfig.from_row(context_row)


def get_context_by_name(ctx_name: str) -> ContextConfig | None:
    """ Return a context object of the given class based on the specified name
        or return None if no context exists with that name.
    """
    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']

    context_row = db.execute("SELECT * FROM contexts WHERE class_id=? AND name=?", [class_id, ctx_name]).fetchone()

    if not context_row:
        return None

    return ContextConfig.from_row(context_row)


def record_context_string(context_str: str) -> int:
    """ Ensure a context string is recorded in the context_strings
        table, and return its row ID.
    """
    db = get_db()
    # Add the context string to the context_strings table, but if it's a duplicate, just get the row ID of the existing one.
    # The "UPDATE SET id=id" is a no-op, but it allows the "RETURNING" to work in case of a conflict as well.
    cur = db.execute("INSERT INTO context_strings (ctx_str) VALUES (?) ON CONFLICT DO UPDATE SET id=id RETURNING id", [context_str])
    context_string_id = cur.fetchone()['id']
    assert isinstance(context_string_id, int)
    return context_string_id
