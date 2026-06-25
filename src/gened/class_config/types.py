# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterable
from sqlite3 import Row
from typing import Any, Generic, Literal, Self, TypeVar

import msgspec
from flask import Blueprint, current_app, url_for
from jinja2 import Template
from werkzeug.datastructures import ImmutableMultiDict

from gened.access import AccessControl
from gened.auth import get_auth, get_auth_class
from gened.db import get_db

# C is defined with covariant=True so that a ConfigTable containing a subclass of
# ConfigItem (such as ConfigTable[TutorConfig]) is considered a subtype of
# ConfigTable[ConfigItem]. This allows code processing arbitrary ConfigTables
# to be typed as ConfigTable[ConfigItem] rather than losing type safety with
# ConfigTable[Any].
C_co = TypeVar('C_co', bound='ConfigItem', covariant=True)

# The following provide the basis for application-specific configuration tables,
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


class ConfigTable(msgspec.Struct, Generic[C_co], frozen=True, kw_only=True):
    name: str
    config_item_class: type[C_co]
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

    def get_items(self, *, available_only: bool = False) -> list[C_co]:
        """Get all config items of this type for the current user's class.

        If available_only is True, only return items whose available date has passed
        (UTC+12, so current date anywhere on earth).

        Items are ordered by class_order.
        """
        db = get_db()
        auth = get_auth()
        class_id = auth.cur_class.class_id if auth.cur_class else None

        if available_only:
            rows = db.execute(
                "SELECT * FROM config_items WHERE class_id=? AND item_type=? AND available <= date('now', '+12 hours') ORDER BY class_order ASC",
                [class_id, self.name]
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM config_items WHERE class_id=? AND item_type=? ORDER BY class_order ASC",
                [class_id, self.name]
            ).fetchall()

        items = []
        for row in rows:
            try:
                items.append(self.config_item_class.from_row(row))
            except (msgspec.DecodeError, msgspec.ValidationError) as e:
                current_app.logger.error(f"Failed to load config item {row['id']} ({self.name}). Error: {e}")

        return items

    def get_item_by_name(self, name: str) -> C_co | None:
        """Get a single config item by name for the current user's class.

        Returns None if no item with that name exists for the current class + type.
        """
        db = get_db()
        auth = get_auth()
        class_id = auth.cur_class.class_id if auth.cur_class else None

        row = db.execute(
            "SELECT * FROM config_items WHERE class_id=? AND item_type=? AND name=?",
            [class_id, self.name, name]
        ).fetchone()

        if row is None:
            return None

        return self.config_item_class.from_row(row)

    def get_item_by_id(self, item_id: int) -> C_co | None:
        """Get a single config item by id for the current user's class.

        Returns None if no item with that id exists for the current class + type.
        """
        db = get_db()
        auth = get_auth()
        class_id = auth.cur_class.class_id if auth.cur_class else None

        row = db.execute(
            "SELECT * FROM config_items WHERE id=? AND class_id=? AND item_type=?",
            [item_id, class_id, self.name]
        ).fetchone()

        if row is None:
            return None

        return self.config_item_class.from_row(row)
