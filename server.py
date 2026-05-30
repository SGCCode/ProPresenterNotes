#!/usr/bin/env python3
"""WSGI entry point for the ProPresenter Notes Flask application."""
from __future__ import annotations

from propresenter_notes import CONFIG_PATH, create_app
from propresenter_notes.config import load_settings

SETTINGS = load_settings(CONFIG_PATH)
app = create_app(SETTINGS)


def main() -> None:
    url = f"http://{SETTINGS.app_host}:{SETTINGS.app_port}"
    print(f"ProPresenter Notes Controller running at {url}")
    print(f"Proxying ProPresenter at {SETTINGS.propresenter_base_url}")
    app.run(host=SETTINGS.app_host, port=SETTINGS.app_port, threaded=True)


if __name__ == "__main__":
    main()
