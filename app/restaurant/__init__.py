from flask import Blueprint

restaurant = Blueprint("restaurant", __name__)

from app.restaurant import routes  # noqa: E402,F401
