# API contract (v1)

Source of truth: `apps/api/app/schemas/`. TypeScript mirror: `apps/web/src/types/triage.ts`.
Change all three together; see [CONTRIBUTING.md](../CONTRIBUTING.md#changing-the-api-contract).
Live OpenAPI docs: `http://localhost:8000/docs`.

Base path: `/api/v1`. All timestamps are ISO 8601 in UTC.

## `GET /health`

```json
{ "status": "ok", "service": "rootcause-api", "version": "0.1.0", "analysis_mode": "mock" }
```

## `POST /triage`

`Content-Type: multipart/form-data`

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `crop` | enum | yes | `rice`, `wheat`, `maize`, `cotton`, `sugarcane`, `soybean`, `groundnut`, `chickpea`, `tomato`, `potato`, `onion`, `chilli`, `other` |
| `description` | string | yes | 10–2000 characters |
| `latitude` | number | yes | −90 to 90, finite |
| `longitude` | number | yes | −180 to 180, finite |
| `location_label` | string | no | ≤ 120 characters |
| `symptom_duration` | enum | no | `less_than_3_days`, `3_to_7_days`, `1_to_2_weeks`, `more_than_2_weeks`, `not_sure` |
| `images` | file (repeat) | yes | 1–3 files; JPEG/PNG/WebP by file signature; ≤ 5 MB each |

### 200 response: `TriageResponse`

| Field | Type | Notes |
| --- | --- | --- |
| `report_id` | string | Mock IDs start with `mock_` |
| `status` | `completed` \| `insufficient_information` | |
| `analysis_mode` | `mock` | Later: real modes. Clients must show a clear banner for `mock` |
| `crop` | enum | Echo of input |
| `summary` | string | Plain-language overview |
| `urgency` | `low` \| `moderate` \| `high` \| `critical` | |
| `urgency_reason` | string | |
| `possible_causes[]` | `PossibleCause` | **Hypotheses**, never diagnoses |
| `evidence[]` | `Evidence` | **Observations** only, including explicit absences |
| `missing_information[]` | `{ item, reason }` | What would improve certainty |
| `recommended_actions[]` | `RecommendedAction` | |
| `requires_expert_review` | boolean | |
| `generated_at` | datetime | |
| `data_sources[]` | `DataSource` | Provenance of everything used or attempted |
| `disclaimer` | string | Must be displayed |

`PossibleCause`

| Field | Type |
| --- | --- |
| `name` | string |
| `explanation` | string |
| `supporting_evidence` | string[] |
| `contradictory_evidence` | string[] |
| `confidence` | `low` \| `medium` \| `high` |
| `uncertainty_note` | string |

`Evidence`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Stable within a response |
| `source` | `farmer_report` \| `photo` \| `weather` \| `satellite` \| `knowledge_base` \| `analysis_engine` | |
| `availability` | `available` \| `unavailable` \| `not_integrated` | Unavailable ≠ normal |
| `observation` | string | |
| `observed_at` | datetime \| null | Real observation time only; null if unknown |

`RecommendedAction`

| Field | Type |
| --- | --- |
| `action` | string |
| `rationale` | string |
| `priority` | `immediate` \| `within_days` \| `monitor` |
| `requires_expert_verification` | boolean |

`DataSource`

| Field | Type |
| --- | --- |
| `id` | string |
| `name` | string |
| `kind` | same values as `Evidence.source` |
| `status` | `used` \| `received_not_analysed` \| `unavailable` \| `not_integrated` |
| `description` | string |
| `retrieved_at` | datetime \| null |

### Errors

Every error uses one envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Some fields are missing or invalid.",
    "details": [{ "field": "latitude", "message": "Input should be less than or equal to 90" }]
  }
}
```

| Status | `code` | When |
| --- | --- | --- |
| 413 | `request_too_large` | `Content-Length` above total cap |
| 413 | `image_too_large` | A photo exceeds the per-file limit |
| 415 | `unsupported_image_type` | File bytes are not JPEG/PNG/WebP |
| 422 | `validation_error` | Missing or invalid form fields (`details[].field` names the field) |
| 422 | `images_required` / `too_many_images` / `empty_image` | Photo count or content problems |
| 500 | `internal_error` | Unexpected server failure |

Submitted values are never echoed in error responses.
