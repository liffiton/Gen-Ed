# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import sys
from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner
from flask import Flask

import codehelp
import gened.base
from gened.base import MissingEnvVarError
from gened.cli import is_serving
from gened.db_admin import init_db

REQUIRED_ENV_VARS = ('SECRET_KEY', 'SYSTEM_API_KEY', 'SYSTEM_MODEL_SHORTNAME')
OPTIONAL_ENV_VARS = (
    'AGE_PUBLIC_KEY',
    'GOOGLE_CLIENT_ID',
    'GOOGLE_CLIENT_SECRET',
    'GITHUB_CLIENT_ID',
    'GITHUB_CLIENT_SECRET',
    'MICROSOFT_CLIENT_ID',
    'MICROSOFT_CLIENT_SECRET',
)


@pytest.fixture
def bare_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every environment variable the application reads.

    Also disables the builder's .env loading so the repository's own .env file
    cannot refill the removed variables.
    """
    monkeypatch.setattr(gened.base, 'load_dotenv', lambda: None)
    for var in REQUIRED_ENV_VARS + OPTIONAL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _create_app_in_cli(command: str, instance_path: Path) -> Flask:
    """Create the app the way `flask <command>` does: inside a click context."""
    created: list[Flask] = []

    @click.group()
    def group() -> None:
        pass

    @group.command(command)
    def _command() -> None:
        created.append(codehelp.create_app(test_config={'TESTING': True}, instance_path=instance_path))

    result = CliRunner().invoke(group, [command])
    assert result.exit_code == 0, result.output
    assert created, 'create_app was not called'
    return created[0]


def test_missing_required_env_var_is_fatal_when_serving(bare_env: None, tmp_path: Path) -> None:  # noqa: ARG001 -- fixture used for its side effects
    """A server process must not start with a missing required variable."""
    with pytest.raises(MissingEnvVarError) as excinfo:
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)
    assert 'SECRET_KEY' in str(excinfo.value)


@pytest.mark.parametrize('varname', REQUIRED_ENV_VARS)
def test_empty_required_env_var_is_fatal_when_serving(
    bare_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    varname: str,
) -> None:
    """An empty required environment variable is treated as missing."""
    for required_var in REQUIRED_ENV_VARS:
        monkeypatch.setenv(required_var, 'test')
    monkeypatch.setenv(varname, '')

    with pytest.raises(MissingEnvVarError, match=varname):
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)


def test_required_config_from_app_config_is_accepted(bare_env: None, tmp_path: Path) -> None:  # noqa: ARG001 -- fixture used for its side effects
    """Required settings supplied through app config (e.g., tests) need no env vars."""
    app = codehelp.create_app(
        test_config={
            'TESTING': True,
            'SECRET_KEY': 'test',
            'SYSTEM_API_KEY': 'test',
            'SYSTEM_MODEL_SHORTNAME': 'test',
        },
        instance_path=tmp_path,
    )
    assert app.config['SECRET_KEY']


def test_missing_required_env_var_is_fatal_for_flask_run(
    bare_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`flask run` serves requests and must still validate the configuration."""
    monkeypatch.setattr(sys, 'argv', ['flask', 'run'])

    @click.group()
    def group() -> None:
        pass

    @group.command('run')
    def _run() -> None:
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)

    result = CliRunner().invoke(group, ['run'])
    assert result.exit_code != 0
    assert isinstance(result.exception, MissingEnvVarError)



def test_cli_commands_defer_missing_config(bare_env: None, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:  # noqa: ARG001 -- fixture used for its side effects
    """`flask migrate` and friends can run with only the database configured."""
    with caplog.at_level(logging.DEBUG):
        app = _create_app_in_cli('migrate', tmp_path)

    assert app.config.get('SECRET_KEY') is None
    # Details are available at DEBUG, but nothing is escalated to a warning.
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
    messages = [record.getMessage() for record in caplog.records]
    assert any('SECRET_KEY' in message for message in messages)
    assert any('AGE_PUBLIC_KEY' in message for message in messages)


def test_other_cli_commands_require_server_config(bare_env: None, tmp_path: Path) -> None:  # noqa: ARG001 -- fixture used for its side effects
    """Commands outside the explicit database-management allowlist validate config."""
    @click.group()
    def group() -> None:
        pass

    @group.command('routes')
    def _routes() -> None:
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)

    result = CliRunner().invoke(group, ['routes'])
    assert isinstance(result.exception, MissingEnvVarError)


def test_cli_help_does_not_require_server_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flask loads the app for command help, but help itself does not serve."""
    detected: list[bool] = []

    @click.group()
    def group() -> None:
        pass

    @group.command('routes')
    def _routes() -> None:
        detected.append(is_serving())

    monkeypatch.setattr(sys, 'argv', ['flask', 'routes', '--help'])
    result = CliRunner().invoke(group, ['routes'])
    assert result.exit_code == 0
    assert detected == [False]


def test_serving_warns_about_missing_optional_features(
    bare_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A server process still gets warnings about disabled optional features."""
    for var in REQUIRED_ENV_VARS:
        monkeypatch.setenv(var, 'test')

    with caplog.at_level(logging.WARNING):
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)

    messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert any('AGE_PUBLIC_KEY' in message for message in messages)
    assert any('GOOGLE' in message for message in messages)
    assert any('MICROSOFT' in message for message in messages)
    assert any('GITHUB' in message for message in messages)


def test_empty_optional_env_vars_are_reported_as_missing(
    bare_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Empty optional environment variables disable the feature and warn."""
    for var in REQUIRED_ENV_VARS:
        monkeypatch.setenv(var, 'test')
    for var in OPTIONAL_ENV_VARS:
        monkeypatch.setenv(var, '')

    with caplog.at_level(logging.WARNING):
        app = codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)

    messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert any('AGE_PUBLIC_KEY' in message for message in messages)
    assert any('GOOGLE' in message for message in messages)
    assert any('MICROSOFT' in message for message in messages)
    assert any('GITHUB' in message for message in messages)
    assert not app.config.get('AGE_PUBLIC_KEY')
    assert not app.config.get('GOOGLE_CLIENT_ID')
    assert not app.config.get('GITHUB_CLIENT_SECRET')


def test_cli_command_tolerates_missing_system_model(
    bare_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An allowlisted user-management command need not configure the system model."""
    for var in REQUIRED_ENV_VARS:
        monkeypatch.setenv(var, 'test')
    app = codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)
    with app.app_context():
        init_db()

    # Now create the app again, as a CLI command would, without the model configured.
    monkeypatch.delenv('SYSTEM_MODEL_SHORTNAME')
    registered: list[Any] = []

    @click.group()
    def group() -> None:
        pass

    @group.command('newuser')
    def _newuser() -> None:
        registered.append(codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path))

    result = CliRunner().invoke(group, ['newuser'])
    assert result.exit_code == 0, result.output
    assert registered
