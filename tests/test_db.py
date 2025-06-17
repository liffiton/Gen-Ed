# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import sqlite3
from unittest.mock import Mock

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from gened.db import get_db


def test_get_close_db(app: Flask) -> None:
    with app.app_context():
        db = get_db()
        assert db is get_db()

    with pytest.raises(sqlite3.ProgrammingError) as e:
        db.execute('SELECT 1')

    assert 'closed' in str(e.value)


def test_init_db_command(runner: FlaskCliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_init_db = Mock()
    monkeypatch.setattr('gened.db.init_db', mock_init_db)
    result = runner.invoke(args=['initdb'])
    assert 'Initialized' in result.output
    mock_init_db.assert_called_once()
