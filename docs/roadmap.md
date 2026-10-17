# Roadmap

Owners: **J** = Jayesh (frontend), **S** = Shivansh (backend), **J+S** = shared.
A phase is done only when its acceptance criteria are met and CI is green on `main`.

## Phase 0: Day 1 · Repository bootstrap ✅

| Work | Owner |
| --- | --- |
| Monorepo, CI, docs, contributing guide | J+S |
| Next.js skeleton: landing, report form, results page | J |
| FastAPI skeleton: health, validated multipart triage endpoint | S |
| Typed response contract + deterministic mock triage | J+S |
| End-to-end form submission | J+S |

Acceptance criteria

- [x] Both apps start locally from README instructions.
- [x] Form validates crop, 1–3 photos, description and coordinates on client and server.
- [x] Submitting calls the API and renders the mock result, clearly labelled as mock.
- [x] Backend-unavailable and validation errors are shown with actionable messages.
- [x] Backend tests, lint and type checks pass; web lint, type-check and build pass.

## Phase 1: Days 2–3 · AI analysis, location and weather

| Work | Owner |
| --- | --- |
| Gemini generateContent adapter with Cerebras fallback; structured output validated by Pydantic | S |
| Timeouts, malformed-output and API-error handling; fallback to explicit failure, not mock | S |
| `analysis_mode` + provenance for model output | J+S (contract) |
| Open-Meteo adapter: recent rainfall, temperature, humidity with real observation periods | S |
| Open-Meteo geocoding for farmer-entered village/district names | S |
| Analysis/weather evidence-fit score (90/10, explicitly heuristic) | J+S |
| Weather evidence UI (periods, values, "unavailable" state) | J |
| Loading/progress UX for slower real analysis | J |

Acceptance criteria

- With `GEMINI_API_KEY` set, a real photo returns hypotheses that pass schema validation.
- If Gemini fails and `CEREBRAS_API_KEY` is set, analysis retries through Cerebras.
- Without a key, the API still works (mock or a clear "analysis unavailable" state).
- Weather evidence shows the actual period and timestamp; failures appear as `unavailable`.
- Tests cover malformed model output, timeouts and weather API failure (mocked HTTP).

## Phase 2: Days 4–6 · Satellite evidence, trusted references and orchestration

| Work | Owner |
| --- | --- |
| Satellite adapter (Earth Engine or direct Sentinel-2/Landsat): field-scale vegetation trend, dates, resolution and cloud metadata | S |
| ADR on spatial resolution limits for approximate coordinates | J+S |
| Knowledge retrieval from attributable sources; retrieved text kept separate from model interpretation | S |
| Evidence-driven orchestrator combining photo, weather, satellite, knowledge | S |
| Evidence visualisation: source badges, timelines, citations with links | J |

Acceptance criteria

- Satellite evidence is optional and states its resolution and cloud limitations.
- Every cited guideline links to a real source; no invented citations or chemical doses.
- Orchestrator degrades gracefully when any source is unavailable.

Phase 2 is **not** adding Google Maps tiles to the report. Maps/geocoding answer “where is this
place?”; Earth Engine is a separate geospatial processing platform for deriving time-series
signals from satellite datasets over an approximate field area. A useful first satellite signal
would be a cloud-screened vegetation-index trend (for example NDVI) with acquisition dates,
pixel size and valid-pixel coverage. It is regional context, not a diagnosis, and needs enough
field-area precision and history to be meaningful.

Knowledge retrieval means fetching crop- and region-relevant guidance from attributable
agricultural sources, preserving the source and link, and giving the text to the model as
separate evidence. The orchestrator then combines the model's photo/report analysis with
weather, satellite and reference evidence, while marking every source used, unavailable or
not integrated. Earth Engine requires a Google Cloud project and authenticated access; it is
more operationally involved than Open-Meteo geocoding and should follow the reference-data and
spatial-resolution design decision.

## Phase 3: Days 7–9 · Reliability and safety

| Work | Owner |
| --- | --- |
| Evaluation set of example reports with expected behaviour | J+S |
| Safety checks: overconfidence, unsupported treatment advice, missing-data handling | S |
| Contract/E2E tests across web and API | J+S |
| Mobile polish, accessibility pass, low-bandwidth behaviour (image downscaling) | J |

Acceptance criteria

- Evaluation examples run in CI or via one documented command.
- No response states a confirmed diagnosis; low-evidence cases ask for more information.
- Report flow is usable on a small phone screen with keyboard and screen reader.

## Phase 4: Days 10–12 · Deployment and demo

| Work | Owner |
| --- | --- |
| Deploy web and API (Docker for API if needed), secrets in platform config | J+S |
| Basic rate limiting and request size limits at the edge | S |
| Demo scenario and sample data | J+S |
| README polish, architecture diagram, competition presentation | J+S |

Acceptance criteria

- Public demo URL works end to end with real analysis.
- Demo script runs reliably start to finish.
- README lets a judge understand and run the project.
