# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from dataclasses import dataclass, replace

from flask import Blueprint


@dataclass
class AdminLink:
    """Represents a link in the admin interface.
    Attributes:
        endpoint: The Flask endpoint name
        _display: The text to show in the navigation UI or a Callable that renders the item contents
        right:    True if this is a right-side link, False (the default) for left-side
    """
    endpoint: str
    _display: str | Callable[[], str]
    right: bool = False

    @property
    def display(self) -> str:
        if isinstance(self._display, str):
            return self._display
        else:
            return self._display()


# Global registry
_admin_bp: Blueprint | None = None
_blueprints: list[Blueprint] = []
_navbar_items: list[AdminLink] = []


def register_admin_blueprint(admin_bp: Blueprint) -> None:
    """Register the admin blueprint for component registration.
    Must be called before any components are registered.

    Args:
        admin_bp: The admin blueprint to register components with
    """
    global _admin_bp
    _admin_bp = admin_bp

    # Register any blueprints that may have already shown up
    for bp in _blueprints:
        _admin_bp.register_blueprint(bp)

    # Add nav items via context processor, ensuring endpoints are prefixed with admin blueprint name
    @_admin_bp.context_processor
    def inject_nav_items() -> dict[str, list[AdminLink]]:
        def prefix_endpoint(link: AdminLink) -> AdminLink:
            """Helper to prefix an endpoint with the admin blueprint name."""
            assert _admin_bp is not None
            return replace(link, endpoint=f"{_admin_bp.name}.{link.endpoint}")

        regular = [prefix_endpoint(item) for item in _navbar_items if not item.right]
        right = [prefix_endpoint(item) for item in _navbar_items if item.right]
        return {
            'admin_links': regular,
            'admin_links_right': right,
        }


def register_blueprint(bp: Blueprint) -> None:
    """Register an admin blueprint as a sub-blueprint of the admin blueprint.

    If the admin blueprint is already registered via register_admin_blueprint(),
    then this immediately adds the new blueprint to it.  Otherwise, it is stored
    to be added when register_admin_blueprint() is called.

    Args:
        bp: The Blueprint to register
    """
    _blueprints.append(bp)

    if _admin_bp is not None:
        _admin_bp.register_blueprint(bp)


def register_navbar_item(endpoint: str, display: str | Callable[[], str], *, right: bool = False) -> None:
    """Register an item for the admin navbar."""
    _navbar_items.append(AdminLink(endpoint, display, right))