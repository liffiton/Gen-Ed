# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

import pytest

from gened.docs import DocParsingError, Document, _parse_frontmatter, _process_doc


def test_parse_frontmatter_standard(tmp_path: Path) -> None:
    doc_path = tmp_path / "test.md"
    doc_path.write_text(
        "---\n"
        "title: Simple Page\n"
        "summary: A simple summary\n"
        "category: Getting Started\n"
        "---\n"
        "\n"
        "# Simple Page\n"
        "Hello World\n",
        encoding="utf-8"
    )

    parsed = _parse_frontmatter(doc_path)
    assert parsed.metadata == {
        "title": "Simple Page",
        "summary": "A simple summary",
        "category": "Getting Started"
    }
    assert parsed.content.strip() == "# Simple Page\nHello World"


def test_parse_frontmatter_no_frontmatter(tmp_path: Path) -> None:
    doc_path = tmp_path / "no_fm.md"
    doc_path.write_text("# Hello World\nNo frontmatter here.", encoding="utf-8")

    with pytest.raises(DocParsingError):
        _parse_frontmatter(doc_path)


def test_parse_frontmatter_missing_closing_marker(tmp_path: Path) -> None:
    doc_path = tmp_path / "missing_marker.md"
    doc_path.write_text(
        "---\n"
        "title: Open\n"
        "Some body text\n",
        encoding="utf-8"
    )

    with pytest.raises(DocParsingError):
        _parse_frontmatter(doc_path)


def test_process_doc_success(tmp_path: Path) -> None:
    doc_path = tmp_path / "test.md"
    doc_path.write_text(
        "---\n"
        "title: My Title\n"
        "summary: My Summary\n"
        "category: My Category\n"
        "---\n"
        "Body content",
        encoding="utf-8"
    )

    doc = _process_doc(doc_path)
    assert isinstance(doc, Document)
    assert doc.name == "test"
    assert doc.title == "My Title"
    assert doc.summary == "My Summary"
    assert doc.category == "My Category"
    assert "Body content" in doc.html


def test_process_doc_missing_optional_category(tmp_path: Path) -> None:
    doc_path = tmp_path / "test.md"
    doc_path.write_text(
        "---\n"
        "title: My Title\n"
        "summary: My Summary\n"
        "---\n"
        "Body content",
        encoding="utf-8"
    )

    doc = _process_doc(doc_path)
    assert doc.category == "Uncategorized"


def test_process_doc_missing_required_key(tmp_path: Path) -> None:
    doc_path = tmp_path / "test.md"
    doc_path.write_text(
        "---\n"
        "summary: My Summary\n"
        "---\n"
        "Body content",
        encoding="utf-8"
    )

    with pytest.raises(KeyError):
        _process_doc(doc_path)
