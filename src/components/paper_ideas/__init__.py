# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.components import GenEdComponent

from .data import DeletionHandler, queries_data_source
from .helper import bp

gened_component = GenEdComponent(
    package=__package__,
    name="paper_ideas",
    display_name="Paper Ideas",
    description="Help students brainstorm ideas for paper topics based on initial seeds they provide.",
    blueprint=bp,
    navbar_item_template="paper_ideas_nav_item.html",
    data_source=queries_data_source,
    deletion_handler=DeletionHandler,
    schema_file="schema.sql",
    migrations_dir="migrations",
)

__all__ = [
    "gened_component",
]
