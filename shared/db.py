from datetime import datetime
import os
import secrets
import shutil
import sqlite3
import string
import sys

import click
from dotenv import load_dotenv
from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

    load_dotenv()
    try:
        init_pw_mark = os.environ["INIT_PW_MARK"]
    except KeyError:
        print("Error:  INIT_PW_MARK environment variable not set.", file=sys.stderr)
        sys.exit(1)

    db.execute("INSERT INTO users(username, password, is_admin) VALUES(?, ?, True)", ["mark", init_pw_mark])
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


@click.command('newuser')
@click.argument('username')
def newuser_command(username):
    """Add a new user to the database (prompts for a password)."""
    db = get_db()
    new_password = ''.join(secrets.choice(string.ascii_letters) for _ in range(6))
    db.execute("INSERT INTO users(username, password) VALUES(?, ?)", [username, generate_password_hash(new_password)])
    db.commit()
    click.echo(f"User added to the database:\nusername: {username}\npassword: {new_password}")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(migrate_command)
    app.cli.add_command(newuser_command)
