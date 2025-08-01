# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.base import GenEdComponent

from .data import LangDeletionHandler, queries_data_source
from .helper import bp

gened_component = GenEdComponent(
    blueprint=bp,
    navbar_item_template="queries_nav_item.html",
    data_source=queries_data_source,
    deletion_handler=LangDeletionHandler,
)

__all__ = [
    "gened_component",
]
