"""HTTP client helpers for the ProPresenter public REST API."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class ProPresenterError(RuntimeError):
    """Error raised when ProPresenter cannot satisfy a proxied request."""

    def __init__(self, message: str, status_code: int = 502, details: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class ProPresenterClient:
    """Small urllib-based client for the ProPresenter public REST API."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def fetch_raw(
        self,
        api_path: str,
        method: str = "GET",
        body: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, str]:
        safe_path = clean_api_path(api_path)
        data = None
        request_headers = {"Accept": "application/json, text/plain, */*"}

        if headers:
            request_headers.update(headers)

        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            self.base_url + safe_path,
            method=method,
            data=data,
            headers=request_headers,
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw_body = response.read()
                content_type = response.headers.get("content-type", "")
                return response.status, raw_body, content_type
        except urllib.error.HTTPError as exc:
            raw_body = exc.read()
            content_type = exc.headers.get("content-type", "") if exc.headers else ""
            detail = parse_response_body(raw_body, content_type)
            raise ProPresenterError(
                "ProPresenter API returned an error",
                status_code=exc.code,
                details={"content_type": content_type, "details": detail},
            ) from exc
        except Exception as exc:
            raise ProPresenterError(str(exc)) from exc

    def fetch(self, api_path: str, method: str = "GET", body: Any | None = None) -> tuple[int, Any]:
        status, raw_body, content_type = self.fetch_raw(
            api_path=api_path,
            method=method,
            body=body,
            headers={"Accept": "application/json, text/plain, */*"},
        )
        return status, parse_response_body(raw_body, content_type)

    def fetch_image(self, api_path: str, method: str = "GET") -> tuple[int, bytes, str]:
        status, raw_body, content_type = self.fetch_raw(
            api_path=api_path,
            method=method,
            body=None,
            headers={"Accept": "image/*, */*"},
        )

        if not is_image_response(content_type):
            raise ProPresenterError(
                "Expected image response from ProPresenter",
                status_code=status,
                details={"content_type": content_type},
            )

        return status, raw_body, content_type


def clean_api_path(api_path: str) -> str:
    path_only = api_path.split("?", 1)[0]
    if not (path_only.startswith("/v1/") or path_only == "/version"):
        raise ValueError("Unsupported ProPresenter API path")
    return api_path


def is_image_response(content_type: str) -> bool:
    return content_type.lower().startswith("image/")


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
