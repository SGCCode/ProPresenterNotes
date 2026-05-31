import unittest

from propresenter_notes import create_app
from propresenter_notes.config import Settings


class FakeProPresenterClient:
    def __init__(self):
        self.paths = []

    def fetch(self, api_path, method="GET", body=None):
        self.paths.append((api_path, method, body))
        return 200, None


class TriggerRouteTests(unittest.TestCase):
    def make_client(self):
        app = create_app(Settings(ui_pin=""))
        app.config.update(TESTING=True)
        fake_client = FakeProPresenterClient()
        app.extensions["propresenter_client"] = fake_client
        return app.test_client(), fake_client

    def test_trigger_slide_uses_presentation_uuid_trigger_endpoint(self):
        client, fake_client = self.make_client()

        response = client.post(
            "/api/trigger/slide",
            json={"libraryId": "ignored-library", "presentationId": "presentation-uuid", "index": 4},
        )

        self.assertEqual(204, response.status_code)
        self.assertEqual(
            [("/v1/presentation/presentation-uuid/4/trigger", "GET", None)],
            fake_client.paths,
        )

    def test_trigger_slide_requires_presentation_id(self):
        client, fake_client = self.make_client()

        response = client.post("/api/trigger/slide", json={"index": 1})

        self.assertEqual(400, response.status_code)
        self.assertEqual({"error": "presentationId is required"}, response.get_json())
        self.assertEqual([], fake_client.paths)

    def test_trigger_slide_url_encodes_presentation_id_and_index(self):
        client, fake_client = self.make_client()

        response = client.post(
            "/api/trigger/slide",
            json={"presentationId": "uuid with/slash", "index": "2/3"},
        )

        self.assertEqual(204, response.status_code)
        self.assertEqual(
            [("/v1/presentation/uuid%20with%2Fslash/2%2F3/trigger", "GET", None)],
            fake_client.paths,
        )


if __name__ == "__main__":
    unittest.main()
