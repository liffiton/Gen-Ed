# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from dataclasses import asdict, dataclass
from sqlite3 import Row

from flask import Flask
from jinja2 import Environment
from typing_extensions import Self  # for 3.10
from werkzeug.datastructures import ImmutableMultiDict

# This module manages application-specific context configuration.
#
# It is kept relatively generic, and much of the specific implementation of
# a context can be controlled by the ContextConfig dataclass and related
# templates.
#
# App-specific context configuration data are stored in dataclasses.  The
# dataclass must specify the template filename, contain the context's name,
# define the config's fields and their types, and implement
# `from_request_form()` and `from_row()` class methods that generate a config
# object based on inputs in request.form (as submitted from the form in the
# specified template) or an SQLite row from the database.

_jinja_env_prompt = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,  # noqa: S701 - no need to escape for the LLM
)
_jinja_env_html = Environment(
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

        template = _jinja_env_prompt.from_string("""\
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
        template = _jinja_env_html.from_string("""\
{% if tools %}
<p><b>Environment & tools:</b> {{ tools }}</p>
{% endif %}
{% if details %}
<p><b>Details:</b></p>
{{ details | markdown }}
{% endif %}
""")
        return template.render(tools=self._list_fmt(self.tools), details=self.details, avoid=self._list_fmt(self.avoid))


def register(app: Flask) -> None:
    """ Grab a copy of the app's markdown filter for use here. """
    _jinja_env_html.filters['markdown'] = app.jinja_env.filters['markdown']
