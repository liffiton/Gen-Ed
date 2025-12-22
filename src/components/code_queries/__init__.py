# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.components import GenEdComponent

from .data import QueriesDeletionHandler, gen_query_charts, queries_data_source
from .helper import bp

gened_component = GenEdComponent(
    package=__package__,
    name="code_queries",
    display_name="Code Queries",
    description="Students can ask the LLM for help with CS/programming issues like planning, debugging, and understanding.  The LLM's response includes guardrails to avoid providing solution code.",
    blueprint=bp,
    navbar_item_template="queries_nav_item.html",
    data_source=queries_data_source,
    admin_chart=gen_query_charts,
    deletion_handler=QueriesDeletionHandler,
    schema_file="schema.sql",
    migrations_dir="migrations",
)

__all__ = [
    "gened_component",
]
