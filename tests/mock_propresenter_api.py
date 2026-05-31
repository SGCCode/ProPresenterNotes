"""Spec-example backed mock ProPresenter API for integration tests."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

EXAMPLES_PATH = Path(__file__).with_name("propresenter_openapi_examples.json")


def load_examples() -> dict[str, Any]:
    with EXAMPLES_PATH.open(encoding="utf-8") as examples_file:
        return json.load(examples_file)


class MockProPresenterAPIServer:
    """Runs a local HTTP API that serves captured OpenAPI example payloads."""

    def __init__(self, examples: dict[str, Any] | None = None) -> None:
        self.examples = examples or load_examples()
        self.requests: list[dict[str, Any]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "MockProPresenterAPIServer":
        self._thread.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        examples = self.examples
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                parsed = urlparse(self.path)
                path = parsed.path
                query = parse_qs(parsed.query)
                requests.append({"method": "GET", "path": path, "query": query})

                if path == "/version":
                    self._send_example(examples["version"])
                    return

                if path == "/v1/libraries":
                    self._send_example(examples["libraries"])
                    return

                if path.startswith("/v1/library/"):
                    library_id = unquote(path.removeprefix("/v1/library/"))
                    if self._known_library_id(library_id):
                        self._send_example(examples["library"])
                    else:
                        self._send_json(404, {"error": "Library not found"})
                    return

                self._send_json(404, {"error": "Not found"})

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _known_library_id(self, library_id: str) -> bool:
                for library in examples["libraries"]["body"]:
                    identifiers = {str(library["uuid"]), str(library["name"]), str(library["index"])}
                    if library_id in identifiers:
                        return True
                return False

            def _send_example(self, example: dict[str, Any]) -> None:
                self._send_json(int(example["status"]), example["body"])

            def _send_json(self, status: int, body: Any) -> None:
                payload = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        return Handler
