# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
from collections.abc import Iterable
from typing import TypeGuard

from flask import current_app

from . import app_data
from .class_config.types import ConfigItem, ConfigShareLink, ConfigTable
from .components import GenEdComponent

# share link keys must be simple slugs (they appear in persisted deep-link URLs)
SHARE_LINK_KEY_RE = re.compile(r'[a-z0-9_]+')


################################
# Component registry interface
#
def is_component_registry(obj: object) -> TypeGuard[dict[str, GenEdComponent]]:
    """ Determines whether all objects in the list are GenEdComponents """
    if not isinstance(obj, dict):
        return False

    keys_are_strings = all( isinstance(x, str) for x in obj )
    values_are_components = all( isinstance(x, GenEdComponent) for x in obj.values() )
    return keys_are_strings and values_are_components


def get_component_registry() -> dict[str, GenEdComponent]:
    key = 'gen_ed_components'

    # Create an empty registry if not present yet
    if key not in current_app.extensions:
        current_app.extensions[key] = dict()

    components = current_app.extensions[key]
    assert is_component_registry(components)
    return components


def register_component(component: GenEdComponent) -> None:
    registry = get_component_registry()

    # raise an exception if duplicate package added
    assert component.name not in registry

    registry[component.name] = component
    _check_share_link_keys()


def _check_share_link_keys() -> None:
    """Validate share-link keys across all registered components.

    Keys must match SHARE_LINK_KEY_RE and be globally unique (a duplicate
    would make deep-link launches ambiguous).
    """
    owners: dict[str, str] = {}
    for c in get_component_registry().values():
        if c.config_table is None:
            continue
        for link in c.config_table.share_links:
            assert SHARE_LINK_KEY_RE.fullmatch(link.key), (
                f"invalid share link key {link.key!r} in component {c.name!r} "
                f"(keys must match {SHARE_LINK_KEY_RE.pattern!r})"
            )
            assert link.key not in owners, (
                f"duplicate share link key {link.key!r} "
                f"(components {owners[link.key]!r} and {c.name!r})"
            )
            owners[link.key] = c.name


def get_component_data_source_by_name(name: str) -> app_data.DataSource | None:
    components = get_registered_components()
    for c in components:
        if (ds := c.data_source) and ds.table_name == name:
            return ds
    return None


def get_component_config_table_by_name(name: str) -> ConfigTable[ConfigItem] | None:
    components = get_registered_components()
    for c in components:
        if (ct := c.config_table) and ct.name == name:
            return ct
    return None


def get_share_link_by_key(key: str) -> ConfigShareLink | None:
    """Return the registered share link with the given key, or None.

    Share link keys are globally unique (enforced at registration), so at
    most one link can match.
    """
    for c in get_registered_components():
        if c.config_table is None:
            continue
        for link in c.config_table.share_links:
            if link.key == key:
                return link
    return None


def get_registered_components() -> Iterable[GenEdComponent]:
    return get_component_registry().values()


def get_navbar_components() -> list[GenEdComponent]:
    return [
        c for c in get_registered_components()
        if c.is_available() and c.is_enabled() and c.main_endpoint
    ]
