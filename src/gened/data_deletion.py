# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Interface and registry for personal data deletion handlers.

This module defines the interface that Gen-Ed applications must implement
for handling personal data deletion and provides the registration mechanism
for those handlers.
"""

from typing import Protocol

from flask import current_app

from .db import get_db


class DeletionHandler(Protocol):
    """Protocol defining the interface for personal data deletion handlers."""
    @staticmethod
    def delete_user_data(user_id: int) -> None:
        """Delete/anonymize all personal data for the given user."""
        ...

    @staticmethod
    def delete_class_data(class_id: int) -> None:
        """Delete/anonymize all personal data for the given class."""
        ...


class UserHasCreatedClassesError(Exception):
    """Raised when attempting to delete a user who has created classes."""


def delete_user_data(user_id: int) -> None:
    """Delete/anonymize all personal data for the given user."""
    db = get_db()

    # Verify the user has no created classes (if they did, they must have deleted them manually first)
    created_classes = db.execute("""
        SELECT class_id
        FROM classes_user
        WHERE creator_user_id = ?
    """, [user_id]).fetchall()

    if created_classes:
        raise UserHasCreatedClassesError

    # Deactivate all roles
    db.execute("UPDATE roles SET user_id = -1, active = 0 WHERE user_id = ?", [user_id])

    # Delete any custom models
    db.execute("DELETE FROM models WHERE owner_id = ?", [user_id])

    # Anonymize and deactivate user account
    db.execute("""
        UPDATE users
        SET full_name = '[deleted]',
            email = '[deleted]',
            auth_name = '[deleted]',
            last_class_id = NULL,
            query_tokens = 0,
            delete_status = 'deleted'
        WHERE id = ?
    """, [user_id])

    # Remove auth entries
    db.execute("DELETE FROM auth_local WHERE user_id = ?", [user_id])
    db.execute("DELETE FROM auth_external WHERE user_id = ?", [user_id])

    # Call component-specific data deletion handler(s)
    for handler in current_app.extensions['gen_ed_deletion_handlers']:
        handler.delete_user_data(user_id)

    db.commit()


def delete_class_data(class_id: int) -> None:
    """Delete/anonymize all personal data for the given class."""
    db = get_db()

    # Call component-specific data deletion handler(s)
    for handler in current_app.extensions['gen_ed_deletion_handlers']:
        handler.delete_class_data(class_id)

    db.commit()
