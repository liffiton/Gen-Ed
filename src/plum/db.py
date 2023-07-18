import errno
import importlib
import secrets
import sqlite3
import string
from datetime import datetime
from getpass import getpass
from pathlib import Path

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash


AUTH_PROVIDER_LOCAL = 1


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def backup_db(target):
    """ Safely make a backup of the database to the given path.
    target: str or any path-like object.  Must not exist yet or be empty.
    """
    target = Path(target)
    if target.exists() and target.stat().st_size > 0:
        raise FileExistsError(errno.EEXISTS, "File already exists or is not empty", target)

    db = get_db()
    tmp_db = sqlite3.connect(target)
    with tmp_db:
        db.backup(tmp_db)
    tmp_db.close()


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    # Common schema in the plum package
    # importlib: https://stackoverflow.com/a/73497763/
    # requires Python 3.9+
    common_schema_res = importlib.resources.files('plum').joinpath("schema_common.sql")
    with importlib.resources.as_file(common_schema_res) as filename:
        with open(filename) as f:
            db.executescript(f.read())

    # App-specific schema in the app's package
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

    db.commit()


@click.command('initdb')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


@click.command('migrate')
@click.argument('migration_script', type=click.File('r'))
def migrate_command(migration_script):
    """Run a migration script against the instance database."""
    # Make a backup of the old database
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = Path(current_app.instance_path) / "backups"
    backup_dir.mkdir(mode=0o770, exist_ok=True)
    backup_dest = backup_dir / f"codehelp.db.{timestamp}.bak"

    backup_db(backup_dest)

    click.echo(f"Backup saved in [33m{backup_dest}[m.")

    # Run the script
    db = get_db()
    script = migration_script.read()
    indented = '\n'.join(f"  {x}" for x in script.split('\n'))
    print(f"Script:\n[35m{indented}[m")
    try:
        db.executescript(script)
        db.commit()
        click.echo("[32;1m===Migration complete===[m")
    except Exception as e:
        click.echo(f"[31;1m===Migration failed===[m  [31m{e}[m")


@click.command('newuser')
@click.argument('username')
@click.option('--admin', is_flag=True, help="Make the new user an admin.")
@click.option('--tester', is_flag=True, help="Make the new user a tester.")
def newuser_command(username, admin=False, tester=False):
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
def setpassword_command(username):
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


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(migrate_command)
    app.cli.add_command(newuser_command)
    app.cli.add_command(setpassword_command)
