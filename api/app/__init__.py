"""Shorty API - Flask application factory."""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from app.cache import link_cache
from app.config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    if app.config["TRUSTED_PROXY_COUNT"]:
        n = app.config["TRUSTED_PROXY_COUNT"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    db.init_app(app)
    migrate.init_app(app, db)
    link_cache.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"])

    from app.routes.analytics import analytics_bp
    from app.routes.links import links_bp
    from app.routes.redirect import redirect_bp

    app.register_blueprint(links_bp, url_prefix="/api/links")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(redirect_bp)  # handles /<short_code>

    @app.get("/health")
    def health():
        return {"status": "healthy", "service": "Shorty API"}

    @app.errorhandler(HTTPException)
    def json_errors(err):
        return jsonify({"error": err.description}), err.code

    return app
