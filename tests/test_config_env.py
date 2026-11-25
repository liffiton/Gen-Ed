# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner, Result
from flask.cli import FlaskGroup

import codehelp
import gened.base
from gened.base import InvalidAGEKeyError, MissingEnvVarError
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


@pytest.fixture
def server_env(bare_env: None, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ARG001 -- fixture used for its side effects
    """Configure exactly the required server settings."""
    for key in REQUIRED_ENV_VARS:
        monkeypatch.setenv(key, 'test')


def _invoke_flask(monkeypatch: pytest.MonkeyPatch, instance_path: Path, *args: str) -> Result:
    """Run a real Flask command, including Flask's lazy app discovery."""
    monkeypatch.setattr(sys, 'argv', ['flask', *args])
    monkeypatch.setenv('FLASK_RUN_FROM_CLI', 'true')  # restore Flask's env change after the test
    group = FlaskGroup(
        create_app=lambda: codehelp.create_app(test_config={'TESTING': True}, instance_path=instance_path),
        load_dotenv=False,
    )
    return CliRunner().invoke(group, list(args))


def test_missing_required_env_var_is_fatal_when_serving(bare_env: None, tmp_path: Path) -> None:  # noqa: ARG001 -- fixture used for its side effects
    """A server process must not start with a missing required variable."""
    with pytest.raises(MissingEnvVarError) as excinfo:
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)
    assert 'SECRET_KEY' in str(excinfo.value)


@pytest.mark.parametrize('varname', REQUIRED_ENV_VARS)
def test_empty_required_env_var_is_fatal_when_serving(
    server_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    varname: str,
) -> None:
    """An empty required environment variable is treated as missing."""
    monkeypatch.setenv(varname, '')

    with pytest.raises(MissingEnvVarError, match=varname):
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)


@pytest.mark.parametrize('key', REQUIRED_ENV_VARS)
def test_empty_required_app_config_is_fatal_when_serving(
    server_env: None,  # noqa: ARG001 -- fixture used for its side effects
    tmp_path: Path,
    key: str,
) -> None:
    with pytest.raises(MissingEnvVarError, match=key):
        codehelp.create_app(test_config={'TESTING': True, key: ''}, instance_path=tmp_path)


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
    def fail_if_serving(*args: object, **kwargs: object) -> None:  # noqa: ARG001 -- match the server callable
        pytest.fail('Started serving without required settings')

    monkeypatch.setattr('flask.cli.run_simple', fail_if_serving)
    result = _invoke_flask(monkeypatch, tmp_path, 'run')
    assert result.exit_code != 0
    assert isinstance(result.exception, MissingEnvVarError)


def test_non_flask_click_command_requires_server_config(
    bare_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(sys, 'argv', ['serve'])

    @click.command()
    def serve() -> None:
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)

    result = CliRunner().invoke(serve)
    assert isinstance(result.exception, MissingEnvVarError)


def test_cli_commands_defer_missing_config(
    bare_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An app-defined command can be loaded without server config."""
    with caplog.at_level(logging.DEBUG):
        result = _invoke_flask(monkeypatch, tmp_path, '--app', 'codehelp', 'migrate', '--help')

    assert result.exit_code == 0, result.exception
    assert '--auto' in result.output
    # Details are available at DEBUG, but nothing is escalated to a warning.
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
    messages = [record.getMessage() for record in caplog.records]
    assert any('SECRET_KEY' in message for message in messages)
    assert any('AGE_PUBLIC_KEY' in message for message in messages)


def test_other_cli_commands_require_server_config(
    bare_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Commands outside the explicit database-management allowlist validate config."""
    result = _invoke_flask(monkeypatch, tmp_path, 'routes')
    assert isinstance(result.exception, MissingEnvVarError)


@pytest.mark.parametrize('args', [(), ('--help',)])
def test_cli_help_does_not_require_server_config(
    bare_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    args: tuple[str, ...],
) -> None:
    """Flask loads the app for command help, but help itself does not serve."""
    result = _invoke_flask(monkeypatch, tmp_path, *args)
    assert result.exit_code == (0 if args else 2), result.exception
    assert 'migrate' in result.output
    assert 'Required environment variable not set' not in result.output


def test_serving_warns_about_missing_optional_features(
    server_env: None,  # noqa: ARG001 -- fixture used for its side effects
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A server process still gets warnings about disabled optional features."""
    with caplog.at_level(logging.WARNING):
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)

    messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert any('AGE_PUBLIC_KEY' in message for message in messages)
    assert any('GOOGLE' in message for message in messages)
    assert any('MICROSOFT' in message for message in messages)
    assert any('GITHUB' in message for message in messages)


def test_empty_oauth_env_vars_are_reported_as_missing(
    server_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Empty optional environment variables disable the feature and warn."""
    for var in OPTIONAL_ENV_VARS:
        if var != 'AGE_PUBLIC_KEY':
            monkeypatch.setenv(var, '')

    with caplog.at_level(logging.WARNING):
        app = codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)

    messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert any('GOOGLE' in message for message in messages)
    assert any('MICROSOFT' in message for message in messages)
    assert any('GITHUB' in message for message in messages)
    assert 'GOOGLE_CLIENT_ID' not in app.config
    assert 'GITHUB_CLIENT_SECRET' not in app.config


def test_empty_age_key_is_invalid_even_for_migrate(
    server_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv('AGE_PUBLIC_KEY', '')

    with pytest.raises(InvalidAGEKeyError, match='AGE_PUBLIC_KEY'):
        codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)

    result = _invoke_flask(monkeypatch, tmp_path, 'migrate', '--help')
    assert isinstance(result.exception, InvalidAGEKeyError)


@pytest.mark.parametrize(('env_suffix', 'config_suffix'), [('CLIENT_ID', 'CLIENT_SECRET'), ('CLIENT_SECRET', 'CLIENT_ID')])
def test_oauth_credentials_can_be_split_between_env_and_app_config(
    server_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    env_suffix: str,
    config_suffix: str,
) -> None:
    monkeypatch.setenv(f'GOOGLE_{env_suffix}', 'from-env')
    monkeypatch.setenv('GITHUB_CLIENT_SECRET', 'incomplete')
    with caplog.at_level(logging.WARNING):
        app = codehelp.create_app(
            test_config={'TESTING': True, f'GOOGLE_{config_suffix}': 'from-config'},
            instance_path=tmp_path,
        )

    assert app.config[f'GOOGLE_{env_suffix}'] == 'from-env'
    assert app.config[f'GOOGLE_{config_suffix}'] == 'from-config'
    assert not any('GOOGLE' in record.getMessage() for record in caplog.records)
    assert 'GITHUB_CLIENT_SECRET' not in app.config


def test_cli_command_tolerates_missing_system_model(
    server_env: None,  # noqa: ARG001 -- fixture used for its side effects
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An allowlisted user-management command need not configure the system model."""
    app = codehelp.create_app(test_config={'TESTING': True}, instance_path=tmp_path)
    with app.app_context():
        init_db()

    # Now create the app again, as a CLI command would, without the model configured.
    monkeypatch.delenv('SYSTEM_MODEL_SHORTNAME')

    result = _invoke_flask(monkeypatch, tmp_path, 'newuser', 'cli-user')
    assert result.exit_code == 0, result.exception
    assert 'User added to the database' in result.output
