# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Flask

from components.code_contexts.data import record_context_string
from gened.data_deletion import delete_class_data
from gened.db import get_db


def test_record_context_string_deduplicates(app: Flask) -> None:
    """Recording the same string returns the same row; different strings get new rows."""
    with app.app_context():
        db = get_db()
        first = record_context_string('same context')
        second = record_context_string('same context')
        different = record_context_string('different context')

        assert isinstance(first, int)
        assert first == second
        assert first != different

        rows = db.execute(
            "SELECT id, ctx_str FROM context_strings WHERE ctx_str IN (?, ?)",
            ['same context', 'different context'],
        ).fetchall()
        assert len(rows) == 2


def test_context_deletion_removes_only_class_context_strings(app: Flask) -> None:
    """Deleting a class removes its context strings but preserves others.

    Uses the production deletion entry point so handler ordering is exercised.
    """
    with app.app_context():
        db = get_db()
        class2_only = record_context_string('class-2-only-context')
        class1_only = record_context_string('class-1-only-context')
        shared = record_context_string('shared-context')
        orphan_referenced = record_context_string('orphan-referenced-context')

        # role 4 is in class 2; role 1 is in class 1.
        # The final row has no role, so its class cannot be established.
        for context_string_id, user_id, role_id in (
            (class2_only, 11, 4),
            (class1_only, 21, 1),
            (shared, 11, 4),
            (shared, 21, 1),
            (orphan_referenced, 11, 4),
            (orphan_referenced, 21, None),
        ):
            cur = db.execute(
                "INSERT INTO code_queries (context_name, context_string_id, code, error, issue, user_id, role_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ['ctx', context_string_id, 'code', 'error', 'issue', user_id, role_id],
            )
            assert cur.lastrowid is not None
        db.commit()

        context_string_ids = [class2_only, class1_only, shared, orphan_referenced]
        before = db.execute(
            "SELECT id FROM context_strings WHERE id IN (?, ?, ?, ?)",
            context_string_ids,
        ).fetchall()
        assert {row['id'] for row in before} == set(context_string_ids)

        delete_class_data(2)

        after = db.execute(
            "SELECT id FROM context_strings WHERE id IN (?, ?, ?, ?)",
            context_string_ids,
        ).fetchall()
        remaining = {row['id'] for row in after}
        # A class-2-only string is removed.
        assert class2_only not in remaining
        # A class-1-only string and a string shared with class 1 are preserved.
        assert class1_only in remaining
        assert shared in remaining
        # A string referenced by a query without a class is also preserved.
        assert orphan_referenced in remaining
