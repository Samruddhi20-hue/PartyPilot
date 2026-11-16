from flask import Blueprint

bookings = Blueprint("bookings", __name__)

from app.bookings import routes