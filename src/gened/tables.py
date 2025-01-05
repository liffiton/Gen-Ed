# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from dataclasses import dataclass, replace
from sqlite3 import Row
from typing import Any, Final, Literal

from .filters import fmt_response_txt, fmt_user


@dataclass(frozen=True)
class Col:
    name: str
    kind: str | None = None
    hidden: bool = False
    align: Literal[None, 'left', 'right', 'center'] = None


@dataclass(frozen=True)
class NumCol(Col):
    align: Final = 'right'
    kind: Final = 'num'


@dataclass(frozen=True, kw_only=True)
class BoolCol(Col):
    url: str | None = None
    reload: bool | None = None
    align: Final = 'center'
    kind: Final = 'bool'


@dataclass(frozen=True)
class UserCol(Col):
    kind: Final = 'html'
    prerender: Final[Callable[[str], str]] = fmt_user


@dataclass(frozen=True)
class TimeCol(Col):
    kind: Final = 'time'


@dataclass(frozen=True)
class DateCol(Col):
    kind: Final = 'date'


@dataclass(frozen=True)
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


def table_prep(cols: list[Col], data: list[Row], max_len: int=1000) -> list[dict[str, Any]]:
    """ Prepare tabular data to be sent to the simple-datatables as JSON.
    This pre-renders columns that have hooks for that, shortens overly-long
    strings (that the user doesn't care to see in the table and that will just
    waste bandwidth) and converts into a format that simple-datatables accepts.
    """
    def process(col: Col, val: Any) -> Any:
        if hasattr(col, 'prerender'):
            return col.prerender(val)
        elif isinstance(val, str) and len(val) > max_len:
            return f"{val[:max_len]} ..."
        else:
            return val

    assert not data or set(data[0].keys()).issuperset(col.name for col in cols), "Data column headings must match column spec names."
    return [
        {col.name: process(col, row[col.name]) for col in cols}
        for row in data
    ]


@dataclass(kw_only=True)
class DataTable:
    name: str
    columns: list[Col]
    link_col: int | None = None
    link_template: str | None = None
    actions: list[Action] | None = None
    create_endpoint: str | None = None
    csv_link: str | None = None
    ajax_url: str | None = None
    data: list[Row] | None = None

    def hide(self, col_name: str) -> None:
        self.columns = [
            replace(col, hidden=True) if col.name == col_name else col
            for col in self.columns
        ]

    @property
    def num_hidden(self) -> int:
        return sum(1 for col in self.columns if col.hidden)

    @property
    def table_data(self) -> list[dict[str, Any]]:
        return table_prep(self.columns, self.data or [])
