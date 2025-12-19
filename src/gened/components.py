# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from copy import deepcopy
from dataclasses import dataclass
from typing import TypeGuard

from flask import Blueprint, current_app

from . import (
    app_data,
    class_config,
)


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


def is_component_list(lst: list[object]) -> TypeGuard[list[GenEdComponent]]:
    """ Determines whether all objects in the list are GenEdComponents """
    return all( isinstance(x, GenEdComponent) for x in lst )


def get_registered_components() -> list[GenEdComponent]:
    components = current_app.extensions['gen_ed_components']
    assert is_component_list(components)
    return components


def get_component_data_sources() -> dict[str, app_data.DataSource]:
    components = get_registered_components()
    return {c.data_source.table_name: deepcopy(c.data_source) for c in components if c.data_source is not None}
