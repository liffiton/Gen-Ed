# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterator

import pytest
from flask import Flask, session

from components.code_contexts.config_table import contexts_config_table
from components.code_contexts.data import ITEM_TYPE as CONTEXT_ITEM_TYPE
from components.code_contexts.model import ContextConfig
from gened.auth import AUTH_SESSION_KEY
from gened.db import get_db
from tests.conftest import AppClient


@pytest.fixture
def class2_request_ctx(app: Flask) -> Iterator[None]:
    """Provides a request context with auth set to class 2, user 11."""
    with app.test_request_context():
        session[AUTH_SESSION_KEY] = {'user_id': 11, 'class_id': 2}
        yield



def test_class_config_view(instructor: AppClient) -> None:
    """Tests that the class config page loads and displays expected sections."""
    response = instructor.get('/instructor/config/')
    assert response.status_code == 200

    # default instructor client is logged in with class '' active
    assert "Configure Class: USER001" in response.text
    for header in ("Access", "Language Model", "Contexts"):
        assert f"{header}</h2>" in response.text


@pytest.mark.usefixtures('class2_request_ctx')
def test_get_items_available_only_filters_by_date() -> None:
    """Tests that get_items(available_only=True) filters out future-dated contexts."""
    # All baseline contexts have past dates, so all should be returned
    available = contexts_config_table.get_items(available_only=True)
    assert len(available) == 4

    # Create a context with a future available date
    db = get_db()
    db.execute(
        "INSERT INTO config_items (class_id, item_type, name, class_order, available, config) VALUES (?, ?, ?, ?, ?, ?)",
        [2, CONTEXT_ITEM_TYPE, 'future_context', 10, '9999-12-31', '{"tools":"","details":"","avoid":""}'],
    )

    # get_items() without filter should return 5
    all_items = contexts_config_table.get_items()
    assert len(all_items) == 5

    # get_items(available_only=True) should still return 4 (future context filtered out)
    available = contexts_config_table.get_items(available_only=True)
    assert len(available) == 4
    assert all(item.name != 'future_context' for item in available)


@pytest.mark.usefixtures('class2_request_ctx')
def test_get_item_by_name_returns_context() -> None:
    """Tests that get_item_by_name() returns the correct context."""
    ctx_item = contexts_config_table.get_item_by_name('default2')
    assert ctx_item is not None
    assert isinstance(ctx_item, ContextConfig)
    assert ctx_item.name == 'default2'
    assert ctx_item.row_id == 6
    assert ctx_item.tools == 'Python2'
    assert ctx_item.avoid == 'avoid2'


@pytest.mark.usefixtures('class2_request_ctx')
def test_get_item_by_name_returns_none_for_wrong_class() -> None:
    """Tests that get_item_by_name() does not return contexts from other classes."""
    # Create a context unique to class 1 and verify it's not returned when class 2 is active.
    db = get_db()
    db.execute(
        "INSERT INTO config_items (class_id, item_type, name, class_order, available, config) VALUES (?, ?, ?, ?, ?, ?)",
        [1, CONTEXT_ITEM_TYPE, 'class1_only', 0, '0001-01-01', '{"tools":"","details":"","avoid":""}'],
    )

    result = contexts_config_table.get_item_by_name('class1_only')
    assert result is None


@pytest.mark.usefixtures('class2_request_ctx')
def test_get_item_by_id_returns_none_for_wrong_class() -> None:
    """Tests that get_item_by_id() does not return contexts from other classes."""
    # Context id=1 belongs to class 1, but active class is 2
    result = contexts_config_table.get_item_by_id(1)
    assert result is None


COPY_URL = '/instructor/config/table/context/copy_from_course'


def test_copy_from_course_copies_selected_items(instructor: AppClient, app: Flask) -> None:
    """Tests that copy_from_course copies only the selected items, renaming duplicates."""
    response = instructor.post(
        COPY_URL,
        data={'source_class_id': '3', 'selected_items': ['3']},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Successfully copied 1 item(s) from 'USER002'." in response.text

    # class 2 starts with 4 contexts (default, default1, default2, default3)
    with app.app_context():
        db = get_db()
        items = db.execute(
            "SELECT name FROM config_items WHERE class_id=2 AND item_type='context' ORDER BY class_order, id"
        ).fetchall()
    assert len(items) == 5
    # 'default' already exists in class 2, so the copied item is renamed
    assert items[-1]['name'] == 'default (1)'


def test_copy_from_course_ignores_ids_not_in_source_course(instructor: AppClient, app: Flask) -> None:
    """Tests that submitted item ids not belonging to the source course are ignored."""
    # id 4 belongs to class 4, not to the source course (class 3)
    response = instructor.post(
        COPY_URL,
        data={'source_class_id': '3', 'selected_items': ['3', '4']},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Successfully copied 1 item(s) from 'USER002'." in response.text

    with app.app_context():
        db = get_db()
        count = db.execute(
            "SELECT COUNT(*) AS n FROM config_items WHERE class_id=2 AND item_type='context'"
        ).fetchone()['n']
    assert count == 5


def test_copy_from_course_empty_selection(instructor: AppClient, app: Flask) -> None:
    """Tests that submitting no selected items flashes a warning and copies nothing."""
    response = instructor.post(
        COPY_URL,
        data={'source_class_id': '3'},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "No contexts selected to copy from 'USER002'." in response.text

    with app.app_context():
        db = get_db()
        count = db.execute(
            "SELECT COUNT(*) AS n FROM config_items WHERE class_id=2 AND item_type='context'"
        ).fetchone()['n']
    assert count == 4


def test_copy_from_course_non_instructor_source_aborts(instructor: AppClient) -> None:
    """Tests that copying from a course where the user is not an instructor is rejected."""
    response = instructor.post(
        COPY_URL,
        data={'source_class_id': '1', 'selected_items': ['1']},
    )
    assert response.status_code == 403


def test_copy_modal_hides_courses_with_inactive_role(instructor: AppClient, app: Flask) -> None:
    """Tests that courses where the user's instructor role is inactive are not offered for copying."""
    with app.app_context():
        db = get_db()
        db.execute("UPDATE roles SET active=0 WHERE id=8")  # testuser's instructor role in class 4 (USER003)
        db.commit()

    response = instructor.get('/instructor/config/')
    assert response.status_code == 200
    assert 'USER002' in response.text  # class 3: still an active instructor role
    assert 'USER003' not in response.text  # class 4: role deactivated



