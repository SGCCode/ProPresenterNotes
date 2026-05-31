import unittest

from propresenter_notes import create_app
from propresenter_notes.client import clean_api_path
from propresenter_notes.config import Settings
from propresenter_notes.services import get_presentations

from tests.openapi_spec import documented_path, json_example_for_path, load_openapi_spec


class FakeProPresenterClient:
    def __init__(self):
        self.paths = []
        self.responses = {}
        self.image_responses = {}

    def fetch(self, api_path, method="GET", body=None):
        self.paths.append((api_path, method, body))
        response = self.responses.get(api_path, (200, {}))
        if isinstance(response, Exception):
            raise response
        return response

    def fetch_image(self, api_path, method="GET"):
        self.paths.append((api_path, method, None))
        response = self.image_responses.get(api_path, (200, b"jpeg-bytes", "image/jpeg"))
        if isinstance(response, Exception):
            raise response
        return response


class SwaggerContractTests(unittest.TestCase):
    def make_client(self):
        app = create_app(Settings(ui_pin=""))
        app.config.update(TESTING=True)
        fake_client = FakeProPresenterClient()
        app.extensions["propresenter_client"] = fake_client
        return app.test_client(), fake_client

    def test_checked_in_swagger_spec_loads_as_openapi_document(self):
        spec = load_openapi_spec()

        self.assertEqual("3.0.2", spec["openapi"])
        self.assertEqual("ProPresenter API", spec["info"]["title"])
        self.assertIn("/version", spec["paths"])
        self.assertIn("/v1/libraries", spec["paths"])
        self.assertIn("/v1/presentation/{uuid}/thumbnail/{index}", spec["paths"])

    def test_client_accepts_representative_documented_swagger_paths(self):
        documented_examples = [
            "/version",
            "/v1/libraries",
            "/v1/library/Library%20Name",
            "/v1/presentation/3C39C433-5C18-4F51-B357-55BB870227C4",
            "/v1/presentation/3C39C433-5C18-4F51-B357-55BB870227C4/thumbnail/0?quality=400&thumbnail_type=jpeg",
            "/v1/presentation/3C39C433-5C18-4F51-B357-55BB870227C4/0/trigger",
            "/v1/status/slide",
            "/v1/trigger/next",
            "/v1/trigger/previous",
        ]

        for api_path in documented_examples:
            with self.subTest(api_path=api_path):
                self.assertEqual(api_path, clean_api_path(api_path))
                self.assertIsInstance(documented_path(api_path), str)

    def test_app_propresenter_requests_are_documented_by_swagger(self):
        client, fake_client = self.make_client()
        fake_client.responses.update(
            {
                "/version": (200, {"api_version": "v1"}),
                "/v1/libraries": (
                    200,
                    [{"id": {"uuid": "lib-1", "name": "Library Name", "index": 0}}],
                ),
                "/v1/library/lib-1": (200, {"items": [{"uuid": "deck-1", "name": "Deck 1"}]}),
                "/v1/library/Library%20Name": (200, {"items": []}),
                "/v1/presentation/deck-1": (
                    200,
                    {"presentation": {"id": {"name": "Deck 1"}, "groups": [{"slides": [{"label": "Welcome"}]}]}},
                ),
                "/v1/status/slide": (200, {"index": 0, "label": "Welcome", "notes": "Say hello"}),
                "/v1/trigger/next": (204, None),
                "/v1/trigger/previous": (204, None),
                "/v1/presentation/deck-1/0/trigger": (204, None),
            }
        )

        route_calls = [
            lambda: client.get("/api/health"),
            lambda: client.get("/api/libraries"),
            lambda: client.get("/api/library/Library Name"),
            lambda: client.get("/api/presentations"),
            lambda: client.get("/api/presentation-cache/deck-1"),
            lambda: client.get("/api/presentation-fingerprint/deck-1"),
            lambda: client.get("/api/slide-state?libraryId=lib-1&presentationId=deck-1"),
            lambda: client.post("/api/trigger/next"),
            lambda: client.post("/api/trigger/previous"),
            lambda: client.post("/api/trigger/slide", json={"presentationId": "deck-1", "index": 0}),
        ]

        for call_route in route_calls:
            response = call_route()
            self.assertLess(response.status_code, 500, response.get_data(as_text=True))

        self.assertGreater(len(fake_client.paths), 0)
        for api_path, method, _body in fake_client.paths:
            with self.subTest(method=method, api_path=api_path):
                self.assertIsInstance(documented_path(api_path, method), str)

    def test_swagger_libraries_example_can_drive_presentation_discovery(self):
        libraries_example = json_example_for_path("/v1/libraries")
        self.assertIsInstance(libraries_example, list)
        library_uuid = libraries_example[0]["id"]["uuid"]
        client = FakeProPresenterClient()
        client.responses.update(
            {
                "/v1/libraries": (200, libraries_example),
                f"/v1/library/{library_uuid}": (200, {"items": [{"uuid": "deck-1", "name": "Deck 1"}]}),
            }
        )

        presentations = get_presentations(client)

        self.assertEqual([{"uuid": "deck-1", "name": "Deck 1"}], [item["presentation"] for item in presentations])
        self.assertEqual(["/v1/libraries", f"/v1/library/{library_uuid}"], [path for path, _method, _body in client.paths])


if __name__ == "__main__":
    unittest.main()
