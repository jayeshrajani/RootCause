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

## Phase 1: Days 2–3 · Gemini analysis and weather

| Work | Owner |
| --- | --- |
| Gemini adapter (Google Gen AI SDK), structured output validated by Pydantic | S |
| Timeouts, malformed-output and API-error handling; fallback to explicit failure, not mock | S |
| `analysis_mode` + provenance for model output | J+S (contract) |
| Open-Meteo adapter: recent rainfall, temperature, humidity with real observation periods | S |
| Weather evidence UI (periods, values, "unavailable" state) | J |
| Loading/progress UX for slower real analysis | J |

Acceptance criteria

- With `GEMINI_API_KEY` set, a real photo returns hypotheses that pass schema validation.
- Without a key, the API still works (mock or a clear "analysis unavailable" state).
- Weather evidence shows the actual period and timestamp; failures appear as `unavailable`.
- Tests cover malformed model output, timeouts and weather API failure (mocked HTTP).

## Phase 2: Days 4–6 · Satellite, knowledge and orchestration

| Work | Owner |
| --- | --- |
| Satellite adapter (Earth Engine or alternative): NDVI, history, cloud cover, metadata | S |
| ADR on spatial resolution limits for approximate coordinates | J+S |
| Knowledge retrieval from attributable sources; retrieved text kept separate from model interpretation | S |
| Evidence-driven orchestrator combining photo, weather, satellite, knowledge | S |
| Evidence visualisation: source badges, timelines, citations with links | J |

Acceptance criteria

- Satellite evidence is optional and states its resolution and cloud limitations.
- Every cited guideline links to a real source; no invented citations or chemical doses.
- Orchestrator degrades gracefully when any source is unavailable.

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
