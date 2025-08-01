# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.base import GenEdComponent

from .config_table import contexts_config_table
from .data import (
    get_available_contexts,
    get_context_by_name,
    get_context_string_by_id,
    record_context_string,
)
from .model import ContextConfig

gened_component = GenEdComponent(
    config_table=contexts_config_table,
    # TODO: deletion_handler=ContextsDeletionHandler,
)

__all__ = [
    "ContextConfig",
    "gened_component",
    "get_available_contexts",
    "get_context_by_name",
    "get_context_string_by_id",
    "record_context_string",
]
