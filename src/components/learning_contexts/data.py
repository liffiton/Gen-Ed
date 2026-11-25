# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only


from gened.db import get_db

from .config_table import contexts_config_table

ITEM_TYPE = contexts_config_table.name


class ContextsDeletionHandler:
    """Personal data deletion for the learning_contexts component."""

    @staticmethod
    def delete_user_data(user_id: int) -> None:
        pass

    @staticmethod
    def delete_class_data(class_id: int) -> None:
        """Delete/Anonymize personal data for a class while preserving non-personal data for analysis."""
        db = get_db()

        # Remove context names and configs as they may contain personal information
        db.execute("""
            UPDATE config_items
            SET name = '[deleted]' || id,
                config = '{}'
            WHERE class_id = ? AND item_type = ?
        """, [class_id, ITEM_TYPE])
