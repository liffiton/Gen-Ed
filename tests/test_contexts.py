from sqlite3 import Row

import pytest
from flask import Flask
from flask.testing import FlaskClient

from gened.db import get_db
from tests.conftest import AuthActions


def _get_context_by_name(app: Flask, name: str) -> Row:
    with app.app_context():
        db = get_db()
        context: Row | None = db.execute("SELECT * FROM contexts WHERE name = ?", [name]).fetchone()
        assert context is not None
        return context


def test_create_context_saves_to_db(app: Flask, instructor: tuple[FlaskClient, AuthActions]) -> None:
    """Tests that creating a context saves its name and config to the database."""
    client, auth = instructor

    response = client.post('/instructor/context/create', data={
        'name': 'Test Context',
        'tools': 'ABC',
        'details': 'XYZ',
        'avoid': '123',
    })

    assert response.status_code == 302  # Redirect after successful creation
    context = _get_context_by_name(app, 'Test Context')
    assert context['config'] == '{"tools": "ABC", "details": "XYZ", "avoid": "123"}'


def test_update_context_saves_changes_to_db(app: Flask, instructor: tuple[FlaskClient, AuthActions]) -> None:
    """Tests that updating a context correctly changes its data in the database."""
    client, auth = instructor

    # First, create a context to be updated
    client.post('/instructor/context/create', data={
        'name': 'Update Test Context',
    })
    context = _get_context_by_name(app, 'Update Test Context')
    context_id = context['id']

    response = client.post(f'/instructor/context/update/{context_id}', data={
        'name': 'Updated Context',
        'tools': 'ABC',
        'details': 'XYZ',
        'avoid': '123',
    })
    assert response.status_code == 302  # Redirect after successful update

    with app.app_context():
        db = get_db()
        updated_context = db.execute("SELECT * FROM contexts WHERE id = ?", (context_id,)).fetchone()
        assert updated_context is not None
        assert updated_context['name'] == 'Updated Context'
        assert updated_context['config'] == '{"tools": "ABC", "details": "XYZ", "avoid": "123"}'


def test_delete_context_removes_from_db(app: Flask, instructor: tuple[FlaskClient, AuthActions]) -> None:
    """Tests that deleting a context removes it from the database."""
    client, auth = instructor

    # First, create a context to be deleted
    client.post('/instructor/context/create', data={
        'name': 'Delete Test Context',
    })
    context = _get_context_by_name(app, 'Delete Test Context')
    context_id = context['id']

    response = client.post(f'/instructor/context/delete/{context_id}')
    assert response.status_code == 302  # Redirect after successful deletion

    with app.app_context():
        db = get_db()
        deleted_context = db.execute("SELECT * FROM contexts WHERE id = ?", (context_id,)).fetchone()
        assert deleted_context is None


@pytest.mark.parametrize('path', [
    '/instructor/context/new',
    '/instructor/context/edit/1',
])
def test_context_pages_require_login(client: FlaskClient, path: str) -> None:
    """Tests that context management pages redirect to login if the user is not authenticated."""
    response = client.get(path)

    assert response.status_code == 302
    assert response.headers['Location'].startswith('/auth/login')


def test_context_pages_require_instructor_role(client: FlaskClient, auth: AuthActions) -> None:
    """Tests that a non-instructor user is redirected from context management pages."""
    # Log in as a regular user (not an instructor)
    auth.login(username='testuser2', password='testuser2password')

    response = client.get('/instructor/context/new')

    assert response.status_code == 302
    assert response.headers['Location'].startswith('/auth/login')


def test_newly_created_contexts_appear_on_config_page(instructor: tuple[FlaskClient, AuthActions]) -> None:
    """Tests that newly created contexts are listed on the main instructor config page."""
    client, auth = instructor

    # Load the config page initially
    response = client.get('/instructor/config/')

    # Check that default contexts are present and new ones are not
    assert response.status_code == 200
    assert b'default1' in response.data
    assert b'default2' in response.data
    assert b'default3' in response.data
    assert b'Context 1' not in response.data
    assert b'Context 2' not in response.data
    assert b'Context 3' not in response.data

    # Create a few new contexts
    client.post('/instructor/context/create', data={'name': 'Context 1'})
    client.post('/instructor/context/create', data={'name': 'Context 2'})
    client.post('/instructor/context/create', data={'name': 'Context 3'})

    # Reload the config page
    response = client.get('/instructor/config/')

    # Check that the new contexts are now displayed
    assert response.status_code == 200
    assert b'Context 1' in response.data
    assert b'Context 2' in response.data
    assert b'Context 3' in response.data
