# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.db import get_db
from gened.instructor import register_class_deletion_handler


def delete_class_data(class_id: int) -> None:
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
    """ Register privacy functionality with the main gened module."""
    register_class_deletion_handler(delete_class_data)
