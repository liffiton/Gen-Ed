# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import sys

import click

# These commands manage the database and do not serve requests, so they may
# run without the application secrets and optional integrations configured.
_COMMANDS_WITHOUT_SERVER_CONFIG = frozenset({
    'initdb',
    'migrate',
    'newuser',
    'setpassword',
})


def in_flask_cli() -> bool:
    """Return True when Flask's CLI is creating the app (e.g., `flask migrate`).

    False for servers (waitress, `app.run()`) and for tests or other code that
    calls the app factory directly.
    """
    return click.get_current_context(silent=True) is not None


def _command_from_argv() -> str | None:
    """Get Flask's top-level command when the app factory runs during lookup.

    Flask loads the app before it creates the command's Click context, so at
    that point the active context is only the root group. Skip global options
    and their values to find the command token.
    """
    args = iter(sys.argv[1:])
    command: str | None = None
    skip_value = False
    for arg in args:
        if skip_value:
            skip_value = False
            continue
        if arg in ('-A', '--app', '-e', '--env-file'):
            skip_value = True
            continue
        if arg.startswith(('--app=', '--env-file=', '-A', '-e')) and arg not in ('-A', '-e'):
            continue
        if arg.startswith('-'):
            continue
        command = arg
        break
    return command


def _command_name() -> str | None:
    """Return the active top-level Flask command, if one can be determined."""
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return None

    # In the command callback (including tests using CliRunner), the command
    # context is available and is more reliable than process argv.
    command_contexts: list[click.Context] = []
    while ctx is not None:
        if ctx.parent is not None:
            command_contexts.append(ctx)
        ctx = ctx.parent
    if command_contexts:
        return command_contexts[-1].info_name

    # Flask's CLI loads the app while resolving the command, before the
    # command-specific context exists.
    return _command_from_argv()


def is_command(name: str) -> bool:
    """Return True when Flask's CLI is creating the app to run the given command.

    Flask loads the app before creating the command context, so that case is
    read from argv (e.g., `flask [--app app] migrate`).
    """
    return in_flask_cli() and _command_name() == name


def is_serving() -> bool:
    """Return True when this process is meant to serve requests.

    That includes servers started outside the CLI (e.g., waitress, `app.run()`)
    and CLI commands that are not explicitly allowed to run without server
    configuration. Help requests and invocations without a command are exempt:
    Flask loads the app to list its commands, but these invocations do not serve
    requests or run management actions.
    """
    if not in_flask_cli():
        return True
    command = _command_name()
    if command is None or any(arg in ('-h', '--help') for arg in sys.argv[1:]):
        return False
    return command not in _COMMANDS_WITHOUT_SERVER_CONFIG
