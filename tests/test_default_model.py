from pathlib import Path

import pytest
from flask import Flask

import codehelp
from gened.db import get_db


def test_valid_default_model(app):
    """Test that a valid default model shortname works.

    Uses app fixture to be able to use its initialized database
    when creating a new app for the test.
    """
    # Should work without raising any exceptions
    test_app = codehelp.create_app(
        test_config={
            'TESTING': True,
            'DATABASE': Path(app.instance_path) / 'test.db',
            # Use an existing, active model from schema_common.sql
            'DEFAULT_CLASS_MODEL_SHORTNAME': 'GPT-4o-mini',
        }
    )
    assert isinstance(test_app, Flask)


def test_invalid_model_shortname(app):
    """Test that an invalid model shortname raises an error.

    Uses app fixture to be able to use its initialized database
    when creating a new app for the test.
    """
    with pytest.raises(SystemExit) as exc_info:
        codehelp.create_app(
            test_config={
                'TESTING': True,
                'DATABASE': Path(app.instance_path) / 'test.db',
                'DEFAULT_CLASS_MODEL_SHORTNAME': 'NONEXISTENT-MODEL',
            }
        )
    assert exc_info.value.code == 1


def test_inactive_model_shortname(app):
    """Test that an inactive model shortname raises an error.

    Uses app fixture to be able to use its initialized database
    when creating a new app for the test.
    """
    with pytest.raises(SystemExit) as exc_info:
        codehelp.create_app(
            test_config={
                'TESTING': True,
                'DATABASE': Path(app.instance_path) / 'test.db',
                # GPT-3.5 should be inactive in the database
                'DEFAULT_CLASS_MODEL_SHORTNAME': 'GPT-3.5',
            }
        )
    assert exc_info.value.code == 1


def test_model_used_in_class_creation(app, client, auth):
    """Test that the default model is actually used when creating a new class."""
    # Login and create a class
    auth.login()
    response = client.post(
        "/classes/create/",
        data={'class_name': 'Test Class', 'openai_key': 'test_key'}
    )
    assert response.status_code == 302

    # Check that the class was created with the correct model
    with app.app_context():
        db = get_db()
        model_id = db.execute(
            """SELECT classes_user.model_id, models.shortname
               FROM classes_user
               JOIN models ON classes_user.model_id = models.id
               ORDER BY classes_user.class_id DESC LIMIT 1"""
        ).fetchone()
        assert model_id['shortname'] == app.config['DEFAULT_CLASS_MODEL_SHORTNAME']
