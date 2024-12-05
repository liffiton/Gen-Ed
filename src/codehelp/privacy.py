# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.db import get_db
from gened.instructor import register_class_deletion_handler
from gened.profile import register_user_deletion_handler


def delete_user_data(user_id: int) -> None:
    """Delete/Anonymize personal data for a user while preserving non-personal data for analysis."""
    db = get_db()

    # Anonymize personal data in queries
    db.execute("""
        UPDATE queries
        SET code = CASE
                WHEN code IS NOT NULL THEN '[deleted]'
                ELSE NULL
            END,
            error = CASE
                WHEN error IS NOT NULL THEN '[deleted]'
                ELSE NULL
            END,
            issue = '[deleted]',
            context_name = '[deleted]',
            context_string_id = NULL,
            user_id = -1
        WHERE user_id = ?
    """, [user_id])

    # Anonymize personal data in chats
    db.execute("""
        UPDATE chats
        SET topic = '[deleted]',
            chat_json = '[]',
            context_name = '[deleted]',
            context_string_id = NULL,
            user_id = -1
        WHERE user_id = ?
    """, [user_id])

    db.commit()


def delete_class_data(class_id: int) -> None:
    """Delete/Anonymize personal data for a class while preserving non-personal data for analysis."""
    db = get_db()

    # Remove context names and configs as they may contain personal information
    db.execute("""
        UPDATE contexts
        SET name = '[deleted]' || id,
            config = '{}'
        WHERE class_id = ?
    """, [class_id])

    # Remove context strings as they may contain personal information
    db.execute("""
        DELETE FROM context_strings
        WHERE id IN (
            SELECT context_string_id
            FROM queries
            WHERE role_id IN (
                SELECT id FROM roles WHERE class_id = ?
            )
            UNION
            SELECT context_string_id
            FROM chats
            WHERE role_id IN (
                SELECT id FROM roles WHERE class_id = ?
            )
        )
    """, [class_id, class_id])

    # Anonymize personal data in queries
    db.execute("""
        UPDATE queries
        SET code = CASE
                WHEN code IS NOT NULL THEN '[deleted]'
                ELSE NULL
            END,
            error = CASE
                WHEN error IS NOT NULL THEN '[deleted]'
                ELSE NULL
            END,
            issue = '[deleted]',
            context_name = '[deleted]',
            context_string_id = NULL,
            user_id = -1
        WHERE role_id IN (
            SELECT id FROM roles WHERE class_id = ?
        )
    """, [class_id])

    # Anonymize personal data in chats
    db.execute("""
        UPDATE chats
        SET topic = '[deleted]',
            chat_json = '[]',
            context_name = '[deleted]',
            context_string_id = NULL,
            user_id = -1
        WHERE role_id IN (
            SELECT id FROM roles WHERE class_id = ?
        )
    """, [class_id])

    db.commit()


def register_with_gened() -> None:
    """ Register privacy functionality with the main gened module."""
    register_class_deletion_handler(delete_class_data)
    register_user_deletion_handler(delete_user_data)
