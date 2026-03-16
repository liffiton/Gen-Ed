# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.components import GenEdComponent

from .data import QueriesDeletionHandler, gen_query_charts, queries_data_source
from .helper import bp

gened_component = GenEdComponent(
    package=__package__,
    name="code_queries",
    display_name="CS Q&A",
    description="Ask an LLM for help with computer science and programming issues like planning, debugging, and understanding.  The response includes guardrails to avoid providing solution code.",
    blueprint=bp,
    icon="svg_qmark_circle",
    main_endpoint="helper.help_form",
    data_source=queries_data_source,
    admin_chart=gen_query_charts,
    deletion_handler=QueriesDeletionHandler,
    schema_file="schema.sql",
    migrations_dir="migrations",
)

__all__ = [
    "gened_component",
]
