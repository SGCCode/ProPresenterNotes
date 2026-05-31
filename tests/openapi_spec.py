"""Helpers for loading and asserting against the checked-in ProPresenter OpenAPI spec."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SPEC_PATH = Path(__file__).with_name("swagger.json")
SPEC_PREFIX = "var openapi_spec = "


@lru_cache(maxsize=1)
def load_openapi_spec() -> dict[str, Any]:
    """Load the Swagger UI JavaScript assignment as an OpenAPI dictionary."""
    raw_spec = SPEC_PATH.read_text(encoding="utf-8").strip()
    if raw_spec.startswith(SPEC_PREFIX):
        raw_spec = raw_spec.removeprefix(SPEC_PREFIX)
    return json.loads(raw_spec)


def operation_for_path(api_path: str, method: str = "get") -> tuple[str, dict[str, Any]]:
    """Return the matching templated OpenAPI path and operation for an API path."""
    path_only = urlsplit(api_path).path
    method = method.lower()
    paths = load_openapi_spec()["paths"]

    if path_only in paths and method in paths[path_only]:
        return path_only, paths[path_only][method]

    for spec_path, operations in paths.items():
        if method not in operations:
            continue
        if re.fullmatch(_path_template_pattern(spec_path), path_only):
            return spec_path, operations[method]

    raise AssertionError(f"{method.upper()} {api_path} is not documented in {SPEC_PATH.name}")


def _path_template_pattern(spec_path: str) -> str:
    parts = re.split(r"(\{[^/]+\})", spec_path)
    return "^" + "".join("[^/]+" if part.startswith("{") else re.escape(part) for part in parts) + "$"


def documented_path(api_path: str, method: str = "get") -> str:
    """Return the matching OpenAPI path template for a concrete API path."""
    return operation_for_path(api_path, method)[0]


def json_example_for_path(api_path: str, method: str = "get", status: str = "200") -> Any:
    """Return an application/json response example for an API operation, if one is present."""
    _spec_path, operation = operation_for_path(api_path, method)
    media_type = operation.get("responses", {}).get(status, {}).get("content", {}).get("application/json", {})
    return media_type.get("example")
