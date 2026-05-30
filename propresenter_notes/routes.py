"""Flask routes for ProPresenter Notes."""
from __future__ import annotations

import urllib.parse
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from .client import ProPresenterClient, ProPresenterError
from .config import Settings
from .services import get_presentations, get_slide_state, try_paths

bp = Blueprint("main", __name__)


def _client() -> ProPresenterClient:
    return current_app.extensions["propresenter_client"]


def _settings() -> Settings:
    return current_app.config["APP_SETTINGS"]


@bp.errorhandler(ProPresenterError)
def handle_propresenter_error(exc: ProPresenterError) -> tuple[Response, int]:
    payload: dict[str, Any] = {"error": str(exc)}
    if exc.details is not None:
        payload["details"] = exc.details
    return jsonify(payload), exc.status_code


@bp.get("/")
def index() -> str:
    return render_template("index.html")


@bp.get("/api/config")
def api_config() -> Response:
    settings = _settings()
    return jsonify(
        {
            "baseUrl": settings.propresenter_base_url,
            "pollTimeoutMs": settings.poll_timeout_ms,
        }
    )


@bp.get("/api/health")
def api_health() -> tuple[Response, int]:
    result = try_paths(_client(), ["/version"])
    return jsonify(result), 200 if result.get("ok") else 502


@bp.get("/api/libraries")
def api_libraries() -> Response:
    _status, data = _client().fetch("/v1/libraries")
    return jsonify(data)


@bp.get("/api/library/<path:library_id>")
def api_library(library_id: str) -> Response:
    _status, data = _client().fetch(f"/v1/library/{urllib.parse.quote(library_id, safe='')}")
    return jsonify(data)


@bp.get("/api/presentations")
def api_presentations() -> Response:
    return jsonify(get_presentations(_client()))


@bp.get("/api/slide-state")
def api_slide_state() -> Response:
    library_id = request.args.get("libraryId", "")
    presentation_id = request.args.get("presentationId", "")
    return jsonify(get_slide_state(_client(), library_id, presentation_id))


@bp.post("/api/trigger/next")
def api_trigger_next() -> tuple[str, int]:
    _client().fetch("/v1/trigger/next")
    return "", 204


@bp.post("/api/trigger/previous")
def api_trigger_previous() -> tuple[str, int]:
    _client().fetch("/v1/trigger/previous")
    return "", 204


@bp.post("/api/trigger/slide")
def api_trigger_slide() -> tuple[Response | str, int]:
    body = request.get_json(silent=True) or {}
    library_id = body.get("libraryId")
    presentation_id = body.get("presentationId")
    index = body.get("index", 0)
    if not library_id or not presentation_id:
        return jsonify({"error": "libraryId and presentationId are required"}), 400

    _client().fetch(
        "/v1/trigger/library/"
        f"{urllib.parse.quote(str(library_id), safe='')}/"
        f"{urllib.parse.quote(str(presentation_id), safe='')}/"
        f"{urllib.parse.quote(str(index), safe='')}"
    )
    return "", 204
