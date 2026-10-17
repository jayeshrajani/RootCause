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
{ "status": "ok", "service": "rootcause-api", "version": "0.1.0", "analysis_mode": "ai", "model": "gemini-flash-latest", "reference_photos": "ready" }
```

`analysis_mode` is `ai` when Gemini or Cerebras is configured, else `mock`. Gemini is used first;
Cerebras is attempted if Gemini returns a provider error. `model` reports the primary configured
model.
`reference_photos` is `disabled` (no `ROOTCAUSE_RETRIEVAL_INDEX_VERSION`), `loading` (model and
index load in the background for about 30 s after startup), `ready` or `failed`.
`satellite_imagery` is `configured` when `GOOGLE_CLOUD_PROJECT_ID` is set (credentials are only
checked on first use), else `disabled`.

## `POST /satellite/analysis`

`Content-Type: application/json`. Sentinel-2 vegetation evidence from Google Earth Engine
(`COPERNICUS/S2_SR_HARMONIZED`). Always returns 200; availability is reported in `status`.

```json
{ "latitude": 30.9010, "longitude": 75.8573, "analysis_date": "2025-05-01", "field_boundary": null }
```

`analysis_date` is optional (defaults to today, not in the future, not before 2017-06-01).
`field_boundary` is an optional GeoJSON `Polygon` (closed rings, ≤ 500 vertices, ≤ 0.2° span);
without it the API samples a 100 m buffer around the point. Clouds, shadows, snow and water are
masked with the Scene Classification Layer (classes 4, 5, 7 kept). NDVI = (B8−B4)/(B8+B4),
NDMI = (B8−B11)/(B8+B11). The latest scene with ≥ 60% clear pixels is reported; the trend compares
the median of the last 45 days with the 45 days before (±0.05 NDVI threshold).

| Field | Type | Notes |
| --- | --- | --- |
| `status` | `available` \| `insufficient_data` \| `unavailable` \| `not_configured` \| `not_requested` | Values are `null` unless `available`; never invented |
| `ndvi`, `ndmi` | number \| null | Mean of clear pixels in the latest usable scene |
| `ndvi_change`, `ndmi_change` | number \| null | Recent median − baseline median |
| `trend`, `ndmi_trend` | `improving` \| `stable` \| `declining` \| `unknown` | |
| `observation_date` | date \| null | Real acquisition date of the reported scene |
| `observation_age_days` | integer \| null | Days between observation and `analysis_date` |
| `valid_pixel_coverage` | number \| null | Clear-pixel share 0–1 of the reported scene |
| `sampling_method`, `buffer_m`, `sampling_area_ha` | | How the area was sampled |
| `recent_window`, `baseline_window` | `{ start, end, clear_observations, ndvi_median, ndmi_median }` \| null | |
| `interpretable` | boolean | `true` only with a precise location, real crop cover, a known trend and a recent scene |
| `limitations[]` | enum[] | `approximate_area`, `approximate_location`, `no_baseline`, `single_observation`, `partial_coverage`, `stale_observation`, `low_vegetation` |
| `reason`, `message` | string \| null | Machine reason and human message when not available |

Results are cached in-process for 6 hours. Coordinates and the field geometry are sent to
Google Earth Engine.

## `POST /triage/identify`

Stage 1. `multipart/form-data` with `images` (same rules as `/triage`) and optional
`latitude`/`longitude`. Runs a short crop-only model call and a cross-crop reference-photo search
(rice, tomato, potato) in parallel. Coordinates, if sent, start the weather and satellite lookups
in the background so the following `/triage` finds them cached.

```json
{ "crop": "tomato", "confidence": "high", "needs_confirmation": false, "candidates": ["tomato", "potato"], "image_quality": "good", "reference_agreement": "agrees", "analysis_mode": "ai" }
```

`needs_confirmation` is `false` only when the model is highly confident, the photo is usable and
the reference photos do not clearly point to another crop (`reference_agreement` is `agrees`,
`not_covered` or `unavailable`). Clients then send the crop to `/triage`; otherwise they ask the
farmer to pick from `candidates`. Model failures return `needs_confirmation: true`, never an error.

## `POST /triage`

`Content-Type: multipart/form-data`. Only photos are required; everything else sharpens the result.

Each browser session ("visit") gets 5 investigations: the web app sends a random id in the
`X-RootCause-Session` header (a session cookie). A per-IP cap (60 per hour) backs it up for clients
that rotate the id. Requests that fail (validation or provider errors) are not counted. Counts are
in memory per API instance. Configure with `ROOTCAUSE_INVESTIGATIONS_PER_SESSION` and
`ROOTCAUSE_INVESTIGATIONS_PER_IP_HOUR` (0 disables).

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `images` | file (repeat) | **yes** | 1–3 files; JPEG/PNG/WebP by file signature; ≤ 5 MB each |
| `description` | string | no | ≤ 2000 characters; typed, or a voice transcript from `POST /transcribe` reviewed by the farmer |
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

Each AI-generated cause includes `analysis_score` (photos and report, from the model),
`condition_key` (a normalised id such as `late_blight`, `water_stress` or `fungal_disease`) and
`evidence_fit_score`, each score 0–100. Causes may also include `reference_score`.

The backend computes evidence fit in two deterministic steps:

1. **Blend** the analysis score with reference photos: rice 70 / 30, potato 80 / 20, tomato
   90 / 10 (analysis / references; tuned on held-out field photos, see
   [retrieval.md](retrieval.md#hybrid-scoring)). Other crops use analysis only.
2. **Adjust** with bounded, rule-based points recorded in `evidence_ledger`: weather −10…+10
   from the last 7 days (temperature band, humid days, rain days, hot days, cold nights per
   condition) and satellite −6…+6 from the Sentinel-2 greenness/moisture trend, only when the
   satellite evidence is `interpretable`. The model does not score weather or satellite.

`weather_score` and `satellite_score` are those points mapped to 0–100 (50 = neutral), kept for
compatibility. Weather and satellite lookups run in parallel and never block a triage.

`reference_score` is the share of the 10 most visually similar labelled reference photos
(DINOv2 + FAISS, rice, tomato and potato only) whose label the model matched to that cause. It is
`null` when reference photos were not compared or no reference label matches the cause; the
response's `reference_weight` gives the weight used. Reference comparison is best-effort and never
blocks a triage. Causes are ranked by evidence fit. Actions keep their urgency tier and are
ranked by `analysis_score` within it (their `evidence_fit_score` equals `analysis_score`). These
heuristic fit scores are not probabilities or calibrated disease likelihoods.

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
| `weather_facts` | `WeatherFacts` \| null | `days`, `start`, `end`, `temp_min_c`, `temp_max_c`, `temp_mean_c`, `rain_total_mm`, `wet_days` (≥ 1 mm), `humid_days` (mean RH ≥ 80%), `hot_days` (≥ 35 °C), `cold_nights` (≤ 8 °C), `pattern` (`wet`, `hot_dry`, `cold`, `humid`, `dry`, `mild`) |
| `satellite` | `SatelliteAnalysis` \| null | See `POST /satellite/analysis`; `null` when satellite evidence is disabled |
| `reference_weight` | integer \| null | Weight (%) of `reference_score` in evidence fit, when any cause has one |
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
| `reference_score` | integer \| null | 0–100 share of similar labelled reference photos showing this cause; not a probability |
| `satellite_score` | integer \| null | Satellite points mapped to 0–100 (50 neutral); `null` unless satellite evidence is interpretable |
| `evidence_fit_score` | integer \| null | Blended score plus ledger points, clamped 0–100; not a probability |
| `condition_key` | string \| null | Normalised condition id used by the rules and reference photos |
| `evidence_ledger[]` | `{ signal: "weather" \| "satellite", effect: "supports" \| "weighs_against" \| "neutral", points, reason }` | Rule-based adjustments; `reason` is English text built from measured values |

`Evidence`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Stable within a response |
| `source` | `farmer_report` \| `photo` \| `weather` \| `satellite` \| `knowledge_base` \| `analysis_engine` \| `reference_photos` | |
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
| 429 | `investigation_limit` | This visit used its 5 investigations, or the IP's hourly cap was hit (then `Retry-After` is set) |
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

## `POST /triage/treatment`

Generic, label-first treatment guidance for the likely cause, shown on the results page's
"Treat it" tab: non-chemical steps first, then up to four generic **active ingredients** (never
brands or doses), safety points and a note to confirm with the local KVK or agriculture officer.
`confirm_first` is true unless `evidence_fit_score` is above 75. Uses the triage model chain
(priority key, fallback key, then Cerebras). Capped per IP (`ROOTCAUSE_ASSIST_REQUESTS_PER_IP_HOUR`).

JSON body: `{ "crop": "potato", "cause": "Late blight", "evidence_fit_score": 82, "response_language": "hi" }`.

## `POST /places/agri-shops`

Up to five agri-input shops or Krishi Vigyan Kendras near the field, from **Gemini grounded on
Google Maps** (works with the Gemini API key; no Maps key). Only places returned by Maps grounding
are listed, each with its Google Maps link and place id. JSON body: `{ "latitude": 18.52,
"longitude": 73.86 }` or `{ "place": "Nashik, Maharashtra" }`. 422 `location_required` without
either; 502 `shops_failed` if every key and model failed.

## `POST /speak`

Reads text aloud with Gemini text-to-speech (`gemini-3.8-flash-lite-tts`, falling back to
`gemini-3.8-flash-tts`; retried once on 429/5xx). The web app sends the result's main points
(cause, urgency, summary, first three steps) in the result's language, prefetches the clip when the
result appears, and falls back to the browser's own speech voice if this call fails. Text and audio
are not stored or logged. Capped per IP (`ROOTCAUSE_TTS_REQUESTS_PER_IP_HOUR`, default 120).

JSON body: `{ "text": "..." }` (1–1200 characters). 200 response: `audio/wav` (24 kHz mono).

| Status | Code | When |
| --- | --- | --- |
| 422 | `validation_error` | Empty or over 1200 characters |
| 429 | `speak_limit` | Hourly per-IP cap reached (`Retry-After` set) |
| 502 | `speech_failed` | Every TTS model failed |
| 503 | `speech_unavailable` | No `GEMINI_API_KEY`, or `ROOTCAUSE_TTS_ENABLED=false` |

## `POST /transcribe`

Voice input for the symptom description. Gemini (`gemini-flash-lite-latest`) when `GEMINI_API_KEY`
is set, falling back to Google Cloud Speech-to-Text V2 (`chirp_3`) when a project is configured
(`ROOTCAUSE_SPEECH_PROVIDER` = `auto` | `gemini` | `google`). The transcript is returned in the
spoken language (never translated; Hindi in Devanagari). The web app sends `language=auto`, adds the
transcript to the report's `description` and submits the report straight away; it is not stored by
the API.

`Content-Type: multipart/form-data`

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `audio` | file | yes | ≤ 5 MB and under 1 minute (Speech-to-Text's synchronous limit; the web app stops at 55 s); WebM/Ogg (Opus), WAV or FLAC by file signature. Speech-to-Text V2 can also decode MP3 and MP4/M4A (AAC), but this API does not accept them yet |
| `language` | string | yes | `auto` (detect English or Hindi), or one of `ROOTCAUSE_SPEECH_LANGUAGES` (default `en-IN`, `hi-IN`) |

200 response: `{ "transcript": "मेरे टमाटर के पत्ते पीले हो रहे हैं", "language": "hi-IN" }`. With
`auto`, `language` is the detected code, or `auto` if it is neither English nor Hindi.

| Status | `code` | When |
| --- | --- | --- |
| 413 | `audio_too_large` | Recording exceeds `ROOTCAUSE_MAX_AUDIO_BYTES` |
| 415 | `unsupported_audio_type` | Bytes are not WebM, Ogg, WAV or FLAC |
| 422 | `audio_required` / `empty_audio` | No recording, or a recording with no audio content |
| 422 | `unsupported_language` | `language` missing or not enabled |
| 422 | `no_speech_detected` | The provider returned no text |
| 502 | `transcription_failed` | Provider error or unexpected response |
| 503 | `transcription_unavailable` | No project configured, or Google credentials missing/rejected |
| 504 | `transcription_timeout` | Provider timed out (`ROOTCAUSE_SPEECH_TIMEOUT_SECONDS`) |

Initial browser targets are Chrome desktop and Chrome on Android (WebM/Opus). iOS/Safari (WAV
fallback) is not yet tested. The endpoint has no authentication or rate limiting yet; abuse
protection is required before public deployment (see [cloud-readiness.md](cloud-readiness.md)).
