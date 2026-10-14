# Contributing

Two developers, one integration branch. Keep changes small and reviewable.

## Ownership

| Area | Owner |
| --- | --- |
| Frontend architecture, reporting UI, results UI, evidence visualisation, mobile, UX | Jayesh |
| Backend architecture, FastAPI endpoints, Gemini, weather/satellite adapters, orchestration, backend tests | Shivansh |
| API contract, data schemas, end-to-end tests, architecture decisions, deployment | Shared |

Owners review each other's PRs; either can approve shared areas.

## Branches

- `main` is the protected integration branch. No direct pushes; it must always build and pass CI.
- Features: `feat/<short-description>` (e.g. `feat/gemini-triage-service`)
- Fixes: `fix/<short-description>` (e.g. `fix/photo-size-error-message`)
- Branch from the latest `main`; rebase or merge `main` before requesting review.

## Pull requests

- Every change goes through a PR with at least one approval and green CI.
- Keep PRs focused, ideally under ~400 changed lines excluding lockfiles.
- Fill in the PR template, including how you tested.
- Squash-merge to keep `main` history readable.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat(api): add Open-Meteo weather adapter
fix(web): show size error for oversized photos
docs: record ADR for satellite provider
test(api): cover malformed Gemini output
chore(ci): cache pip dependencies
```

Scopes: `api`, `web`, `contract`, `docs`, `ci`. Small commits, one logical change each.

## Changing the API contract

The contract is the boundary between our two areas, so it changes only by agreement:

1. Open an issue or draft PR describing the change and tag the other developer.
2. Agree on the shape before writing code.
3. Update **in the same PR**: `apps/api/app/schemas/triage.py`,
   `apps/web/src/types/triage.ts`, and `docs/api-contract.md`.
4. Prefer additive, optional fields. Breaking changes need a note in `docs/decisions/`.

## Before merging

Backend (`apps/api`, venv active):

```bash
ruff check . && ruff format --check . && mypy app tests && pytest
```

Frontend (`apps/web`):

```bash
npm run lint && npm run typecheck && npm run build
```

## Ground rules

- No secrets in code. Configuration comes from environment variables; see `.env.example`.
- Never log farmer descriptions, coordinates, place names or image data.
- Never present AI output as a confirmed diagnosis or invent weather, satellite data or citations.
  Missing data must be shown as missing, not as normal.
- No new services, databases or heavy dependencies without an ADR in `docs/decisions/`.
