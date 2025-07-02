from flask import Blueprint

from . import admin, data
from .chat import bp as chat_bp
from .guided import bp as guided_bp

bp = Blueprint('tutors', __name__, url_prefix='/tutor', template_folder='templates')
bp.register_blueprint(chat_bp)
bp.register_blueprint(guided_bp)

admin.register_with_gened()

def register_with_gened() -> None:
    data.register_with_gened()

__all__ = [
    "bp",
    "register_with_gened",
]
