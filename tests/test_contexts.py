import pytest
from gened.db import get_db


def test_create_context(app, client, auth):
    auth.login()
    response = client.get('/classes/switch/2')  # switch to class 2 (where this user is an instructor)

    response = client.post('/instructor/context/create', data={
        'name': 'Test Context',
        'tools': 'ABC',
        'details': 'XYZ',
        'avoid': '123',
    })
    assert response.status_code == 302  # Redirect after successful creation

    with app.app_context():
        db = get_db()
        context = db.execute("SELECT * FROM contexts WHERE name = 'Test Context'").fetchone()
        assert context is not None
        assert context['config'] == '{"tools": "ABC", "details": "XYZ", "avoid": "123"}'


def test_update_context(app, client, auth):
    auth.login()
    response = client.get('/classes/switch/2')  # switch to class 2 (where this user is an instructor)

    # First, create a context
    client.post('/instructor/context/create', data={
        'name': 'Update Test Context',
    })
    
    with app.app_context():
        # Get the id of the created context
        db = get_db()
        context = db.execute("SELECT id FROM contexts WHERE name = 'Update Test Context'").fetchone()
        assert context is not None
        context_id = context['id']

    # Now update the context
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
        assert updated_context['name'] == 'Updated Context'
        assert updated_context['config'] == '{"tools": "ABC", "details": "XYZ", "avoid": "123"}'


def test_delete_context(app, client, auth):
    auth.login()
    response = client.get('/classes/switch/2')  # switch to class 2 (where this user is an instructor)

    # First, create a context
    client.post('/instructor/context/create', data={
        'name': 'Delete Test Context',
    })
    
    with app.app_context():
        # Get the id of the created context
        db = get_db()
        context = db.execute("SELECT id FROM contexts WHERE name = 'Delete Test Context'").fetchone()
        assert context is not None
        context_id = context['id']

    # Now delete the context
    response = client.post(f'/instructor/context/delete/{context_id}')
    assert response.status_code == 302  # Redirect after successful deletion

    with app.app_context():
        db = get_db()
        deleted_context = db.execute("SELECT * FROM contexts WHERE id = ?", (context_id,)).fetchone()
        assert deleted_context is None


@pytest.mark.parametrize('path', (
    '/instructor/context/new',
    '/instructor/context/edit/1',
))
def test_login_required(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers['Location'].startswith('/auth/login')


def test_instructor_required(client, auth):
    auth.login(username='testuser2', password='testuser2password')
    response = client.get('/instructor/context/new')
    assert response.status_code == 302
    assert response.headers['Location'].startswith('/auth/login')


def test_context_list_display(client, auth):
    auth.login()
    response = client.get('/classes/switch/2')  # switch to class 2 (where this user is an instructor)

    # Check if existing contexts are displayed on the config page
    response = client.get('/instructor/config/')
    assert response.status_code == 200
    assert b'default1' in response.data
    assert b'default2' in response.data
    assert b'default3' in response.data
    # Check if to-be-added are *not* displayed on the config page
    assert b'Context 1' not in response.data
    assert b'Context 2' not in response.data
    assert b'Context 3' not in response.data

    # Create a few contexts
    client.post('/instructor/context/create', data={'name': 'Context 1'})
    client.post('/instructor/context/create', data={'name': 'Context 2'})
    client.post('/instructor/context/create', data={'name': 'Context 3'})

    # Check if they're displayed on the config page
    response = client.get('/instructor/config/')
    assert response.status_code == 200
    assert b'Context 1' in response.data
    assert b'Context 2' in response.data
    assert b'Context 3' in response.data
