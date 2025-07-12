from gened.class_config import ConfigTable, register_config_table

from .data import (
    get_available_contexts,
    get_context_by_name,
    get_context_string_by_id,
    record_context_string,
)
from .model import ContextConfig, get_markdown_filter

# Register the configuration UI inside gened's class_config module
contexts_config_table = ConfigTable(
    config_item_class=ContextConfig,
    name='context',
    db_table_name='contexts',
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
