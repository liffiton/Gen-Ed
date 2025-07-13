# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Applications can register additional forms/UI for including in the class
# configuration page.  Each must be provided as a template for its portion of
# the configuration screen's UI and a function that provides all data needed to
# render that template (assuming there is an active request when it is called)
#
# The application is responsible for registering a blueprint with request
# handlers for any routes needed by that UI.

@dataclass(frozen=True)
class ExtraSectionProvider:
    """Stores information needed to provide an extra section in the class config UI."""
    # The name of the Jinja template file for this section.
    template_name: str

    # A function that returns a dictionary of context variables for the template.
    context_provider: Callable[[], dict[str, Any]]

    # Either None or a string containing a single experiment name; this section
    # will not be shown unless that experiment is active in the current class.
    requires_experiment: str | None = None


# This module global stores registered providers for extra config sections.
_extra_section_providers: list[ExtraSectionProvider] = []

def register_extra_section(
    template_name: str,
    context_provider: Callable[[], dict[str, Any]],
    *,
    requires_experiment: str | None = None,
) -> None:
    """ Register a new section for the class configuration UI. """
    section = ExtraSectionProvider(
        template_name,
        context_provider,
        requires_experiment,
    )
    _extra_section_providers.append(section)


def get_extra_sections() -> list[ExtraSectionProvider]:
    return _extra_section_providers.copy()
