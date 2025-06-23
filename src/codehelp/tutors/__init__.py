from flask import Blueprint

from . import admin  # noqa: F401 -- imported for its side effects
from .chat import bp as chat_bp
from .guided import bp as guided_bp

bp = Blueprint('tutors', __name__, url_prefix='/tutor', template_folder='templates')
bp.register_blueprint(chat_bp)
bp.register_blueprint(guided_bp)

__all__ = [
    "bp",
]
