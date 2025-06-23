from flask import Blueprint

from . import admin  # noqa: F401 -- imported for its side effects
from .chat import bp as chat_bp
from .config import bp as config_bp

bp = Blueprint('tutors', __name__, url_prefix='/tutor', template_folder='templates')
bp.register_blueprint(chat_bp)
bp.register_blueprint(config_bp)

__all__ = [
    "bp",
]
