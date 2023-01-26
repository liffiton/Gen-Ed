import os
import sqlite3
import sys

import click
from dotenv import load_dotenv
from flask import current_app, g


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
        init_pw_brad = os.environ["INIT_PW_BRAD"]
        init_pw_andrew = os.environ["INIT_PW_ANDREW"]
    except KeyError:
        print("Error:  INIT_PW_{MARK,BRAD} environment variable not set.", file=sys.stderr)
        sys.exit(1)

    db.execute("INSERT INTO users(username, password, is_admin) VALUES(?, ?, True)", ["mark", init_pw_mark])
    db.execute("INSERT INTO users(username, password) VALUES(?, ?)", ["brad", init_pw_brad])
    db.execute("INSERT INTO users(username, password) VALUES(?, ?)", ["andrew", init_pw_andrew])

    db.commit()


@click.command('initdb')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
