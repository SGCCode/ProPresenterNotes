import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from propresenter_notes.client import (
    ProPresenterClient,
    ProPresenterError,
    clean_api_path,
    is_image_response,
    parse_response_body,
)


class ClientHelperTests(unittest.TestCase):
    def test_clean_api_path_allows_supported_paths_and_query_strings(self):
        self.assertEqual("/version", clean_api_path("/version"))
        self.assertEqual("/v1/libraries?include=all", clean_api_path("/v1/libraries?include=all"))

    def test_clean_api_path_rejects_unsupported_paths(self):
        with self.assertRaises(ValueError):
            clean_api_path("/v2/libraries")

        with self.assertRaises(ValueError):
            clean_api_path("https://example.com/v1/libraries")

    def test_parse_response_body_handles_json_text_empty_and_invalid_json(self):
        self.assertIsNone(parse_response_body(b"", "application/json"))
        self.assertEqual({"ok": True}, parse_response_body(b'{"ok": true}', "application/json"))
        self.assertEqual({"ok": True}, parse_response_body(b'{"ok": true}', "text/plain"))
        self.assertEqual("not json", parse_response_body(b"not json", "application/json"))

    def test_is_image_response_requires_image_content_type(self):
        self.assertTrue(is_image_response("image/jpeg"))
        self.assertTrue(is_image_response("IMAGE/PNG; charset=binary"))
        self.assertFalse(is_image_response("application/json"))


class ProPresenterClientTests(unittest.TestCase):
    @patch("propresenter_notes.client.urllib.request.urlopen")
    def test_fetch_sends_json_body_and_parses_response(self, urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"saved": true}'
        response.headers.get.return_value = "application/json"
        response.__enter__.return_value = response
        urlopen.return_value = response

        client = ProPresenterClient("http://localhost:1025/", 1.5)
        status, data = client.fetch("/v1/test", method="POST", body={"name": "Deck"})

        self.assertEqual(200, status)
        self.assertEqual({"saved": True}, data)
        request = urlopen.call_args.args[0]
        self.assertEqual("http://localhost:1025/v1/test", request.full_url)
        self.assertEqual("POST", request.get_method())
        self.assertEqual(json.dumps({"name": "Deck"}).encode("utf-8"), request.data)
        self.assertEqual("application/json", request.headers["Content-type"])

    @patch("propresenter_notes.client.urllib.request.urlopen")
    def test_fetch_raw_wraps_http_errors_with_details(self, urlopen):
        error = urllib.error.HTTPError(
            url="http://localhost:1025/v1/test",
            code=418,
            msg="teapot",
            hdrs={"content-type": "application/json"},
            fp=None,
        )
        error.read = MagicMock(return_value=b'{"error": "short"}')
        urlopen.side_effect = error

        client = ProPresenterClient("http://localhost:1025", 1.0)

        with self.assertRaises(ProPresenterError) as raised:
            client.fetch("/v1/test")

        self.assertEqual(418, raised.exception.status_code)
        self.assertEqual(
            {"content_type": "application/json", "details": {"error": "short"}},
            raised.exception.details,
        )

    @patch("propresenter_notes.client.urllib.request.urlopen")
    def test_fetch_image_rejects_non_image_responses(self, urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"not": "image"}'
        response.headers.get.return_value = "application/json"
        response.__enter__.return_value = response
        urlopen.return_value = response

        client = ProPresenterClient("http://localhost:1025", 1.0)

        with self.assertRaises(ProPresenterError) as raised:
            client.fetch_image("/v1/presentation/deck/thumbnail/0")

        self.assertEqual(200, raised.exception.status_code)
        self.assertEqual({"content_type": "application/json"}, raised.exception.details)


if __name__ == "__main__":
    unittest.main()
