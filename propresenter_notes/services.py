"""Application services for presentation discovery and slide state parsing."""
from __future__ import annotations

import urllib.parse
from typing import Any

from .client import ProPresenterClient, ProPresenterError, is_image_response


def get_presentation(client: ProPresenterClient, presentation_id: str) -> dict[str, Any] | None:
    try:
        status, data = client.fetch(f"/v1/presentation/{urllib.parse.quote(presentation_id, safe='')}")
        if status == 200 and isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def get_presentation_thumbnail(
    client: ProPresenterClient, presentation_id: str, slide_index: int
) -> bytes | None:
    try:
        status, image_bytes, content_type = client.fetch_image(
            f"/v1/presentation/{urllib.parse.quote(presentation_id, safe='')}/thumbnail/"
            f"{urllib.parse.quote(str(slide_index), safe='')}?quality=400&thumbnail_type=jpeg"
        )
        if status == 200 and is_image_response(content_type):
            return image_bytes
    except Exception:
        pass
    return None


def first_non_empty_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def text_from_object(value: Any, depth: int = 0) -> str:
    if value is None or depth > 4:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(filter(None, (text_from_object(v, depth + 1) for v in value)))
    if isinstance(value, dict):
        preferred = first_non_empty_string(
            value.get("text"),
            value.get("plainText"),
            value.get("plain_text"),
            value.get("value"),
            value.get("body"),
            value.get("content"),
        )
        if preferred:
            return preferred
        return "\n".join(filter(None, (text_from_object(v, depth + 1) for v in value.values())))
    return ""


def find_notes(value: Any, seen: set[int] | None = None) -> str:
    if not isinstance(value, (dict, list)):
        return ""
    if seen is None:
        seen = set()
    ident = id(value)
    if ident in seen:
        return ""
    seen.add(ident)

    note_keys = [
        "notes",
        "note",
        "slide_notes",
        "slideNotes",
        "speaker_notes",
        "speakerNotes",
        "presenter_notes",
        "presenterNotes",
        "stage_notes",
        "stageNotes",
        "cue_notes",
        "cueNotes",
    ]
    if isinstance(value, dict):
        for key in note_keys:
            if key in value:
                found = text_from_object(value[key])
                if found:
                    return found
        iterable = value.values()
    else:
        iterable = value

    for item in iterable:
        found = find_notes(item, seen)
        if found:
            return found
    return ""


def find_slide_index(status: Any) -> int:
    if not isinstance(status, dict):
        return 0
    candidates = [
        status.get("index"),
        status.get("slide_index"),
        status.get("slideIndex"),
        nested(status, "presentation", "index"),
        nested(status, "presentation", "slideIndex"),
        nested(status, "cue", "index"),
        nested(status, "current", "index"),
        nested(status, "id", "index"),
    ]
    for candidate in candidates:
        try:
            parsed = int(candidate)
            if parsed >= 0:
                return parsed
        except Exception:
            continue
    return 0


def find_slide_title(status: Any) -> str:
    if not isinstance(status, dict):
        return ""
    return first_non_empty_string(
        status.get("name"),
        nested(status, "slide", "name"),
        nested(status, "cue", "name"),
        nested(status, "presentation", "name"),
        nested(status, "id", "name"),
    )


def nested(obj: Any, *keys: str) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def uuid_value(value: Any) -> str:
    if isinstance(value, dict):
        if isinstance(value.get("uuid"), dict):
            return uuid_value(value["uuid"])
        return str(value.get("uuid") or value.get("name") or value.get("index") or "")
    return str(value or "")


def flatten_presentations(
    nodes: Any, library_id: str | None = None, out: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    if out is None:
        out = []
    if not isinstance(nodes, list):
        return out
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id", node)
        node_library_id = library_id or uuid_value(node_id)
        if isinstance(node.get("items"), list):
            for item in node["items"]:
                if isinstance(item, dict) and item.get("id"):
                    out.append({"libraryId": node_library_id, "presentation": item["id"], "raw": item})
        for key in ("children", "libraries"):
            if isinstance(node.get(key), list):
                flatten_presentations(node[key], node_library_id, out)
    return out


def try_paths(client: ProPresenterClient, paths: list[str]) -> dict[str, Any]:
    errors = []
    for api_path in paths:
        if not api_path:
            continue
        try:
            _status, data = client.fetch(api_path)
            return {"ok": True, "path": api_path, "data": data}
        except Exception as exc:
            errors.append({"path": api_path, "message": str(exc)})
    return {"ok": False, "errors": errors}


def get_presentations(client: ProPresenterClient) -> list[dict[str, Any]]:
    _status, libraries = client.fetch("/v1/libraries")
    presentations: list[dict[str, Any]] = []
    for lib in libraries if isinstance(libraries, list) else []:
        lib_uuid = lib.get("uuid", lib) if isinstance(lib, dict) else lib
        library_uuid = uuid_value(lib_uuid)
        if not library_uuid:
            continue
        try:
            _s, library = client.fetch(f"/v1/library/{urllib.parse.quote(library_uuid, safe='')}")
            items = library.get("items") if isinstance(library, dict) else library if isinstance(library, list) else []
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict) and item.get("uuid"):
                    presentations.append({"library": lib, "presentation": item, "raw": item})
        except Exception:
            continue
    if not presentations:
        presentations.extend(flatten_presentations(libraries))
    return presentations


def get_slide_state(client: ProPresenterClient, library_id: str, presentation_id: str) -> dict[str, Any]:
    paths = [
        "/v1/status/slide",
        "/v1/presentation/active",
        f"/v1/presentation/{urllib.parse.quote(presentation_id, safe='')}" if presentation_id else "",
        f"/v1/library/{urllib.parse.quote(library_id, safe='')}/{urllib.parse.quote(presentation_id, safe='')}"
        if library_id and presentation_id
        else "",
    ]
    result = try_paths(client, paths)
    if not result.get("ok"):
        raise ProPresenterError(
            "Could not read slide status from ProPresenter",
            details={"attempts": result.get("errors")},
        )

    data = result.get("data")
    slide_index = find_slide_index(data)
    notes = find_notes(data)
    title = find_slide_title(data)

    if presentation_id and (not notes or not title):
        detail_paths = [
            f"/v1/presentation/{urllib.parse.quote(presentation_id, safe='')}",
            f"/v1/library/{urllib.parse.quote(library_id, safe='')}/{urllib.parse.quote(presentation_id, safe='')}"
            if library_id
            else "",
        ]
        detail = try_paths(client, detail_paths)
        if detail.get("ok"):
            d = detail.get("data")
            slides = []
            if isinstance(d, dict):
                slides = d.get("slides") or d.get("cues") or d.get("items") or nested(d, "presentation", "slides") or []
            elif isinstance(d, list):
                slides = d
            slide = slides[slide_index] if isinstance(slides, list) and slide_index < len(slides) else None
            notes = notes or find_notes(slide)
            title = title or find_slide_title(slide)

    return {
        "sourcePath": result.get("path"),
        "slideIndex": slide_index,
        "slideNumber": slide_index + 1,
        "title": title,
        "notes": notes,
        "raw": data,
    }
