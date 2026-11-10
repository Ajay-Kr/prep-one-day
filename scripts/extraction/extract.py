#!/usr/bin/env python3
"""Extract Striver A2Z resources from the saved TakeUForward HTML snapshot."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = ROOT / "data/raw/tuf_sheet.html"
OUTPUT_DIR = ROOT / "data/processed"

DRAFT_FILE = OUTPUT_DIR / "extraction-draft.json"
CLASSIFICATION_FILE = OUTPUT_DIR / "learning-classifications.json"

BASE_URL = "https://takeuforward.org"
EXPECTED = {
    "practice_placements": 453,
    "learning_placements": 42,
    "unique_resources": 494,
    "unique_practice": 453,
    "unique_learning": 41,
}

PUSH_RE = re.compile(
    r"self\.__next_f\.push\((\[.*?\])\)</script>",
    re.DOTALL,
)


class ExtractionError(Exception):
    """Raised when the source does not match the expected structure."""


def fail(message: str) -> None:
    raise ExtractionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_syllabus(html: str) -> dict:
    """Decode the sheet_syllabus object embedded in the Next.js RSC payload."""
    payload_parts = []

    for match in PUSH_RE.finditer(html):
        try:
            chunk = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            fail(f"Could not decode an RSC payload chunk: {exc}")

        if (
            isinstance(chunk, list)
            and len(chunk) > 1
            and isinstance(chunk[1], str)
        ):
            payload_parts.append(chunk[1])

    if not payload_parts:
        fail("No usable Next.js RSC payload chunks were found.")

    payload = "".join(payload_parts)
    marker = '"sheet_syllabus":'
    marker_position = payload.find(marker)

    if marker_position == -1:
        fail('Could not find "sheet_syllabus" in the RSC payload.')

    object_start = payload.find("{", marker_position + len(marker))
    if object_start == -1:
        fail("Found sheet_syllabus marker but no JSON object follows it.")

    try:
        syllabus, _ = json.JSONDecoder().raw_decode(payload, object_start)
    except json.JSONDecodeError as exc:
        fail(f"Could not decode sheet_syllabus JSON: {exc}")

    for key in ("fields", "rows", "roots"):
        if key not in syllabus:
            fail(f"sheet_syllabus is missing required key: {key}")

    return syllabus


def decode_rows(syllabus: dict) -> list[dict]:
    fields = syllabus["fields"]
    rows = syllabus["rows"]

    if not isinstance(fields, list) or not isinstance(rows, list):
        fail("sheet_syllabus fields and rows must both be arrays.")

    decoded = []

    for index, compact_row in enumerate(rows):
        if not isinstance(compact_row, list) or not compact_row:
            fail(f"Row {index} is empty or malformed.")

        schema_index = compact_row[0]
        if not isinstance(schema_index, int) or not 0 <= schema_index < len(fields):
            fail(f"Row {index} has invalid schema index: {schema_index!r}")

        schema = fields[schema_index]
        values = compact_row[1:]

        if len(schema) != len(values):
            fail(
                f"Row {index} has {len(values)} values but "
                f"its schema defines {len(schema)} fields."
            )

        decoded.append(dict(zip(schema, values)))

    return decoded


def normalize_url(value, field_name: str, stable_id: str) -> str | None:
    if value is None or value == "":
        return None

    if not isinstance(value, str):
        fail(f"{stable_id}: {field_name} must be a string or null.")

    return urljoin(BASE_URL + "/", value)


def normalize_duration(value, stable_id: str) -> int | None:
    """Normalize source duration strings to integer minutes."""
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        fail(f"{stable_id}: duration cannot be a boolean.")

    if isinstance(value, int):
        if value < 0:
            fail(f"{stable_id}: duration cannot be negative.")
        return value

    if isinstance(value, float):
        if value < 0 or not value.is_integer():
            fail(f"{stable_id}: duration must be a non-negative integer.")
        return int(value)

    if not isinstance(value, str):
        fail(f"{stable_id}: unsupported duration value {value!r}.")

    match = re.fullmatch(r"\s*(\d+)\s*(min|minutes?|hours?)\s*", value, re.I)

    if not match:
        fail(
            f"{stable_id}: unrecognized duration {value!r}. "
            "Expected a numeric value followed by min or hours."
        )

    amount = int(match.group(1))
    unit = match.group(2).lower()

    if unit.startswith("hour"):
        amount *= 60

    return amount


def extract_resources(syllabus: dict, rows: list[dict]) -> tuple[list, list, dict]:
    roots = syllabus["roots"]
    if not isinstance(roots, list):
        fail("sheet_syllabus roots must be an array.")

    resources_by_id = {}
    placement_counts = {"practice": 0, "learning": 0}

    def visit(row_index: int, category_path: list[str], ancestors: set[int]):
        if not isinstance(row_index, int) or not 0 <= row_index < len(rows):
            fail(f"Hierarchy contains invalid row reference: {row_index!r}")

        if row_index in ancestors:
            fail(f"Hierarchy cycle detected at row {row_index}.")

        row = rows[row_index]
        row_type = row.get("type")

        if row_type == "category":
            label = row.get("label")
            if not isinstance(label, str) or not label.strip():
                fail(f"Category row {row_index} has no valid label.")

            next_path = category_path + [label.strip()]
            children = row.get("children") or []

            if not isinstance(children, list):
                fail(f"Category row {row_index} has malformed children.")

            next_ancestors = ancestors | {row_index}
            for child_index in children:
                visit(child_index, next_path, next_ancestors)
            return

        if row_type != "item":
            return

        layout = row.get("layoutType")
        if layout not in ("practice", "learning"):
            return

        source_id = row.get("id")
        title = row.get("label")
        slug = row.get("slug")
        redirect = row.get("redirectTo")

        if source_id is None or not isinstance(title, str) or not title.strip():
            fail(f"Item row {row_index} is missing its source ID or title.")

        if not isinstance(slug, str) or not slug:
            fail(f"Item {source_id} ({title}) has no source slug.")

        if not isinstance(redirect, dict):
            fail(f"Item {source_id} ({title}) has no redirectTo object.")

        subject_slug = redirect.get("subjectSlug") or row.get("subjectSlug")
        item_slug = redirect.get("itemSlug") or row.get("itemSlug")

        if not isinstance(subject_slug, str) or not subject_slug:
            fail(f"Item {source_id} ({title}) has no subjectSlug.")

        stable_id = f"tuf-dsa-{source_id}"

        if layout == "practice" and (
            not isinstance(item_slug, str) or not item_slug
        ):
            fail(f"Practice item {stable_id} has no itemSlug.")

        if not category_path:
            fail(f"Item {stable_id} has no category placement.")

        placement = {
            "module": category_path[0],
            "topic": category_path[-1],
            "path": category_path + [title.strip()],
            "sourceCategory": redirect.get("category") or row.get("category"),
        }

        placement_counts[layout] += 1

        if stable_id not in resources_by_id:
            source_tier = row.get("difficulty")
            if source_tier not in (None, "basic", "core", "pro"):
                fail(
                    f"{stable_id}: unexpected source tier "
                    f"{source_tier!r}; refusing to map it."
                )

            if layout == "practice":
                primary_url = (
                    f"{BASE_URL}/{subject_slug}/practice/{item_slug}"
                )
            else:
                primary_url = normalize_url(
                    row.get("free_blog_link"), "free_blog_link", stable_id
                )

            resources_by_id[stable_id] = {
                "schemaVersion": 1,
                "source": {
                    "provider": "takeuforward",
                    "sourceId": source_id,
                    "slug": slug,
                    "subjectSlug": subject_slug,
                },
                "stableId": stable_id,
                "title": title.strip(),
                "type": layout,
                "resourceType": (
                    "Coding Problem" if layout == "practice" else None
                ),
                "sourceTier": source_tier,
                "duration": normalize_duration(row.get("duration"), stable_id),
                "placements": [],
                "resources": {
                    "primaryUrl": primary_url,
                    "articleUrl": normalize_url(
                        row.get("free_blog_link"), "free_blog_link", stable_id
                    ),
                    "videoUrl": normalize_url(
                        row.get("yt_video"), "yt_video", stable_id
                    ),
                    "leetcodeUrl": normalize_url(
                        row.get("leetcode_link"), "leetcode_link", stable_id
                    ),
                },
            }
        else:
            existing = resources_by_id[stable_id]
            if (
                existing["title"] != title.strip()
                or existing["type"] != layout
                or existing["source"]["slug"] != slug
            ):
                fail(
                    f"Conflicting source metadata for duplicate "
                    f"resource {stable_id}."
                )

        resources_by_id[stable_id]["placements"].append(placement)

    for root_index in roots:
        visit(root_index, [], set())

    resources = list(resources_by_id.values())
    classifications = []

    for resource in resources:
        if resource["type"] == "learning":
            classifications.append({
                "stableId": resource["stableId"],
                "title": resource["title"],
                "articleUrl": resource["resources"]["articleUrl"],
                "videoUrl": resource["resources"]["videoUrl"],
                "placements": resource["placements"],
                "classification": None,
                "rationale": None,
                "reviewStatus": "needs_review",
            })

    return resources, classifications, placement_counts


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if not SOURCE_FILE.is_file():
        fail(f"Raw source file does not exist: {SOURCE_FILE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    existing_outputs = [
        str(path.relative_to(ROOT))
        for path in (DRAFT_FILE, CLASSIFICATION_FILE)
        if path.exists()
    ]
    if existing_outputs:
        fail(
            "Refusing to overwrite existing output(s): "
            + ", ".join(existing_outputs)
        )

    initial_checksum = sha256(SOURCE_FILE)
    html = SOURCE_FILE.read_text(encoding="utf-8")

    syllabus = decode_syllabus(html)
    rows = decode_rows(syllabus)

    print(
        f"Decoded source: {len(syllabus['fields'])} field schemas, "
        f"{len(rows)} rows, {len(syllabus['roots'])} roots"
    )

    resources, classifications, counts = extract_resources(syllabus, rows)

    practice_count = sum(r["type"] == "practice" for r in resources)
    learning_count = sum(r["type"] == "learning" for r in resources)

    actual = {
        "practice_placements": counts["practice"],
        "learning_placements": counts["learning"],
        "unique_resources": len(resources),
        "unique_practice": practice_count,
        "unique_learning": learning_count,
    }

    print("\nExtraction counts:")
    for key, value in actual.items():
        print(f"  {key}: {value} (expected {EXPECTED[key]})")

    if actual != EXPECTED:
        fail(
            "Extraction counts differ from the verified source baseline. "
            "No output files have been written."
        )

    if len(classifications) != EXPECTED["unique_learning"]:
        fail("Learning classification manifest has an unexpected record count.")

    final_checksum = sha256(SOURCE_FILE)
    if final_checksum != initial_checksum:
        fail("Raw HTML checksum changed during extraction.")

    # Both output paths were checked before writing; use temporary files
    # so incomplete JSON is not left behind if serialization fails.
    draft_temp = DRAFT_FILE.with_suffix(".json.tmp")
    classification_temp = CLASSIFICATION_FILE.with_suffix(".json.tmp")

    try:
        write_json(draft_temp, resources)
        write_json(classification_temp, classifications)
        draft_temp.replace(DRAFT_FILE)
        classification_temp.replace(CLASSIFICATION_FILE)
    except Exception:
        draft_temp.unlink(missing_ok=True)
        classification_temp.unlink(missing_ok=True)
        DRAFT_FILE.unlink(missing_ok=True)
        CLASSIFICATION_FILE.unlink(missing_ok=True)
        raise

    print("\nOutput files:")
    print(f"  {DRAFT_FILE.relative_to(ROOT)}")
    print(f"  {CLASSIFICATION_FILE.relative_to(ROOT)}")
    print(f"\nRaw source SHA-256: {final_checksum}")
    print("Extraction completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ExtractionError, OSError, json.JSONDecodeError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
