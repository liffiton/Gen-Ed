from jinja2 import Environment

from gened.class_config import ConfigTable, register_config_table

from .data import (
    get_available_contexts,
    get_context_by_name,
    get_context_string_by_id,
    record_context_string,
)
from .model import ContextConfig, get_markdown_filter

# Register the configuration UI inside gened's class_config module
context_config_help = Environment(autoescape=True).from_string("""\
  <p>Contexts provide additional information to the LLM for each query a student makes.  You can have a single default context that is always used, or you can create separate contexts for individual assignments or modules.  If multiple contexts are available, students will be able to select from them when making queries.</p>
  {% if ctx.item_data | length == 0 %}
    <p class="has-text-danger">While not strictly required, we recommend defining at least one context to specify the language(s), frameworks, and/or libraries in use in this class.</p>
  {% endif %}
  {# Link to the 'contexts.md' docs page if it exists #}
  {% if 'contexts' in docs_pages %}
    <p>See the <a href="{{ url_for('docs.page', name='contexts') }}">contexts documentation</a> for more information and suggestions.</p>
  {% endif %}
""")
contexts_config_table = ConfigTable(
    config_item_class=ContextConfig,
    name='context',
    db_table_name='contexts',
    display_name='context',
    display_name_plural='contexts',
    help_text=context_config_help,
    edit_form_template='context_edit_form.html',
)
register_config_table(contexts_config_table)

__all__ = [
    "ContextConfig",
    "get_available_contexts",
    "get_context_by_name",
    "get_context_string_by_id",
    "get_markdown_filter",
    "record_context_string",
]
