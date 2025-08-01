# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.base import GenEdComponent

from . import admin
from .chat import bp as bp
from .data import TutorsDeletionHandler, chats_data_source
from .guided import guided_tutor_config_table

admin.register_with_gened()

gened_component = GenEdComponent(
    blueprint=bp,
    navbar_item_template="tutor_nav_item.html",
    data_source=chats_data_source,
    config_table=guided_tutor_config_table,
    deletion_handler=TutorsDeletionHandler,
)


__all__ = [
    "gened_component",
]
