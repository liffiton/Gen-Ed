import importlib
import os
import secrets
import shutil
import sqlite3
import string
import sys
from datetime import datetime
from tempfile import NamedTemporaryFile

import click
from dotenv import load_dotenv
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


def get_db_backup():
    """ Return a NamedTemporaryFile object containing a backup of the database. """
    db = get_db()
    tmp_file = NamedTemporaryFile()
    tmp_db = sqlite3.connect(tmp_file.name)
    with tmp_db:
        db.backup(tmp_db)
    tmp_db.close()
    return tmp_file


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

    load_dotenv()
    try:
        init_pw_mark = os.environ["INIT_PW_MARK"]
    except KeyError:
        print("Error:  INIT_PW_MARK environment variable not set.", file=sys.stderr)
        sys.exit(1)

    cur = db.execute("INSERT INTO users(auth_provider, auth_name, is_admin, is_tester, query_tokens) VALUES(?, ?, True, True, 0)", [AUTH_PROVIDER_LOCAL, "mark"])
    db.execute("INSERT INTO auth_local(user_id, username, password) VALUES(?, ?, ?)", [cur.lastrowid, "mark", init_pw_mark])
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
    backup_dir = os.path.join(current_app.instance_path, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_dest = os.path.join(backup_dir, f"codehelp.db.{timestamp}.bak")
    shutil.copy2(current_app.config['DATABASE'], backup_dest)
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


class UserExistsError(Exception):
    pass


def create_user(username):
    """ Add a new user to the database.
    If it already exists, raises UserExistsError.
    Otherwise, returns a generated password for the new user as a string.
    """
    db = get_db()

    # Check for pre-existing username
    existing = db.execute("SELECT username FROM auth_local WHERE username=?", [username]).fetchone()
    if existing:
        raise UserExistsError
    else:
        new_password = ''.join(secrets.choice(string.ascii_letters) for _ in range(6))
        cur = db.execute("INSERT INTO users(auth_provider, auth_name, query_tokens) VALUES(?, ?, 0)", [AUTH_PROVIDER_LOCAL, username])
        db.execute("INSERT INTO auth_local(user_id, username, password) VALUES(?, ?, ?)",
                   [cur.lastrowid, username, generate_password_hash(new_password)])
        db.commit()
        return new_password


@click.command('newuser')
@click.argument('username')
def newuser_command(username):
    """Add a new user to the database (generates a password)."""
    try:
        new_password = create_user(username)
    except UserExistsError:
        click.secho(f"Error: username {username} already exists.", fg='red')
        return

    click.secho("User added to the database:", fg='green')
    click.echo(f"  username: {username}\n  password: {new_password}")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(migrate_command)
    app.cli.add_command(newuser_command)
