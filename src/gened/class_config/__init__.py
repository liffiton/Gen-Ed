# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Blueprint, Flask

from gened.auth import instructor_required

from .base import bp as base_bp
from .config_table import (
    ConfigItem,
    ConfigShareLink,
    ConfigTable,
    create_blueprint,
)
from .extra_sections import ExtraSectionProvider, register_extra_section


def build_blueprint(app: Flask) -> Blueprint:
    bp = Blueprint('class_config', __name__, template_folder='templates')

    # Apply instructor_required to protect all class_config blueprint endpoints.
    bp.before_request(instructor_required(lambda: None))

    bp.register_blueprint(base_bp)

    config_table_bp = create_blueprint(app)
    bp.register_blueprint(config_table_bp)

    return bp

__all__ = [
    'ConfigItem',
    'ConfigShareLink',
    'ConfigTable',
    'ExtraSectionProvider',
    'build_blueprint',
    'register_extra_section',
]
