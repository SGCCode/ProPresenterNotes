"""Configuration loading for ProPresenter Notes."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    app_host: str = "127.0.0.1"
    app_port: int = 3000
    propresenter_scheme: str = "http"
    propresenter_host: str = "127.0.0.1"
    propresenter_port: int = 1025
    poll_timeout_ms: int = 2500
    ui_pin: str = ""

    @property
    def propresenter_base_url(self) -> str:
        return f"{self.propresenter_scheme}://{self.propresenter_host}:{self.propresenter_port}"

    @property
    def timeout_seconds(self) -> float:
        return max(self.poll_timeout_ms / 1000.0, 0.25)


def _int_value(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def load_settings(config_path: Path) -> Settings:
    """Load app settings from config.json with environment variable overrides."""
    data: dict[str, Any] = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Warning: could not read config.json: {exc}", file=sys.stderr)

    return Settings(
        app_host=os.environ.get("APP_HOST", data.get("app_host", Settings.app_host)),
        app_port=_int_value(os.environ.get("APP_PORT", data.get("app_port")), Settings.app_port),
        propresenter_scheme=os.environ.get(
            "PROPRESENTER_SCHEME", data.get("propresenter_scheme", Settings.propresenter_scheme)
        ),
        propresenter_host=os.environ.get(
            "PROPRESENTER_HOST", data.get("propresenter_host", Settings.propresenter_host)
        ),
        propresenter_port=_int_value(
            os.environ.get("PROPRESENTER_PORT", data.get("propresenter_port")),
            Settings.propresenter_port,
        ),
        poll_timeout_ms=_int_value(
            os.environ.get("POLL_TIMEOUT_MS", data.get("poll_timeout_ms")),
            Settings.poll_timeout_ms,
        ),
        ui_pin=str(os.environ.get("UI_PIN", data.get("ui_pin", Settings.ui_pin))).strip(),
    )
