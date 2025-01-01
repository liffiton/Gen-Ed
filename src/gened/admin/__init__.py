# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Blueprint

from gened.auth import admin_required

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

@bp.before_request
@admin_required
def before_request() -> None:
    """ Apply decorator to protect all admin blueprint endpoints. """

# Register the admin blueprint
register_admin_blueprint(bp)


# Public exports for other modules
__all__ = [
    'bp',
    'register_blueprint',
    'register_navbar_item',
]
