# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.components import GenEdComponent

from .data import DeletionHandler, queries_data_source
from .helper import bp

gened_component = GenEdComponent(
    package=__package__,
    name="language_help",
    display_name="Writing Check",
    description="Provide some writing in just about any language, and an LLM will point out errors in the use of the language, showing the location and type of each error but not providing a correction.",
    blueprint=bp,
    icon="svg_pencil",
    main_endpoint="language_helper.help_form",
    data_source=queries_data_source,
    deletion_handler=DeletionHandler,
    schema_file="schema.sql",
    migrations_dir="migrations",
)

__all__ = [
    "gened_component",
]
