# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterable
from typing import TypeGuard

from flask import current_app

from . import app_data
from .class_config import types as class_config_types
from .components import GenEdComponent


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

def get_registered_components() -> Iterable[GenEdComponent]:
    return get_component_registry().values()


def register_component(component: GenEdComponent) -> None:
    registry = get_component_registry()

    # raise an exception if duplicate package added
    assert component.package not in registry

    registry[component.package] = component


def get_component_data_source_by_name(name: str) -> app_data.DataSource | None:
    components = get_registered_components()
    for c in components:
        if (ds := c.data_source) and ds.table_name == name:
            return ds
    return None


def get_component_config_table_by_name(name: str) -> class_config_types.ConfigTable | None:
    components = get_registered_components()
    for c in components:
        if (ct := c.config_table) and ct.name == name:
            return ct
    return None


def get_component_navbar_templates() -> list[str]:
    return [
        c.navbar_item_template
        for c in get_registered_components()
        if c.navbar_item_template and c.is_available() and c.is_enabled()
    ]
