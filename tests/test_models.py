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
        'model': "Primary AI",
    })
    assert response.status_code == 302 # successful redirect

    page = client.get("/profile/")
    assert "own_llm" in page.text
    assert 'own_endpoint' in page.text
    assert 'Primary AI' in page.text

    model = _get_model_by_shortname(app, "own_llm")

    edit_page = client.get(f"models/edit/{model['id']}")
    assert "own_llm" in edit_page.text
    assert 'own_endpoint' in edit_page.text
    assert 'Primary AI' in edit_page.text

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
    client.login(username="testadmin", password="testadminpassword")

    response = client.get("/profile/")
    assert "shortname" not in response.text
    assert "model" not in response.text
    assert "custom_endpoint" not in response.text
    assert "Add custom model" not in response.text

    response = client.post("/classes/create/", data={
        'class_name': "Algorithms and Data Structures",
        'llm_api_key': 'none',
    })
    assert response.status_code == 302

    response = client.get("/profile/")
    assert "shortname" in response.text
    assert "model" in response.text
    assert "custom_endpoint" in response.text
    assert "Add custom model" in response.text
