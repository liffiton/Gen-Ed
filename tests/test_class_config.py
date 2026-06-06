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



