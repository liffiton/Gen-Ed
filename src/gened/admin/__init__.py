# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Blueprint

from gened.access import Access, control_blueprint_access

from . import (  # noqa: F401 -- Importing these modules registers routes
    consumers,
    download,
    main,
    pruning,
)
from .component_registry import (
    register_admin_blueprint,
    register_blueprint,
    register_navbar_item,
)

bp = Blueprint('admin', __name__, template_folder='templates')

# Require admin account for all routes in the blueprint
control_blueprint_access(bp, Access.ADMIN)

# Register the admin blueprint
register_admin_blueprint(bp)


# Public exports for other modules
__all__ = [
    'bp',
    'register_blueprint',
    'register_navbar_item',
]
