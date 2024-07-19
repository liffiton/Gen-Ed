# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import dataclass
from pathlib import Path

import frontmatter  # type: ignore [import-untyped]
from flask import Blueprint, abort, current_app, render_template
from markdown_it import MarkdownIt

# get a processor that does HTML parsing for our docs (trusted content, HTML parsing okay)
_markdown_processor = MarkdownIt("commonmark", {"typographer": True})
_markdown_processor.enable(["replacements", "smartquotes"])

bp = Blueprint('docs', __name__, url_prefix="/docs", template_folder='templates')


@dataclass(frozen=True)
class Document:
    """ Metadata and contents for one page of documentation """
    name: str  # the document's filename without .md
    html: str
    title: str
    summary: str


def _process_doc(docfile_path: Path) -> Document:
    ''' Given a markdown processor (md) and a Path object to a markdown documentation page,
    return a Document for that page.
    '''
    md_doc = frontmatter.load(docfile_path)
    html = _markdown_processor.render(md_doc.content)

    title = md_doc['title']
    summary = md_doc['summary']

    return Document(
        name=docfile_path.stem,
        html=html,
        title=title,
        summary=summary,
    )


def list_pages() -> list[str]:
    docs_dir = current_app.config.get('DOCS_DIR')
    assert docs_dir  # base.py shouldn't load this blueprint if we have no documentation directory configured

    pages_paths = docs_dir.glob('*.md')
    return [path.stem for path in pages_paths]


@bp.route('/')
def main() -> str:
    ''' Show an index of documentation pages. '''
    docs_dir = current_app.config.get('DOCS_DIR')
    assert docs_dir  # base.py shouldn't load this blueprint if we have no documentation directory configured

    docs_pages = []
    for md_file in docs_dir.glob("*.md"):
        try:
            page = _process_doc(md_file)
            docs_pages.append(page)
        except KeyError as e:
            current_app.logger.warning(f"Failed to load docs page: {md_file}.  KeyError: {e}")

    docs_pages.sort(key=lambda x: x.title)

    return render_template("docs_index.html", pages=docs_pages)


@bp.route('/<string:name>')
def page(name: str) -> str:
    ''' Serve up a doc page based on matching a filename into the docs directory. '''
    docs_dir = current_app.config.get('DOCS_DIR')
    assert docs_dir  # base.py shouldn't load this blueprint if we have no documentation directory configured

    # Validate and sanitize the input
    if '/' in name or '\\' in name or '..' in name:
        abort(404)  # Return a 404 error if the input is invalid

    full_path = docs_dir / (name + '.md')

    if full_path.parent != docs_dir:
        abort(404)  # Return a 404 error if the input is invalid

    if not full_path.is_file():
        abort(404)  # Return a 404 error if the file is not found

    page = _process_doc(full_path)

    return render_template('docs_page.html', html_content=page.html)
