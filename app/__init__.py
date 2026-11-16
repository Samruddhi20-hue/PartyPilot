import os
import secrets
import hmac

from flask import Flask, jsonify, render_template, session, request, abort

from config import Config
from app.extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    if os.getenv("FLASK_ENV") == "production" and not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be configured in production.")
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    @app.before_request
    def protect_state_changing_requests():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("_csrf_token")
            supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRFToken")
            if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
                abort(400, description="Your session security token is invalid. Refresh the page and try again.")

    @app.context_processor
    def inject_csrf_token():
        def csrf_token():
            token = session.get("_csrf_token")
            if not token:
                token = secrets.token_urlsafe(32)
                session["_csrf_token"] = token
            return token
        return {"csrf_token": csrf_token}

    from app.auth import auth
    app.register_blueprint(auth)
    from app.venues import venues
    app.register_blueprint(venues)
    from app.customer import customer
    app.register_blueprint(customer, url_prefix="/customer")
    from app.restaurant import restaurant
    app.register_blueprint(restaurant, url_prefix="/restaurant")
    from app.bookings import bookings
    app.register_blueprint(bookings)
    from app.admin import admin
    app.register_blueprint(admin, url_prefix="/admin")

    from app.cli import create_admin
    app.cli.add_command(create_admin)

    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/health")
    def health():
        return jsonify({"status": "success", "message": "PartyPilot backend is running."}), 200

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if os.getenv("FLASK_ENV") == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.errorhandler(413)
    def request_too_large(error):
        return render_template("413.html"), 413

    @app.errorhandler(400)
    def bad_request(error):
        if request.accept_mimetypes.accept_html:
            return render_template("400.html", error=error), 400
        return jsonify({"error": "bad_request", "message": str(error.description)}), 400

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        db.session.rollback()
        return render_template("500.html"), 500

    return app
