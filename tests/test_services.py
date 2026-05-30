import unittest
from unittest.mock import patch

from propresenter_notes.services import build_presentation_cache, presentation_slides


PRESENTATION_PAYLOAD = {
    "presentation": {
        "id": {
            "uuid": "70623736-5b63-4dd6-83e5-2c01c2897240",
            "name": "Sermon Deck",
            "index": 0,
        },
        "groups": [
            {
                "name": "",
                "color": None,
                "slides": [
                    {
                        "enabled": True,
                        "notes": "do not delete this slide",
                        "text": "Slide 0",
                        "label": "DO NOT DELETE",
                    },
                    {
                        "enabled": True,
                        "notes": "Slide notes for slide 1",
                        "text": "Slide 1",
                        "label": "",
                    },
                    {
                        "enabled": True,
                        "notes": "slide notes for slide 2",
                        "text": "Slide 2",
                        "label": "",
                    },
                ],
                "uuid": "43b9715f-614f-4819-a083-d82dc3cd44da",
            }
        ],
    }
}


class FakeClient:
    def fetch(self, api_path):
        self.last_path = api_path
        return 200, PRESENTATION_PAYLOAD


class PresentationCacheTests(unittest.TestCase):
    def test_presentation_slides_flattens_grouped_propresenter_payload(self):
        slides = presentation_slides(PRESENTATION_PAYLOAD)

        self.assertEqual(3, len(slides))
        self.assertEqual("do not delete this slide", slides[0]["notes"])
        self.assertEqual("Slide notes for slide 1", slides[1]["notes"])
        self.assertEqual("slide notes for slide 2", slides[2]["notes"])

    @patch("propresenter_notes.services.get_presentation_thumbnail", return_value=b"jpeg-bytes")
    def test_build_presentation_cache_uses_grouped_slides_and_titles(self, _thumbnail):
        cached = build_presentation_cache(FakeClient(), "70623736-5b63-4dd6-83e5-2c01c2897240")

        self.assertEqual("Sermon Deck", cached["title"])
        self.assertEqual(3, len(cached["slides"]))
        self.assertEqual("DO NOT DELETE", cached["slides"][0]["title"])
        self.assertEqual("Slide 1", cached["slides"][1]["title"])
        self.assertEqual("slide notes for slide 2", cached["slides"][2]["notes"])
        self.assertTrue(cached["slides"][0]["thumbnail"].startswith("data:image/jpeg;base64,"))


if __name__ == "__main__":
    unittest.main()
