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
from werkzeug.wrappers.response import Response

from gened.db import backup_db

from .navbar import register_admin_link


@dataclass(frozen=True)
class DBDownloadStatus:
    """Status of database download encryption."""
    encrypted: bool
    reason: str | None = None  # reason provided if not encrypted

def inject_db_download_status() -> dict[str, DBDownloadStatus]:
    if platform.system() == "Windows":
        status = DBDownloadStatus(False, "Encryption unavailable on Windows servers.")
    elif not current_app.config.get('AGE_PUBLIC_KEY'):
        status = DBDownloadStatus(False, "No encryption key configured, AGE_PUBLIC_KEY not set.")
    else:
        status = DBDownloadStatus(True)
    return {'db_download_status': status}


def init_bp(bp: Blueprint) -> None:
    bp.context_processor(inject_db_download_status)

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
