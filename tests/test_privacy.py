# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

from flask import url_for

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


def test_delete_user_data_requires_confirmation(app, client, auth):
    """Test that user data deletion requires proper confirmation"""
    login_instructor_in_class(client, auth)
    with app.app_context():
        user_id = get_db().execute("SELECT id FROM users WHERE auth_name='testuser'").fetchone()['id']

    # Test without confirmation
    response = client.post('/profile/delete_data', follow_redirects=True)
    assert response.status_code == 200
    assert b"Data deletion requires confirmation" in response.data

    # Test with wrong confirmation
    response = client.post('/profile/delete_data', data={'confirm_delete': 'WRONG'}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Data deletion requires confirmation" in response.data

    # Verify nothing was deleted
    with app.app_context():
        db = get_db()
        user = db.execute("SELECT auth_name FROM users WHERE id = ?", [user_id]).fetchone()
        assert user['auth_name'] == 'testuser'


def test_delete_user_data_full_process(app, client, auth):
    """Test complete user data deletion process"""
    login_instructor_in_class(client, auth)
    with app.app_context():
        user_id = get_db().execute("SELECT id FROM users WHERE auth_name='testuser'").fetchone()['id']

    # Capture initial state
    with app.app_context():
        db = get_db()
        initial_queries = db.execute("SELECT * FROM queries WHERE user_id = ?", [user_id]).fetchall()
        initial_chats = db.execute("SELECT * FROM chats WHERE user_id = ?", [user_id]).fetchall()
        assert len(initial_queries) > 0, "Test data should include queries"
        assert len(initial_chats) > 0, "Test data should include chats"
        initial_query_ids = [row['id'] for row in initial_queries]
        initial_chat_ids = [row['id'] for row in initial_chats]

    # Perform deletion with proper confirmation
    response = client.post('/profile/delete_data', data={'confirm_delete': 'DELETE'})
    assert response.status_code == 302
    assert response.location == "/profile/"  # redirect to profile because we have a user-created class
    response = client.get('/profile/')
    assert b"You must delete all classes you created before deleting your data." in response.data

    # Delete the classes so user deletion can proceed
    client.post('/instructor/class/delete', data={'class_id': 2, 'confirm_delete': 'DELETE'})
    client.get('/classes/switch/3')
    client.post('/instructor/class/delete', data={'class_id': 3, 'confirm_delete': 'DELETE'})
    client.get('/classes/switch/4')
    client.post('/instructor/class/delete', data={'class_id': 4, 'confirm_delete': 'DELETE'})

    # Perform deletion with proper confirmation
    response = client.post('/profile/delete_data', data={'confirm_delete': 'DELETE'})
    assert response.status_code == 302
    assert response.location == "/auth/login"  # redirect to login because user was successfully deleted

    # Verify final state of all affected tables
    with app.app_context():
        db = get_db()

        # Check user account state
        user = db.execute("SELECT * FROM users WHERE id = ?", [user_id]).fetchone()
        assert user['full_name'] == '[deleted]'
        assert user['email'] == '[deleted]'
        assert user['auth_name'] == '[deleted]'
        assert user['query_tokens'] == 0
        assert user['last_class_id'] is None

        # Check roles
        verify_row_count(
            "roles", "WHERE user_id = ? AND active = 1", [user_id],
            0, "No roles should be active"
        )

        # Check auth entries removed
        verify_row_count(
            "auth_local", "WHERE user_id = ?", [user_id],
            0, "Local auth entry should be deleted"
        )
        verify_row_count(
            "auth_external", "WHERE user_id = ?", [user_id],
            0, "External auth entry should be deleted"
        )

        # Check queries anonymization
        query_list = ','.join('?' * len(initial_query_ids))  # for SQL IN clause
        queries = db.execute(f"SELECT * FROM queries WHERE id IN ({query_list})", initial_query_ids).fetchall()
        # Verify each query has been properly anonymized
        assert len(queries) == len(initial_query_ids), "All original queries should still exist"
        for query in queries:
            assert query['user_id'] == -1, f"Query {query['id']}: user_id should be -1"
            # NULL values should remain NULL
            if query['code'] is not None:
                assert query['code'] == '[deleted]', f"Query {query['id']}: non-NULL code should be '[deleted]'"
            if query['error'] is not None:
                assert query['error'] == '[deleted]', f"Query {query['id']}: non-NULL error should be '[deleted]'"
            # These fields should always be '[deleted]' or NULL as specified
            assert query['issue'] == '[deleted]', f"Query {query['id']}: issue should be '[deleted]'"
            assert query['context_name'] == '[deleted]', f"Query {query['id']}: context_name should be '[deleted]'"
            assert query['context_string_id'] is None, f"Query {query['id']}: context_string_id should be NULL"

        # Check chats anonymization
        chat_list = ','.join('?' * len(initial_chat_ids))  # for SQL IN clause
        chats = db.execute(f"SELECT * FROM chats WHERE id IN ({chat_list})", initial_chat_ids).fetchall()
        # Verify each chat has been properly anonymized
        assert len(chats) == len(initial_chat_ids), "All original chats should still exist"
        for chat in chats:
            assert chat['topic'] == '[deleted]', "Chat topic should be deleted"
            assert chat['chat_json'] == '[]', "Chat JSON should be empty"
            assert chat['context_name'] == '[deleted]', "Chat context_name should be deleted"
            assert chat['context_string_id'] is None, "Chat context_string_id should be nulled"


def test_delete_user_data_unauthorized(app, client):
    """Test unauthorized access to user data deletion"""
    # Test without login
    response = client.post('/profile/delete_data', data={'confirm_delete': 'DELETE'})
    assert response.status_code == 302
    assert response.location.startswith('/auth/login?')

    # Verify nothing was deleted
    with app.app_context():
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE auth_name='testuser'").fetchone()
        assert user['full_name'] != '[deleted]'


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


def test_anonymize_user_unauthorized(app, client):
    """Test unauthorized access to user anonymization"""
    # Test without login
    response = client.post('/profile/anonymize')
    assert response.status_code == 302
    assert response.location.startswith('/auth/login?')


def test_anonymize_user_provider_restrictions(app, client, auth):
    """Test provider restrictions for anonymization"""
    auth.login('testuser', 'testpassword')

    with app.app_context():
        db = get_db()
        # Get original user data
        init_user = db.execute("SELECT * FROM users WHERE auth_name='testuser'").fetchone()

        # Force-set current user as LTI user
        db.execute("""
            UPDATE auth_external
            SET auth_provider = (SELECT id FROM auth_providers WHERE name = 'lti')
            WHERE user_id = (SELECT id FROM users WHERE auth_name = 'testuser')
        """)
        db.commit()

        response = client.post('/profile/anonymize', follow_redirects=True)
        assert response.status_code == 200
        assert b"Account anonymization is only available to external, non-LTI accounts" in response.data

        # Verify nothing was anonymized
        user = db.execute("SELECT * FROM users WHERE auth_name='testuser'").fetchone()
        assert user['full_name'] == init_user['full_name']
        assert user['email'] == init_user['email']


def test_anonymize_user_full_process(app, client, mock_oauth_patch):
    """Test complete user anonymization process"""
    # Set up mock OAuth login
    with app.test_request_context():
        auth_url = url_for('oauth.auth', provider_name='google')

    # Perform OAuth login
    with client:
        response = client.get(auth_url)
        assert response.status_code == 302

    # Get initial state
    with app.app_context():
        db = get_db()
        initial_user = db.execute("SELECT * FROM users WHERE full_name=?", [mock_oauth_patch.test_user['name']]).fetchone()
        user_id = initial_user['id']
        initial_auth = db.execute("SELECT * FROM auth_external WHERE user_id = ?", [user_id]).fetchone()

        # Verify initial state
        assert not initial_auth['is_anon']  # This is the key state we're testing

    # Perform anonymization
    response = client.post('/profile/anonymize')
    assert response.status_code == 302
    assert response.location == "/profile/"

    # Verify final state
    with app.app_context():
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", [user_id]).fetchone()
        auth = db.execute("SELECT * FROM auth_external WHERE user_id = ?", [user_id]).fetchone()

        # Check user record
        assert user['full_name'] != initial_user['full_name']
        # Anonymous usernames are three capitalized words concatenated
        assert re.match(r"^(?:[A-Z][a-z]+){3}$", user['full_name'])
        assert user['email'] is None
        assert user['auth_name'] is None

        # Check external auth set to anonymous
        assert auth['is_anon'] == 1

        # Verify other data remains intact
        assert user['id'] == initial_user['id']
        assert user['auth_provider'] == initial_user['auth_provider']
        assert user['is_admin'] == initial_user['is_admin']
        assert user['is_tester'] == initial_user['is_tester']
        assert user['query_tokens'] == initial_user['query_tokens']
        assert user['last_class_id'] == initial_user['last_class_id']
