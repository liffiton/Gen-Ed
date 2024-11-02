from pathlib import Path


def test_well_known_file(client, app):
    """Test serving an existing file from .well-known"""
    # Create a test file in the instance/.well-known directory
    well_known_dir = Path(app.instance_path) / '.well-known'
    well_known_dir.mkdir(exist_ok=True)
    test_file = well_known_dir / 'test.txt'
    test_file.write_text('test content')

    # Request the file
    response = client.get('/.well-known/test.txt')

    assert response.status_code == 200
    assert response.data == b'test content'


def test_well_known_missing(client):
    """Test requesting a non-existent file from .well-known"""
    response = client.get('/.well-known/nonexistent.txt')
    assert response.status_code == 404


def test_well_known_subdir(client, app):
    """Test serving a file from a subdirectory in .well-known"""
    # Create a test file in a subdirectory
    well_known_dir = Path(app.instance_path) / '.well-known'
    subdir = well_known_dir / 'subdir'
    subdir.mkdir(parents=True, exist_ok=True)
    test_file = subdir / 'test.txt'
    test_file.write_text('subdir test content')

    # Request the file
    response = client.get('/.well-known/subdir/test.txt')

    assert response.status_code == 200
    assert response.data == b'subdir test content'


def test_well_known_traversal(client, app):
    """Test that path traversal attempts are blocked"""
    # Create a file in the instance directory (parent of .well-known)
    secret_file = Path(app.instance_path) / 'secret.txt'
    secret_file.write_text('secret content')

    # Attempt to access the file through path traversal
    response = client.get('/.well-known/../secret.txt')
    assert response.status_code == 404

    # Verify the file exists and is readable directly from disk
    assert secret_file.exists()
    assert secret_file.read_text() == 'secret content'
