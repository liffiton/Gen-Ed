# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from sqlite3 import Cursor, Row
from typing import Final, Protocol, Self
from urllib.parse import urlencode

from flask import request

from gened.tables import DataTable

from .auth import get_auth
from .db import get_db

""" Manage app-specific data. """


class DeletionHandler(Protocol):
    """Protocol defining the interface for personal data deletion handlers."""
    @staticmethod
    def delete_user_data(user_id: int) -> None:
        """Delete/anonymize all personal data for the given user."""
        ...

    @staticmethod
    def delete_class_data(class_id: int) -> None:
        """Delete/anonymize all personal data for the given class."""
        ...


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
        'row_id': FilterSpec('row_id', 't.id', None),
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

    def add(self, spec_name: str, value: str | int, *, with_display: bool=False) -> Self:
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

        return self  # for chaining


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

@dataclass(frozen=True, kw_only=True)
class DataSource:
    table_name: str
    display_name: str
    get_data: DataFunction
    table: DataTable
    time_col: str | None = None
    requires_experiment: str | None = None

    def get_populated_table(self, filters: Filters, * , limit: int=-1, offset: int=0) -> DataTable:
        table = deepcopy(self.table)
        table.data = self.get_data(filters, limit=limit, offset=offset).fetchall()
        return table

    def get_user_data(self, limit: int) -> list[Row]:
        '''Fetch current user's history.'''
        auth = get_auth()
        assert auth.user_id is not None
        filters = Filters().add('user', auth.user_id)
        return self.get_data(filters, limit=limit).fetchall()

    def get_user_counts(self, user_id: int) -> dict[str, int]:
        assert self.time_col is not None
        db = get_db()
        sql = f"""
            SELECT
                COUNT(t.id) AS num_total,
                COUNT(IIF(t.{self.time_col} > date('now', '-7 days'), 1, null)) AS num_1wk
            FROM {self.table_name} AS t
            WHERE t.user_id = ?
        """
        row = db.execute(sql, [user_id]).fetchone()
        return dict(row)

    def get_row(self, row_id: int) -> Row:
        return _get_data_row(self, row_id)


class DataAccessError(Exception):
    pass

class RowNotFoundError(DataAccessError):
    pass

class AccessDeniedError(DataAccessError):
    pass

def _get_data_row(data_source: DataSource, row_id: int) -> Row:
    '''Fetch a single row from a registerd data source with an access permission check.'''
    auth = get_auth()
    assert auth.user_id is not None

    filters = Filters()
    filters.add('row_id', row_id)

    row = data_source.get_data(filters, limit=1).fetchone()

    if not row:
        raise RowNotFoundError

    is_owner = ( auth.user_id == row['user_id'] )
    is_instructor_in_class = (
        auth.cur_class
        and auth.cur_class.role == 'instructor'
        and auth.cur_class.class_id == row['class_id']
    )
    access_permitted = is_owner or is_instructor_in_class or auth.is_admin

    if not access_permitted:
        raise AccessDeniedError

    assert isinstance(row, Row)
    return row
