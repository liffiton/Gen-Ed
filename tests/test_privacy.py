# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from gened.db import get_db


def login_instructor_in_class(client, auth):
    """Setup test data and login as instructor"""
    auth.login()  # as testuser, who is instructor in class id 2
    response = client.get('/classes/switch/2')
    assert response.status_code == 302
    return 2  # return the class_id we're working with


def verify_row_count(table: str, where_clause: str, params: list[str | int], expected_count: int, msg: str) -> None:
    """Helper to check number of matching rows in a table"""
    db = get_db()
    count = db.execute(f"SELECT COUNT(*) FROM {table} {where_clause}", params).fetchone()[0]
    assert count == expected_count, f"{msg}: expected {expected_count}, got {count}"


def test_delete_class_requires_confirmation(app, client, auth):
    class_id = login_instructor_in_class(client, auth)

    # Test without confirmation
    response = client.post('/instructor/class/delete', data={'class_id': class_id}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Class deletion requires confirmation" in response.data

    # Test with wrong confirmation
    response = client.post('/instructor/class/delete', data={'class_id': class_id, 'confirm_delete': 'WRONG'}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Class deletion requires confirmation" in response.data

    # Verify nothing was deleted
    with app.app_context():
        db = get_db()

        # Check class state
        verify_row_count("classes", "WHERE id = ?", [class_id], 1, "Class should still exist")
        class_row = db.execute("SELECT * FROM classes WHERE id = ?", [class_id]).fetchone()
        assert class_row['name'] != '[deleted]'
        assert class_row['enabled'] == 1


def test_delete_class_full_process(app, client, auth):
    class_id = login_instructor_in_class(client, auth)

    # Capture initial state
    with app.app_context():
        db = get_db()
        initial_queries = db.execute("SELECT COUNT(*) FROM queries WHERE role_id IN (SELECT id FROM roles WHERE class_id = ?)",
[class_id]).fetchone()[0]
        initial_contexts = db.execute("SELECT COUNT(*) FROM contexts WHERE class_id = ?", [class_id]).fetchone()[0]
        assert initial_queries > 0, "Test data should include queries"
        assert initial_contexts > 0, "Test data should include contexts"

    # Perform deletion with proper confirmation
    response = client.post('/instructor/class/delete', data={'class_id': class_id, 'confirm_delete': 'DELETE'})
    assert response.status_code == 302
    assert response.location == "/profile/"

    # Verify final state of all affected tables
    with app.app_context():
        db = get_db()

        # Check class state
        class_row = db.execute("SELECT * FROM classes WHERE id = ?", [class_id]).fetchone()
        assert class_row['name'] == '[deleted]'
        assert class_row['enabled'] == 0

        # Check roles
        verify_row_count(
            "roles", "WHERE class_id = ? AND user_id != -1", [class_id],
            0, "All roles should be reassigned to deleted user"
        )
        verify_row_count(
            "roles", "WHERE class_id = ? AND active = 1", [class_id],
            0, "No roles should be active"
        )

        # Check class-specific tables
        verify_row_count(
            "classes_lti", "WHERE class_id = ?", [class_id],
            0, "LTI class entry should be deleted"
        )
        verify_row_count(
            "classes_user", "WHERE class_id = ?", [class_id],
            0, "User class entry should be deleted"
        )

        # Check queries anonymization
        queries = db.execute("""
            SELECT *
            FROM queries
            WHERE role_id IN (SELECT id FROM roles WHERE class_id = ?)
        """, [class_id]).fetchall()
        for query in queries:
            assert query['user_id'] == -1, "Queries should be anonymized"
            assert query['code'] in (None, '[deleted]'), "Query code should be deleted"
            assert query['error'] in (None, '[deleted]'), "Query error should be deleted"
            assert query['issue'] == '[deleted]', "Query issue should be deleted"
            assert query['context_name'] == '[deleted]', "Query context_name should be deleted"
            assert query['context_string_id'] is None, "Query context_string_id should be nulled"

        # Check contexts anonymization
        contexts = db.execute("SELECT * FROM contexts WHERE class_id = ?", [class_id]).fetchall()
        for context in contexts:
            assert context['name'].startswith('[deleted]'), "Context names should be anonymized"
            assert context['config'] == '{}', "Context configs should be emptied"

        # Check user last_class_id updates
        verify_row_count(
            "users", "WHERE last_class_id = ?", [class_id],
            0, "No users should reference deleted class"
        )


def test_delete_class_unauthorized(app, client, auth):
    class_id = login_instructor_in_class(client, auth)

    # Test as non-instructor
    auth.logout()
    auth.login('testuser2', 'testuser2password')

    response = client.post('/instructor/class/delete', data={'class_id': class_id, 'confirm_delete': 'DELETE'})
    assert response.status_code == 302
    assert response.location.startswith('/auth/login?')

    # Verify nothing was deleted
    with app.app_context():
        verify_row_count("classes", "WHERE id = ? AND name != '[deleted]'", [class_id], 1, "Class should still exist")

