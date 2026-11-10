
import json
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path

path = Path("data/processed/learning-classifications.json")
backup = path.with_suffix(".json.bak")

# Evidence assessment for all 41 approved classifications.
evidence = {
    # Original article/content reviewed
    "tuf-dsa-17136": "content_verified",
    "tuf-dsa-17132": "content_verified",
    "tuf-dsa-17133": "content_verified",
    "tuf-dsa-17134": "content_verified",
    "tuf-dsa-17135": "content_verified",
    "tuf-dsa-17137": "content_verified",
    "tuf-dsa-17138": "content_verified",

    # Related course supports the classification, exact lesson not established
    "tuf-dsa-17083": "secondary_evidence",
    "tuf-dsa-17084": "unverified",
    "tuf-dsa-17085": "unverified",

    # Lesson content investigated
    "tuf-dsa-1216": "content_verified",
    "tuf-dsa-1205": "content_verified",
    "tuf-dsa-1219": "content_verified",
    "tuf-dsa-1218": "content_verified",

    # Official source label, but original content not inspected
    "tuf-dsa-1217": "source_label_only",

    # Title/hierarchy only
    "tuf-dsa-1193": "unverified",
    "tuf-dsa-1194": "unverified",
    "tuf-dsa-1214": "unverified",

    # Article content reviewed
    "tuf-dsa-1213": "content_verified",
    "tuf-dsa-1203": "content_verified",
    "tuf-dsa-1204": "content_verified",

    # Recursion lessons
    "tuf-dsa-1199": "content_verified",
    "tuf-dsa-1198": "content_verified",

    # Supporting notes, not full original lesson
    "tuf-dsa-2400": "secondary_evidence",

    # Linked-list lessons
    "tuf-dsa-1237": "content_verified",
    "tuf-dsa-1235": "secondary_evidence",
    "tuf-dsa-1236": "secondary_evidence",
    "tuf-dsa-1234": "content_verified",
    "tuf-dsa-1232": "content_verified",
    "tuf-dsa-1233": "content_verified",

    # Remaining reviewed lessons
    "tuf-dsa-1155": "content_verified",
    "tuf-dsa-1254": "content_verified",

    # Original lesson unavailable
    "tuf-dsa-1256": "coming_soon",

    "tuf-dsa-1154": "content_verified",
    "tuf-dsa-1153": "content_verified",
    "tuf-dsa-1223": "content_verified",
    "tuf-dsa-1222": "content_verified",

    # Directly verified by user
    "tuf-dsa-1221": "user_verified",

    "tuf-dsa-1195": "content_verified",
    "tuf-dsa-2390": "user_verified",
    "tuf-dsa-2399": "content_verified",
}

if not path.is_file():
    raise SystemExit(f"ERROR: Manifest not found: {path}")

if backup.exists():
    raise SystemExit(
        f"ERROR: Backup already exists: {backup}\n"
        "Inspect it before deciding how to proceed."
    )

records = json.loads(path.read_text(encoding="utf-8"))

if len(records) != 41:
    raise SystemExit(f"ERROR: Expected 41 records, found {len(records)}")

ids = [r.get("stableId") for r in records]

if len(set(ids)) != 41:
    raise SystemExit("ERROR: Duplicate or missing stable IDs.")

if set(ids) != set(evidence):
    missing = set(ids) - set(evidence)
    unexpected = set(evidence) - set(ids)
    raise SystemExit(
        f"ERROR: Evidence mapping mismatch.\n"
        f"Missing mappings: {sorted(missing)}\n"
        f"Unexpected mappings: {sorted(unexpected)}"
    )

# Apply the one approved classification correction.
target = next(r for r in records if r["stableId"] == "tuf-dsa-1198")
target["classification"] = "Tutorial"
target["rationale"] = (
    "The lesson demonstrates parameterized recursion through "
    "worked coding examples. Classified as Tutorial based on "
    "the instructional implementation focus; approved by the user."
)

for record in records:
    record["reviewStatus"] = "approved"
    record["evidenceStatus"] = evidence[record["stableId"]]

concept_count = sum(
    r["classification"] == "Concept" for r in records
)
tutorial_count = sum(
    r["classification"] == "Tutorial" for r in records
)

if concept_count != 17 or tutorial_count != 24:
    raise SystemExit(
        f"ERROR: Unexpected totals: {concept_count} Concepts, "
        f"{tutorial_count} Tutorials."
    )

# Create a backup, then atomically replace the manifest.
shutil.copy2(path, backup)

temp_path = None
try:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        suffix=".tmp",
        delete=False,
    ) as temp:
        json.dump(records, temp, indent=2, ensure_ascii=False)
        temp.write("\n")
        temp_path = Path(temp.name)

    os.replace(temp_path, path)
except Exception:
    if temp_path and temp_path.exists():
        temp_path.unlink()
    raise

print("Manifest updated successfully.")
print("Records:", len(records))
print("Classifications:", dict(Counter(
    r["classification"] for r in records
)))
print("Review statuses:", dict(Counter(
    r["reviewStatus"] for r in records
)))
print("Evidence statuses:", dict(Counter(
    r["evidenceStatus"] for r in records
)))
print("Backup:", backup)
