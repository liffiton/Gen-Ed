from sqlite3 import Row

from flask import Flask

from gened.db import get_db
from tests.conftest import AppClient


def _get_model_by_shortname(app: Flask, name: str) -> Row:
    with app.app_context():
        db = get_db()
        model: Row | None = db.execute("SELECT * FROM models WHERE shortname = ?", [name]).fetchone()
        assert model is not None
        return model

def test_model_creates(app: Flask, client: AppClient) -> None:
    client.login()
    response = client.post("models/create", data={
        'shortname': "own_llm",
        'custom_endpoint': 'own_endpoint',
        'model': "own_model",
    })
    assert response.status_code == 302 # successful redirect

    # verify model shows up in profile
    response = client.get("/profile/")
    assert 'own_llm' in response.text
    assert 'own_endpoint' in response.text
    assert 'own_model' in response.text

    # verify model shows up in class configuration screen (as option)
    client.get("/classes/switch/2")  # switch to class the current user created
    config_response = client.get("/instructor/config/")
    assert config_response.status_code == 200
    assert 'Custom own_llm' in config_response.text

    # verify edit response populates with model details
    model = _get_model_by_shortname(app, "own_llm")
    edit_response = client.get(f"models/edit/{model['id']}")
    assert edit_response.status_code == 200
    assert 'own_llm' in edit_response.text
    assert 'own_endpoint' in edit_response.text
    assert 'own_model' in edit_response.text

    # verify model does *not* show up in class configuration screen for another user
    client.logout()
    client.login('testadmin', 'testadminpassword')
    client.get("/classes/switch/5")  # switch to class the current user created
    config_response2 = client.get("/instructor/config/")
    assert config_response2.status_code == 200
    assert 'own_llm' not in config_response2.text

def test_model_handle_duplicate(client: AppClient) -> None:
    client.login()
    response = client.post("models/create", data={
        'shortname': 'Ollama',
        'custom_endpoint': 'ollama_endpoint',
        'model': 'meta',
    })
    assert response.status_code == 302
    response = client.get("/profile/")

    assert "Ollama" in response.text
    assert "Ollama (1)" not in response.text

    response = client.post("models/create", data={
        'shortname': 'Ollama',
        'custom_endpoint': 'ollama_endpoint',
        'model': 'meta',
    })
    assert response.status_code == 302
    response = client.get("/profile/")

    assert "Ollama" in response.text
    assert "Ollama (1)" in response.text

def test_display_models_after_created_class(client: AppClient) -> None:
    client.login(username="testinstructor", password="testinstructorpassword")

    response = client.get("/profile/")
    assert "Additional Models" not in response.text
    assert "model" not in response.text
    assert "endpoint" not in response.text
    assert "Add custom model" not in response.text

    response = client.post("/classes/create/", data={
        'class_name': "Algorithms and Data Structures",
        'llm_api_key': 'none',
    })
    assert response.status_code == 302

    response = client.get("/profile/")
    assert "Additional Models" in response.text
    assert "model" in response.text
    assert "endpoint" in response.text
    assert "Add custom model" in response.text
