# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

import click
from flask import current_app
from flask.app import Flask

from .component_registry import get_registered_components
from .db import get_db
from .db_admin import backup_db, drop_views, on_init_db, rebuild_views


@dataclass(frozen=True)
class Migration:
    package: str
    filename: str
    contents: str
    applied_on: datetime | None
    skipped: bool | None
    succeeded: bool | None


class DuplicateMigrationError(Exception):
    def __init__(self, files: Iterable[str]):
        super().__init__(f"Migration filenames must be unique.  Duplicates found: {', '.join(files)}")


def _do_migration(migration: Migration) -> tuple[bool, str]:
    """
    Run a migration script against the instance database, recording and returning success or failure.

    Parameters:
      migration - Migration: The script and its metadata

    Returns a tuple:
      [0] - bool: True on success, False otherwise.
      [1] - str: on failure, contains the exception that occurred as a string.
    """
    name = migration.filename
    script = migration.contents

    db = get_db()
    db.execute("INSERT OR IGNORE INTO migrations (filename) VALUES (?)", [name])
    db.commit()

    try:
        # Drop all views before migration to avoid errors
        drop_views()

        db.executescript(script)
        db.commit()

        db.execute("UPDATE migrations SET applied_on=CURRENT_TIMESTAMP, succeeded=True WHERE filename=?", [name])
        db.commit()

    except sqlite3.Error as e:
        db.rollback()
        db.execute("UPDATE migrations SET applied_on=CURRENT_TIMESTAMP, succeeded=False WHERE filename=?", [name])
        db.commit()
        return False, str(e)

    try:
        # Rebuild views post-migration
        rebuild_views()
    except sqlite3.Error as e:
        current_app.logger.warning(f"DB error while rebuilding views after migration {name}.  Check this carefully.  It may be okay (handled by a later migration) or it may be a problem.\nError: {e}")

    return True, ''


def _apply_migrations(migrations: list[Migration], *, verbose: bool = False) -> None:
    """
    Apply a list of migrations in the order provided.

    migrations: a list of Migration objects.
    """
    if not migrations:
        current_app.logger.info("_apply_migrations() called with an empty list of migrations.  No migrations applied.")
        return

    # Make a backup of the old database
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")   # noqa: DTZ005 - a timezone-unaware object is fine here
    backup_dir = Path(current_app.instance_path) / "backups"
    backup_dir.mkdir(mode=0o770, exist_ok=True)
    backup_dest = backup_dir / f"{current_app.config['DATABASE_NAME']}.{timestamp}.bak"
    if current_app.config.get('AGE_PUBLIC_KEY'):
        backup_dest = backup_dest.with_suffix('.age')

    backup_db(backup_dest)
    click.echo(f"Database backup saved in {click.style(str(backup_dest), fg='yellow')}.")

    # Run the scripts
    for migration in migrations:
        click.secho(f"═╦═Applying {migration.filename}═══", fg="magenta", bold=True)
        if verbose:
            script = migration.contents
            indented = '\n'.join(f" ║ {x}" for x in script.split('\n'))
            click.echo(indented)

        success, err = _do_migration(migration)
        if success:
            click.secho("═╩═Migration succeeded═══", fg="green", bold=True)
        else:
            click.secho("═╩═Migration failed═══  ", fg="red", bold=True, nl=False)
            click.secho(err, fg="red")
            raise click.Abort  # end here, and ensure exit code is non-zero


def _migration_info(package: str, resource: Traversable) -> Migration:
    """Get info on a migration, provided as an importlib.resources resource."""
    db = get_db()
    with resources.as_file(resource) as path, path.open(encoding="utf-8") as f:
        filename = path.name
        contents = f.read()
        applied_on = None
        skipped = None
        succeeded = None

        row = db.execute("SELECT * FROM migrations WHERE filename=?", [filename]).fetchone()

        if row:
            applied_on = row['applied_on']
            skipped = bool(row['skipped'])
            succeeded = bool(row['succeeded'])

        return Migration(
            package=package,
            filename=filename,
            contents=contents,
            applied_on=applied_on,
            skipped=skipped,
            succeeded=succeeded,
        )


def _get_migrations() -> list[Migration]:
    # Common migrations in the gened package + app migrations + registered component migrations
    migration_dirs = [
        ('gened', 'migrations'),
        (current_app.name, 'migrations'),
    ]
    # Add component migrations
    migration_dirs.extend(
        (c.package, c.migrations_dir) for c in get_registered_components() if c.migrations_dir
    )

    # Collect info
    migrations: list[Migration] = []
    for package_name, migrations_dir in migration_dirs:
        path = resources.files(package_name).joinpath(migrations_dir)
        if path.is_dir():
            migrations.extend(
                _migration_info(package_name, res)
                for res in path.iterdir()
                if res.name.endswith('.sql') and not res.name.startswith('.')
            )

    # Sort by filename (to apply migrations in order)
    migrations.sort(key=lambda x: x.filename)

    # Check for duplicate filenames (relies on sorting by filename above)
    duplicates = {
        migrations[i].filename for i in range(len(migrations) - 1)
        if migrations[i].filename == migrations[i+1].filename
    }
    if duplicates:
        raise DuplicateMigrationError(duplicates)

    return migrations


@on_init_db
def _mark_all_as_applied() -> None:
    db = get_db()
    for migration in _get_migrations():
        db.execute("INSERT OR IGNORE INTO migrations (filename) VALUES (?)", [migration.filename])
        db.execute("UPDATE migrations SET succeeded=True WHERE filename=?", [migration.filename])
    db.commit()


@click.command('migrate')
@click.option('--auto', is_flag=True, help='Automatically run all pending migrations.')
def migrate_command(*, auto: bool) -> None:
    """ Apply (if --auto) or manage migration scripts. """
    migrations = _get_migrations()
    pending = [m for m in migrations if not m.succeeded and not m.skipped]

    if auto:
        _apply_migrations(pending, verbose=False)
    else:
        _migrate_ui(migrations, pending)


def _migrate_ui(migrations: list[Migration], pending: list[Migration]) -> None:
    """ Launch a simple text interface for managing migration scripts. """
    click.echo("  # status  script file")
    click.echo("--- ------  --------------------")
    status_new = "☐"
    status_success = click.style("☑", fg="green")
    status_skipped = click.style("☑", fg="yellow")
    status_failed = click.style("☒", fg="red")
    for i, migration in enumerate(migrations):
        status = status_new
        if migration.succeeded:
            status = status_success
        if migration.skipped:
            status = status_skipped
        if migration.succeeded is False:
            status = status_failed
        click.echo(f"{i+1:3}   {status}     {migration.filename}")

    click.echo()
    click.echo(f"Key:  {status_new}  = new  {status_success}  = applied successfully  {status_skipped}  = skipped  {status_failed}  = failed to apply")
    click.echo()

    click.echo("[A]pply all new or failed migrations  [M]ark all as successfully applied  [Q]uit")
    choice = click.prompt("Choice", type=click.Choice(['a', 'm', 'q'], case_sensitive=False), default='q', show_choices=True)
    click.echo()

    if choice.lower() == 'm':
        if click.confirm("Are you sure? This should pretty much never be used...", default=False):
            _mark_all_as_applied()
            click.echo("Done.")
    elif choice.lower() == 'a':
        if not pending:
            click.echo("No pending migrations to apply.")
        else:
            _apply_migrations(pending, verbose=True)


def init_app(app: Flask) -> None:
    app.cli.add_command(migrate_command)
