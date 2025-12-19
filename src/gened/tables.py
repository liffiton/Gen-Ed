# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from sqlite3 import Row
from typing import Any, Final, Literal, Self

from .filters import fmt_response_txt, fmt_user


@dataclass(frozen=True, kw_only=True)
class Col:
    name: str = field(kw_only=False)  # override kw_only so that only this argument can be positional
    kind: str | None = None
    hidden: bool = False
    align: Literal['left', 'right', 'center'] | None = None


@dataclass(frozen=True, kw_only=True)
class NumCol(Col):
    align: Final = 'right'
    kind: Final = 'num'


@dataclass(frozen=True, kw_only=True)
class BoolCol(Col):
    url: str | None = None
    reload: bool | None = None
    align: Final = 'center'
    kind: Final = 'bool'


@dataclass(frozen=True, kw_only=True)
class UserCol(Col):
    kind: Final = 'html'
    prerender: Final[Callable[[str], str]] = fmt_user


@dataclass(frozen=True, kw_only=True)
class TimeCol(Col):
    kind: Final = 'time'


@dataclass(frozen=True, kw_only=True)
class DateCol(Col):
    kind: Final = 'date'


@dataclass(frozen=True, kw_only=True)
class ResponseCol(Col):
    kind: Final = 'html'
    prerender: Final[Callable[[str], str]] = fmt_response_txt


@dataclass(frozen=True)
class Action:
    text: str
    icon: str
    url: str
    id_col: int
    query_arg: str | None = None


@dataclass(frozen=True, kw_only=True)
class DataTableSpec:
    name: str
    columns: list[Col]
    link_col: int | None = None
    link_template: str | None = None
    actions: list[Action] | None = None
    create_endpoint: str | None = None
    csv_link: str | None = None
    ajax_url: str | None = None

    def with_hidden(self, col_name: str) -> Self:
        new_columns = [
            replace(col, hidden=True) if col.name == col_name else col
            for col in self.columns
        ]
        return replace(self, columns=new_columns)

    @property
    def num_hidden(self) -> int:
        return sum(1 for col in self.columns if col.hidden)


@dataclass(kw_only=True)
class DataTable:
    spec: DataTableSpec
    data: list[Row]

    @property
    def data_for_json(self) -> list[dict[str, Any]]:
        """ Prepare tabular data to be sent to simple-datatables as JSON.
        This pre-renders columns that have hooks for that, shortens overly-long
        strings (that the user doesn't care to see in the table and that will just
        waste bandwidth) and converts into a format that simple-datatables accepts.
        """
        data = self.data
        cols = self.spec.columns
        assert not data or set(data[0].keys()).issuperset(col.name for col in cols), f"Data column headings must match column spec names: {data[0].keys()} {cols}"

        max_len = 1000
        def process(col: Col, val: Any) -> Any:
            if hasattr(col, 'prerender'):
                return col.prerender(val)
            elif isinstance(val, str) and len(val) > max_len:
                return f"{val[:max_len]} ..."
            else:
                return val

        return [
            { col.name: process(col, row[col.name]) for col in cols }
            for row in data
        ]
