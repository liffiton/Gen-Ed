# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import dataclass, field
from sqlite3 import Row
from typing import Final, Literal


@dataclass(frozen=True)
class Col:
    name: str
    kind: str | None = None
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
    kind: Final = 'user'


@dataclass(frozen=True)
class TimeCol(Col):
    kind: Final = 'time'


@dataclass(frozen=True)
class DataTable:
    name: str
    data: list[Row]
    columns: list[Col]
    hidden_cols: list[str] = field(default_factory=list)
    link_col: int | None = None
    link_template: str | None = None
    extra_links: list[dict[str, str]] | None = None
    create_endpoint: str | None = None
    csv_link: str | None = None
    ajax_url: str | None = None
