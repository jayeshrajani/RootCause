# API contract (v1)

Source of truth: `apps/api/app/schemas/`. TypeScript mirror: `apps/web/src/types/triage.ts`.
Change all three together; see [CONTRIBUTING.md](../CONTRIBUTING.md#changing-the-api-contract).
Live OpenAPI docs: `http://localhost:8000/docs`.

Base path: `/api/v1`. All timestamps are ISO 8601 in UTC.

## `GET /locations/search?q={query}`

Returns up to six selectable Open-Meteo geocoding matches. Each item contains the place name,
first-level administrative region (state/province), country, country code and coordinates. The
client should let the farmer select the intended place before submitting; display names as
`city, state, country`. Search requires at least two characters. A typed free-form location can
still be submitted without selecting a match, but weather lookup may not resolve ambiguous text.

## `GET /health`

```json
{ "status": "ok", "service": "rootcause-api", "version": "0.1.0", "analysis_mode": "ai", "model": "qwen-3.8-27b" }
```

`analysis_mode` is `ai` when an analysis provider is configured (currently Cerebras), else `mock`.

## `POST /triage`

`Content-Type: multipart/form-data`. Only photos are required; everything else sharpens the result.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `images` | file (repeat) | **yes** | 1–3 files; JPEG/PNG/WebP by file signature; ≤ 5 MB each |
| `description` | string | no | ≤ 2000 characters (later: voice transcript) |
| `crop` | enum | no | `rice`, `wheat`, `maize`, `cotton`, `sugarcane`, `soybean`, `groundnut`, `chickpea`, `tomato`, `potato`, `onion`, `chilli`, `other` |
| `symptom_duration` | enum | no | `less_than_3_days`, `3_to_7_days`, `1_to_2_weeks`, `more_than_2_weeks`, `not_sure` |
| `latitude` | number | no* | −90 to 90, finite |
| `longitude` | number | no* | −180 to 180, finite |
| `location_label` | string | no | ≤ 120 characters |
| `response_language` | `en` \| `hi` \| `pa` \| `es` \| `fr` | no | Defaults to English; used for farmer-facing AI response text |

\* Latitude and longitude must be sent together or not at all.
When coordinates are present and AI analysis is enabled, the API requests recent daily
minimum/maximum temperature, precipitation and mean relative humidity from Open-Meteo.
If only `location_label` is provided, the API first tries Open-Meteo Geocoding to resolve the
place to coordinates, then requests the same weather data.
Weather lookup is best-effort: analysis continues if coordinates are missing or the provider
is unavailable or the place cannot be matched. The forecast endpoint returns model-based
estimates, not measurements at the field. Mock analysis does not retrieve or analyse weather.

The response includes `location_label` for a farmer-entered place, or `approximate_location`
for shared coordinates (rounded to two decimals), plus `weather_summary` when recent estimates
are available. No reverse geocoding is performed.

Each AI-generated cause and recommended action includes `analysis_score`, `weather_score`, and
`evidence_fit_score`, each from 0 to 100. The backend calculates the evidence-fit score as
`90% analysis_score + 10% weather_score`; the weather component is `null` and omitted from the
calculation when weather is unavailable. Causes are ranked by evidence fit. Actions retain their
urgency tier and are ranked by evidence fit within that tier. These heuristic fit scores are not
probabilities or calibrated disease likelihoods; image/report analysis is the dominant signal
until a reference-embedding model is available.

### 200 response: `TriageResponse`

| Field | Type | Notes |
| --- | --- | --- |
| `report_id` | string | `mock_…` for mock results, `rpt_…` for AI results |
| `status` | `completed` \| `insufficient_information` | `insufficient_information` when photos are unusable |
| `analysis_mode` | `mock` \| `ai` | Clients must show a clear banner for `mock` and the engine for `ai` |
| `response_language` | `en` \| `hi` \| `pa` \| `es` \| `fr` | Language requested for this generated response |
| `crop` | enum \| null | The farmer's choice; `null` if not given |
| `detected_crop` | string \| null | Crop the photos appear to show (AI-read, unconfirmed); only set when the model's crop identification is high-confidence, otherwise `null` |
| `location_label` | string \| null | Farmer-entered place name, if provided |
| `approximate_location` | string \| null | Coordinates rounded to two decimals and formatted for display |
| `weather_summary` | string \| null | Recent Open-Meteo estimate summary, when available |
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
| `analysis_score` | integer \| null | 0–100 image/report relevance; not a probability |
| `weather_score` | integer \| null | 0–100 weather relevance; `null` when unavailable |
| `evidence_fit_score` | integer \| null | Weighted fit score; not a probability |

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
| `addresses` | string \| null — the symptom or possible cause this step targets |
| `analysis_score` | integer \| null | 0–100 crop/symptom relevance; not a probability |
| `weather_score` | integer \| null | 0–100 weather relevance; `null` when unavailable |
| `evidence_fit_score` | integer \| null | Weighted fit score; not a probability |

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
| 502 | `analysis_unavailable` | The AI provider failed, timed out or returned invalid output (after one retry). Never silently replaced by mock output |

Submitted values are never echoed in error responses.

## `POST /triage/translate`

JSON body: `{ "result": TriageResponse, "target_language": "en" | "hi" | "pa" | "es" | "fr" }`.
Returns the same `TriageResponse` with farmer-facing text translated and `response_language` set to
`target_language`. The photos are not re-analysed. Scores, confidence, urgency, priorities, ids,
sources and the farmer's own quoted words are kept unchanged. If the result is already in the target
language, it is returned as-is without a model call. The web app caches each translation in the
browser tab and always translates from the original result.

| Status | `code` | When |
| --- | --- | --- |
| 413 | `request_too_large` | Translatable text exceeds 20,000 characters |
| 422 | `validation_error` | Invalid result or unsupported language |
| 502 | `translation_unavailable` | The AI provider failed or changed the result's structure (after one retry) |
| 503 | `translation_unavailable` | AI analysis is not configured (mock mode results are English only) |
