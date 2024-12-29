# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import csv
import datetime as dt
import io
from sqlite3 import Row

from flask import flash, make_response, render_template
from werkzeug.wrappers.response import Response


def csv_response(file_name: str, kind: str, table: list[Row]) -> str | Response:
    if not table:
        flash("There are no rows to export yet.", "warning")
        return render_template("error.html")

    stringio = io.StringIO()
    writer = csv.writer(stringio)
    writer.writerow(table[0].keys())  # column headers
    writer.writerows(table)

    output = make_response(stringio.getvalue())
    file_name = file_name.replace(" ","-")
    timestamp = dt.datetime.now().strftime("%Y%m%d")
    output.headers["Content-Disposition"] = f"attachment; filename={timestamp}_{file_name}_{kind}.csv"
    output.headers["Content-type"] = "text/csv"

    return output
