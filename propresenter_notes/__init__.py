"""Application factory for ProPresenter Notes."""
from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, jsonify

from .client import ProPresenterClient
from .config import Settings, load_settings
from .routes import bp

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings(CONFIG_PATH)
    app = Flask(
        __name__,
        static_folder="static",
        static_url_path="",
        template_folder="templates",
    )
    app.config["APP_SETTINGS"] = settings
    app.extensions["propresenter_client"] = ProPresenterClient(
        settings.propresenter_base_url,
        settings.timeout_seconds,
    )

    app.register_blueprint(bp)

    @app.errorhandler(404)
    def handle_not_found(_exc: Exception) -> tuple[Response, int]:
        return jsonify({"error": "Not found"}), 404

    return app
