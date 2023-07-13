from flask import Blueprint, abort, current_app, render_template

bp = Blueprint('docs', __name__, url_prefix="/docs", template_folder='templates')


def _process_doc(md, docfile_path):
    ''' Given a markdown processor (md) and a Path object to a markdown documentation page,
    return a dictionary for that page with:
      - name (filename without .md)
      - html
      - title
      - summary
    All as strings.
    '''
    md_text = docfile_path.read_text()
    html = md.convert(md_text)
    metadata = md.Meta  # https://python-markdown.github.io/extensions/meta_data/

    title = metadata['title'][0]
    summary = metadata['summary'][0]

    return dict(
        name=docfile_path.stem,
        html=html,
        title=title,
        summary=summary,
    )


@bp.route('/')
def main():
    ''' Show an index of documentation pages. '''
    docs_dir = current_app.config.get('DOCS_DIR')
    assert docs_dir  # plum/base.py shouldn't load this blueprint if we have no documentation directory configured

    md = current_app.markdown_processor

    docs_pages = []
    for md_file in docs_dir.glob("*.md"):
        try:
            page = _process_doc(md, md_file)
            docs_pages.append(page)
        except KeyError as e:
            current_app.logger.warning(f"Failed to load docs page: {md_file}.  KeyError: {e}")

    docs_pages.sort(key=lambda x: x['title'])

    return render_template("docs_index.html", pages=docs_pages)


@bp.route('/<string:name>')
def page(name):
    ''' Serve up a doc page based on matching a filename into the docs directory. '''
    docs_dir = current_app.config.get('DOCS_DIR')
    assert docs_dir  # plum/base.py shouldn't load this blueprint if we have no documentation directory configured

    # Validate and sanitize the input
    if '/' in name or '\\' in name or '..' in name:
        abort(404)  # Return a 404 error if the input is invalid

    full_path = docs_dir / (name + '.md')

    if full_path.parent != docs_dir:
        abort(404)  # Return a 404 error if the input is invalid

    if not full_path.is_file():
        abort(404)  # Return a 404 error if the file is not found

    with open(full_path, 'r') as file:
        md_content = file.read()

    html_content = current_app.markdown_processor.convert(md_content)

    return render_template('docs_page.html', html_content=html_content)
