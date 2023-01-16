from flask import Blueprint, render_template

helper = Blueprint('helper', __name__, template_folder='templates')


@helper.route('/')
def index():
    return render_template("index.html")
