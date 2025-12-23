# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterable
from dataclasses import dataclass

from flask import Blueprint

from . import app_data
from .access import (
    Access,
    AccessControl,
    RequireComponent,
    check_access,
    control_blueprint_access,
)
from .auth import get_auth
from .class_config import types as class_config_types
from .db import get_db


@dataclass(frozen=True, kw_only=True)
class ComponentFeature:
    # name/slug for referencing this feature -- will be in a namespace, referenced as "component:feature"
    name: str

    # name/description to be shown to users
    display_name: str
    description: str


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
    # "subcomponents" or "features" that can be enabled/disabled independently
    features: Iterable[ComponentFeature] = ()
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
        that this component be registered + available + enabled.
        """
        if self.blueprint is not None:
            control_blueprint_access(self.blueprint, RequireComponent(self.name))
        if self.config_table is not None and self.config_table.extra_routes is not None:
            control_blueprint_access(self.config_table.extra_routes, RequireComponent(self.name))

    def is_enabled(self, feature: str | None = None) -> bool:
        """
        Returns True if this component (and optionally a specific feature) is enabled in the current class.
        """
        if self.always_enabled:
            return True

        auth = get_auth()
        class_id = auth.cur_class.class_id if auth.cur_class else None

        if class_id is None:
            # Not in any class: use the default
            return True

        db = get_db()

        # Check the component itself and, if specified, the feature (namespaced)
        names_to_check = [self.name]
        if feature:
            names_to_check.append(f"{self.name}:{feature}")

        for name in names_to_check:
            check_row = db.execute(
                "SELECT enabled FROM class_components WHERE class_id=? AND component_name=?",
                [class_id, name]
            ).fetchone()

            # If either the component or (if specified) the feature are disabled, return False
            if check_row and not check_row['enabled']:
                return False

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

