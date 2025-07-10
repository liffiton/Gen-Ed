# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Applications can register additional forms/UI for including in the class
# configuration page.  Each must be provided as a template for its portion of
# the configuration screen's UI and a function that provides all data needed to
# render that template (assuming there is an active request when it is called)
#
# The application is responsible for registering a blueprint with request
# handlers for any routes needed by that UI.

@dataclass
class ExtraSectionProvider:
    """Stores information needed to provide an extra section in the class config UI."""
    template_name: str
    context_provider: Callable[[], dict[str, Any]]
    extra_args: dict[str, Any]

# This module global stores registered providers for extra config sections.
_extra_section_providers: list[ExtraSectionProvider] = []

def register_extra_section(template_name: str, context_provider: Callable[[], dict[str, Any]], extra_args: dict[str, Any] | None = None) -> None:
    """ Register a new section for the class configuration UI.
        Args:
            template_name: The name of the Jinja template file for this section.
            context_provider: A function that returns a dictionary of context variables for the template.
            extra_args: A dictionary of additional name/value pairs to pass to the template.
    """
    section = ExtraSectionProvider(template_name, context_provider, extra_args or dict())
    _extra_section_providers.append(section)


def get_extra_sections_data() -> list[dict[str, Any]]:
    return [
        {
            'template_name': provider.template_name,
            'context': provider.context_provider() | provider.extra_args,
        }
        for provider in _extra_section_providers
    ]

