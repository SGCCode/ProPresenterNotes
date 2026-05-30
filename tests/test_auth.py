import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from propresenter_notes import create_app
from propresenter_notes.config import Settings, load_settings


class PinAuthTests(unittest.TestCase):
    def make_client(self, ui_pin="1234"):
        app = create_app(Settings(ui_pin=ui_pin))
        app.config.update(TESTING=True)
        return app.test_client()

    def test_pin_auth_disabled_by_default_allows_ui(self):
        client = self.make_client(ui_pin="")

        response = client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn(b"ProPresenter Notes", response.data)

    def test_pin_auth_redirects_page_requests_to_login(self):
        client = self.make_client()

        response = client.get("/")

        self.assertEqual(302, response.status_code)
        self.assertIn("/login?next=/", response.headers["Location"])

    def test_pin_auth_blocks_api_requests_with_401(self):
        client = self.make_client()

        response = client.get("/api/config")

        self.assertEqual(401, response.status_code)
        self.assertEqual({"error": "PIN required"}, response.get_json())

    def test_successful_login_allows_ui_and_api(self):
        client = self.make_client()

        login_response = client.post("/login", data={"pin": "1234", "next": "/"})
        ui_response = client.get("/")
        api_response = client.get("/api/config")

        self.assertEqual(302, login_response.status_code)
        self.assertEqual("/", login_response.headers["Location"])
        self.assertEqual(200, ui_response.status_code)
        self.assertIn(b"Lock", ui_response.data)
        self.assertEqual(200, api_response.status_code)
        self.assertIn("baseUrl", api_response.get_json())

    def test_invalid_login_shows_error(self):
        client = self.make_client()

        response = client.post("/login", data={"pin": "wrong"})

        self.assertEqual(200, response.status_code)
        self.assertIn(b"Invalid PIN", response.data)

    def test_login_next_url_must_be_local(self):
        client = self.make_client()

        response = client.post("/login", data={"pin": "1234", "next": "https://example.com"})

        self.assertEqual(302, response.status_code)
        self.assertEqual("/", response.headers["Location"])


class PinConfigTests(unittest.TestCase):
    def test_ui_pin_loads_from_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            path.write_text(json.dumps({"ui_pin": "2468"}), encoding="utf-8")

            settings = load_settings(path)

        self.assertEqual("2468", settings.ui_pin)

    def test_ui_pin_env_override_takes_precedence(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict("os.environ", {"UI_PIN": "1357"}):
            path = Path(tmpdir) / "config.json"
            path.write_text(json.dumps({"ui_pin": "2468"}), encoding="utf-8")

            settings = load_settings(path)

        self.assertEqual("1357", settings.ui_pin)


if __name__ == "__main__":
    unittest.main()
