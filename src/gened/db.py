# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import errno
import secrets
import sqlite3
import string
from collections.abc import Callable
from datetime import date, datetime
from getpass import getpass
from importlib import resources
from pathlib import Path

import click
from flask import current_app, g
from flask.app import Flask
from werkzeug.security import generate_password_hash

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


def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    assert isinstance(g.db, sqlite3.Connection)
    return g.db


def backup_db(target: str | Path) -> None:
    """ Safely make a backup of the database to the given path.
    target: str or any path-like object.  Must not exist yet or be empty.
    """
    target = Path(target)
    if target.exists() and target.stat().st_size > 0:
        raise FileExistsError(errno.EEXIST, "File already exists or is not empty", target)

    db = get_db()
    tmp_db = sqlite3.connect(target)
    with tmp_db:
        db.backup(tmp_db)
    tmp_db.close()


def close_db(e: BaseException | None = None) -> None:  # noqa: ARG001 - unused function argument
    db = g.pop('db', None)

    if db is not None:
        db.close()


# Functions to be called at the end of init_db().
_on_init_db_callbacks: list[Callable[[], None]] = []


def on_init_db(func: Callable[[], None]) -> Callable[[], None]:
    """Decorator to mark a function as a callback to be called at the end of init_db()."""
    _on_init_db_callbacks.append(func)
    return func


def init_db() -> None:
    db = get_db()

    # Common schema in the gened package
    # importlib.resources: https://stackoverflow.com/a/73497763/
    # requires Python 3.9+
    common_schema_res = resources.files('gened').joinpath("schema_common.sql")
    with resources.as_file(common_schema_res) as file_path, file_path.open(encoding="utf-8") as f:
        db.executescript(f.read())

    # App-specific schema in the app's package
    with current_app.open_resource('schema.sql', 'rb') as f:
        db.executescript(f.read().decode("utf-8"))  # type: ignore [attr-defined]

    # Mark all existing migrations as applied (since this is a fresh DB)
    for func in _on_init_db_callbacks:
        func()

    db.commit()


@click.command('initdb')
def init_db_command() -> None:
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


@click.command('newuser')
@click.argument('username')
@click.option('--admin', is_flag=True, help="Make the new user an admin.")
@click.option('--tester', is_flag=True, help="Make the new user a tester.")
def newuser_command(username: str, admin: bool = False, tester: bool = False) -> None:
    """Add a new user to the database.  Generates and prints a random password."""
    db = get_db()

    # Check for pre-existing username
    existing = db.execute("SELECT username FROM auth_local WHERE username=?", [username]).fetchone()
    if existing:
        click.secho(f"Error: username {username} already exists.", fg='red')
        return

    new_password = ''.join(secrets.choice(string.ascii_letters) for _ in range(6))
    cur = db.execute("INSERT INTO users(auth_provider, auth_name, is_admin, is_tester, query_tokens) VALUES(?, ?, ?, ?, 0)",
                     [AUTH_PROVIDER_LOCAL, username, admin, tester])
    db.execute("INSERT INTO auth_local(user_id, username, password) VALUES(?, ?, ?)",
               [cur.lastrowid, username, generate_password_hash(new_password)])
    db.commit()

    click.secho("User added to the database:", fg='green')
    click.echo(f"  username: {username}\n  password: {new_password}")


@click.command('setpassword')
@click.argument('username')
def setpassword_command(username: str) -> None:
    """Set the password for an existing user.  Requests the password interactively."""
    db = get_db()

    # Check for pre-existing username
    existing = db.execute("SELECT username FROM auth_local WHERE username=?", [username]).fetchone()
    if not existing:
        click.secho(f"Error: username {username} does not exist as a local user.", fg='red')
        return

    password1 = getpass("New password: ")
    if len(password1) < 3:
        click.secho("Error: password must be at least 3 characters long.", fg='red')
        return

    password2 = getpass("      Repeat: ")
    if password1 != password2:
        click.secho("Error: passwords do not match.", fg='red')
        return

    db.execute("UPDATE auth_local SET password=? WHERE username=?", [generate_password_hash(password1), username])
    db.commit()

    click.secho(f"Password updated for user {username}.", fg='green')


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(newuser_command)
    app.cli.add_command(setpassword_command)
