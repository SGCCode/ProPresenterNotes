import importlib.util
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "capture_propresenter_examples.py"
SPEC = importlib.util.spec_from_file_location("capture_propresenter_examples", SCRIPT_PATH)
capture_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(capture_script)


class CaptureProPresenterExamplesTests(unittest.TestCase):
    def test_library_identifiers_include_uuid_name_and_index(self):
        identifiers = capture_script.library_identifiers(
            {
                "uuid": "30afaec9-33ff-406e-a2fa-7b7596aa56c2",
                "name": "Default",
                "index": 0,
            }
        )

        self.assertEqual(["30afaec9-33ff-406e-a2fa-7b7596aa56c2", "Default", "0"], identifiers)

    def test_presentation_identifiers_choose_first_available_value_per_item(self):
        identifiers = capture_script.presentation_identifiers(
            {
                "ok": True,
                "body": {
                    "update_type": "all",
                    "items": [
                        {"uuid": "deck-uuid", "name": "Deck", "index": 0},
                        {"name": "Name Only", "index": 1},
                        {"index": 2},
                        "ignored",
                    ],
                },
            }
        )

        self.assertEqual(["deck-uuid", "Name Only", "2"], identifiers)

    def test_decode_body_preserves_binary_payload_as_base64(self):
        decoded = capture_script.decode_body(b"jpeg", "image/jpeg")

        self.assertEqual("image/jpeg", decoded["content_type"])
        self.assertEqual(4, decoded["body_length"])
        self.assertEqual("anBlZw==", decoded["body_base64"])
        self.assertNotIn("body", decoded)


if __name__ == "__main__":
    unittest.main()
