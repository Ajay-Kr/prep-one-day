
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]

CANONICAL_FILE = ROOT / "data/processed/canonical-resources-v1.json"
DRAFT_FILE = ROOT / "data/processed/extraction-draft.json"
MANIFEST_FILE = ROOT / "data/processed/learning-classifications.json"

EXPECTED = {
    "resources": 494,
    "practice": 453,
    "learning": 41,
    "practice_placements": 453,
    "learning_placements": 42,
    "total_placements": 495,
}

RECORD_KEYS = {
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

RESOURCE_KEYS = {
    "primaryUrl",
    "articleUrl",
    "videoUrl",
    "leetcodeUrl",
}

PLACEMENT_KEYS = {
    "module",
    "topic",
    "path",
    "sourceCategory",
}

SOURCE_TIERS = {"basic", "core", "pro", None}
LEARNING_TYPES = {"Concept", "Tutorial"}
EVIDENCE_STATUSES = {
    "content_verified",
    "secondary_evidence",
    "unverified",
    "source_label_only",
    "coming_soon",
    "user_verified",
}

errors = []


def error(message):
    errors.append(message)


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        error(f"File not found: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        error(f"Invalid JSON in {path.name}: {exc}")
    return None


def is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_url(value, field, stable_id):
    if value is None:
        return

    if not is_nonempty_string(value):
        error(f"{stable_id}: {field} must be a URL or null.")
        return

    parsed = urlparse(value)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or not parsed.hostname
    ):
        error(f"{stable_id}: {field} is not an absolute HTTP(S) URL.")


def validate_record(record):
    if not isinstance(record, dict):
        error("Resource record must be an object.")
        return

    stable_id = record.get("stableId")

    if not is_nonempty_string(stable_id):
        error("Resource has a missing or invalid stableId.")
        return

    if set(record) != RECORD_KEYS:
        missing = RECORD_KEYS - set(record)
        extra = set(record) - RECORD_KEYS
        error(
            f"{stable_id}: field mismatch. "
            f"Missing={sorted(missing)}, Extra={sorted(extra)}"
        )

    if (
        type(record.get("schemaVersion")) is not int
        or record["schemaVersion"] != 1
    ):
        error(f"{stable_id}: schemaVersion must be integer 1.")

    if not is_nonempty_string(record.get("title")):
        error(f"{stable_id}: title must be a non-empty string.")

    source = record.get("source")

    if not isinstance(source, dict):
        error(f"{stable_id}: source must be an object.")
        return

    if set(source) != SOURCE_KEYS:
        error(f"{stable_id}: source fields do not match schema.")

    if source.get("provider") != "takeuforward":
        error(f"{stable_id}: unexpected source provider.")

    source_id = source.get("sourceId")

    if type(source_id) is not int or source_id < 0:
        error(f"{stable_id}: sourceId must be a non-negative integer.")
    elif stable_id != f"tuf-dsa-{source_id}":
        error(f"{stable_id}: stableId does not match sourceId.")

    if not is_nonempty_string(source.get("slug")):
        error(f"{stable_id}: source slug is invalid.")

    if not is_nonempty_string(source.get("subjectSlug")):
        error(f"{stable_id}: subjectSlug is invalid.")

    resource_type = record.get("type")

    if resource_type not in ("practice", "learning"):
        error(f"{stable_id}: type must be practice or learning.")

    if record.get("sourceTier") not in SOURCE_TIERS:
        error(f"{stable_id}: invalid sourceTier.")

    duration = record.get("duration")

    if duration is not None and (
        type(duration) is not int or duration < 0
    ):
        error(f"{stable_id}: duration must be a non-negative integer or null.")

    resources = record.get("resources")

    if not isinstance(resources, dict):
        error(f"{stable_id}: resources must be an object.")
        return

    if set(resources) != RESOURCE_KEYS:
        error(f"{stable_id}: resources fields do not match schema.")

    for field in RESOURCE_KEYS:
        validate_url(resources.get(field), field, stable_id)

    if resource_type == "practice":
        if record.get("resourceType") != "Coding Problem":
            error(f"{stable_id}: practice resourceType must be Coding Problem.")

        expected_url = (
            "https://takeuforward.org/"
            f"{source.get('subjectSlug')}/practice/{source.get('slug')}"
        )

        if resources.get("primaryUrl") != expected_url:
            error(f"{stable_id}: incorrect canonical practice URL.")

        if resources.get("primaryUrl") is None:
            error(f"{stable_id}: practice primaryUrl cannot be null.")

    elif resource_type == "learning":
        if record.get("resourceType") not in LEARNING_TYPES:
            error(f"{stable_id}: invalid learning resourceType.")

        if resources.get("primaryUrl") != resources.get("articleUrl"):
            error(f"{stable_id}: learning primaryUrl must equal articleUrl.")

    placements = record.get("placements")

    if not isinstance(placements, list) or not placements:
        error(f"{stable_id}: placements must be a non-empty array.")
        return

    for index, placement in enumerate(placements):
        if not isinstance(placement, dict):
            error(f"{stable_id}: placement {index} must be an object.")
            continue

        if set(placement) != PLACEMENT_KEYS:
            error(f"{stable_id}: placement {index} fields do not match schema.")

        module = placement.get("module")
        topic = placement.get("topic")
        path = placement.get("path")
        category = placement.get("sourceCategory")

        if not is_nonempty_string(module):
            error(f"{stable_id}: placement {index} has invalid module.")

        if not is_nonempty_string(topic):
            error(f"{stable_id}: placement {index} has invalid topic.")

        if (
            not isinstance(path, list)
            or len(path) < 3
            or not all(is_nonempty_string(part) for part in path)
        ):
            error(f"{stable_id}: placement {index} has invalid path.")
        else:
            if path[0] != module:
                error(f"{stable_id}: placement {index} module/path mismatch.")

            if path[1] != topic:
                error(f"{stable_id}: placement {index} topic/path mismatch.")

            if path[-1] != record.get("title"):
                error(f"{stable_id}: placement {index} title/path mismatch.")

        if category is not None and not isinstance(category, str):
            error(f"{stable_id}: placement {index} sourceCategory is invalid.")


def index_records(records, label):
    indexed = {}

    for record in records:
        if not isinstance(record, dict):
            error(f"{label}: non-object record found.")
            continue

        stable_id = record.get("stableId")

        if not is_nonempty_string(stable_id):
            error(f"{label}: record with missing stableId.")
            continue

        if stable_id in indexed:
            error(f"{label}: duplicate stableId {stable_id}.")
            continue

        indexed[stable_id] = record

    return indexed


def validate_source_preservation(canonical, draft, manifest):
    canonical_by_id = index_records(canonical, "Canonical")
    draft_by_id = index_records(draft, "Draft")
    manifest_by_id = index_records(manifest, "Manifest")

    if set(canonical_by_id) != set(draft_by_id):
        error("Canonical and draft stable ID sets differ.")

    learning_ids = {
        stable_id
        for stable_id, record in draft_by_id.items()
        if record.get("type") == "learning"
    }

    if learning_ids != set(manifest_by_id):
        error("Manifest IDs do not exactly match draft learning IDs.")

    for stable_id in set(canonical_by_id) & set(draft_by_id):
        expected = copy.deepcopy(draft_by_id[stable_id])

        if expected.get("type") == "learning":
            reviewed = manifest_by_id.get(stable_id)

            if reviewed is None:
                continue

            if reviewed.get("reviewStatus") != "approved":
                error(f"{stable_id}: classification is not approved.")

            if reviewed.get("evidenceStatus") not in EVIDENCE_STATUSES:
                error(f"{stable_id}: invalid evidenceStatus.")

            if reviewed.get("classification") not in LEARNING_TYPES:
                error(f"{stable_id}: invalid manifest classification.")
                continue

            expected["resourceType"] = reviewed["classification"]

        if canonical_by_id[stable_id] != expected:
            error(
                f"{stable_id}: canonical record differs from its "
                "expected draft/manifest combination."
            )


def main():
    canonical = load_json(CANONICAL_FILE)
    draft = load_json(DRAFT_FILE)
    manifest = load_json(MANIFEST_FILE)

    if canonical is None or draft is None or manifest is None:
        return

    if not isinstance(canonical, list):
        error("Canonical dataset must be a JSON array.")
        return

    if not isinstance(draft, list):
        error("Extraction draft must be a JSON array.")
        return

    if not isinstance(manifest, list):
        error("Classification manifest must be a JSON array.")
        return

    for record in canonical:
        validate_record(record)

    canonical_by_id = index_records(canonical, "Canonical")

    identities = []
    for record in canonical:
        if not isinstance(record, dict):
            continue

        source = record.get("source")
        if isinstance(source, dict):
            identities.append((
                source.get("provider"),
                source.get("subjectSlug"),
                source.get("sourceId"),
            ))

    if len(identities) != len(set(identities)):
        error("Duplicate source identity detected.")

    practice = [
        r for r in canonical
        if isinstance(r, dict) and r.get("type") == "practice"
    ]
    learning = [
        r for r in canonical
        if isinstance(r, dict) and r.get("type") == "learning"
    ]

    practice_placements = sum(
        len(r.get("placements", [])) for r in practice
        if isinstance(r.get("placements"), list)
    )
    learning_placements = sum(
        len(r.get("placements", [])) for r in learning
        if isinstance(r.get("placements"), list)
    )

    actual = {
        "resources": len(canonical),
        "practice": len(practice),
        "learning": len(learning),
        "practice_placements": practice_placements,
        "learning_placements": learning_placements,
        "total_placements": practice_placements + learning_placements,
    }

    if actual != EXPECTED:
        error(f"Dataset count mismatch. Expected={EXPECTED}, Actual={actual}")

    classification_counts = Counter(
        r.get("resourceType") for r in learning
    )

    if classification_counts != Counter({"Concept": 17, "Tutorial": 24}):
        error(
            "Learning classification totals mismatch: "
            f"{dict(classification_counts)}"
        )

    validate_source_preservation(canonical, draft, manifest)

    print("Canonical records:", len(canonical))
    print("Practice:", len(practice))
    print("Learning:", len(learning))
    print("Classification totals:", dict(classification_counts))
    print("Practice placements:", practice_placements)
    print("Learning placements:", learning_placements)
    print("Total placements:", actual["total_placements"])
    print("Unique stable IDs:", len(canonical_by_id))

    if errors:
        print(f"\nVALIDATION FAILED: {len(errors)} error(s)")
        for item in errors[:50]:
            print(" -", item)

        if len(errors) > 50:
            print(f" ... and {len(errors) - 50} more.")

        sys.exit(1)

    print("\nPASS: Canonical schema checks.")
    print("PASS: Stable identity and uniqueness checks.")
    print("PASS: Placement integrity checks.")
    print("PASS: URL integrity checks.")
    print("PASS: Expected dataset counts.")
    print("PASS: Learning classifications.")
    print("PASS: Draft and manifest preservation.")
    print("\nALL VALIDATION CHECKS PASSED.")


if __name__ == "__main__":
    main()
