# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Blueprint

from gened.components import GenEdComponent

from .config_table import contexts_config_table
from .data import ContextsDeletionHandler
from .model import ContextConfig

# This component does not have any routes, but we use a Blueprint to register
# its templates folder for the template fragments it provides.
bp = Blueprint('contexts', __name__, template_folder='templates')

gened_component = GenEdComponent(
    package=__package__,
    name="contexts",
    display_name="Learning Contexts",
    description="Instructors can define learning contexts that provide additional information to LLMs along with individual queries or chats.",
    blueprint=bp,
    config_table=contexts_config_table,
    deletion_handler=ContextsDeletionHandler,
    migrations_dir="migrations",
    always_enabled=True,  # always on, not toggleable by instructors
)

__all__ = [
    "ContextConfig",
    "contexts_config_table",
    "gened_component",
]
