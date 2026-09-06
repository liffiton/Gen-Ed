# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import dataclass
from typing import Any, NoReturn

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pylti.flask import LTI  # type: ignore[import-untyped]
from pylti.flask import lti as lti_flask
from werkzeug.wrappers.response import Response

from .access import check_access
from .auth import (
    LoginData,
    RoleType,
    ext_login_update_or_create,
    set_session_auth_class,
    set_session_auth_user,
)
from .classes import get_or_create_lti_class
from .component_registry import (
    get_component_config_table_by_name,
    get_share_link_by_key,
)
from .db import get_db

bp = Blueprint('lti', __name__, template_folder='templates')


@dataclass(frozen=True)
class LTILaunchData:
    lti_user_id: str
    consumer: str
    context_id: str
    class_name: str
    full_name: str | None
    email: str | None
    role: RoleType
    message_type: str | None


def reload_consumers() -> None:
    db = get_db()
    consumer_rows = db.execute("SELECT * FROM consumers").fetchall()
    consumer_dict = {
        row['lti_consumer']: {"secret": row['lti_secret']} for row in consumer_rows
    }
    current_app.config['PYLTI_CONFIG']['consumers'] = consumer_dict


# An LTI-specific error handler
def lti_error(exception: dict[str, Any]) -> tuple[str, int]:
    """Log the error and render a simple error page."""
    current_app.logger.error(f"LTI exception: {exception['exception']=} {exception['kwargs']=} {exception['args']=}")
    return "There was an LTI communication error", 500


def _reject(code: int, detail: str | None = None) -> NoReturn:
    session.clear()
    abort(code, detail)


def _resolve_deep_link(dl_table: str, dl_link: str, content_id: str, class_id: int) -> str | None:  # noqa: PLR0911 - each validation step logs a distinct reason
    """ Resolve a deep-link launch to a target URL, or None if it cannot be resolved.

    The launch URL's query args name a config item and the specific share link
    that produced the deep link.  The item must exist in the launched class,
    and both the table's and the link's access requirements must be met.  The
    target endpoint always comes from the registered ConfigShareLink
    definition, never from the request.  Deep links to items that are not yet
    marked available are allowed (the item is served, not gated).
    """
    table = get_component_config_table_by_name(dl_table)
    if table is None:
        current_app.logger.warning(f"LTI deep link failed: unknown dl_table {dl_table!r} (class {class_id})")
        return None

    link = get_share_link_by_key(dl_link)
    if link is None:
        current_app.logger.warning(f"LTI deep link failed: unknown dl_link {dl_link!r} (class {class_id})")
        return None

    # Share link keys are globally unique, so the link must be checked against
    # the named table (a mismatched pair would otherwise resolve cross-table).
    if link.key not in {share_link.key for share_link in table.share_links}:
        current_app.logger.warning(f"LTI deep link failed: dl_link {dl_link!r} does not belong to dl_table {dl_table!r} (class {class_id})")
        return None

    if not check_access(*table.availability_requirements):
        current_app.logger.warning(f"LTI deep link failed: dl_table {dl_table!r} not available (class {class_id})")
        return None

    if not check_access(*link.extra_requirements):
        current_app.logger.warning(f"LTI deep link failed: dl_link {dl_link!r} access denied (class {class_id})")
        return None

    try:
        item_id = int(content_id)
    except ValueError:
        current_app.logger.warning(f"LTI deep link failed: non-integer content_id {content_id!r} (class {class_id})")
        return None

    item = table.get_item_by_id(item_id)
    if item is None:
        current_app.logger.warning(f"LTI deep link failed: no {dl_table!r} item with id {item_id} in class {class_id}")
        return None

    return link.render_url({'name': item.name})


def _validate_launch() -> LTILaunchData:
    """Read LTI session data, run sanity checks, and return validated launch data."""
    authenticated = session.get("lti_authenticated", False)
    lti_message_type = session.get("lti_message_type")
    raw_role = session.get("roles", "").lower()
    full_name = session.get("lis_person_name_full", None)
    email = session.get("lis_person_contact_email_primary", None)
    lti_user_id = session.get("user_id", "")
    lti_consumer = session.get("oauth_consumer_key", "")
    lti_context_id = session.get("context_id", "")
    class_name = session.get("context_label", "")

    current_app.logger.debug(f"LTI login: {lti_consumer=} {lti_message_type=} {full_name=} {email=} {raw_role=} {class_name=}")

    if not authenticated:
        current_app.logger.warning("LTI login not authenticated.")
        _reject(403)

    if not lti_user_id or not lti_consumer or not lti_context_id or not class_name:
        current_app.logger.warning(f"LTI login missing one of: {lti_user_id=} {lti_consumer=} {lti_context_id=} {class_name=}")
        _reject(400)

    if not full_name and (not email or '@' not in email):
        current_app.logger.warning(f"LTI login missing name or email: {lti_consumer=} {full_name=} {email=}")
        _reject(400, "LTI login missing name and email (at least one required).")

    role: RoleType
    instructor_role_substrs = ["instructor", "teachingassistant"]
    if any(substr in raw_role for substr in instructor_role_substrs):
        role = "instructor"
    else:
        role = "student"

    if lti_message_type == "ContentItemSelectionRequest":
        if role != "instructor":
            current_app.logger.warning("LTI login requests content item selection, but role != 'instructor'")
            _reject(400)
        if 'content_item_return_url' not in session:
            current_app.logger.warning("LTI login requests content item selection, but session does not contain 'content_item_return_url'")
            _reject(400)

    return LTILaunchData(
        lti_user_id=lti_user_id,
        consumer=lti_consumer,
        context_id=lti_context_id,
        class_name=class_name,
        full_name=full_name,
        email=email,
        role=role,
        message_type=lti_message_type,
    )


def _provision_lti_identity(launch: LTILaunchData) -> tuple[int, int]:
    """Get-or-create class, user, and role for an LTI launch. Returns (user_id, class_id)."""
    db = get_db()

    # The consumer must exist: pylti verified the launch signature against the
    # registered consumers, so this key is guaranteed to be present in the table.
    consumer_row = db.execute(
        "SELECT id FROM consumers WHERE lti_consumer=?", [launch.consumer]
    ).fetchone()
    lti_consumer_id: int = consumer_row['id']

    class_id = get_or_create_lti_class(lti_consumer_id, launch.context_id, launch.class_name)

    lti_id = f"{launch.consumer}_{launch.lti_user_id}_{launch.email}"
    user_normed = LoginData(ext_id=lti_id, email=launch.email, full_name=launch.full_name)
    # LTI users given 0 tokens by default -- should only ever use API key registered w/ LTI consumer
    user_row = ext_login_update_or_create('lti', user_normed, query_tokens=0)
    user_id: int = user_row['id']

    role_row = db.execute(
        "SELECT * FROM roles WHERE user_id=? AND class_id=?", [user_id, class_id]
    ).fetchone()

    if not role_row:
        db.execute(
            "INSERT INTO roles(user_id, class_id, role) VALUES(?, ?, ?)",
            [user_id, class_id, launch.role],
        )
        db.commit()
    elif not role_row['active']:
        _reject(403)

    return user_id, class_id


# Handles LTI 1.0/1.1 initial request / login
# https://github.com/mitodl/pylti/blob/master/pylti/flask.py
# https://github.com/mitodl/mit_lti_flask_sample
@bp.route("/", methods=['GET', 'POST'])
@lti_flask(request='initial', error=lti_error)  # type: ignore[untyped-decorator]
def lti_login(lti: LTI) -> Response:  # noqa: ARG001 (unused argument required by lti_flask decorator)
    launch = _validate_launch()

    user_id, class_id = _provision_lti_identity(launch)

    set_session_auth_user(user_id)
    set_session_auth_class(class_id)

    # Handle a deep-link launch (student or instructor opening a saved content
    # item): the LMS re-launches the stored URL, whose query args name the item.
    dl_table = request.args.get('dl_table')
    dl_link = request.args.get('dl_link')
    content_id = request.args.get('content_id')
    if dl_table and dl_link and content_id:
        deep_link_url = _resolve_deep_link(dl_table, dl_link, content_id, class_id)
        if deep_link_url is not None:
            return redirect(deep_link_url)
        # A failed deep link must not silently land the user on an unrelated
        # page: explain what happened on the page they are about to see.
        flash("The linked content could not be opened. It may have been deleted from this class, or a feature that provides it may be disabled.", "warning")

    # Redirect to the app
    if launch.role == "instructor":
        if launch.message_type == "ContentItemSelectionRequest":
            # The selection page reads content_item_return_url from the session
            # (pylti stored it from the OAuth-verified launch).
            return redirect(url_for("class_config.base.lti_content_select"))
        else:
            return redirect(url_for("class_config.base.config_form"))
    else:
        return redirect(url_for(current_app.config['DEFAULT_LOGIN_ENDPOINT']))


@bp.route("/config.xml")
def lti_config() -> tuple[str, int, dict[str, str]]:
    return render_template("lti_config.xml"), 200, {'Content-Type': 'text/xml'}


#@bp.route("debug", methods=['GET'])
#@lti(request='session')
#def lti_debug(lti: LTI):
#    return {var: session[var] for var in session}
