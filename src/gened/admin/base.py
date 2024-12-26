# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import platform
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import ParamSpec, TypeVar

from flask import (
    Blueprint,
    current_app,
    send_file,
)
from werkzeug.wrappers.response import Response

from gened.auth import admin_required
from gened.db import backup_db

from .consumers import bp as bp_consumers

bp = Blueprint('admin', __name__, template_folder='templates')

bp.register_blueprint(bp_consumers, url_prefix='/consumer')

@bp.before_request
@admin_required
def before_request() -> None:
    """ Apply decorator to protect all admin blueprint endpoints. """


@dataclass(frozen=True)
class AdminLink:
    """Represents a link in the admin interface.
    Attributes:
        endpoint: The Flask endpoint name
        display: The text to show in the navigation UI
    """
    endpoint: str
    display: str

# For decorator type hints
P = ParamSpec('P')
R = TypeVar('R')

@dataclass
class AdminLinks:
    """Container for registering admin navigation links."""
    regular: list[AdminLink] = field(default_factory=list)
    right: list[AdminLink] = field(default_factory=list)

    def register(self, display_name: str, *, right: bool = False) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Decorator to register an admin page link.
        Args:
            display_name: Text to show in the admin interface navigation
            right: If True, display this link on the right side of the nav bar
        """
        def decorator(route_func: Callable[P, R]) -> Callable[P, R]:
            handler_name = f"admin.{route_func.__name__}"
            link = AdminLink(handler_name, display_name)
            if right:
                self.right.append(link)
            else:
                self.regular.append(link)
            return route_func
        return decorator

    def get_template_context(self) -> dict[str, list[AdminLink]]:
        return {
            'admin_links': self.regular,
            'admin_links_right': self.right,
        }

# Module-level instance
_admin_links = AdminLinks()
register_admin_link = _admin_links.register  # name for the decorator to be imported/used in other modules

@bp.context_processor
def inject_admin_links() -> dict[str, list[AdminLink]]:
    return _admin_links.get_template_context()


@dataclass(frozen=True)
class DBDownloadStatus:
    """Status of database download encryption."""
    encrypted: bool
    reason: str | None = None  # reason provided if not encrypted

@bp.context_processor
def inject_db_download_status() -> dict[str, DBDownloadStatus]:
    if platform.system() == "Windows":
        status = DBDownloadStatus(False, "Encryption unavailable on Windows servers.")
    elif not current_app.config.get('AGE_PUBLIC_KEY'):
        status = DBDownloadStatus(False, "No encryption key configured, AGE_PUBLIC_KEY not set.")
    else:
        status = DBDownloadStatus(True)
    return {'db_download_status': status}


@register_admin_link("Download DB", right=True)
@bp.route("/get_db")
def get_db_file() -> Response:
    db_name = current_app.config['DATABASE_NAME']
    db_basename = Path(db_name).stem
    dl_name = f"{db_basename}_{date.today().strftime('%Y%m%d')}.db"
    if current_app.config.get('AGE_PUBLIC_KEY'):
        dl_name += '.age'

    if platform.system() == "Windows":
        # Slightly unsafe way to do it, because the file may be written while
        # send_file is sending it.  Temp file issues make it hard to do
        # otherwise on Windows, though, and no one should run a production
        # server for this on Windows, anyway.
        if current_app.config.get('AGE_PUBLIC_KEY'):
            current_app.logger.warning("Database download on Windows does not support encryption")
        return send_file(current_app.config['DATABASE'],
                         mimetype='application/vnd.sqlite3',
                         as_attachment=True, download_name=dl_name)
    else:
        db_backup_file = NamedTemporaryFile()
        backup_db(Path(db_backup_file.name))
        return send_file(db_backup_file,
                         mimetype='application/vnd.sqlite3',
                         as_attachment=True, download_name=dl_name)
