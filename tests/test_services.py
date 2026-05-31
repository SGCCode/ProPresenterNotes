import unittest
from unittest.mock import patch

from propresenter_notes.client import ProPresenterError
from propresenter_notes.services import (
    build_presentation_cache,
    find_notes,
    find_slide_index,
    find_slide_title,
    flatten_presentations,
    get_presentations,
    get_slide_state,
    presentation_fingerprint,
    presentation_slides,
    text_from_object,
    try_paths,
    uuid_value,
)


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
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.paths = []

    def fetch(self, api_path):
        self.paths.append(api_path)
        response = self.responses.get(api_path, (200, PRESENTATION_PAYLOAD))
        if isinstance(response, Exception):
            raise response
        return response


class PresentationParsingTests(unittest.TestCase):
    def test_presentation_slides_flattens_grouped_propresenter_payload(self):
        slides = presentation_slides(PRESENTATION_PAYLOAD)

        self.assertEqual(3, len(slides))
        self.assertEqual("do not delete this slide", slides[0]["notes"])
        self.assertEqual("Slide notes for slide 1", slides[1]["notes"])
        self.assertEqual("slide notes for slide 2", slides[2]["notes"])

    def test_presentation_slides_supports_top_level_lists_and_alternate_keys(self):
        self.assertEqual([{"name": "Slide"}], presentation_slides([{"name": "Slide"}]))
        self.assertEqual([{"name": "Cue"}], presentation_slides({"presentation": {"cues": [{"name": "Cue"}]}}))
        self.assertEqual([], presentation_slides({"presentation": {"groups": []}}))

    def test_text_from_object_collects_nested_text(self):
        value = [{"text": "Line one"}, {"body": "Line two"}, 7]

        self.assertEqual("Line one\nLine two\n7", text_from_object(value))

    def test_find_notes_finds_preferred_note_keys_recursively_and_avoids_cycles(self):
        node = {"children": [{"slideNotes": {"plainText": "Speaker note"}}]}
        node["cycle"] = node

        self.assertEqual("Speaker note", find_notes(node))

    def test_find_slide_index_uses_first_non_negative_index_candidate(self):
        self.assertEqual(3, find_slide_index({"index": "3"}))
        self.assertEqual(5, find_slide_index({"presentation": {"slideIndex": 5}}))
        self.assertEqual(0, find_slide_index({"index": -1, "cue": {"index": "bad"}}))

    def test_find_slide_title_uses_label_name_text_and_nested_values(self):
        self.assertEqual("Welcome", find_slide_title({"label": " Welcome "}))
        self.assertEqual("Cue title", find_slide_title({"cue": {"name": "Cue title"}}))
        self.assertEqual("", find_slide_title([]))

    def test_uuid_value_reads_nested_uuid_name_index_or_scalar(self):
        self.assertEqual("abc", uuid_value({"uuid": {"uuid": "abc"}}))
        self.assertEqual("lib-1", uuid_value({"id": {"uuid": "lib-1", "name": "Library"}}))
        self.assertEqual("Library", uuid_value({"name": "Library"}))
        self.assertEqual("4", uuid_value({"index": 4}))
        self.assertEqual("plain", uuid_value("plain"))

    def test_flatten_presentations_walks_nested_libraries(self):
        libraries = [
            {
                "id": {"uuid": "lib-1"},
                "items": [{"id": {"uuid": "deck-1", "name": "Deck 1"}}, {"no_id": True}],
                "children": [{"id": {"uuid": "child-lib"}, "items": [{"id": {"uuid": "deck-2"}}]}],
            }
        ]

        flattened = flatten_presentations(libraries)

        self.assertEqual(2, len(flattened))
        self.assertEqual("lib-1", flattened[0]["libraryId"])
        self.assertEqual({"uuid": "deck-1", "name": "Deck 1"}, flattened[0]["presentation"])
        self.assertEqual("lib-1", flattened[1]["libraryId"])

    def test_presentation_fingerprint_is_stable_for_key_ordering(self):
        self.assertEqual(presentation_fingerprint({"b": 2, "a": 1}), presentation_fingerprint({"a": 1, "b": 2}))
        self.assertEqual("", presentation_fingerprint(None))


class PresentationServiceTests(unittest.TestCase):
    @patch("propresenter_notes.services.get_presentation_thumbnail", return_value=b"jpeg-bytes")
    def test_build_presentation_cache_uses_grouped_slides_and_titles(self, _thumbnail):
        cached = build_presentation_cache(FakeClient(), "70623736-5b63-4dd6-83e5-2c01c2897240")

        self.assertEqual("Sermon Deck", cached["title"])
        self.assertEqual(3, len(cached["slides"]))
        self.assertEqual("DO NOT DELETE", cached["slides"][0]["title"])
        self.assertEqual("Slide 1", cached["slides"][1]["title"])
        self.assertEqual("slide notes for slide 2", cached["slides"][2]["notes"])
        self.assertTrue(cached["slides"][0]["thumbnail"].startswith("data:image/jpeg;base64,"))

    def test_build_presentation_cache_raises_when_presentation_missing(self):
        client = FakeClient({"/v1/presentation/missing": (404, {"error": "missing"})})

        with self.assertRaises(ProPresenterError) as raised:
            build_presentation_cache(client, "missing")

        self.assertEqual(404, raised.exception.status_code)

    def test_try_paths_returns_first_success_and_records_failures(self):
        client = FakeClient({"/bad": RuntimeError("nope"), "/good": (200, {"ok": True})})

        result = try_paths(client, ["", "/bad", "/good"])

        self.assertEqual({"ok": True, "path": "/good", "data": {"ok": True}}, result)
        self.assertEqual(["/bad", "/good"], client.paths)

    def test_try_paths_returns_errors_when_all_paths_fail(self):
        client = FakeClient({"/bad": RuntimeError("nope")})

        result = try_paths(client, ["/bad"])

        self.assertFalse(result["ok"])
        self.assertEqual([{"path": "/bad", "message": "nope"}], result["errors"])

    def test_get_presentations_fetches_each_library_uuid(self):
        client = FakeClient(
            {
                "/v1/libraries": (200, [{"uuid": "lib one"}, {"uuid": "lib/two"}]),
                "/v1/library/lib%20one": (200, {"items": [{"uuid": "deck-1", "name": "Deck 1"}]}),
                "/v1/library/lib%2Ftwo": RuntimeError("offline"),
            }
        )

        presentations = get_presentations(client)

        self.assertEqual(1, len(presentations))
        self.assertEqual({"uuid": "deck-1", "name": "Deck 1"}, presentations[0]["presentation"])
        self.assertEqual(["/v1/libraries", "/v1/library/lib%20one", "/v1/library/lib%2Ftwo"], client.paths)

    def test_get_presentations_falls_back_to_flattening_library_payload(self):
        libraries = [{"id": {"uuid": "lib-1"}, "items": [{"id": {"uuid": "deck-1"}}]}]
        client = FakeClient({"/v1/libraries": (200, libraries), "/v1/library/lib-1": RuntimeError("old api")})

        presentations = get_presentations(client)

        self.assertEqual("lib-1", presentations[0]["libraryId"])
        self.assertEqual({"uuid": "deck-1"}, presentations[0]["presentation"])

    def test_get_slide_state_uses_status_payload(self):
        client = FakeClient({"/v1/status/slide": (200, {"index": 2, "label": "Verse", "notes": "Sing softly"})})

        state = get_slide_state(client, "lib", "deck")

        self.assertEqual("/v1/status/slide", state["sourcePath"])
        self.assertEqual(2, state["slideIndex"])
        self.assertEqual(3, state["slideNumber"])
        self.assertEqual("Verse", state["title"])
        self.assertEqual("Sing softly", state["notes"])

    def test_get_slide_state_falls_back_to_presentation_details_for_title_and_notes(self):
        client = FakeClient(
            {
                "/v1/status/slide": (200, {"index": 1}),
                "/v1/presentation/deck%20uuid": (
                    200,
                    {"presentation": {"groups": [{"slides": [{"label": "One"}, {"label": "Two", "notes": "Note two"}]}]}},
                ),
            }
        )

        state = get_slide_state(client, "lib uuid", "deck uuid")

        self.assertEqual("Two", state["title"])
        self.assertEqual("Note two", state["notes"])
        self.assertEqual(["/v1/status/slide", "/v1/presentation/deck%20uuid"], client.paths)

    def test_get_slide_state_raises_when_no_status_path_works(self):
        client = FakeClient({"/v1/status/slide": RuntimeError("offline"), "/v1/presentation/active": RuntimeError("offline")})

        with self.assertRaises(ProPresenterError) as raised:
            get_slide_state(client, "", "")

        self.assertEqual("Could not read slide status from ProPresenter", str(raised.exception))
        self.assertEqual(2, len(raised.exception.details["attempts"]))


if __name__ == "__main__":
    unittest.main()
