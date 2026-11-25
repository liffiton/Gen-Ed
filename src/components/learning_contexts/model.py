# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Self

from flask import current_app
from werkzeug.datastructures import ImmutableMultiDict

from gened.class_config.types import ConfigItem


class ContextConfig(ConfigItem):
    details: str = ''
    guidance: str = ''
    avoid: str = ''

    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, str]) -> Self:
        """ Instantiate a context object from a request form to get its config as json. """
        return cls(
            name=form['name'],
            details=form.get('details', ''),
            guidance=form.get('guidance', ''),
            avoid=form.get('avoid', ''),
        )

    @staticmethod
    def _list_fmt(s: str) -> str:
        """ Format newline-separated text as a semicolon-separated list. """
        lines = [line.strip() for line in s.splitlines()]
        return '; '.join(line for line in lines if line)

    def prompt_str(self) -> str:
        """ Convert this context into a string to be used in an LLM prompt. """
        details = self.details if self.details.strip() else ''
        guidance = self.guidance if self.guidance.strip() else ''
        avoid = self._list_fmt(self.avoid)

        # If nothing is provided but a name, use just that name by itself.
        if not details and not guidance and not avoid:
            return self.name

        parts = [f'Context name: <name>{self.name}</name>']
        if details:
            parts.append(f'Details: <details>{details}</details>')
        if guidance:
            parts.append(f'General guidance: <guidance>{guidance}</guidance>')
        if avoid:
            parts.append(
                'Terms and concepts to avoid (do not mention these terms or '
                f'concepts in your response at all): <avoid>{avoid}</avoid>'
            )
        return '\n\n'.join(parts)

    def desc_html(self) -> str:
        """ Convert this context into a description for users in HTML.

        Only the details are shown to students; guidance and the avoid set are
        for the LLM only.
        """
        if not self.details.strip():
            return ''
        template = current_app.jinja_env.from_string('{{ details | markdown }}')
        return template.render(details=self.details)
