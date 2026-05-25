# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for gened.app_data, focusing on the _get_data_row() access control logic.

These tests exercise _get_data_row() through the existing /help/view/<id> route,
which calls queries_data_source.get_row() → _get_data_row() internally.

The test data has these relevant users:
  user 11 (testuser):       password=testpassword,       instructor in class 2 (role 4)
  user 12 (testadmin):      password=testadminpassword,   admin, student in class 2 (role 5)
  user 13 (testinstructor): password=testinstructorpassword, student in class 2 (role 6)

code_queries relevant to these tests:
  id=5: user_id=13 (testinstructor), role_id=6 → class_id=2
  id=8: user_id=11 (testuser),       role_id=4 → class_id=2
  id=1: user_id=21 (ltiuser1),       role_id=1 → class_id=1
"""

import datetime as dt
import sqlite3
from unittest.mock import MagicMock, patch

from gened.app_data import DataSource
from gened.tables import DataTableSpec, NumCol
from tests.conftest import AppClient

# ── Helpers ──────────────────────────────────────────────────────────────────


_ALL_QUERY_COLS = [
    "id",
    "user",
    "time",
    "context",
    "code",
    "error",
    "issue",
    "response",
    "helpful",
    "rating",
    "user_id",
    "context_string_id",
    "class_id",
    "topics_json",
]


def _build_mock_row(**fields: str | int | None | dt.datetime) -> MagicMock:
    """Build a mock sqlite3.Row with the given fields.

    The mock supports both key-based and index-based access, matching the
    behavior of real sqlite3.Row objects.

    Note: spec=sqlite3.Row causes __len__ to return 0 by default (since Row
    defines __len__), which makes bool(row) == False.  We override __len__ so
    that truthiness checks (``if not row:``) work correctly.
    """
    field_list = list(fields.keys())

    row = MagicMock(spec=sqlite3.Row)
    row.__getitem__.side_effect = lambda key: (
        fields[key] if isinstance(key, str) else fields[field_list[key]]
    )
    row.keys.return_value = field_list
    row.__len__.return_value = len(field_list)
    return row


def _make_query_mock_row(**overrides: str | int | None | dt.datetime) -> MagicMock:
    """Create a mock row with all columns expected by help_view."""
    fields: dict[str, str | int | None | dt.datetime] = {
        "id": 100,
        "user": '["testuser","local",""]',
        "time": dt.datetime(2024, 1, 1, 12, 0, 0),
        "context": "ctx1",
        "code": "some code",
        "error": "some error",
        "issue": "some issue",
        "response": '{"main": "test response"}',
        "helpful": 0,
        "rating": None,
        "user_id": 11,
        "context_string_id": 1,
        "class_id": 2,
        "topics_json": None,
    }
    fields.update(overrides)
    return _build_mock_row(**fields)


def _make_mock_ds(mock_row: MagicMock) -> DataSource:
    """Create a DataSource backed by a mock row, handling both get_row and get_user_data calls."""
    mock_cursor = MagicMock(spec=sqlite3.Cursor)
    mock_cursor.fetchone.side_effect = [mock_row, None]
    mock_cursor.fetchall.return_value = [mock_row]

    def fake_get_data(
        filters: object = None, /, limit: int = -1, offset: int = 0  # noqa: ARG001 -- need to match existing interface
    ) -> object:
        return mock_cursor

    spec = DataTableSpec(
        columns=[NumCol(c) for c in _ALL_QUERY_COLS],
    )
    return DataSource(
        table_name="test",
        display_name="test",
        get_data=fake_get_data,  # type: ignore[arg-type]
        table_spec=spec,
    )


# ── Integration tests through /help/view/<id> (real data) ────────────────────


def test_owner_views_own_query(client: AppClient) -> None:
    """Row owner can access their own data via the help view route."""
    client.login("testuser", "testpassword")
    client.get("/classes/switch/2")
    response = client.get("/help/view/8")

    assert response.status_code == 200
    assert "code21" in response.text


def test_instructor_views_student_query_in_same_class(instructor: AppClient) -> None:
    """Instructor can view a student's query in their class."""
    response = instructor.get("/help/view/5")

    assert response.status_code == 200
    assert "code11" in response.text


def test_admin_views_any_query(client: AppClient) -> None:
    """Admin can view any user's query regardless of class."""
    client.login("testadmin", "testadminpassword")
    response = client.get("/help/view/1")

    assert response.status_code == 200
    assert "code01" in response.text


def test_student_cannot_view_other_student_query_in_same_class(
    client: AppClient,
) -> None:
    """Student cannot view another student's query in the same class."""
    client.login("testinstructor", "testinstructorpassword")
    client.get("/classes/switch/2")
    response = client.get("/help/view/8")

    assert response.status_code == 400
    assert "Invalid id" in response.text


def test_student_cannot_view_query_from_different_class(client: AppClient) -> None:
    """Student cannot view a query from a different class."""
    client.login("testinstructor", "testinstructorpassword")
    client.get("/classes/switch/2")
    response = client.get("/help/view/1")

    assert response.status_code == 400
    assert "Invalid id" in response.text


def test_nonexistent_query_returns_error(client: AppClient) -> None:
    """Accessing a non-existent query returns an error."""
    client.login("testuser", "testpassword")
    response = client.get("/help/view/99999")

    assert response.status_code == 400
    assert "Invalid id" in response.text


# ── Mock-based tests: patch queries_data_source in code_queries.helper ───────


def test_get_data_row_owner_can_access(client: AppClient) -> None:
    """_get_data_row: owner (matching user_id) can access the row."""
    mock_row = _make_query_mock_row(user_id=11, class_id=2)
    mock_ds = _make_mock_ds(mock_row)

    client.login("testuser", "testpassword")
    client.get("/classes/switch/2")
    with patch("components.code_queries.helper.queries_data_source", mock_ds):
        response = client.get("/help/view/100")

    assert response.status_code == 200


def test_get_data_row_instructor_can_access(instructor: AppClient) -> None:
    """_get_data_row: instructor in matching class can access another user's row."""
    mock_row = _make_query_mock_row(user_id=13, class_id=2)
    mock_ds = _make_mock_ds(mock_row)

    with patch("components.code_queries.helper.queries_data_source", mock_ds):
        response = instructor.get("/help/view/100")

    assert response.status_code == 200


def test_get_data_row_admin_can_access(client: AppClient) -> None:
    """_get_data_row: admin can access any row regardless of ownership."""
    mock_row = _make_query_mock_row(user_id=21, class_id=1)
    mock_ds = _make_mock_ds(mock_row)

    client.login("testadmin", "testadminpassword")
    with patch("components.code_queries.helper.queries_data_source", mock_ds):
        response = client.get("/help/view/100")

    assert response.status_code == 200


def test_get_data_row_same_class_student_denied(client: AppClient) -> None:
    """_get_data_row: student cannot access another student's row in same class."""
    mock_row = _make_query_mock_row(user_id=11, class_id=2)
    mock_ds = _make_mock_ds(mock_row)

    client.login("testinstructor", "testinstructorpassword")
    client.get("/classes/switch/2")
    with patch("components.code_queries.helper.queries_data_source", mock_ds):
        response = client.get("/help/view/100")

    assert response.status_code == 400
    assert "Invalid id" in response.text


def test_get_data_row_cross_class_student_denied(client: AppClient) -> None:
    """_get_data_row: student cannot access a row from a different class."""
    mock_row = _make_query_mock_row(user_id=21, class_id=1)
    mock_ds = _make_mock_ds(mock_row)

    client.login("testinstructor", "testinstructorpassword")
    client.get("/classes/switch/2")
    with patch("components.code_queries.helper.queries_data_source", mock_ds):
        response = client.get("/help/view/100")

    assert response.status_code == 400
    assert "Invalid id" in response.text


def test_get_data_row_not_found(client: AppClient) -> None:
    """_get_data_row: non-existent row returns RowNotFoundError."""
    mock_cursor = MagicMock(spec=sqlite3.Cursor)
    mock_cursor.fetchone.side_effect = [None, None]
    mock_cursor.fetchall.return_value = []

    def empty_get_data(
        filters: object = None, /, limit: int = -1, offset: int = 0  # noqa: ARG001 -- need to match existing interface
    ) -> object:
        return mock_cursor

    mock_ds = DataSource(
        table_name="test",
        display_name="test",
        get_data=empty_get_data,  # type: ignore[arg-type]
        table_spec=DataTableSpec(columns=[NumCol(c) for c in _ALL_QUERY_COLS]),
    )

    client.login("testuser", "testpassword")
    with patch("components.code_queries.helper.queries_data_source", mock_ds):
        response = client.get("/help/view/99999")

    assert response.status_code == 400
    assert "Invalid id" in response.text


def test_get_data_row_no_current_class(client: AppClient) -> None:
    """_get_data_row: user with no current class is denied (not owner, not admin)."""
    mock_row = _make_query_mock_row(user_id=11, class_id=2)
    mock_ds = _make_mock_ds(mock_row)

    # testuser2 (user 14) has no role in any class → cur_class is None
    client.login("testuser2", "testuser2password")
    with patch("components.code_queries.helper.queries_data_source", mock_ds):
        response = client.get("/help/view/100")

    assert response.status_code == 400
    assert "Invalid id" in response.text


def test_get_data_row_owner_no_current_class(client: AppClient) -> None:
    """_get_data_row: owner can access their own row even with no current class."""
    mock_row = _make_query_mock_row(user_id=14, class_id=2)
    mock_ds = _make_mock_ds(mock_row)

    # testuser2 (user 14) has no role in any class, but owns this row
    client.login("testuser2", "testuser2password")
    with patch("components.code_queries.helper.queries_data_source", mock_ds):
        response = client.get("/help/view/100")

    assert response.status_code == 200


def test_get_data_row_instructor_from_different_class(instructor: AppClient) -> None:
    """_get_data_row: instructor in one class cannot see rows from another class."""
    mock_row = _make_query_mock_row(user_id=13, class_id=1)
    mock_ds = _make_mock_ds(mock_row)

    # testuser (user 11) is instructor in class 2, not class 1
    with patch("components.code_queries.helper.queries_data_source", mock_ds):
        response = instructor.get("/help/view/100")

    assert response.status_code == 400
    assert "Invalid id" in response.text
