# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Blueprint

from gened.base import GenEdComponent

from .config_table import contexts_config_table
from .data import (
    ContextsDeletionHandler,
    get_available_contexts,
    get_context_by_name,
    get_context_string_by_id,
    record_context_string,
)
from .model import ContextConfig

# This component does not have any routes, but we use a Blueprint to register
# its templates folder for the template fragments it provides.
bp = Blueprint('contexts', __name__, template_folder='templates')

gened_component = GenEdComponent(
    package=__package__,
    blueprint=bp,
    config_table=contexts_config_table,
    deletion_handler=ContextsDeletionHandler,
    schema_file="schema.sql",
    migrations_dir="migrations",
)

__all__ = [
    "ContextConfig",
    "gened_component",
    "get_available_contexts",
    "get_context_by_name",
    "get_context_string_by_id",
    "record_context_string",
]
