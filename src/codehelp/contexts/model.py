# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import dataclass
from typing import Self

from flask import Flask
from jinja2 import Environment
from werkzeug.datastructures import ImmutableMultiDict

from gened.class_config import ConfigItem

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

@dataclass
class ContextConfig(ConfigItem):
    name: str
    tools: str = ''
    details: str = ''
    avoid: str = ''

    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, str]) -> Self:
        """ Instantiate a context object from a request form to get its config as json. """
        return cls(
            name=form['name'],
            tools=form.get('tools', ''),
            details=form.get('details', ''),
            avoid=form.get('avoid', ''),
        )

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


def get_markdown_filter(app: Flask) -> None:
    """ Grab a copy of the app's markdown filter for use here. """
    _jinja_env_html.filters['markdown'] = app.jinja_env.filters['markdown']
