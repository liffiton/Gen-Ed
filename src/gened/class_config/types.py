# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterable
from sqlite3 import Row
from typing import Any, Literal, Self

import msgspec
from flask import Blueprint, url_for
from jinja2 import Template
from werkzeug.datastructures import ImmutableMultiDict

from gened.access import AccessControl
from gened.auth import get_auth_class

# This module provides the basis for application-specific configuration tables,
# in which multiple elements of a given type need to be managed in a table.
#
# It is kept relatively generic, and much of the specific implementation of the
# configured items can be controlled by the provided msgspec Struct and related
# templates.
#
# App-specific configuration data are stored in msgspec Structs.  The Struct
# must specify the item's name, define the config's fields and their types, and
# implement the `from_request_form()` class method that creates a new object
# based on inputs in request.form (as submitted from the form in the specified
# template).
#
# Related routes are defined in config_table.py.


class ConfigItem(msgspec.Struct):
    """ Base class for defining types of configuration items to be
    managed in a ConfigTable.
    """
    name: str
    row_id: int | None = None

    @classmethod
    def initial(cls) -> Self:
        """ Return an "initial" object for this class.
        Can be overridden if needed.
        """
        return cls(name='')

    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, str]) -> Self:
        raise NotImplementedError

    @classmethod
    def from_row(cls, row: Row) -> Self:
        """ Instantiate an item object from an SQLite row.
            (Requires correct field names in the row and in its 'config' JSON column.)
        """
        attrs = msgspec.json.decode(row['config'])
        attrs['name'] = row['name']
        attrs['row_id'] = row['id']
        return msgspec.convert(attrs, cls)

    def to_json(self) -> str:
        """ Dump config data (all but row_id) to JSON """
        d = msgspec.structs.asdict(self)
        d.pop("row_id")
        return msgspec.json.encode(d).decode()


class ConfigShareLink(msgspec.Struct, frozen=True):
    label: str
    endpoint: str
    args: set[Literal['class_id', 'ctx_name', 'tutor_name']]
    extra_requirements: Iterable[AccessControl] = ()

    def render_url(self, item: dict[str, Any]) -> str:
        kwargs: dict[str, str] = dict()
        for arg in self.args:
            match arg:
                case 'class_id':
                    kwargs[arg] = str(get_auth_class().class_id)
                case 'ctx_name' | 'tutor_name':
                    kwargs[arg] = item['name']
        return url_for(self.endpoint, _external=True, **kwargs)


class ConfigTable(msgspec.Struct, frozen=True, kw_only=True):
    name: str
    config_item_class: type[ConfigItem]
    db_table_name: str
    display_name: str
    display_name_plural: str
    help_text: Template | str | None = None
    edit_form_template: str
    share_links: Iterable[ConfigShareLink] = ()
    extra_routes: Blueprint | None = None
    availability_requirements: Iterable[AccessControl] = ()

    @property
    def new_url(self) -> str:
        return url_for('class_config.table.crud.new_item_form', table_name=self.name)
