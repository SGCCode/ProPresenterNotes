import unittest

from propresenter_notes import create_app
from propresenter_notes.client import ProPresenterClient, ProPresenterError
from propresenter_notes.config import Settings

from tests.mock_propresenter_api import MockProPresenterAPIServer


class MockProPresenterAPIIntegrationTests(unittest.TestCase):
    def make_app_client(self, base_url):
        app = create_app(Settings(propresenter_host="127.0.0.1", ui_pin=""))
        app.config.update(TESTING=True)
        app.extensions["propresenter_client"] = ProPresenterClient(base_url, 2)
        return app.test_client()

    def test_health_uses_spec_example_version_payload_from_mock_api(self):
        with MockProPresenterAPIServer() as mock_api:
            response = self.make_app_client(mock_api.base_url).get("/api/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "ok": True,
                "path": "/version",
                "data": {
                    "api_version": "v1",
                    "host_description": "ProPresenter 7.8.1",
                    "name": "Main sanctuary Pro7 machine",
                    "os_version": "10.0.19043",
                    "platform": "win",
                },
            },
            response.get_json(),
        )

    def test_libraries_and_presentations_are_discovered_through_mock_api(self):
        with MockProPresenterAPIServer() as mock_api:
            client = self.make_app_client(mock_api.base_url)
            libraries_response = client.get("/api/libraries")
            presentations_response = client.get("/api/presentations")

            request_paths = [request["path"] for request in mock_api.requests]

        self.assertEqual(200, libraries_response.status_code)
        self.assertEqual(
            [
                {
                    "uuid": "30afaec9-33ff-406e-a2fa-7b7596aa56c2",
                    "name": "Default",
                    "index": 0,
                },
                {
                    "uuid": "fbd814b9-530c-4a66-bef1-0bd5a1db44ff",
                    "name": "Sample",
                    "index": 1,
                },
            ],
            libraries_response.get_json(),
        )
        presentations = presentations_response.get_json()
        self.assertEqual(16, len(presentations))
        self.assertEqual("Announcements", presentations[0]["presentation"]["name"])
        self.assertEqual("Greater Love Memorial Day", presentations[-1]["presentation"]["name"])
        self.assertEqual(
            [
                "/v1/libraries",
                "/v1/libraries",
                "/v1/library/30afaec9-33ff-406e-a2fa-7b7596aa56c2",
                "/v1/library/fbd814b9-530c-4a66-bef1-0bd5a1db44ff",
            ],
            request_paths,
        )

    def test_library_route_accepts_name_uuid_or_index_and_returns_404_for_unknown_ids(self):
        with MockProPresenterAPIServer() as mock_api:
            client = ProPresenterClient(mock_api.base_url, 2)
            for library_id in ("30afaec9-33ff-406e-a2fa-7b7596aa56c2", "Default", "0"):
                status, payload = client.fetch(f"/v1/library/{library_id}")
                self.assertEqual(200, status)
                self.assertEqual("all", payload["update_type"])
                self.assertEqual("Sermon Deck", payload["items"][3]["name"])

            with self.assertRaises(ProPresenterError) as raised:
                client.fetch("/v1/library/missing")

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual(
            {"content_type": "application/json", "details": {"error": "Library not found"}},
            raised.exception.details,
        )


if __name__ == "__main__":
    unittest.main()
