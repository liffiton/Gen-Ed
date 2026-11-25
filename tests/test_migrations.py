# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

import pytest
from flask import Flask

import codehelp
from gened.db import get_db
from gened.db_admin import init_db

MIGRATION_FILENAME = '20261125--learning-contexts--refactor.sql'
PRECEDING_MIGRATION_FILENAME = '20260605--unify-contexts-and-tutors.sql'

# Old-style context configs: (id, column name, config JSON)
OLD_CONTEXTS = [
    (1, 'both', '{"name": "both-name", "tools": "Python\\nFlask", "details": "Students are learning.", "avoid": "eval()\\nzfill()"}'),
    (2, 'tools-only', '{"name": "tools-only-name", "tools": "Python2\\nFlask2", "details": "", "avoid": ""}'),
    (3, 'details-only', '{"name": "details-only-name", "tools": "", "details": "details3", "avoid": ""}'),
    (4, 'empty-keys', '{"name": "empty-keys-name", "tools": "", "details": "", "guidance": "", "avoid": ""}'),
    (5, 'crlf', '{"name": "crlf-name", "tools": "Python\\r\\nFlask\\r\\n", "details": "Details\\r\\nline", "avoid": "sum()\\r\\neval()\\r\\n"}'),
    (6, 'empty-json', '{}'),
    (7, 'column-name', '{"details": "value7"}'),
    (8, 'custom-name', '{"name": "JSON name", "tools": " value8 ", "details": "  detail8  "}'),
    (9, 'preserve-guidance', '{"name": "guidance-name", "tools": "", "details": "", "guidance": "Be nice.", "avoid": "x"}'),
    (11, 'extra-key', '{"name": "extra-name", "tools": "", "details": "d", "custom_key": "keep"}'),
]

ERASED_CONTEXT_ID = 10

CONTEXT_STRINGS = [
    (1, 'context 1'),
    (2, 'context 2'),
    (3, 'a longer context string used for length checks'),
]

QUERY_CONTEXT_IDS = [1, 2, 1, 3]


def _get_config(db: Any, item_id: int) -> dict[str, Any]:
    row = db.execute("SELECT config FROM config_items WHERE id = ?", [item_id]).fetchone()
    assert row is not None
    return cast('dict[str, Any]', json.loads(row['config']))


@pytest.fixture
def migration_app() -> Generator[Flask]:
    """A fresh CodeHelp database with old-style contexts and the new migration pending."""
    with tempfile.TemporaryDirectory() as temp_dir:
        instance_path = Path(temp_dir)
        app = codehelp.create_app(
            test_config={
                'TESTING': True,
                'DATABASE': str(instance_path / 'migration_test.db'),
                'SYSTEM_API_KEY': 'invalid',
            },
            instance_path=instance_path,
        )

        with app.app_context():
            init_db()
            db = get_db()
            db.executescript("""
                INSERT INTO classes (id, name, enabled) VALUES (1, 'MIG101', 1);
                INSERT INTO users (id, auth_provider, auth_name) VALUES (1, 1, 'migrationuser');
            """)
            for item_id, column_name, config in OLD_CONTEXTS:
                db.execute(
                    "INSERT INTO config_items (id, class_id, item_type, name, class_order, available, config)"
                    " VALUES (?, 1, 'context', ?, ?, '0001-01-01', ?)",
                    [item_id, column_name, item_id, config],
                )
            db.execute(
                "INSERT INTO config_items (id, class_id, item_type, name, class_order, available, config)"
                " VALUES (?, 1, 'context', ?, ?, '0001-01-01', '{}')",
                [ERASED_CONTEXT_ID, f'[deleted]{ERASED_CONTEXT_ID}', ERASED_CONTEXT_ID],
            )
            db.executemany(
                "INSERT INTO context_strings (id, ctx_str) VALUES (?, ?)",
                CONTEXT_STRINGS,
            )
            for query_id, context_string_id in enumerate(QUERY_CONTEXT_IDS, start=1):
                db.execute(
                    "INSERT INTO code_queries (id, context_name, context_string_id, code, error, issue, user_id)"
                    " VALUES (?, 'ctx', ?, 'code', 'error', 'issue', 1)",
                    [query_id, context_string_id],
                )
            # Make the refactor migration pending; every other migration stays applied.
            db.execute("DELETE FROM migrations WHERE filename = ?", [MIGRATION_FILENAME])
            db.commit()

        yield app


def _apply_pending_migration(app: Flask) -> None:
    with app.app_context():
        result = app.test_cli_runner().invoke(args=['migrate', '--auto'])
    assert result.exit_code == 0, result.output
    assert MIGRATION_FILENAME in result.output


def test_migration_runs_after_unified_config_migration(migration_app: Flask) -> None:
    """The new migration filename sorts after the migration that populates config_items."""
    assert PRECEDING_MIGRATION_FILENAME < MIGRATION_FILENAME
    with migration_app.app_context():
        row = get_db().execute(
            "SELECT succeeded FROM migrations WHERE filename = ?",
            [PRECEDING_MIGRATION_FILENAME],
        ).fetchone()
        assert row is not None
        assert row['succeeded']

    _apply_pending_migration(migration_app)


def test_config_json_transform(migration_app: Flask) -> None:
    _apply_pending_migration(migration_app)

    with migration_app.app_context():
        db = get_db()

        both = _get_config(db, 1)
        assert both['name'] == 'both-name'
        assert both['details'] == '**Environment and tools:** Python; Flask\n\nStudents are learning.'
        assert both['guidance'] == ''
        assert both['avoid'] == 'eval()\nzfill()'

        tools_only = _get_config(db, 2)
        assert tools_only['name'] == 'tools-only-name'
        assert tools_only['details'] == '**Environment and tools:** Python2; Flask2'

        details_only = _get_config(db, 3)
        assert details_only['name'] == 'details-only-name'
        assert details_only['details'] == 'details3'

        empty = _get_config(db, 4)
        assert empty == {
            'name': 'empty-keys-name',
            'details': '',
            'guidance': '',
            'avoid': '',
        }

        crlf = _get_config(db, 5)
        assert crlf['details'] == '**Environment and tools:** Python; Flask\n\nDetails\nline'
        # The old avoid text is preserved as-is; prompt formatting handles CRLF.
        assert crlf['avoid'] == 'sum()\r\neval()\r\n'

        # A non-anonymized "{}" row is a legacy empty config and gains the column name.
        empty_json = _get_config(db, 6)
        assert empty_json == {
            'name': 'empty-json',
            'details': '',
            'guidance': '',
            'avoid': '',
        }

        # A missing JSON name gets the column name.
        column_name = _get_config(db, 7)
        assert column_name['name'] == 'column-name'
        assert column_name['details'] == 'value7'
        assert column_name['guidance'] == ''
        assert column_name['avoid'] == ''

        custom_name = _get_config(db, 8)
        assert custom_name['name'] == 'JSON name'
        assert custom_name['details'] == '**Environment and tools:** value8\n\ndetail8'

        guidance = _get_config(db, 9)
        assert guidance['details'] == ''
        assert guidance['guidance'] == 'Be nice.'
        assert guidance['avoid'] == 'x'

        # Other config keys are preserved; the legacy tools key is removed.
        extra = _get_config(db, 11)
        assert extra['custom_key'] == 'keep'
        assert extra['details'] == 'd'

        # Every transformed row (except the deliberate extra-key case) has
        # exactly the four new keys.
        for item_id in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            config = _get_config(db, item_id)
            assert set(config) == {'name', 'details', 'guidance', 'avoid'}


def test_erased_rows_are_not_transformed(migration_app: Flask) -> None:
    _apply_pending_migration(migration_app)

    with migration_app.app_context():
        row = get_db().execute(
            "SELECT name, config FROM config_items WHERE id = ?",
            [ERASED_CONTEXT_ID],
        ).fetchone()
        assert row is not None
        assert row['name'] == f'[deleted]{ERASED_CONTEXT_ID}'
        assert row['config'] == '{}'


def test_context_strings_and_queries_are_unchanged(migration_app: Flask) -> None:
    _apply_pending_migration(migration_app)

    with migration_app.app_context():
        db = get_db()

        rows = db.execute("SELECT id, ctx_str FROM context_strings ORDER BY id").fetchall()
        assert [(row['id'], row['ctx_str']) for row in rows] == CONTEXT_STRINGS

        total_length = db.execute("SELECT COALESCE(SUM(length(ctx_str)), 0) FROM context_strings").fetchone()[0]
        assert total_length == sum(len(ctx_str) for _id, ctx_str in CONTEXT_STRINGS)

        referenced = db.execute(
            "SELECT q.id, s.ctx_str FROM code_queries AS q"
            " JOIN context_strings AS s ON s.id = q.context_string_id"
            " ORDER BY q.id"
        ).fetchall()
        assert [row['id'] for row in referenced] == list(range(1, len(QUERY_CONTEXT_IDS) + 1))
        assert [row['ctx_str'] for row in referenced] == [
            CONTEXT_STRINGS[context_id - 1][1] for context_id in QUERY_CONTEXT_IDS
        ]
