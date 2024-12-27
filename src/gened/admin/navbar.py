# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ParamSpec, TypeVar

from flask import Blueprint


@dataclass(frozen=True)
class AdminLink:
    """Represents a link in the admin interface.
    Attributes:
        endpoint: The Flask endpoint name
        _display: The text to show in the navigation UI or a Callable that renders the item contents
    """
    endpoint: str
    _display: str | Callable[[], str]
    @property
    def display(self) -> str:
        if isinstance(self._display, str):
            return self._display
        else:
            return self._display()

@dataclass
class AdminLinks:
    """Container for registering admin navigation links."""
    regular: list[AdminLink] = field(default_factory=list)
    right: list[AdminLink] = field(default_factory=list)

# A module-level list of registered links for the admin navbar.  Updated by register_admin_link()
_admin_links = AdminLinks()


# For decorator type hints
P = ParamSpec('P')
R = TypeVar('R')

def register_admin_link(display: str | Callable[[], str], bp_name: str | None = None, *, right: bool = False) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that registers an admin page navbar link to the decorated endpoint.
    Args:
        display: Text to show in the admin interface navigation or a function
                 that returns the text to render.
        bp_name: Name of the blueprint (under the admin blueprint) that
                 contains this endpoint, or None is the endpoint is in the
                 admin blueprint itself.
        right: If True, display this link on the right side of the nav bar
    """
    def decorator(route_func: Callable[P, R]) -> Callable[P, R]:
        if bp_name:
            handler_name = f"admin.{bp_name}.{route_func.__name__}"
        else:
            handler_name = f"admin.{route_func.__name__}"
        link = AdminLink(handler_name, display)
        if right:
            _admin_links.right.append(link)
        else:
            _admin_links.regular.append(link)
        return route_func
    return decorator


def init_bp(bp: Blueprint) -> None:
    @bp.context_processor
    def inject_admin_links() -> dict[str, list[AdminLink]]:
        return {
            'admin_links': _admin_links.regular,
            'admin_links_right': _admin_links.right,
        }
