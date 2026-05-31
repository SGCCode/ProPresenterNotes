import unittest

from propresenter_notes import create_app
from propresenter_notes.client import ProPresenterError
from propresenter_notes.config import Settings


class FakeProPresenterClient:
    def __init__(self):
        self.paths = []
        self.responses = {}
        self.image_responses = {}

    def fetch(self, api_path, method="GET", body=None):
        self.paths.append((api_path, method, body))
        response = self.responses.get(api_path, (200, None))
        if isinstance(response, Exception):
            raise response
        return response

    def fetch_image(self, api_path, method="GET"):
        self.paths.append((api_path, method, None))
        response = self.image_responses.get(api_path, (200, b"jpeg-bytes", "image/jpeg"))
        if isinstance(response, Exception):
            raise response
        return response


class RouteTests(unittest.TestCase):
    def make_client(self):
        app = create_app(Settings(ui_pin=""))
        app.config.update(TESTING=True)
        fake_client = FakeProPresenterClient()
        app.extensions["propresenter_client"] = fake_client
        return app.test_client(), fake_client

    def test_api_config_returns_public_runtime_settings(self):
        client, _fake_client = self.make_client()

        response = client.get("/api/config")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"baseUrl": "http://127.0.0.1:1025", "pollTimeoutMs": 2500},
            response.get_json(),
        )

    def test_api_health_reports_successful_version_probe(self):
        client, fake_client = self.make_client()
        fake_client.responses["/version"] = (200, {"version": "18.0"})

        response = client.get("/api/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "path": "/version", "data": {"version": "18.0"}}, response.get_json())

    def test_api_health_reports_failed_version_probe(self):
        client, fake_client = self.make_client()
        fake_client.responses["/version"] = ProPresenterError("offline")

        response = client.get("/api/health")

        self.assertEqual(502, response.status_code)
        self.assertEqual(False, response.get_json()["ok"])
        self.assertEqual("/version", response.get_json()["errors"][0]["path"])

    def test_libraries_and_library_routes_proxy_to_propresenter(self):
        client, fake_client = self.make_client()
        fake_client.responses["/v1/libraries"] = (200, [{"uuid": "lib-1"}])
        fake_client.responses["/v1/library/lib%20one"] = (200, {"items": []})

        libraries_response = client.get("/api/libraries")
        library_response = client.get("/api/library/lib one")

        self.assertEqual(200, libraries_response.status_code)
        self.assertEqual([{"uuid": "lib-1"}], libraries_response.get_json())
        self.assertEqual(200, library_response.status_code)
        self.assertEqual({"items": []}, library_response.get_json())
        self.assertIn(("/v1/library/lib%20one", "GET", None), fake_client.paths)

    def test_presentation_cache_route_builds_cached_slide_payload(self):
        client, fake_client = self.make_client()
        fake_client.responses["/v1/presentation/deck%20uuid"] = (
            200,
            {
                "presentation": {
                    "id": {"name": "Sunday"},
                    "groups": [{"slides": [{"label": "Welcome", "notes": "Say hello"}]}],
                }
            },
        )

        response = client.get("/api/presentation-cache/deck uuid")

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("deck uuid", payload["presentationId"])
        self.assertEqual("Sunday", payload["title"])
        self.assertEqual("Welcome", payload["slides"][0]["title"])
        self.assertEqual("Say hello", payload["slides"][0]["notes"])
        self.assertTrue(payload["slides"][0]["thumbnail"].startswith("data:image/jpeg;base64,"))

    def test_presentation_fingerprint_route_returns_404_when_presentation_missing(self):
        client, fake_client = self.make_client()
        fake_client.responses["/v1/presentation/missing"] = (404, {"error": "missing"})

        response = client.get("/api/presentation-fingerprint/missing")

        self.assertEqual(404, response.status_code)
        self.assertEqual({"error": "Could not read presentation from ProPresenter"}, response.get_json())

    def test_trigger_next_and_previous_proxy_to_propresenter(self):
        client, fake_client = self.make_client()

        next_response = client.post("/api/trigger/next")
        previous_response = client.post("/api/trigger/previous")

        self.assertEqual(204, next_response.status_code)
        self.assertEqual(204, previous_response.status_code)
        self.assertEqual(
            [("/v1/trigger/next", "GET", None), ("/v1/trigger/previous", "GET", None)],
            fake_client.paths,
        )

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

    def test_propresenter_errors_are_returned_as_json(self):
        client, fake_client = self.make_client()
        fake_client.responses["/v1/trigger/next"] = ProPresenterError(
            "ProPresenter unavailable",
            status_code=503,
            details={"host": "127.0.0.1"},
        )

        response = client.post("/api/trigger/next")

        self.assertEqual(503, response.status_code)
        self.assertEqual(
            {"error": "ProPresenter unavailable", "details": {"host": "127.0.0.1"}},
            response.get_json(),
        )


if __name__ == "__main__":
    unittest.main()
