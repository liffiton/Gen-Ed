# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import dataclass, field

from flask import current_app
from gened.class_config import get_class_config as gened_get_config
from gened.class_config import ClassConfig, register_class_config
from typing_extensions import Self
from werkzeug.datastructures import ImmutableMultiDict


def _default_langs() -> list[str]:
    langs: list[str] = current_app.config['DEFAULT_LANGUAGES']  # declaration keeps mypy happy
    return langs


@dataclass(frozen=True)
class CodeHelpClassConfig(ClassConfig):
    template: str = "codehelp_class_config_form.html"
    languages: list[str] = field(default_factory=_default_langs)
    default_lang: str | None = None
    avoid: str = ''

    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, str]) -> Self:
        return cls(
            languages=form.getlist('languages[]'),
            default_lang=form.get('default_lang', None),
            avoid=form['avoid'],
        )


def get_class_config() -> CodeHelpClassConfig:
    return gened_get_config(CodeHelpClassConfig)


def register_with_gened() -> None:
    register_class_config(CodeHelpClassConfig)
