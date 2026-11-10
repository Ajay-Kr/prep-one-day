# Canonical Resource Schema — Version 1

- **Project:** Prep One Day
- **Schema version:** 1
- **Initial source:** TakeUForward — Striver's A2Z DSA Sheet
- **Status:** Approved
**Last updated:** 2026-11-11

---

## 1. Purpose

This document defines the canonical data contract for Prep One Day.

The canonical dataset is the source of truth for resource metadata across all preparation modules. It standardizes resource identity, source metadata, classification, hierarchy placement and resource URLs.

The initial implementation targets the Striver's A2Z DSA Sheet from TakeUForward. The schema is designed to support additional preparation modules without requiring a fundamental redesign.

### 1.1 Data pipeline

The project follows this pipeline:

Official Source → Raw Snapshot → Extraction → Canonical JSON → Validation → GitHub Projects Synchronization → Personal Progress Tracking

### 1.2 Source of truth

- Official source data determines resource metadata.
- The canonical JSON dataset stores normalized resource metadata.
- GitHub Projects stores personal progress.
- GitHub Project item IDs are never used as canonical resource identities.

---

## 2. Dataset organization

Version 1 uses a single JSON file containing an array of canonical resource records.

The initial dataset is expected to contain 494 unique resources.

Each unique resource appears exactly once, regardless of how many hierarchy locations reference it.

The dataset will contain both practice and learning resources.

Contests are excluded from the initial canonical dataset.

---

## 3. Record structure

Every canonical resource must follow this structure:

```json
{
  "schemaVersion": 1,
  "stableId": "tuf-dsa-41",
  "source": {
    "provider": "takeuforward",
    "sourceId": 41,
    "slug": "linear-search",
    "subjectSlug": "strivers-a2z-dsa-sheet"
  },
  "title": "Linear Search",
  "type": "practice",
  "resourceType": "Coding Problem",
  "sourceTier": "basic",
  "duration": null,
  "placements": [
    {
      "module": "Arrays",
      "topic": "Fundamentals",
      "path": [
        "Arrays",
        "Fundamentals",
        "Linear Search"
      ],
      "sourceCategory": "fundamentals"
    }
  ],
  "resources": {
    "primaryUrl": "https://takeuforward.org/strivers-a2z-dsa-sheet/practice/linear-search",
    "articleUrl": null,
    "videoUrl": null,
    "leetcodeUrl": null
  }
}
```

All records must conform to this structure.

---

## 4. Field definitions

### 4.1 Root fields

| Field | Type | Required | Nullable |
|---|---|---|---|
| schemaVersion | Integer | Yes | No |
| stableId | String | Yes | No |
| source | Object | Yes | No |
| title | String | Yes | No |
| type | String enum | Yes | No |
| resourceType | String enum | Yes | No |
| sourceTier | String enum | Yes | Yes |
| duration | Integer | Yes | Yes |
| placements | Array | Yes | No |
| resources | Object | Yes | No |

### 4.2 schemaVersion

- Type: Integer
- Required: Yes
- Nullable: No
- Version 1 value: `1`

This field identifies the canonical schema version.

Any breaking changes to the record structure or field semantics must introduce an appropriate schema version.

### 4.3 stableId

- Type: String
- Required: Yes
- Nullable: No

Format:

`tuf-dsa-{sourceId}`

Examples:

- `tuf-dsa-41`
- `tuf-dsa-1203`
- `tuf-dsa-405`

Rules:

1. Every canonical resource must have a unique stable ID.
2. IDs are derived from the original source identity.
3. IDs must not depend on titles, hierarchy positions or GitHub Project IDs.
4. Moving a resource between topics must not change its stable ID.
5. Multiple placements of the same resource must share one stable ID.

### 4.4 source

The source object preserves the original resource identity and provenance.

| Field | Type | Required | Nullable |
|---|---|---|---|
| provider | String | Yes | No |
| sourceId | Integer | Yes | No |
| slug | String | Yes | No |
| subjectSlug | String | Yes | No |

Definitions:

- `provider`: Original content provider. Version 1 uses `takeuforward`.
- `sourceId`: Original numeric resource ID.
- `slug`: Original resource slug.
- `subjectSlug`: Original syllabus identifier.

Source values must be preserved independently of canonical identity.

### 4.5 title

- Type: String
- Required: Yes
- Nullable: No

The original resource title.

Do not replace source titles with manually rewritten titles during extraction.

### 4.6 type

- Type: String enum
- Required: Yes
- Nullable: No

Represents the original source layout classification.

Allowed values:

| Value | Meaning |
|---|---|
| practice | Resource originating from the practice layout |
| learning | Resource originating from the learning layout |

This classification must remain independent of `resourceType`.

### 4.7 resourceType

- Type: String enum
- Required: Yes
- Nullable: No

Represents the canonical classification used by Prep One Day and GitHub Projects.

Allowed combinations:

| type | resourceType |
|---|---|
| practice | Coding Problem |
| learning | Concept |
| learning | Tutorial |

#### Learning classification rules

Learning resources must be individually classified according to their actual content.

**Concept**

Use when the primary purpose is explaining fundamentals, principles, definitions, underlying ideas or theoretical understanding.

**Tutorial**

Use when the primary purpose is demonstrating a guided process, instructional walkthrough, practical implementation or step-by-step learning.

The resource format alone must not determine classification.

For example:

- An article can be either Concept or Tutorial.
- A video can be either Concept or Tutorial.

When content is insufficient to determine the classification reliably, flag it for manual review instead of guessing.

The original `type` must remain `learning` regardless of this classification.

### 4.8 sourceTier

- Type: String enum or null
- Required: Yes
- Nullable: Yes

Preserves the original TakeUForward source tier.

Allowed values:

- `basic`
- `core`
- `pro`
- `null`

Rules:

1. Preserve the source terminology.
2. Do not map source tiers to Easy, Medium or Hard.
3. Do not infer missing tiers.
4. Use JSON null when the source does not provide a tier.

### 4.9 duration

- Type: Integer or null
- Required: Yes
- Nullable: Yes
- Unit: Minutes

Preserves the source's estimated duration as a numeric value normalized to minutes.

Rules:

1. Use a JSON integer, not a formatted string.
2. Preserve the duration's meaning when normalizing its unit.
3. Values expressed in minutes must be stored as their numeric minute value.
4. Values expressed in hours must be converted to minutes (1 hour = 60 minutes).
5. Do not invent missing durations.
6. Use null when the source does not provide a duration.
7. Reject unrecognized or malformed duration formats rather than silently discarding or guessing their meaning.

The extraction implementation must normalize all valid durations to minutes, regardless of the source's original unit.

---

## 5. Placement structure

Every resource must contain a `placements` array.

Each placement represents one location in the original syllabus hierarchy.

### 5.1 Placement fields

| Field | Type | Required | Nullable |
|---|---|---|---|
| module | String | Yes | No |
| topic | String | Yes | No |
| path | Array of strings | Yes | No |
| sourceCategory | String | Yes | Yes |

Example:

```json
{
  "module": "Arrays",
  "topic": "Fundamentals",
  "path": [
    "Arrays",
    "Fundamentals",
    "Linear Search"
  ],
  "sourceCategory": "fundamentals"
}
```

Definitions:

- `module`: First hierarchy level used for the GitHub Module field.
- `topic`: Second hierarchy level used for the GitHub Topic field.
- `path`: Complete hierarchy path from the root to the resource.
- `sourceCategory`: Original source category metadata when available.

### 5.2 Placement ordering

Placements must preserve the original depth-first traversal order of the official source hierarchy.

Do not alphabetically sort placements.

The first placement in the array is the primary placement.

### 5.3 Primary placement

The first placement determines the resource's default hierarchy assignment.

GitHub Projects synchronization must use:

- Module = `placements[0].module`
- Topic = `placements[0].topic`

Additional placements remain available in the canonical dataset but must not create additional GitHub Project items.

### 5.4 Multiple placements

A resource may appear in multiple hierarchy locations.

All valid placements must be preserved.

Example: Basic Hashing (source ID 1203).

```json
{
  "stableId": "tuf-dsa-1203",
  "title": "Basic Hashing",
  "type": "practice",
  "resourceType": "Coding Problem",
  "placements": [
    {
      "module": "Beginner Problems",
      "topic": "Concept Basics",
      "path": [
        "Beginner Problems",
        "Concept Basics",
        "Basic Hashing"
      ],
      "sourceCategory": "concept-basics"
    },
    {
      "module": "Hashing",
      "topic": "Theory",
      "path": [
        "Hashing",
        "Theory",
        "Basic Hashing"
      ],
      "sourceCategory": "theory"
    }
  ]
}
```

This must produce exactly one canonical record and eventually one GitHub Project item.

---

## 6. Resource URL structure

Every resource must contain a `resources` object.

### 6.1 Resource URL fields

| Field | Type | Required | Nullable |
|---|---|---|---|
| primaryUrl | String | Yes | Yes |
| articleUrl | String | Yes | Yes |
| videoUrl | String | Yes | Yes |
| leetcodeUrl | String | Yes | Yes |

### 6.2 primaryUrl

The primary entry point for accessing the resource.

For practice resources, use the verified canonical practice URL.

For learning resources, use the verified article URL when available.

If no verified primary URL exists, use null.

### 6.3 articleUrl

The verified article or blog URL.

For learning resources, use the source's `free_blog_link` when available.

Relative article paths must be converted into absolute URLs using:

`https://takeuforward.org`

Do not invent article routes.

### 6.4 videoUrl

The original video URL obtained from source metadata when available.

Preserve it independently of the primary URL.

### 6.5 leetcodeUrl

The original LeetCode URL obtained from source metadata when available.

Preserve it independently of the primary URL.

### 6.6 Practice URL rules

The canonical practice URL pattern is:

`https://takeuforward.org/{subjectSlug}/practice/{itemSlug}`

Rules:

1. Use the current verified URL structure.
2. Do not reuse the old practice URL format.
3. Construct URLs only using verified source slugs.
4. Every practice resource must have a valid `itemSlug` in the source.
5. The generated URL must be an absolute HTTP(S) URL.

### 6.7 Learning URL rules

1. Do not invent `/learn/...` routes.
2. Use `free_blog_link` as the primary URL when available.
3. Convert verified relative article paths into absolute URLs.
4. If no verified article URL exists, use null.
5. Preserve video and LeetCode links separately.
6. Do not fabricate missing URLs.

For learning resources, `primaryUrl` and `articleUrl` may contain the same URL. This is intentional.

### 6.8 URL validation

All non-null URLs must:

- Be valid absolute URLs.
- Use HTTP or HTTPS.
- Contain a valid hostname.
- Not be empty strings.
- Follow the appropriate source-specific URL rules.

---

## 7. Missing value conventions

Use JSON null for unavailable optional values.

| Situation | Representation |
|---|---|
| Missing source tier | null |
| Missing duration | null |
| Missing article URL | null |
| Missing video URL | null |
| Missing LeetCode URL | null |
| Missing primary URL | null |
| Missing source category | null |

Rules:

1. Required properties must remain present even when nullable.
2. Do not use empty strings as missing values.
3. Do not use `"N/A"`, `"Unknown"` or similar placeholders.
4. Do not fabricate URLs or metadata.
5. Missing required non-nullable values must cause validation failure.

---

## 8. Deduplication and identity rules

Canonical resource identity is determined by the combination:

`source.provider + source.subjectSlug + source.sourceId`

For the initial TakeUForward dataset, `sourceId` is unique within the selected syllabus.

Deduplication rules:

1. Each unique source identity produces exactly one canonical record.
2. Repeated hierarchy appearances become additional placements.
3. Titles must not be used as the primary deduplication key.
4. Slugs alone must not be used as the primary deduplication key.
5. Conflicting metadata for the same source identity must be flagged.
6. Different source identities must not be merged solely because their titles match.
7. The first source traversal occurrence determines the primary placement.

---

## 9. Expected source counts

The initial extraction must satisfy the following audited counts.

| Metric | Expected count |
|---|---:|
| Practice placements | 453 |
| Learning placements | 42 |
| Total placements | 495 |
| Unique practice resources | 453 |
| Unique learning resources | 41 |
| Unique canonical resources | 494 |
| Resources with multiple placements | 1 |
| Learning Concepts | 17 |
| Learning Tutorials | 24 |

The known multiple-placement resource is:

- Basic Hashing
- Source ID: 1203
- Placements: 2

Contests are excluded from these canonical dataset counts.

Any unexpected count discrepancy must be investigated before dataset approval.

---

## 10. Separation of source metadata and personal progress

The canonical dataset must contain source metadata only.

Personal tracking fields belong exclusively to GitHub Projects.

### 10.1 Canonical dataset responsibilities

- Stable ID and source identity
- Title and resource classification
- Source tier and duration
- Hierarchy placements
- Resource URLs

### 10.2 GitHub Projects responsibilities

Synced resource metadata:
- Module and Topic (from primary placement)
- Resource Type
- Source
- Resource URL
- Solution URL (where applicable)
- Difficulty (where applicable)

Personal tracking data:
- Status
- Start Date
- Completion Date
- Next Revision
- Revision Count
- Confidence
The canonical dataset remains the source of truth for resource metadata. GitHub Projects holds the user's progress.

---

## 11. Validation requirements

The validation implementation must verify the following categories.

### 11.1 Schema validation

- `schemaVersion` equals 1.
- Every record contains all required root properties.
- No unexpected data types are present.
- Nullable fields follow the defined conventions.

### 11.2 Identity validation

- Stable IDs follow the approved naming convention.
- Stable IDs are unique.
- Source identities are unique.
- Stable IDs correspond to their original source IDs.

### 11.3 Classification validation

- `type` is either practice or learning.
- Practice resources use Coding Problem.
- Learning resources use Concept or Tutorial.
- Source tiers belong to the approved enum.

### 11.4 Placement validation

- Every resource has at least one placement.
- Placement order is preserved.
- Module and topic correspond to the first two hierarchy levels.
- Paths contain valid hierarchy segments.
- Duplicate source identities are represented through placements rather than duplicate records.

### 11.5 URL validation

- Non-null URLs are valid absolute HTTP(S) URLs.
- Practice URLs follow the verified canonical format.
- Learning URLs follow the approved article URL rules.
- No fabricated or placeholder URLs exist.

### 11.6 Dataset integrity

- Canonical record counts match the audited expectations.
- No source identity has been silently discarded.
- No unexpected duplicate canonical records exist.
- All expected placements are preserved.

Validation failures must be reported with enough context to identify the affected resource and field.

The validator must not silently repair or mutate invalid records.

---

## 12. Versioning and future extensibility

Version 1 is designed around source-independent canonical concepts while retaining source-specific metadata.

Future modules may introduce additional providers, resource types, metadata or hierarchy structures.

Any future extension must:

1. Preserve stable identity.
2. Avoid breaking existing records unnecessarily.
3. Maintain the separation between source metadata and personal progress.
4. Document changes to the schema.
5. Update validation rules alongside schema changes.

Breaking structural or semantic changes require a schema version update.

---

## 13. Implementation boundaries

The following tasks are deliberately outside the scope of this document:

- Raw HTML downloading.
- RSC payload parsing.
- Source extraction implementation.
- Canonical dataset generation.
- GitHub Projects API integration.
- Personal progress automation.

These implementations must follow this schema contract.

---

## 14. Approval and implementation sequence

The schema design has been approved with these decisions:

| Decision | Approved value |
|---|---|
| Schema version | 1 |
| Duration representation | Nullable number |
| Placement ordering | Official source traversal order |
| Primary placement | First placement |
| Dataset organization | Single JSON array |
| Deduplication | Provider + subjectSlug + sourceId |
| Learning classification | Concept or Tutorial |
| Personal progress | GitHub Projects only |

Implementation sequence:

1. Canonical schema documentation.
2. Extraction script.
3. Canonical dataset generation.
4. Validation script.
5. Dataset audit and manual review.
6. GitHub Projects synchronization preparation.

No GitHub Project items may be imported until the canonical dataset has passed validation and received explicit approval.

---

**End of Canonical Resource Schema — Version 1**
