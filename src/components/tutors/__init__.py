# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from gened.components import GenEdComponent

from .chat import bp as bp
from .data import TutorsDeletionHandler, chats_data_source, gen_chats_chart
from .guided import guided_tutor_config_table

gened_component = GenEdComponent(
    package=__package__,
    name="tutors",
    display_name="Tutors",
    description="Students can chat with an LLM designed to interact as a tutor focused on teaching and learning.  Students can initiate Inquiry Chats on topics or questions of their own.  Instructors can design Focused Tutors for students with pre-defined learning objectives and assessment questions (e.g., to be used as reinforcement and/or low-stakes assessments following a reading or video).",
    blueprint=bp,
    navbar_item_template="tutor_nav_item.html",
    data_source=chats_data_source,
    admin_chart=gen_chats_chart,
    config_table=guided_tutor_config_table,
    deletion_handler=TutorsDeletionHandler,
    schema_file="schema.sql",
    migrations_dir="migrations",
)

__all__ = [
    "gened_component",
]
