from gened.class_config import register_extra_section

from .blueprint import bp
from .data import (
    get_available_contexts,
    get_context_by_name,
    get_context_config_data,
    get_context_string_by_id,
    record_context_string,
)
from .model import ContextConfig, register

# Register the configuration UI (render function) inside gened's class_config module
register_extra_section("context_config.html", get_context_config_data)

__all__ = [
    "ContextConfig",
    "bp",
    "get_available_contexts",
    "get_context_by_name",
    "get_context_string_by_id",
    "record_context_string",
    "register",
]
