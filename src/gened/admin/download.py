# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import platform
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import (
    Blueprint,
    current_app,
    send_file,
)
from markupsafe import Markup
from werkzeug.wrappers.response import Response

from gened.db import backup_db

from .component_registry import register_blueprint, register_navbar_item


@dataclass(frozen=True)
class EncryptionStatus:
    """Status of database download encryption."""
    encrypted: bool
    reason: str | None = None  # reason provided if not encrypted

def get_encryption_status() -> EncryptionStatus:
    if platform.system() == "Windows":
        return EncryptionStatus(False, "Encryption unavailable on Windows servers.")
    elif not current_app.config.get('AGE_PUBLIC_KEY'):
        return EncryptionStatus(False, "No encryption key configured, AGE_PUBLIC_KEY not set.")
    else:
        return EncryptionStatus(True)


def render_link() -> Markup:
    status = get_encryption_status()
    if status.encrypted:
        return Markup("""
            Download DB
            <span class="ml-2 icon-text px-1 has-text-success-dark" title="Download will be encrypted">
              <span class="icon">
                <svg aria-hidden="true" style="height: 80%;">
                  <use href="#svg_admin_check" />
                </svg>
              </span>
            </span>
        """)
    else:
        return Markup(f"""
            Download DB
            <span class="ml-2 icon-text px-1 tag is-warning" title="{status.reason}">
              <span class="icon">
                <svg aria-hidden="true" style="height: 80%;">
                  <use href="#svg_admin_alert" />
                </svg>
              </span>
              <span class="text" style="margin-left: -0.5em;">&nbsp;&nbsp;unencrypted</span>
            </span>
        """)


bp = Blueprint('admin_download', __name__, url_prefix='/get_db', template_folder='templates')

register_blueprint(bp)
register_navbar_item("admin_download.get_db_file", render_link, right=True)


@bp.route("/")
def get_db_file() -> Response:
    db_name = current_app.config['DATABASE_NAME']
    db_basename = Path(db_name).stem
    dl_name = f"{db_basename}_{date.today().strftime('%Y%m%d')}.db"

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
        if current_app.config.get('AGE_PUBLIC_KEY'):
            dl_name += '.age'
        return send_file(db_backup_file,
                        mimetype='application/vnd.sqlite3',
                        as_attachment=True, download_name=dl_name)

