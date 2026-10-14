# RootCause

AI-assisted crop distress triage and early warning, built for the **Google AI Builder Cup 2026**
(Sustainability & Social Impact).

RootCause is not a disease classifier. It helps a farmer answer:

- What could be wrong with this crop, and how sure are we?
- How urgent is it?
- What evidence supports that, and what is missing?
- What are safe next steps?

Observations, hypotheses, missing evidence and recommendations are always kept separate. Model
output is never presented as a confirmed diagnosis.

> **Status: photo analysis live.** With `CEREBRAS_API_KEY` set, photos and the farmer's text are
> analysed by **Qwen 3.8 (27B) on Cerebras**, validated against a strict schema and safety-checked.
> Without a key the API returns a clearly labelled **mock** (`analysis_mode: "mock"`). Weather,
> satellite and knowledge sources are not connected yet. Gemini is planned but blocked on the LSEG
> network. See [docs/roadmap.md](docs/roadmap.md).

## Repository layout

```text
apps/
  web/   Next.js (App Router, TypeScript strict, Tailwind v4, shadcn/ui)  · owner: Jayesh
  api/   FastAPI (Python 3.12, Pydantic v2, pytest)                       · owner: Shivansh
docs/    architecture, API contract, roadmap, decision records
.github/ CI workflow and PR template
```

## Prerequisites

- Node.js 20.9+ (CI uses 22) and npm
- Python 3.12+

## Setup

```bash
git clone <repo-url> rootcause && cd rootcause
cp .env.example .env            # optional; defaults work for local dev
```

### API (terminal 1)

```bash
cd apps/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

- Health: <http://localhost:8000/api/v1/health>
- Interactive docs: <http://localhost:8000/docs>

### Web (terminal 2)

```bash
cd apps/web
npm install
npm run dev
```

Open <http://localhost:3000>, choose **Report a crop problem**, add a photo, and submit.

The web app calls `http://localhost:8000` by default. To change it, create `apps/web/.env.local`
with `NEXT_PUBLIC_API_BASE_URL=...`. If you run the web app on a different port, add that origin
to `ROOTCAUSE_CORS_ORIGINS` in `.env`.

No API keys are required: without one, the API returns labelled mock results. For real photo
analysis, set `CEREBRAS_API_KEY` in the repo-root `.env` (never commit it) and restart the API;
`/api/v1/health` then reports `"analysis_mode": "ai"`.

## Checks (same as CI)

```bash
# apps/api (with the venv active)
ruff check . && ruff format --check . && mypy app tests && pytest

# apps/web
npm run lint && npm run typecheck && npm run build
```

## Documentation

- [Architecture](docs/architecture.md)
- [API contract](docs/api-contract.md)
- [Roadmap](docs/roadmap.md)
- [Decision records](docs/decisions/)
- [Contributing](CONTRIBUTING.md)

## Known limitations

- AI triage sees only the photos and the farmer's text; weather, satellite data and references
  are not checked yet. Output is hypotheses, never a diagnosis.
- Voice notes are not implemented yet (the mic button is disabled).
- Results are not persisted. The latest result is kept in the browser tab's `sessionStorage`.
- No authentication or rate limiting; do not deploy publicly as-is.
- Requests without a `Content-Length` header skip the early total-size check (each photo is
  still capped individually).

## Troubleshooting

- **"Couldn't reach RootCause"** in the form: the API isn't running, is on another port, or CORS
  doesn't allow your web origin.
- **TLS / certificate errors during `npm install` or `npx shadcn` behind a corporate proxy**: on
  Node 22+ try `NODE_OPTIONS=--use-system-ca` so Node trusts the OS certificate store.
