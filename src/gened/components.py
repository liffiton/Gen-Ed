# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import dataclass
from typing import TypeGuard

from flask import Blueprint, current_app

from . import (
    app_data,
    class_config,
)
from .auth import get_auth


@dataclass(frozen=True, kw_only=True)
class GenEdComponent:
    # name of the package that defined this component (used to locate schema and migration resources)
    package: str

    # ..all items below here are optional..
    # register the component's own routes or use this just to register a template folder
    blueprint: Blueprint | None = None
    # add an item to the navbar by specifying a template file for it
    navbar_item_template: str | None = None
    # configure a DataSource, used primarily to present data from this component to users, instructors, and admins
    data_source: app_data.DataSource | None = None
    # set up a table in the class configuration screen for configuring items for this component
    config_table: class_config.ConfigTable | None = None
    # add a time series chart to the top of the admin dashboard
    admin_chart: app_data.ChartGenerator | None = None
    # register a DeletionHandler to properly delete or anonymize data for this component when deleting a user or class
    deletion_handler: app_data.DeletionHandler | None = None
    # relative path to an SQL schema file within the component package for any needed tables/indexes/views/etc.
    schema_file: str | None = None
    # relative path to a directory within the component package for schema migration scripts
    migrations_dir: str | None = None
    # only make this component available if the given experiment is active (or, if None, component is always available)
    requires_experiment: str | None = None

    def is_available(self) -> bool:
        auth = get_auth()
        return self.requires_experiment is None or self.requires_experiment in auth.class_experiments


def is_component_list(lst: list[object]) -> TypeGuard[list[GenEdComponent]]:
    """ Determines whether all objects in the list are GenEdComponents """
    return all( isinstance(x, GenEdComponent) for x in lst )


def get_registered_components() -> list[GenEdComponent]:
    components = current_app.extensions['gen_ed_components']
    assert is_component_list(components)
    return components


def get_component_data_source_by_name(name: str) -> app_data.DataSource | None:
    components = get_registered_components()
    for c in components:
        if (ds := c.data_source) and ds.table_name == name:
            return ds
    return None


def get_component_navbar_templates() -> list[str]:
    return [ c.navbar_item_template for c in get_registered_components() if c.navbar_item_template ]
