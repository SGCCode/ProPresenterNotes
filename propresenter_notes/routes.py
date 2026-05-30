"""Flask routes for ProPresenter Notes."""
from __future__ import annotations

import secrets
import urllib.parse
from typing import Any

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from .client import ProPresenterClient, ProPresenterError
from .config import Settings
from .services import (
    build_presentation_cache,
    get_presentation,
    get_presentations,
    get_slide_state,
    presentation_fingerprint,
    try_paths,
)

bp = Blueprint("main", __name__)


def _client() -> ProPresenterClient:
    return current_app.extensions["propresenter_client"]


def _settings() -> Settings:
    return current_app.config["APP_SETTINGS"]


def _pin_is_enabled() -> bool:
    return bool(_settings().ui_pin)


def _access_cookie_name() -> str:
    return current_app.config.get("APP_ACCESS_COOKIE", "propresenter_notes_access")


def _access_token() -> str:
    return current_app.config["APP_ACCESS_TOKEN"]


def _has_ui_access() -> bool:
    if not _pin_is_enabled():
        return True
    access_cookie = request.cookies.get(_access_cookie_name(), "")
    return secrets.compare_digest(access_cookie, _access_token())


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def _safe_next_url(value: str | None) -> str:
    if not value:
        return url_for("main.index")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return url_for("main.index")
    return value


@bp.before_request
def require_ui_pin() -> Response | tuple[Response, int] | None:
    allowed_endpoints = {"main.login", "static"}
    if request.endpoint in allowed_endpoints or _has_ui_access():
        return None

    if _wants_json():
        return jsonify({"error": "PIN required"}), 401

    return redirect(url_for("main.login", next=request.full_path if request.query_string else request.path))


@bp.errorhandler(ProPresenterError)
def handle_propresenter_error(exc: ProPresenterError) -> tuple[Response, int]:
    payload: dict[str, Any] = {"error": str(exc)}
    if exc.details is not None:
        payload["details"] = exc.details
    return jsonify(payload), exc.status_code


@bp.get("/")
def index() -> str:
    return render_template("index.html", pin_enabled=_pin_is_enabled())


@bp.route("/login", methods=["GET", "POST"])
def login() -> Response | str:
    if not _pin_is_enabled() or _has_ui_access():
        return redirect(_safe_next_url(request.args.get("next")))

    error = ""
    if request.method == "POST":
        submitted_pin = str(request.form.get("pin", ""))
        if secrets.compare_digest(submitted_pin, _settings().ui_pin):
            response = redirect(_safe_next_url(request.form.get("next")))
            response.set_cookie(
                _access_cookie_name(),
                _access_token(),
                httponly=True,
                samesite="Lax",
            )
            return response
        error = "Invalid PIN. Please try again."

    return render_template(
        "login.html",
        error=error,
        next_url=_safe_next_url(request.args.get("next")),
    )


@bp.post("/logout")
def logout() -> Response:
    response = redirect(url_for("main.login" if _pin_is_enabled() else "main.index"))
    response.delete_cookie(_access_cookie_name())
    return response


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


@bp.get("/api/presentation-cache/<path:presentation_id>")
def api_presentation_cache(presentation_id: str) -> Response:
    return jsonify(build_presentation_cache(_client(), presentation_id))


@bp.get("/api/presentation-fingerprint/<path:presentation_id>")
def api_presentation_fingerprint(presentation_id: str) -> tuple[Response, int]:
    presentation = get_presentation(_client(), presentation_id)
    if presentation is None:
        return jsonify({"error": "Could not read presentation from ProPresenter"}), 404
    return jsonify({"presentationId": presentation_id, "fingerprint": presentation_fingerprint(presentation)}), 200


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
