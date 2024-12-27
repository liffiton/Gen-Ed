# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Blueprint

from gened.auth import admin_required

from . import consumers, download, main, navbar
from .main import ChartData

bp = Blueprint('admin', __name__, template_folder='templates')

@bp.before_request
@admin_required
def before_request() -> None:
    """ Apply decorator to protect all admin blueprint endpoints. """

download.init_bp(bp)
navbar.init_bp(bp)

bp.register_blueprint(main.bp, url_prefix='/')
bp.register_blueprint(consumers.bp, url_prefix='/consumer')


register_admin_chart = main.register_admin_chart
register_admin_link = navbar.register_admin_link

__all__ = [
    'ChartData',
    'bp',
    'register_admin_chart',
    'register_admin_link',
]
