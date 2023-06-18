from pathlib import Path

from flask import Blueprint, abort, render_template

MODULE_DIR = Path(__file__).resolve().parent
DOCS_HTML_DIR = MODULE_DIR / 'docs'

bp = Blueprint('docs', __name__, url_prefix="/docs", template_folder='templates')


@bp.route('/<string:filename>')
def serve_doc_html(filename):
    ''' Serve up a doc page based on matching a filename into the docs directory. '''

    # Validate and sanitize the input
    if '/' in filename or '\\' in filename or '..' in filename:
        abort(403)  # Return a 403 Forbidden error if the input is invalid

    full_path = DOCS_HTML_DIR / (filename + '.html')

    if full_path.parent != DOCS_HTML_DIR:
        abort(403)  # Return a 403 Forbidden error if the input is invalid

    if not full_path.is_file():
        abort(404)  # Return a 404 error if the file is not found

    with open(full_path, 'r') as file:
        html_content = file.read()

    return render_template('docs_page.html', html_content=html_content)
