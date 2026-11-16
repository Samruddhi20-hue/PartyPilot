
from flask import Blueprint

venues = Blueprint("venues", __name__)

from app.venues import routes
