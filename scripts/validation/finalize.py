
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
DRAFT_FILE = ROOT / "data/processed/extraction-draft.json"
CLASSIFICATION_FILE = ROOT / "data/processed/learning-classifications.json"
OUTPUT_FILE = ROOT / "data/processed/canonical-resources-v1.json"

EXPECTED = {
    "resources": 494,
    "practice": 453,
    "learning": 41,
    "practice_placements": 453,
    "learning_placements": 42,
    "total_placements": 495,
}

SOURCE_TIERS = {"basic", "core", "pro", None}
RESOURCE_TYPES = {"Coding Problem", "Concept", "Tutorial"}
CLASSIFICATIONS = {"Concept", "Tutorial"}

RESOURCE_KEYS = {
    "schemaVersion",
    "source",
    "stableId",
    "title",
    "type",
    "resourceType",
    "sourceTier",
    "duration",
    "placements",
    "resources",
}

SOURCE_KEYS = {
    "provider",
    "sourceId",
    "slug",
    "subjectSlug",
}

RESOURCE_URL_KEYS = {
    "primaryUrl",
    "articleUrl",
    "videoUrl",
    "leetcodeUrl",
}


def fail(message):
    raise ValueError(message)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Required file not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path}: {exc}")


def validate_url(value, field, stable_id):
    if value is None:
        return

    if not isinstance(value, str) or not value:
        fail(f"{stable_id}: {field} must be a non-empty URL or null.")

    parsed = urlparse(value)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        fail(f"{stable_id}: {field} is not an absolute HTTP(S) URL.")


def validate_placement(placement, stable_id):
    if not isinstance(placement, dict):
        fail(f"{stable_id}: placement must be an object.")

    required = {"module", "topic", "path", "sourceCategory"}

    if not required.issubset(placement):
        fail(f"{stable_id}: placement is missing required fields.")

    if not isinstance(placement["module"], str) or not placement["module"]:
        fail(f"{stable_id}: invalid placement module.")

    if not isinstance(placement["topic"], str) or not placement["topic"]:
        fail(f"{stable_id}: invalid placement topic.")

    path = placement["path"]

    if (
        not isinstance(path, list)
        or len(path) < 3
        or not all(isinstance(part, str) and part for part in path)
    ):
        fail(f"{stable_id}: invalid placement path.")

    if path[0] != placement["module"]:
        fail(f"{stable_id}: placement path/module mismatch.")

    if path[1] != placement["topic"]:
        fail(f"{stable_id}: placement path/topic mismatch.")

    if path[-1] != stable_id_to_title[stable_id]:
        fail(f"{stable_id}: placement path/title mismatch.")

    category = placement["sourceCategory"]

    if category is not None and not isinstance(category, str):
        fail(f"{stable_id}: sourceCategory must be a string or null.")


def validate_record(record):
    if not isinstance(record, dict):
        fail("Every resource must be a JSON object.")

    stable_id = record.get("stableId")

    if not isinstance(stable_id, str) or not stable_id:
        fail("Resource has a missing or invalid stableId.")

    if set(record) != RESOURCE_KEYS:
        missing = RESOURCE_KEYS - set(record)
        extra = set(record) - RESOURCE_KEYS
        fail(
            f"{stable_id}: record field mismatch. "
            f"Missing={sorted(missing)}, Extra={sorted(extra)}"
        )

    if record["schemaVersion"] != 1:
        fail(f"{stable_id}: unsupported schemaVersion.")

    if not isinstance(record["title"], str) or not record["title"]:
        fail(f"{stable_id}: invalid title.")

    source = record["source"]

    if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
        fail(f"{stable_id}: invalid source structure.")

    if source["provider"] != "takeuforward":
        fail(f"{stable_id}: unexpected source provider.")

    if (
        not isinstance(source["sourceId"], int)
        or isinstance(source["sourceId"], bool)
    ):
        fail(f"{stable_id}: sourceId must be an integer.")

    if not source["slug"] or not isinstance(source["slug"], str):
        fail(f"{stable_id}: invalid source slug.")

    if (
        not source["subjectSlug"]
        or not isinstance(source["subjectSlug"], str)
    ):
        fail(f"{stable_id}: invalid subjectSlug.")

    expected_stable_id = f"tuf-dsa-{source['sourceId']}"

    if stable_id != expected_stable_id:
        fail(f"{stable_id}: stableId does not match sourceId.")

    resource_type = record["type"]

    if resource_type not in ("practice", "learning"):
        fail(f"{stable_id}: invalid resource type.")

    if record["sourceTier"] not in SOURCE_TIERS:
        fail(f"{stable_id}: invalid sourceTier.")

    duration = record["duration"]

    if duration is not None and (
        not isinstance(duration, int)
        or isinstance(duration, bool)
        or duration < 0
    ):
        fail(f"{stable_id}: duration must be a non-negative integer or null.")

    resources = record["resources"]

    if not isinstance(resources, dict) or set(resources) != RESOURCE_URL_KEYS:
        fail(f"{stable_id}: invalid resources structure.")

    for field in RESOURCE_URL_KEYS:
        validate_url(resources[field], field, stable_id)

    if resource_type == "practice":
        if record["resourceType"] != "Coding Problem":
            fail(f"{stable_id}: practice resourceType must be Coding Problem.")

        expected_url = (
            "https://takeuforward.org/"
            f"{source['subjectSlug']}/practice/{source['slug']}"
        )

        if resources["primaryUrl"] != expected_url:
            fail(f"{stable_id}: practice primaryUrl is not canonical.")

    else:
        if record["resourceType"] not in CLASSIFICATIONS:
            fail(f"{stable_id}: learning resourceType is not classified.")

        if resources["primaryUrl"] != resources["articleUrl"]:
            fail(f"{stable_id}: learning primaryUrl must equal articleUrl.")

    placements = record["placements"]

    if not isinstance(placements, list) or not placements:
        fail(f"{stable_id}: placements must be a non-empty array.")

    for placement in placements:
        validate_placement(placement, stable_id)


def main():
    if OUTPUT_FILE.exists():
        fail(
            f"Output already exists: {OUTPUT_FILE}\n"
            "Refusing to overwrite it."
        )

    draft = read_json(DRAFT_FILE)
    manifest = read_json(CLASSIFICATION_FILE)

    if not isinstance(draft, list) or not isinstance(manifest, list):
        fail("Draft and classification manifest must be JSON arrays.")

    if len(draft) != EXPECTED["resources"]:
        fail(f"Expected 494 draft records, found {len(draft)}.")

    if len(manifest) != EXPECTED["learning"]:
        fail(f"Expected 41 classifications, found {len(manifest)}.")

    draft_by_id = {}

    for record in draft:
        stable_id = record.get("stableId")

        if not stable_id or stable_id in draft_by_id:
            fail(f"Duplicate or missing draft stableId: {stable_id}")

        draft_by_id[stable_id] = record

    manifest_by_id = {}

    for record in manifest:
        stable_id = record.get("stableId")

        if not stable_id or stable_id in manifest_by_id:
            fail(f"Duplicate or missing manifest stableId: {stable_id}")

        manifest_by_id[stable_id] = record

    learning_ids = {
        stable_id
        for stable_id, record in draft_by_id.items()
        if record.get("type") == "learning"
    }

    if learning_ids != set(manifest_by_id):
        fail("Manifest IDs do not exactly match draft learning IDs.")

    final_records = []

    for original in draft:
        record = dict(original)
        stable_id = record["stableId"]

        if record.get("type") == "learning":
            reviewed = manifest_by_id[stable_id]

            if reviewed.get("reviewStatus") != "approved":
                fail(f"{stable_id}: classification is not approved.")

            classification = reviewed.get("classification")

            if classification not in CLASSIFICATIONS:
                fail(f"{stable_id}: invalid learning classification.")

            record["resourceType"] = classification

        final_records.append(record)

    global stable_id_to_title
    stable_id_to_title = {
        record["stableId"]: record["title"]
        for record in final_records
    }

    for record in final_records:
        validate_record(record)

    practice = [r for r in final_records if r["type"] == "practice"]
    learning = [r for r in final_records if r["type"] == "learning"]

    practice_placements = sum(len(r["placements"]) for r in practice)
    learning_placements = sum(len(r["placements"]) for r in learning)
    total_placements = practice_placements + learning_placements

    actual = {
        "resources": len(final_records),
        "practice": len(practice),
        "learning": len(learning),
        "practice_placements": practice_placements,
        "learning_placements": learning_placements,
        "total_placements": total_placements,
    }

    if actual != EXPECTED:
        fail(
            "Dataset count mismatch.\n"
            f"Expected: {EXPECTED}\n"
            f"Actual: {actual}"
        )

    identities = [
        (
            r["source"]["provider"],
            r["source"]["subjectSlug"],
            r["source"]["sourceId"],
        )
        for r in final_records
    ]

    if len(identities) != len(set(identities)):
        fail("Duplicate source identity detected.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(
        final_records,
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=OUTPUT_FILE.parent,
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp.write(content)
            temp_path = Path(temp.name)

        # Atomic creation without overwriting an existing output.
        os.link(temp_path, OUTPUT_FILE)

    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()

    print("Canonical dataset generated successfully.")
    print("Output:", OUTPUT_FILE.relative_to(ROOT))
    print("Resources:", actual["resources"])
    print("Practice:", actual["practice"])
    print("Learning:", actual["learning"])
    print("Practice placements:", actual["practice_placements"])
    print("Learning placements:", actual["learning_placements"])
    print("Total placements:", actual["total_placements"])
    print("Canonical schema version: 1")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"\nERROR: {exc}")
