# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import sqlite3
import time
from datetime import date, datetime

from flask import current_app, g
from flask.app import Flask

AUTH_PROVIDER_LOCAL = 1


# https://docs.python.org/3/library/sqlite3.html#sqlite3-adapter-converter-recipes
# Register adapters going from date/datetime to text (going into SQLite).
def adapt_date_iso(val: date) -> str:
    """Adapt datetime.date to ISO 8601 date."""
    return val.isoformat()

def adapt_datetime_iso(val: datetime) -> str:
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    return val.isoformat()

# And converters for coming from SQLite and converting back to date/datetime objects.
def convert_date(val: bytes) -> date:
    """Convert ISO 8601 date to datetime.date object."""
    return date.fromisoformat(val.decode())

def convert_datetime(val: bytes) -> datetime:
    """Convert ISO 8601 datetime to datetime.datetime object."""
    return datetime.fromisoformat(val.decode())

sqlite3.register_adapter(date, adapt_date_iso)
sqlite3.register_adapter(datetime, adapt_datetime_iso)
sqlite3.register_converter("date", convert_date)
sqlite3.register_converter("datetime", convert_datetime)


class TimingConnection(sqlite3.Connection):
    """A Connection subclass that logs query execution times when in debug mode."""
    def execute(self, sql: str, *args, **kwargs) -> sqlite3.Cursor:  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        try:
            result = super().execute(sql, *args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            current_app.logger.debug("Query took %.3fs: %s", elapsed, sql)
        return result

    def executescript(self, *args, **kwargs) -> sqlite3.Cursor:  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        try:
            result = super().executescript(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            current_app.logger.debug("Script execution took %.3fs", elapsed)
        return result


def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        connection_class = TimingConnection if current_app.debug else sqlite3.Connection
        #connection_class = sqlite3.Connection
        db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES,
            factory=connection_class
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode = WAL")    # for performance (and Litestream will enable anyway)
        db.execute("PRAGMA synchronous = NORMAL")  # recommended setting for WAL mode
        db.execute("PRAGMA busy_timeout = 5000")   # to avoid immediate errors on some blocked writes
        db.execute("PRAGMA foreign_keys = ON")
        g.db = db

    assert isinstance(g.db, sqlite3.Connection)
    return g.db


def close_db(_e: BaseException | None = None) -> None:
    db = g.pop('db', None)

    if db is not None:
        db.execute("PRAGMA optimize")  # https://sqlite.org/pragma.html#pragma_optimize
        db.close()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
