import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from propresenter_notes.config import Settings, load_settings


class SettingsTests(unittest.TestCase):
    def test_base_url_and_timeout_are_derived_from_settings(self):
        settings = Settings(
            propresenter_scheme="https",
            propresenter_host="propresenter.local",
            propresenter_port=2048,
            poll_timeout_ms=1250,
        )

        self.assertEqual("https://propresenter.local:2048", settings.propresenter_base_url)
        self.assertEqual(1.25, settings.timeout_seconds)

    def test_timeout_has_minimum_floor(self):
        self.assertEqual(0.25, Settings(poll_timeout_ms=10).timeout_seconds)


class LoadSettingsTests(unittest.TestCase):
    def test_missing_config_uses_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = load_settings(Path(tmpdir) / "missing.json")

        self.assertEqual(Settings(), settings)

    def test_invalid_integers_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "app_port": "not-a-port",
                        "propresenter_port": None,
                        "poll_timeout_ms": "slow",
                    }
                ),
                encoding="utf-8",
            )

            settings = load_settings(path)

        self.assertEqual(Settings.app_port, settings.app_port)
        self.assertEqual(Settings.propresenter_port, settings.propresenter_port)
        self.assertEqual(Settings.poll_timeout_ms, settings.poll_timeout_ms)

    def test_environment_overrides_config_values(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {
                "APP_HOST": "0.0.0.0",
                "APP_PORT": "8080",
                "PROPRESENTER_SCHEME": "https",
                "PROPRESENTER_HOST": "deck.local",
                "PROPRESENTER_PORT": "2048",
                "POLL_TIMEOUT_MS": "5000",
                "UI_PIN": " 9999 ",
            },
        ):
            path = Path(tmpdir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "app_host": "127.0.0.1",
                        "app_port": 3000,
                        "propresenter_scheme": "http",
                        "propresenter_host": "127.0.0.1",
                        "propresenter_port": 1025,
                        "poll_timeout_ms": 2500,
                        "ui_pin": "1234",
                    }
                ),
                encoding="utf-8",
            )

            settings = load_settings(path)

        self.assertEqual("0.0.0.0", settings.app_host)
        self.assertEqual(8080, settings.app_port)
        self.assertEqual("https", settings.propresenter_scheme)
        self.assertEqual("deck.local", settings.propresenter_host)
        self.assertEqual(2048, settings.propresenter_port)
        self.assertEqual(5000, settings.poll_timeout_ms)
        self.assertEqual("9999", settings.ui_pin)


if __name__ == "__main__":
    unittest.main()
