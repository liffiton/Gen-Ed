# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for tutors component serialization and data models."""

import json
from dataclasses import asdict

from flask import Flask
from werkzeug.datastructures import ImmutableMultiDict

from components.tutors.data import ChatData, fmt_analysis
from components.tutors.guided import LearningObjective, TutorConfig
from gened.db import get_db
from tests.conftest import AppClient


def test_chat_data_roundtrip() -> None:
    """Test serializing and deserializing ChatData with various edge cases."""
    # Test with all fields including complex nested structures
    original = ChatData(
        id=1,
        user_id=11,
        user_json='{"display_name": "Test User"}',
        class_id=5,
        topic="Test topic with special chars: <>&'",
        context_name="ctx1",
        messages=[
            {'role': 'system', 'content': 'You are a tutor'},
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there'}
        ],
        usages=[{'prompt_tokens': 10, 'completion_tokens': 20}, {'prompt_tokens': 15, 'completion_tokens': 25}],
        mode="guided",
        analysis={'summary': 'test', 'progress': [{'objective': 'Vars', 'status': 'completed'}]}
    )
    # Serialize
    json_str = json.dumps(asdict(original))
    # Deserialize
    data = json.loads(json_str)
    restored = ChatData(**data)
    # Verify all fields match
    assert restored == original
    assert restored.topic == original.topic
    assert restored.messages == original.messages
    assert restored.usages == original.usages
    assert restored.analysis == original.analysis

    # Test with empty strings and special values
    minimal = ChatData(
        id=2,
        user_id=12,
        topic="",
        messages=[],
        mode="inquiry"
    )
    json_str2 = json.dumps(asdict(minimal))
    data2 = json.loads(json_str2)
    restored2 = ChatData(**data2)
    assert restored2 == minimal
    assert restored2.topic == ""
    assert restored2.messages == []


def test_tutor_config_roundtrip() -> None:
    """Test serializing and deserializing TutorConfig."""
    original = TutorConfig(
        name="Python Basics",
        topic="Introduction to Python",
        context="Learning context",
        document_filename="notes.txt",
        document_text="Some notes",
        objectives=[
            LearningObjective(name="Variables", questions=["What is a variable?", "How to use variables?"]),
            LearningObjective(name="Functions", questions=["How do you define a function?"])
        ]
    )
    # Serialize using to_json (from ConfigItem)
    json_str = original.to_json()
    # Deserialize
    data = json.loads(json_str)
    data['name'] = "Python Basics"
    # Convert dict objectives to LearningObjective objects (as from_row does)
    if data.get('objectives'):
        data['objectives'] = [LearningObjective(**obj) for obj in data['objectives']]
    restored = TutorConfig(**data)
    # Verify all fields match
    assert restored == original
    assert restored.document_filename == original.document_filename
    assert restored.document_text == original.document_text

    # Test with empty objectives
    minimal = TutorConfig(name="Minimal", topic="Test", objectives=[])
    json_str2 = minimal.to_json()
    data2 = json.loads(json_str2)
    data2['name'] = "Minimal"
    data2['objectives'] = []
    restored2 = TutorConfig(**data2)
    assert restored2 == minimal


def test_tutor_config_from_request_form() -> None:
    """Test creating TutorConfig from request form."""
    form = ImmutableMultiDict([
        ('name', 'Python Basics'),
        ('topic', 'Introduction to Python'),
        ('context', 'Learning context'),
        ('objectives', 'Variables'),
        ('objectives', 'Functions'),
        ('questions[0]', 'What is a variable?'),
        ('questions[0]', 'How do you use variables?'),
        ('questions[1]', 'How do you define a function?'),
    ])

    config = TutorConfig.from_request_form(form)

    assert config.name == "Python Basics"
    assert config.topic == "Introduction to Python"
    assert len(config.objectives) == 2
    assert config.objectives[0].name == "Variables"
    assert config.objectives[0].questions == ['What is a variable?', 'How do you use variables?']
    assert config.objectives[1].name == "Functions"
    assert config.objectives[1].questions == ['How do you define a function?']


def test_read_chat_from_database(client: AppClient) -> None:
    """Test reading chat data from the database via HTTP request."""
    # Login to set up auth context
    client.login('testuser', 'testpassword')
    # Chat ID 1 exists in test_data.sql
    # Access it via the chat interface
    response = client.get('/tutor/1')
    assert response.status_code == 200
    # Verify the chat content is rendered
    assert 'topic1' in response.text
    assert 'user_msg_1' in response.text
    assert 'assistant_msg_1' in response.text


def test_read_chat_with_analysis_from_database(app: Flask, client: AppClient) -> None:
    """Test reading chat with analysis data from database."""
    # Insert a chat with analysis data
    with app.app_context():
        db = get_db()
        chat_json = {
            "topic": "Python Basics",
            "mode": "guided",
            "messages": [
                {"role": "system", "content": "You are a tutor"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ],
            "usages": [{"prompt_tokens": 10, "completion_tokens": 20}],
            "analysis": {
                "summary": "Student progressing well",
                "progress": [
                    {"objective": "Variables", "status": "completed"}
                ]
            }
        }
        db.execute(
            "INSERT INTO chats (chat_json, user_id, role_id) VALUES (?, ?, ?)",
            [json.dumps(chat_json), 11, 4]
        )
        db.commit()
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Access via HTTP request
    client.login('testuser', 'testpassword')
    response = client.get(f'/tutor/{new_id}')
    assert response.status_code == 200
    assert 'Python Basics' in response.text
    # Verify analysis data is present
    assert 'Variables' in response.text
    assert 'completed' in response.text


def test_fmt_analysis_valid() -> None:
    """Test fmt_analysis with valid analysis JSON."""
    analysis_json = '''{
        "summary": "Student is progressing well",
        "progress": [
            {"objective": "Variables", "status": "completed"},
            {"objective": "Functions", "status": "completed"},
            {"objective": "Loops", "status": "in progress"},
            {"objective": "Recursion", "status": "not started"}
        ]
    }'''
    result = fmt_analysis(analysis_json)
    # Should contain tags for each status
    result_str = str(result)
    assert "tag" in result_str
    # Should not contain "parse error"
    assert "parse error" not in result_str


def test_fmt_analysis_invalid_json(app: Flask) -> None:
    """Test fmt_analysis with invalid JSON."""
    invalid_json = 'not valid json'
    with app.app_context():
        assert fmt_analysis(invalid_json) == "parse error"

    invalid_json = '{"summary": "test"}'
    with app.app_context():
        assert fmt_analysis(invalid_json) == "parse error"


def test_chat_save_and_retrieve(app: Flask, client: AppClient) -> None:
    """Test saving a ChatData object and retrieving it."""
    # Login to set up auth context
    client.login('testuser', 'testpassword')

    # Create and save a ChatData object
    original = ChatData(
        user_id=11,
        topic="Test Save and Retrieve",
        mode="inquiry",
        messages=[
            {"role": "system", "content": "You are a helpful tutor"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
    )

    # Insert into database
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO chats (chat_json, user_id, role_id) VALUES (?, ?, ?)",
            [json.dumps(asdict(original)), 11, 4]
        )
        db.commit()
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        original.id = new_id

    # Retrieve via HTTP request
    response = client.get(f'/tutor/{new_id}')
    assert response.status_code == 200
    assert 'Test Save and Retrieve' in response.text
    assert 'You are a helpful tutor' not in response.text
    assert 'Hello' in response.text
    assert 'Hi there' in response.text
