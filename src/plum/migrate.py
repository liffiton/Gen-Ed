import itertools
from datetime import datetime
from importlib import resources
from pathlib import Path

import click
from flask import current_app

from .db import get_db, backup_db, on_init_db


def _do_migration(name, script):
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


def _apply_migrations(migrations):
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

    click.echo(f"Database backup saved in [33m{backup_dest}[m.")

    # Run the scripts
    for migration in migrations:
        name = migration['name']
        script = migration['contents']
        click.echo(f"[35;1m═╦═Applying {name}═══[m")
        indented = '\n'.join(f" ║ {x}" for x in script.split('\n'))
        click.echo(indented)
        success, err = _do_migration(name, script)
        if success:
            click.echo("[32;1m═╩═Migration succeeded═══[m")
        else:
            click.echo(f"[31;1m═╩═Migration failed═══[m  [31m{err}[m")
            return  # End here


def _migration_info(resource):
    """Get info on a migration, provided as an importlib.resources resource."""
    db = get_db()
    with resources.as_file(resource) as path, open(path) as f:
        name = path.name
        info = {
            'name': name,
            'path': path,
            'contents': f.read(),
            'mtime': path.stat().st_mtime,
            'applied_on': None,
            'skipped': None,
            'succeeded': None,
        }
        row = db.execute("SELECT * FROM migrations WHERE filename=?", [name]).fetchone()
        if row:
            info = info | {
                'applied_on': row['applied_on'],
                'skipped': row['skipped'],
                'succeeded': row['succeeded'],
            }

        return info


def _get_migrations():
    # Pull shared Plum migrations and app-specific migrations
    plum_migrations = resources.files('plum').joinpath("migrations")
    app_migrations = resources.files(current_app.name).joinpath("migrations")
    migration_files = itertools.chain(
        *(x.iterdir() for x in (plum_migrations, app_migrations) if x.is_dir())
    )

    # Collect info and sort by name and modified time (to apply migrations in order)
    migrations = [
        _migration_info(res)
        for res in migration_files
        if not res.name.startswith('.') and res.name.endswith('.sql')
    ]
    migrations.sort(key=lambda x: (x['name'], x['mtime']))

    return migrations


@on_init_db
def _mark_all_as_applied():
    db = get_db()
    for migration in _get_migrations():
        db.execute("INSERT OR IGNORE INTO migrations (filename) VALUES (?)", [migration['name']])
        db.execute("UPDATE migrations SET succeeded=True WHERE filename=?", [migration['name']])
    db.commit()


@click.command('migrate')
def migrate_command():
    """???"""
    migrations = _get_migrations()

    click.echo("  # status  script file")
    click.echo("--- ------  --------------------")
    status_new = "☐"
    status_success = "[32m☑[m"
    status_skipped = "[33m☑[m"
    status_failed = "[31m☒[m"
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
    choice = input(f"[1-{len(migrations)}] Select individual migration   [A]pply all new or failed migrations  [M]ark all as successfully applied  [Q]uit   Choice? ")
    click.echo()

    if choice.isnumeric() and 1 <= int(choice) <= len(migrations):
        click.echo("Individual selection not yet implemented.")
    elif choice.lower() == 'm':
        sure = input("Are you sure?  This should pretty much never be used... [yN] ")
        if sure.lower() == 'y':
            _mark_all_as_applied()
            click.echo("Done.")
    elif choice.lower() == 'a':
        if all(m['succeeded'] for m in migrations):
            click.echo("No new or failed migrations to apply.")
        else:
            _apply_migrations(m for m in migrations if not m['succeeded'] and not m['skipped'])


def init_app(app):
    app.cli.add_command(migrate_command)
