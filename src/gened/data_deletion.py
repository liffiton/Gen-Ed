# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Interface and registry for personal data deletion handlers.

This module defines the interface that Gen-Ed applications must implement
for handling personal data deletion and provides the registration mechanism
for those handlers.
"""

from typing import Protocol


class DeletionHandler(Protocol):
    """Protocol defining the interface for personal data deletion handlers."""
    def delete_user_data(self, user_id: int) -> None:
        """Delete/anonymize all personal data for the given user."""
        ...

    def delete_class_data(self, class_id: int) -> None:
        """Delete/anonymize all personal data for the given class."""
        ...


_handler: DeletionHandler | None = None


def register_handler(handler: DeletionHandler) -> None:
    """Register the application's deletion handler implementation."""
    global _handler
    _handler = handler


def has_handler() -> bool:
    """Return whether a deletion handler has been registered (True) or not (False)."""
    return _handler is not None


def delete_user_data(user_id: int) -> None:
    """Delete/anonymize all personal data for the given user."""
    if _handler is None:
        raise RuntimeError("No deletion handler registered")
    _handler.delete_user_data(user_id)


def delete_class_data(class_id: int) -> None:
    """Delete/anonymize all personal data for the given class."""
    if _handler is None:
        raise RuntimeError("No deletion handler registered")
    _handler.delete_class_data(class_id)
