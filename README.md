# RootCause

AI-assisted crop distress triage and early warning, built for the **Google AI Builder Cup 2026**
(Sustainability & Social Impact).

> *Your crop can't talk. We listen anyway.*

A farmer snaps a leaf and says what's wrong, in Hindi or English. RootCause cross-examines the
photo against the field's recent weather, Sentinel-2 satellite imagery and a rule-backed evidence
score, then says what's likely, what isn't, how urgent it is, and what to do next. It is triage,
never a diagnosis: observations, hypotheses, missing evidence and recommendations are always kept
separate.

## What it does

**Report (photo first, no typing)**

- Add up to 3 photos, or tap a built-in **sample** (chilli, potato, tomato) to try it instantly.
- The crop is identified from the photo; the farmer is asked only when the model is unsure.
- **Voice note** in English or Hindi, language auto-detected (Gemini); the transcript goes
  straight into the report and starts the analysis.
- An explain-first **location prompt** ("Where's the patient?"); optional village search if declined.
- A live analysis screen that names each real step as it runs.

**Analysis (`POST /api/v1/triage`)**

- **Gemini** reads the photos and the farmer's words into observations, possible causes and actions.
- **Weather**: the past 7 days at the field (Open-Meteo).
- **Satellite**: cloud-masked Sentinel-2 L2A NDVI/NDMI over a 100 m buffer, 45 days, via
  Google Earth Engine.
- **Evidence ledger**: each cause gets a 0–100 fit (model read plus bounded, rule-based weather
  and satellite points, each with a reason). Causes under 50 are hidden; one above 75 stands alone.
- Guardrails: urgency rating, treatments flagged for expert confirmation, missing data never
  treated as normal.

**Results**

- Summary card with crop, likely cause, urgency, what we saw and field conditions.
- **Listen**: reads the main points aloud with Gemini text-to-speech, in the result's language
  (prefetched, so playback starts at once; browser voice as fallback).
- Tabs: **Possible causes** (with supporting and contradicting evidence), **Do next**, and
  **Treat it**: non-chemical steps first, generic active ingredients (never brands or doses),
  safety points, a KVK check, and **nearby agri-input shops from Google Maps** (Gemini grounding).
- Results translate on demand into English, हिन्दी, ਪੰਜਾਬੀ, Español and Français.

**Fair use**: 5 investigations per browser session (a session cookie, enforced by the API too),
with a friendly limit screen; per-IP hourly caps on every model-backed endpoint.

## Google AI and Cloud used

| What | Where |
| --- | --- |
| Gemini Flash (`gemini-flash-latest`), multimodal structured output | Crop ID, triage, translation, treatment guidance |
| Gemini Flash-Lite | Voice transcription (auto-detected language), shop search |
| Gemini TTS (`gemini-3.8-flash-lite-tts`) | Read-aloud of results |
| Gemini grounding with Google Maps | Nearby agri-input shops and KVKs |
| Google Earth Engine (Sentinel-2) | Satellite vegetation evidence |
| Cloud Speech-to-Text V2 (Chirp 3) | Optional voice fallback |
| Cloud Run, Cloud Build, Artifact Registry, Secret Manager | Deployment ([deploy/README.md](deploy/README.md)) |

Model calls fall back in order: the priority Gemini key, then the fallback key, then Cerebras
(`qwen-3.8-27b`) for analysis. Without any key the API returns a clearly labelled mock.

## Repository layout

```text
apps/
  web/     Next.js 16 (App Router, TypeScript strict, Tailwind v4)       · owner: Jayesh
  api/     FastAPI (Python 3.12, Pydantic v2, pytest)                     · owner: Shivansh
deploy/    Cloud Build config and Cloud Run deployment guide
docs/      architecture, API contract, roadmap, cloud readiness, decision records
.github/   CI workflow and PR template
```

## Prerequisites

- Node.js 20.9+ (CI uses 22) and npm
- Python 3.12+ (or [uv](https://docs.astral.sh/uv/))

## Setup

```bash
git clone <repo-url> rootcause && cd rootcause
cp .env.example .env            # then add keys; never commit .env
```

Keys in the repo-root `.env` (all optional; without them the API returns labelled mock results):

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY_PRIORITY` | Gemini key tried first (`GEMINI_API_KEY` also works) |
| `GEMINI_API_KEY_FALLBACK` | Second Gemini key, used when calls on the first fail |
| `CEREBRAS_API_KEY` | Analysis fallback when Gemini is unavailable |
| `GOOGLE_CLOUD_PROJECT_ID` | Earth Engine project for satellite evidence (log in with `gcloud auth application-default login` or `earthengine authenticate`) |

Every other setting (models, limits, timeouts) is documented in [.env.example](.env.example).

### API (terminal 1)

```bash
cd apps/api
uv run uvicorn app.main:app --reload --port 8000
# or: python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && uvicorn app.main:app --reload --port 8000
```

- Health: <http://localhost:8000/api/v1/health> (shows the analysis mode, model and satellite status)
- Interactive docs: <http://localhost:8000/docs>

Settings are read at startup: restart the API after editing `.env` (`--reload` watches code only).

### Web (terminal 2)

```bash
cd apps/web
npm install
npm run dev
```

Open <http://localhost:3000>, tap **Start a crop report**, add a photo (or a sample) and speak or
tap **Get crop guidance**. The web app calls `http://localhost:8000` by default; to change it,
set `NEXT_PUBLIC_API_BASE_URL` in `apps/web/.env.local`. If the web app runs on another origin,
add it to `ROOTCAUSE_CORS_ORIGINS` in `.env`.

## Checks (same as CI)

```bash
# apps/api
uv run ruff check . && uv run ruff format --check . && uv run mypy app tests && uv run pytest

# apps/web
npm run lint && npm run typecheck && npm test && npm run build
```

## Deploy

Two Cloud Run services (`rootcause-api`, `rootcause-web`) built by Cloud Build. One-time setup
(APIs, service account, secrets) and the deploy commands are in [deploy/README.md](deploy/README.md).
Gemini keys go in Secret Manager, never in the image or the repo.

## Documentation

- [Architecture](docs/architecture.md)
- [API contract](docs/api-contract.md): every endpoint, request and error code
- [Cloud readiness](docs/cloud-readiness.md) and [deployment](deploy/README.md)
- [Reference retrieval (DINOv2 + FAISS)](docs/retrieval.md) and [reference datasets](docs/datasets.md)
- [Roadmap](docs/roadmap.md) · [Decision records](docs/decisions/) · [Contributing](CONTRIBUTING.md)

## Privacy

Photos, voice notes and read-aloud text are processed in memory for the request and never stored
or logged. The latest result lives only in the browser tab (`sessionStorage`). Location is used
for the weather, satellite and shop lookups only.

## Known limitations

- Output is triage guidance from photos, the farmer's words, weather and satellite data, not a
  confirmed diagnosis. Always confirm with a local agricultural expert before treating crops.
- Reference-photo matching (DINOv2 + FAISS) is built but disabled in the default deployment.
- Usage limits are kept in memory per API instance, so they reset on restart and are per-instance
  when Cloud Run scales out. Fine for a preview, not billing-grade.
- Treatment guidance names generic active ingredients from the model's knowledge; it is not a
  registered-product database. The app always says to follow the label and check with the KVK.
- Maps grounding and TTS are billed per request on Gemini's paid tier; check your key's quota.
- The UI is fully translated in English and Hindi; other languages fall back to English in places.
- iOS Safari voice recording is untested.

## Troubleshooting

- **"Couldn't reach RootCause"**: the API isn't running, is on another port, or CORS doesn't
  allow your web origin.
- **Results say "via Cerebras"**: both Gemini keys are rate-limited or out of quota (HTTP 429);
  enable billing on the Gemini project or wait for the daily reset.
- **Voice says it isn't available**: no Gemini key is set (and no Speech-to-Text project).
- **TLS / certificate errors behind a corporate proxy**: the API uses the OS trust store; for
  `npm install` on Node 22+, try `NODE_OPTIONS=--use-system-ca`.
