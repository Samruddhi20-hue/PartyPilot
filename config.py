import os
from pathlib import Path
from sqlalchemy.engine import make_url

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or (
        "local-development-only-change-before-deployment"
    )

    _database_url = os.getenv("DATABASE_URL")
    if _database_url:
        if _database_url.startswith("postgres://"):
            _database_url = _database_url.replace(
                "postgres://", "postgresql+psycopg://", 1
            )
        elif _database_url.startswith("postgresql://"):
            _database_url = _database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        parsed_url = make_url(_database_url)
        if parsed_url.drivername.startswith("postgresql") and "sslmode" not in parsed_url.query:
            parsed_url = parsed_url.update_query_dict({"sslmode": "require"})
        SQLALCHEMY_DATABASE_URI = parsed_url
    else:
        from sqlalchemy import URL
        SQLALCHEMY_DATABASE_URI = URL.create(
            drivername="postgresql+psycopg",
            username=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "postgres"),
            query={"sslmode": "require"},
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(40 * 1024 * 1024)))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV", "development") == "production"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8
