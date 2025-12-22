# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeGuard

from flask import Blueprint, current_app

from . import app_data
from .access import (
    Access,
    AccessControl,
    RequireComponentEnabled,
    check_access,
    control_blueprint_access,
)
from .auth import get_auth
from .class_config import types as class_config_types
from .db import get_db


@dataclass(frozen=True, kw_only=True)
class GenEdComponent:
    # name of the package that defined this component (used to locate schema and migration resources)
    # should be set to __package__ when initializing the component
    package: str

    # name/slug to register this component in the database and in-memory component registry
    # do not change this once in use or database entries will become out of sync
    name: str

    # name/description to be shown to users (inc. instructors when enabling/disabling components)
    display_name: str
    description: str

    # ..all items below here are optionally specified..
    # register the component's own routes or use this just to register a template folder
    blueprint: Blueprint | None = None
    # add an item to the navbar by specifying a template file for it
    navbar_item_template: str | None = None
    # configure a DataSource, used primarily to present data from this component to users, instructors, and admins
    data_source: app_data.DataSource | None = None
    # set up a table in the class configuration screen for configuring items for this component
    config_table: class_config_types.ConfigTable | None = None
    # add a time series chart to the top of the admin dashboard
    admin_chart: app_data.ChartGenerator | None = None
    # register a DeletionHandler to properly delete or anonymize data for this component when deleting a user or class
    deletion_handler: app_data.DeletionHandler | None = None
    # relative path to an SQL schema file within the component package for any needed tables/indexes/views/etc.
    schema_file: str | None = None
    # relative path to a directory within the component package for schema migration scripts
    migrations_dir: str | None = None

    # availability control checks: all must pass for this component to be
    # available within a class/user context.  Will be automatically applied to
    # all routes in the component (see `__post_init__()`).
    # Other checks can be added manually to specific routes.
    # default: login required
    # NOTE: 'available' is independent from 'enabled.'
    availability_requirements: tuple[AccessControl] = (Access.LOGIN, )

    # is this component always enabled (True) or
    # enabled by default but can be disabled per-class by the instructor (False)
    always_enabled: bool = False

    def __post_init__(self) -> None:
        """
        Automatically add access control to any stored blueprints requiring
        that this component be available+enabled.
        """
        # Delegate to stored availablity requirements (so we get their connected responses),
        # and add a requirement that this component be enabled as well.
        access_controls = (*self.availability_requirements, RequireComponentEnabled(self))
        if self.blueprint is not None:
            control_blueprint_access(self.blueprint, *access_controls)
        if self.config_table is not None and self.config_table.extra_routes is not None:
            control_blueprint_access(self.config_table.extra_routes, *access_controls)

    def is_enabled(self) -> bool:
        """ Returns True if this component is enabled in the current class. """
        if self.always_enabled:
            return True

        db = get_db()
        auth = get_auth()
        class_id = auth.cur_class.class_id if auth.cur_class else None
        check_row = db.execute(
            "SELECT enabled FROM class_components WHERE class_id=? AND component_name=?",
            [class_id, self.package]
        ).fetchone()

        if check_row:
            return bool(check_row['enabled'])
        else:
            # No entry in the database: use the default.
            return True

    def is_available(self) -> bool:
        """
        Returns True if this component is available in the current context,
        performing registered availability checks.

        NOTE: this does not check if the component is enabled; that can/should
        be checked independently.
        """
        return check_access(*self.availability_requirements)


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
