#!/usr/bin/env python3
"""Local ProPresenter notes controller.

No Docker and no Python packages are required. This is a tiny HTTP server that:
- serves the browser UI from ./public
- proxies selected requests to the ProPresenter public REST API
"""
from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import socket
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from openai import base_url

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict[str, Any]:
    data: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Warning: could not read config.json: {exc}", file=sys.stderr)
    return {
        "app_host": os.environ.get("APP_HOST", data.get("app_host", "127.0.0.1")),
        "app_port": int(os.environ.get("APP_PORT", data.get("app_port", 3000))),
        "propresenter_scheme": os.environ.get("PROPRESENTER_SCHEME", data.get("propresenter_scheme", "http")),
        "propresenter_host": os.environ.get("PROPRESENTER_HOST", data.get("propresenter_host", "127.0.0.1")),
        "propresenter_port": int(os.environ.get("PROPRESENTER_PORT", data.get("propresenter_port", 1025))),
        "poll_timeout_ms": int(os.environ.get("POLL_TIMEOUT_MS", data.get("poll_timeout_ms", 2500))),
    }

CONFIG = load_config()
BASE_URL = f"{CONFIG['propresenter_scheme']}://{CONFIG['propresenter_host']}:{CONFIG['propresenter_port']}"
TIMEOUT_SECONDS = max(CONFIG["poll_timeout_ms"] / 1000.0, 0.25)


def clean_api_path(api_path: str) -> str:
    path_only = api_path.split("?", 1)[0]
    if not (path_only.startswith("/v1/") or path_only == "/version"):
        raise ValueError("Unsupported ProPresenter API path")
    return api_path

def is_image_response(content_type: str) -> bool:
    return content_type.lower().startswith("image/")


def pro_fetch_raw(
    api_path: str,
    method: str = "GET",
    body: Any | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, str]:
    """
    Low-level shared fetcher.

    Returns:
        (status_code, raw_response_bytes, content_type)
    """
    safe_path = clean_api_path(api_path)

    data = None
    request_headers = {
        "Accept": "application/json, text/plain, */*"
    }

    if headers:
        request_headers.update(headers)

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        BASE_URL + safe_path,
        method=method,
        data=data,
        headers=request_headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            raw_body = response.read()
            content_type = response.headers.get("content-type", "")

            return response.status, raw_body, content_type

    except urllib.error.HTTPError as exc:
        raw_body = exc.read()
        content_type = exc.headers.get("content-type", "") if exc.headers else ""

        detail = parse_response_body(raw_body, content_type)

        raise RuntimeError(
            json.dumps({
                "status": exc.code,
                "content_type": content_type,
                "details": detail,
            })
        ) from exc

    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def pro_fetch(
    api_path: str,
    method: str = "GET",
    body: Any | None = None,
) -> tuple[int, Any]:
    """
    Normal ProPresenter fetch helper for JSON/text API calls.
    """
    status, raw_body, content_type = pro_fetch_raw(
        api_path=api_path,
        method=method,
        body=body,
        headers={
            "Accept": "application/json, text/plain, */*"
        },
    )

    return status, parse_response_body(raw_body, content_type)

def pro_fetch_image(
    api_path: str,
    method: str = "GET",
) -> tuple[int, bytes, str]:
    """
    Fetches binary image data from ProPresenter.

    Returns:
        (status_code, image_bytes, content_type)
    """
    status, raw_body, content_type = pro_fetch_raw(
        api_path=api_path,
        method=method,
        body=None,
        headers={
            "Accept": "image/*, */*"
        },
    )

    if not content_type.lower().startswith("image/"):
        raise RuntimeError(
            json.dumps({
                "status": status,
                "content_type": content_type,
                "details": "Expected image response from ProPresenter",
            })
        )

    return status, raw_body, content_type

def get_presentation(presentation_id: str) -> dict[str, Any] | None:
    try:
        status, data = pro_fetch(f"/v1/presentation/{urllib.parse.quote(presentation_id, safe='')}")
        if status == 200 and isinstance(data, dict):
            return data
    except Exception:
        pass
    return None

def get_presentation_thumbnail(presentation_id: str, slide_index: int) -> bytes | None:
    try:
        
        status, image_bytes, content_type = pro_fetch_image(f"/v1/presentation/{presentation_id}/thumbnail/{slide_index}?quality=400&thumnail_type=jpeg")
        if status == 200 and is_image_response(content_type):
            return image_bytes
    except Exception:
        pass
    return None

def parse_response_body(raw: bytes, content_type: str) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    if "json" in content_type.lower():
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def first_non_empty_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def text_from_object(value: Any, depth: int = 0) -> str:
    if value is None or depth > 4:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(filter(None, (text_from_object(v, depth + 1) for v in value)))
    if isinstance(value, dict):
        preferred = first_non_empty_string(
            value.get("text"), value.get("plainText"), value.get("plain_text"),
            value.get("value"), value.get("body"), value.get("content")
        )
        if preferred:
            return preferred
        return "\n".join(filter(None, (text_from_object(v, depth + 1) for v in value.values())))
    return ""


def find_notes(value: Any, seen: set[int] | None = None) -> str:
    if not isinstance(value, (dict, list)):
        return ""
    if seen is None:
        seen = set()
    ident = id(value)
    if ident in seen:
        return ""
    seen.add(ident)

    note_keys = [
        "notes", "note", "slide_notes", "slideNotes", "speaker_notes", "speakerNotes",
        "presenter_notes", "presenterNotes", "stage_notes", "stageNotes", "cue_notes", "cueNotes"
    ]
    if isinstance(value, dict):
        for key in note_keys:
            if key in value:
                found = text_from_object(value[key])
                if found:
                    return found
        iterable = value.values()
    else:
        iterable = value

    for item in iterable:
        found = find_notes(item, seen)
        if found:
            return found
    return ""


def find_slide_index(status: Any) -> int:
    if not isinstance(status, dict):
        return 0
    candidates = [
        status.get("index"), status.get("slide_index"), status.get("slideIndex"),
        nested(status, "presentation", "index"), nested(status, "presentation", "slideIndex"),
        nested(status, "cue", "index"), nested(status, "current", "index"), nested(status, "id", "index"),
    ]
    for candidate in candidates:
        try:
            parsed = int(candidate)
            if parsed >= 0:
                return parsed
        except Exception:
            continue
    return 0


def find_slide_title(status: Any) -> str:
    if not isinstance(status, dict):
        return ""
    return first_non_empty_string(
        status.get("name"), nested(status, "slide", "name"), nested(status, "cue", "name"),
        nested(status, "presentation", "name"), nested(status, "id", "name")
    )


def nested(obj: Any, *keys: str) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def uuid_value(value: Any) -> str:
    if isinstance(value, dict):
        if isinstance(value.get("uuid"), dict):
            return uuid_value(value["uuid"])
        return str(value.get("uuid") or value.get("name") or value.get("index") or "")
    return str(value or "")


def flatten_presentations(nodes: Any, library_id: str | None = None, out: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if out is None:
        out = []
    if not isinstance(nodes, list):
        return out
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id", node)
        node_library_id = library_id or uuid_value(node_id)
        if isinstance(node.get("items"), list):
            for item in node["items"]:
                if isinstance(item, dict) and item.get("id"):
                    out.append({"libraryId": node_library_id, "presentation": item["id"], "raw": item})
        for key in ("children", "libraries"):
            if isinstance(node.get(key), list):
                flatten_presentations(node[key], node_library_id, out)
    return out


def try_paths(paths: list[str]) -> dict[str, Any]:
    errors = []
    for api_path in paths:
        if not api_path:
            continue
        try:
            _status, data = pro_fetch(api_path)
            return {"ok": True, "path": api_path, "data": data}
        except Exception as exc:
            errors.append({"path": api_path, "message": str(exc)})
    return {"ok": False, "errors": errors}


class Handler(BaseHTTPRequestHandler):
    server_version = "ProPresenterNotesController/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/config":
                return self.json({"baseUrl": BASE_URL, "pollTimeoutMs": CONFIG["poll_timeout_ms"]})
            if path == "/api/health":
                result = try_paths(["/version"])
                return self.json(result, 200 if result.get("ok") else 502)
            if path == "/api/libraries":
                return self.proxy_json("/v1/libraries")
            if path.startswith("/api/library/"):
                library_id = urllib.parse.quote(path.removeprefix("/api/library/"), safe="")
                return self.proxy_json(f"/v1/library/{library_id}")
            if path == "/api/presentations":
                return self.handle_presentations()
            if path == "/api/slide-state":
                library_id = query.get("libraryId", [""])[0]
                presentation_id = query.get("presentationId", [""])[0]
                return self.handle_slide_state(library_id, presentation_id)
            return self.serve_static(path)
        except Exception as exc:
            return self.json({"error": str(exc)}, 500)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/trigger/next":
                pro_fetch("/v1/trigger/next")
                return self.empty()
            if path == "/api/trigger/previous":
                pro_fetch("/v1/trigger/previous")
                return self.empty()
            if path == "/api/trigger/slide":
                body = self.read_json_body()
                library_id = body.get("libraryId")
                presentation_id = body.get("presentationId")
                index = body.get("index", 0)
                if not library_id or not presentation_id:
                    return self.json({"error": "libraryId and presentationId are required"}, 400)
                pro_fetch(f"/v1/trigger/library/{urllib.parse.quote(str(library_id), safe='')}/{urllib.parse.quote(str(presentation_id), safe='')}/{urllib.parse.quote(str(index), safe='')}")
                return self.empty()
            return self.json({"error": "Not found"}, 404)
        except Exception as exc:
            return self.json({"error": str(exc)}, 502)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def proxy_json(self, api_path: str) -> None:
        _status, data = pro_fetch(api_path)
        return self.json(data)

    def handle_presentations(self) -> None:
        _status, libraries = pro_fetch("/v1/libraries")
        presentations: list[dict[str, Any]] = []
        for lib in libraries if isinstance(libraries, list) else []:
            print(f"Processing library: {lib}")
            lib_uuid = lib.get("uuid", lib) if isinstance(lib, dict) else lib
            library_uuid = uuid_value(lib_uuid)
            if not library_uuid:
                continue
            try:
                _s, library = pro_fetch(f"/v1/library/{urllib.parse.quote(library_uuid, safe='')}")
                items = library.get("items") if isinstance(library, dict) else library if isinstance(library, list) else []
                for item in items if isinstance(items, list) else []:
                    if isinstance(item, dict) and item.get("uuid"):
                        presentations.append({"library": lib, "presentation": item, "raw": item})
            except Exception:
                continue
        if not presentations:
            presentations.extend(flatten_presentations(libraries))
        return self.json(presentations)

    def handle_slide_state(self, library_id: str, presentation_id: str) -> None:
        paths = [
            "/v1/status/slide",
            "/v1/presentation/active",
            f"/v1/presentation/{urllib.parse.quote(presentation_id, safe='')}" if presentation_id else "",
            f"/v1/library/{urllib.parse.quote(library_id, safe='')}/{urllib.parse.quote(presentation_id, safe='')}" if library_id and presentation_id else "",
        ]
        result = try_paths(paths)
        if not result.get("ok"):
            return self.json({"error": "Could not read slide status from ProPresenter", "attempts": result.get("errors")}, 502)
        data = result.get("data")
        slide_index = find_slide_index(data)
        notes = find_notes(data)
        title = find_slide_title(data)

        if presentation_id and (not notes or not title):
            detail_paths = [
                f"/v1/presentation/{urllib.parse.quote(presentation_id, safe='')}",
                f"/v1/library/{urllib.parse.quote(library_id, safe='')}/{urllib.parse.quote(presentation_id, safe='')}" if library_id else "",
            ]
            detail = try_paths(detail_paths)
            if detail.get("ok"):
                d = detail.get("data")
                slides = []
                if isinstance(d, dict):
                    slides = d.get("slides") or d.get("cues") or d.get("items") or nested(d, "presentation", "slides") or []
                elif isinstance(d, list):
                    slides = d
                slide = slides[slide_index] if isinstance(slides, list) and slide_index < len(slides) else None
                notes = notes or find_notes(slide)
                title = title or find_slide_title(slide)

        return self.json({
            "sourcePath": result.get("path"),
            "slideIndex": slide_index,
            "slideNumber": slide_index + 1,
            "title": title,
            "notes": notes,
            "raw": data,
        })

    def serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        safe = posixpath.normpath(urllib.parse.unquote(path)).lstrip("/")
        target = (PUBLIC / safe).resolve()
        if not str(target).startswith(str(PUBLIC.resolve())) or not target.exists() or not target.is_file():
            return self.json({"error": "Not found"}, 404)
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def empty(self) -> None:
        self.send_response(204)
        self.end_headers()


def main() -> None:
    app_host = CONFIG["app_host"]
    app_port = CONFIG["app_port"]
    try:
        server = ThreadingHTTPServer((app_host, app_port), Handler)
    except OSError as exc:
        print(f"Could not start server on {app_host}:{app_port}: {exc}", file=sys.stderr)
        sys.exit(1)
    url = f"http://{app_host}:{app_port}"
    print(f"ProPresenter Notes Controller running at {url}")
    print(f"Proxying ProPresenter at {BASE_URL}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")


if __name__ == "__main__":
    main()
