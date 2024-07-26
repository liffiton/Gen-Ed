# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import itertools
import sys
from collections.abc import Iterable
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import TypedDict

if sys.version_info >= (3, 11):
    from importlib.resources.abc import Traversable
else:
    from importlib.abc import Traversable  # - Deprecated in 3.12, removed in 3.14

import click
from flask import current_app
from flask.app import Flask

from .db import backup_db, get_db, on_init_db


class MigrationDict(TypedDict):
    name: str
    contents: str
    mtime: float
    applied_on: str | None
    skipped: bool | None
    succeeded: bool | None


def _do_migration(name: str, script: str) -> tuple[bool, str]:
    """
    Run a migration script against the instance database, recording and returning success or failure.

    Parameters:
      name - str: The filename of the script.
      script - str: The script contents (a string of SQL commands).

    Returns a tuple:
      [0] - bool: True on success, False otherwise.
      [1] - str: on failure, contains the exception that occurred as a string.
    """
    db = get_db()
    db.execute("INSERT OR IGNORE INTO migrations (filename) VALUES (?)", [name])
    db.commit()

    try:
        db.executescript(script)
        db.commit()
        db.execute("UPDATE migrations SET applied_on=CURRENT_TIMESTAMP, succeeded=True WHERE filename=?", [name])
        db.commit()
        return True, ''
    except Exception as e:
        db.rollback()
        db.execute("UPDATE migrations SET applied_on=CURRENT_TIMESTAMP, succeeded=False WHERE filename=?", [name])
        db.commit()
        return False, str(e)


def _apply_migrations(migrations: Iterable[MigrationDict]) -> None:
    """
    Apply a list of migrations in the order provided.

    migrations: an iterable of dictionaries, each defined as in migrate_command() below.
    """
    # Make a backup of the old database
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = Path(current_app.instance_path) / "backups"
    backup_dir.mkdir(mode=0o770, exist_ok=True)
    backup_dest = backup_dir / f"{current_app.config['DATABASE_NAME']}.{timestamp}.bak"

    backup_db(backup_dest)

    click.echo(f"Database backup saved in \x1B[33m{backup_dest}\x1B[m.")

    # Run the scripts
    for migration in migrations:
        name = migration['name']
        script = migration['contents']
        click.echo(f"\x1B[35;1m═╦═Applying {name}═══\x1B[m")
        indented = '\n'.join(f" ║ {x}" for x in script.split('\n'))
        click.echo(indented)
        success, err = _do_migration(name, script)
        if success:
            click.echo("\x1B[32;1m═╩═Migration succeeded═══\x1B[m")
        else:
            click.echo(f"\x1B[31;1m═╩═Migration failed═══\x1B[m  \x1B[31m{err}\x1B[m")
            return  # End here


def _migration_info(resource: Traversable) -> MigrationDict:
    """Get info on a migration, provided as an importlib.resources resource."""
    db = get_db()
    with resources.as_file(resource) as path, path.open(encoding="utf-8") as f:
        name = path.name
        info: MigrationDict = {
            'name': name,
            'contents': f.read(),
            'mtime': path.stat().st_mtime,
            'applied_on': None,
            'skipped': None,
            'succeeded': None,
        }
        row = db.execute("SELECT * FROM migrations WHERE filename=?", [name]).fetchone()
        if row:
            info['applied_on'] = row['applied_on']
            info['skipped'] = row['skipped']
            info['succeeded'] = row['succeeded']

        return info


def _get_migrations() -> list[MigrationDict]:
    # Pull shared Gen-ed migrations and app-specific migrations
    gened_migrations = resources.files('gened').joinpath("migrations")
    app_migrations = resources.files(current_app.name).joinpath("migrations")
    migration_resources = itertools.chain(
        *(x.iterdir() for x in (gened_migrations, app_migrations) if x.is_dir())
    )

    # Collect info and sort by name and modified time (to apply migrations in order)
    migrations = [
        _migration_info(res)
        for res in migration_resources
        if not res.name.startswith('.') and res.name.endswith('.sql')
    ]
    migrations.sort(key=lambda x: (x['name'], x['mtime']))

    return migrations


@on_init_db
def _mark_all_as_applied() -> None:
    db = get_db()
    for migration in _get_migrations():
        db.execute("INSERT OR IGNORE INTO migrations (filename) VALUES (?)", [migration['name']])
        db.execute("UPDATE migrations SET succeeded=True WHERE filename=?", [migration['name']])
    db.commit()


@click.command('migrate')
def migrate_command() -> None:
    """ Launch a simple text interface for managing migration scripts. """
    migrations = _get_migrations()

    click.echo("  # status  script file")
    click.echo("--- ------  --------------------")
    status_new = "☐"
    status_success = "\x1B[32m☑\x1B[m"
    status_skipped = "\x1B[33m☑\x1B[m"
    status_failed = "\x1B[31m☒\x1B[m"
    for i, migration in enumerate(migrations):
        status = status_new
        if migration['succeeded']:
            status = status_success
        if migration['skipped']:
            status = status_skipped
        if migration['succeeded'] is False:
            status = status_failed
        click.echo(f"{i+1:3}   {status}     {migration['name']}")

    click.echo()
    click.echo(f"Key:  {status_new}  = new  {status_success}  = applied successfully  {status_skipped}  = skipped  {status_failed}  = failed to apply")
    click.echo()
    choice = input("[A]pply all new or failed migrations  [M]ark all as successfully applied  [Q]uit   Choice? ")
    click.echo()

    if choice.lower() == 'm':
        sure = input("Are you sure?  This should pretty much never be used... [yN] ")
        if sure.lower() == 'y':
            _mark_all_as_applied()
            click.echo("Done.")
    elif choice.lower() == 'a':
        if all(m['succeeded'] for m in migrations):
            click.echo("No new or failed migrations to apply.")
        else:
            _apply_migrations(m for m in migrations if not m['succeeded'] and not m['skipped'])


def init_app(app: Flask) -> None:
    app.cli.add_command(migrate_command)
