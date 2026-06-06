# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only


from gened.db import get_db

from .config_table import contexts_config_table

ITEM_TYPE = contexts_config_table.name


def record_context_string(context_str: str) -> int:
    """ Ensure a context string is recorded in the context_strings
        table, and return its row ID.
    """
    db = get_db()
    # Add the context string to the context_strings table, but if it's a duplicate, just get the row ID of the existing one.
    # The "UPDATE SET id=id" is a no-op, but it allows the "RETURNING" to work in case of a conflict as well.
    cur = db.execute("INSERT INTO context_strings (ctx_str) VALUES (?) ON CONFLICT DO UPDATE SET id=id RETURNING id", [context_str])
    context_string_id = cur.fetchone()['id']
    assert isinstance(context_string_id, int)
    return context_string_id


class ContextsDeletionHandler:
    """Personal data deletion for the code_contexts component."""

    @staticmethod
    def delete_user_data(user_id: int) -> None:
        pass

    @staticmethod
    def delete_class_data(class_id: int) -> None:
        """Delete/Anonymize personal data for a class while preserving non-personal data for analysis."""
        db = get_db()
        db.execute("PRAGMA foreign_keys=OFF")  # so we can delete context_string entries before NULLing the foreign keys referencing them

        # Remove context names and configs as they may contain personal information
        db.execute("""
            UPDATE config_items
            SET name = '[deleted]' || id,
                config = '{}'
            WHERE class_id = ? AND item_type = ?
        """, [class_id, ITEM_TYPE])

        # Remove context strings as they may contain personal information
        db.execute("""
            DELETE FROM context_strings
            WHERE id IN (
                SELECT context_string_id
                FROM code_queries
                WHERE role_id IN (
                    SELECT id FROM roles WHERE class_id = ?
                )
            )
        """, [class_id])

        db.execute("PRAGMA foreign_keys=ON")
