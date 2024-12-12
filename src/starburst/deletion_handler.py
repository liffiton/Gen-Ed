# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.data_deletion import DeletionHandler, register_handler
from gened.db import get_db


class StarburstDeletionHandler(DeletionHandler):
    """Handler for deleting Starburst user data."""

    def delete_user_data(self, user_id: int) -> None:
        """Delete/Anonymize personal data for a user while preserving non-personal data for analysis."""
        db = get_db()

        # Delete queries
        db.execute("""
            DELETE queries
            WHERE user_id = ?
        """, [user_id])

        db.commit()

    def delete_class_data(self, class_id: int) -> None:
        """Delete/Anonymize personal data for a class while preserving non-personal data for analysis."""
        db = get_db()

        # Delete queries
        db.execute("""
            DELETE FROM queries
            WHERE role_id IN (
                SELECT id FROM roles WHERE class_id = ?
            )
        """, [class_id])

        db.commit()


def register_with_gened() -> None:
    """Register Starburst deletion handler with the gened framework."""
    register_handler(StarburstDeletionHandler())
