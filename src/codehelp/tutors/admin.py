# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json

from flask import (
    Blueprint,
    render_template,
)

import gened.admin
from gened.db import get_db
from gened.tables import Col, DataTable, NumCol

# ### Admin routes ###
bp_admin = Blueprint('admin_tutor', __name__, url_prefix='/tutor', template_folder='templates')

# Register the tutors admin component.
gened.admin.register_blueprint(bp_admin)
gened.admin.register_navbar_item("admin_tutor.tutor_admin", "Tutor Chats")


@bp_admin.route("/")
@bp_admin.route("/<int:chat_id>")
def tutor_admin(chat_id : int|None = None) -> str:
    db = get_db()
    chats = db.execute("""
        SELECT
            chats.id AS id,
            users.display_name AS user,
            chats.topic AS topic,
            (
                SELECT COUNT(*)
                FROM json_each(chats.chat_json)
                WHERE json_extract(json_each.value, '$.role')='user'
            ) as "user messages"
        FROM chats
        JOIN users ON chats.user_id=users.id
        ORDER BY chats.id DESC
    """).fetchall()

    table = DataTable(
        name='chats',
        columns=[NumCol('id'), Col('user'), Col('topic'), NumCol('user messages')],
        link_col=0,
        link_template='${value}',
        data=chats,
    )

    if chat_id is not None:
        chat_row = db.execute("SELECT users.display_name, topic, chat_json FROM chats JOIN users ON chats.user_id=users.id WHERE chats.id=?", [chat_id]).fetchone()
        chat = json.loads(chat_row['chat_json'])
    else:
        chat_row = None
        chat = None

    return render_template("tutor_admin.html", chats=table, chat_row=chat_row, chat=chat)
