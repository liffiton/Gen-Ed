# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from datetime import datetime, timedelta

from flask import Flask

from gened.admin.pruning import get_candidates
from gened.db import get_db


def test_v_user_items_content(app: Flask) -> None:
    """Verify that v_user_items correctly aggregates activity from multiple tables."""
    with app.app_context():
        db = get_db()

        # Check overall count (based on test_data.sql)
        # code_queries: 10 rows
        # chats: 3 rows
        # total: 13 rows
        count = db.execute("SELECT COUNT(*) FROM v_user_items").fetchone()[0]
        assert count == 13

        # Check specific entry from code_queries (id=1, user_id=21, role_id=1)
        row = db.execute("SELECT * FROM v_user_items WHERE component='code_queries' AND user_id=21 AND role_id=1").fetchone()
        assert row is not None

        # Check specific entry from chats (id=1, user_id=11, role_id=4)
        row = db.execute("SELECT * FROM v_user_items WHERE component='chats' AND user_id=11 AND role_id=4").fetchone()
        assert row is not None


def test_v_user_activity_aggregation(app: Flask) -> None:
    """Verify that v_user_activity correctly identifies the last activity for a user."""
    with app.app_context():
        db = get_db()

        # testuser (id=11) has:
        # - created: [now]
        # - role created: [now]
        # - class created: [now]
        # - query (id=8, 9): [now]
        # - chat (id=1): [now]

        # Let's set some specific historical dates to verify aggregation
        # We'll make everything old except one query
        db.execute("UPDATE users SET created='2020-01-01 00:00:00' WHERE id=11")
        db.execute("UPDATE roles SET created='2020-01-02 00:00:00' WHERE user_id=11")
        db.execute("UPDATE classes_user SET created='2020-01-03 00:00:00' WHERE creator_user_id=11")
        db.execute("UPDATE code_queries SET query_time='2020-01-04 00:00:00' WHERE user_id=11")
        db.execute("UPDATE chats SET chat_started='2020-01-05 00:00:00' WHERE user_id=11")

        # Now set one activity to be the latest
        latest_time = '2024-01-01 12:00:00'
        db.execute("UPDATE code_queries SET query_time=? WHERE id=8", [latest_time])
        db.commit()

        row = db.execute("SELECT * FROM v_user_activity WHERE id=11").fetchone()
        assert row['created'] == '2020-01-01 00:00:00'
        assert row['last_role_created_time'] == '2020-01-02 00:00:00'
        assert row['last_class_created_time'] == '2020-01-03 00:00:00'
        assert row['last_query_time'] == latest_time
        assert row['last_activity'] == latest_time


def test_pruning_candidates_logic(app: Flask) -> None:
    """Verify that pruning correctly identifies candidates based on retention time."""
    with app.app_context():
        db = get_db()
        retention_days = app.config['RETENTION_TIME_DAYS']

        # Set a user's activity to be just outside the retention period
        cutoff_date = (datetime.now() - timedelta(days=retention_days + 1)).strftime('%Y-%m-%d %H:%M:%S')

        # User 14 (testuser2) - make them old
        db.execute("UPDATE users SET created='2010-01-01 00:00:00' WHERE id=14")
        db.execute("UPDATE chats SET chat_started=? WHERE user_id=14", [cutoff_date])

        # User 22 (ltiuser2) - make them new (should not be a candidate)
        now_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute("UPDATE users SET created=? WHERE id=22", [now_date])
        db.execute("UPDATE code_queries SET query_time=? WHERE user_id=22", [now_date])

        db.commit()

        candidates, _num_candidates = get_candidates()

        candidate_ids = [row['id'] for row in candidates if not row['whitelist?']]
        assert 14 in candidate_ids
        assert 22 not in candidate_ids
