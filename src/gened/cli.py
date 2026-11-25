# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import sys

import click
from flask.cli import FlaskGroup

# These commands manage the database and do not serve requests, so they may
# run without the application secrets and optional integrations configured.
_COMMANDS_WITHOUT_SERVER_CONFIG = frozenset({
    'initdb',
    'migrate',
    'newuser',
    'setpassword',
})


def _flask_context() -> click.Context | None:
    """Find the active context only if the root command is Flask's CLI."""
    ctx = click.get_current_context(silent=True)
    if ctx is not None and isinstance(ctx.find_root().command, FlaskGroup):
        return ctx
    return None


def _command_from_argv() -> str | None:
    """Get Flask's top-level command when the app factory runs during lookup.

    Flask loads the app before it creates the command's Click context, so at
    that point the active context is only the root group. Skip global options
    and their values to find the command token.
    """
    args = iter(sys.argv[1:])
    for arg in args:
        if arg in ('-A', '--app', '-e', '--env-file'):
            next(args, None)
        elif arg in ('-h', '--help'):
            return None
        elif arg == '--':
            return next(args, None)
        elif not arg.startswith('-'):
            return arg
    return None


def _command_name(ctx: click.Context) -> str | None:
    if ctx.parent is None:
        # Flask loads the app while looking up app-defined commands, before
        # Click has created the subcommand context.
        return _command_from_argv()

    # For built-in commands like `flask run`, Flask loads the app in the
    # command callback and Click already knows the command name.
    while ctx.parent.parent is not None:
        ctx = ctx.parent
    return ctx.info_name


def is_command(name: str) -> bool:
    """Return True if Flask's CLI is loading the app for the named command."""
    ctx = _flask_context()
    return ctx is not None and _command_name(ctx) == name


def requires_server_config() -> bool:
    """Exempt only Flask's management commands and top-level help.

    Flask loads the app for top-level help to list app-defined commands. An
    unrelated Click context is not enough to opt out of server validation.
    """
    ctx = _flask_context()
    if ctx is None:
        return True
    command = _command_name(ctx)
    return command is not None and command not in _COMMANDS_WITHOUT_SERVER_CONFIG
