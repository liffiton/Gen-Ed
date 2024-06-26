# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import dataclass, field

from flask import current_app
from gened.contexts import ContextConfig, register_context
from typing_extensions import Self
from werkzeug.datastructures import ImmutableMultiDict


def _default_langs() -> list[str]:
    langs: list[str] = current_app.config['DEFAULT_LANGUAGES']  # declaration keeps mypy happy
    return langs


@dataclass(frozen=True)
class CodeHelpContext(ContextConfig):
    template: str = "codehelp_context_form.html"
    name: str = ''
    languages: list[str] = field(default_factory=_default_langs)
    default_lang: str | None = None
    avoid: str = ''

    @classmethod
    def from_request_form(cls, name: str, form: ImmutableMultiDict[str, str]) -> Self:
        return cls(
            name=name,
            languages=form.getlist('languages[]'),
            default_lang=form.get('default_lang', None),
            avoid=form['avoid'],
        )

    def to_str(self) -> str:
        """ Convert this context into a string to be used in an LLM prompt. """
        # TODO: this is a draft -- add more
        return f"<languages>{self.languages}</languages><avoid>{self.avoid}</avoid>"


def register_with_gened() -> None:
    register_context(CodeHelpContext)
