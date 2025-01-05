# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass, field
from sqlite3 import Cursor, Row
from typing import Final, Protocol
from urllib.parse import urlencode

from flask import request
from typing_extensions import Self  # for 3.10

from gened.tables import DataTable

from .auth import get_auth
from .db import get_db

""" Manage app-specific data. """


@dataclass(frozen=True)
class ChartData:
    labels: list[str | int | float]
    series: dict[str, list[int | float]]
    colors: list[str]


@dataclass(frozen=True)
class FilterSpec:
    name: str
    column: str
    display_query: str | None


@dataclass(frozen=True)
class Filter:
    spec: FilterSpec
    value: str | int
    display_value: str | None


class Filters:
    _available_filter_specs: Final = {
        'consumer': FilterSpec('consumer', 'consumers.id', 'SELECT lti_consumer FROM consumers WHERE id=?'),
        'class': FilterSpec('class', 'classes.id', 'SELECT name FROM classes WHERE id=?'),
        'user': FilterSpec('user', 'users.id', 'SELECT display_name FROM users WHERE id=?'),
        'role': FilterSpec('role', 'roles.id', """
            SELECT printf("%s (%s:%s)", users.display_name, role_class.name, roles.role)
            FROM roles
            LEFT JOIN users ON users.id=roles.user_id
            LEFT JOIN classes AS role_class ON role_class.id=roles.class_id
            WHERE roles.id=?
        """),
        'query': FilterSpec('query', 'queries.id', None),
    }

    def __init__(self) -> None:
        self._filters: list[Filter] = []

    def __iter__(self) -> Iterator[Filter]:
        return self._filters.__iter__()

    @classmethod
    def from_args(cls, *, with_display: bool=False) -> Self:
        """ Generate a Filters object for use in a CSV export, API response,
        etc.  where display values are not needed (and so we do not need to run
        queries to generate them).

        If with_display is True, also query the database to get display values
        for each filter.
        """
        filters = cls()

        for spec in cls._available_filter_specs:
            if spec in request.args:
                value = request.args[spec]
                filters.add(spec, value, with_display=with_display)

        return filters

    def add(self, spec_name: str, value: str | int, *, with_display: bool=False) -> None:
        spec = self._available_filter_specs.get(spec_name)

        if not spec:
            raise RuntimeError(f"Invalid filter spec name: {spec_name}")

        if with_display and spec.display_query:
            display_row = get_db().execute(spec.display_query, [value]).fetchone()
            if not display_row:
                raise RuntimeError(f"Invalid filter value: {spec_name}={value}")
            display_value = display_row[0]
        else:
            display_value = None
        self._filters.append(Filter(spec, value, display_value))


    def make_where(self, selected: list[str]) -> tuple[str, list[str | int]]:
        filters = [f for f in self._filters if f.spec.name in selected]
        if not filters:
            return "1", []
        else:
            return (
                " AND ".join(f"{f.spec.column}=?" for f in filters),
                [f.value for f in filters]
            )

    def filter_string(self) -> str:
        filter_dict = {f.spec.name: f.value for f in self._filters}
        return f"?{urlencode(filter_dict)}"

    def filter_string_without(self, exclude_name: str) -> str:
        filter_dict = {f.spec.name: f.value for f in self._filters if f.spec.name != exclude_name}
        return f"?{urlencode(filter_dict)}"

    def template_string(self, selected_name: str) -> str:
        '''
        Return a string that will be used to create a link URL for each row in
        a table.  This string is passed to a Javascript function as
        `{{template_string}}`, to be used with string interpolation in
        Javascript.  Therefore, it should contain "${{value}}" as a placeholder
        for the value -- it is rendered by Python's f-string interpolation as
        "${value}" in the page source, suitable for Javascript string
        interpolation.
        '''
        return self.filter_string_without(selected_name) + f"&{selected_name}=${{value}}"


class ChartGenerator(Protocol):
    def __call__(self, filters: Filters) -> list[ChartData]:
        ...

class DataFunction(Protocol):
    def __call__(self, filters: Filters, /, limit: int=-1, offset: int=0) -> Cursor:
        ...

@dataclass(frozen=True)
class DataSource:
    name: str
    function: DataFunction
    table: DataTable

@dataclass
class AppDataConfig:
    """ Configuratin of app-specific data types/sources.
    Application-specific charts and data sources can be registered with
    register_admin_chart(), register_data().
    """
    admin_chart_generators: list[ChartGenerator] = field(default_factory=list)
    data_source_map: dict[str, DataSource] = field(default_factory=dict)

_appdata = AppDataConfig()

def register_admin_chart(generator_func: ChartGenerator) -> None:
    _appdata.admin_chart_generators.append(generator_func)

def get_admin_charts() -> list[ChartGenerator]:
    return _appdata.admin_chart_generators

def register_data(name: str, data_func: DataFunction, data_table: DataTable) -> None:
    data_source = DataSource(name, data_func, data_table)
    if name in _appdata.data_source_map:
        # don't allow overwriting the same name
        # but this may occur in tests or other situations that re-use the module across applications...
        assert _appdata.data_source_map[name] == data_source

    _appdata.data_source_map[name] = data_source

def get_registered_data_sources() -> dict[str, DataSource]:
    return deepcopy(_appdata.data_source_map)

def get_registered_data_source(name: str) -> DataSource:
    source = _appdata.data_source_map.get(name)
    if not source:
        raise RuntimeError(f"Invalid data source name: {name}")
    return deepcopy(source)


class DataAccessError(Exception):
    pass

class RowNotFoundError(DataAccessError):
    pass

class AccessDeniedError(DataAccessError):
    pass

def get_query(query_id: int) -> Row:
    '''Fetch a single query with an access permission check.'''
    auth = get_auth()
    assert auth.user_id is not None

    filters = Filters()
    filters.add('query', query_id)

    get_data = get_registered_data_source('queries').function
    row = get_data(filters).fetchone()

    if not row:
        raise RowNotFoundError

    access_permitted = (
        auth.user_id == row['user_id']
        or auth.is_admin
        or (auth.cur_class and auth.cur_class.role == 'instructor' and auth.cur_class.class_id == row['class_id'])
    )

    if not access_permitted:
        raise AccessDeniedError

    assert isinstance(row, Row)
    return row


def get_user_data(kind: str, limit: int) -> list[Row]:
    '''Fetch current user's query history.'''
    auth = get_auth()
    assert auth.user_id is not None

    filters = Filters()
    filters.add('user', auth.user_id)

    get_data = get_registered_data_source(kind).function
    data = get_data(filters, limit=limit).fetchall()

    return data
