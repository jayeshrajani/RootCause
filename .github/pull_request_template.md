## What

<!-- One or two sentences. Link the issue/milestone if there is one. -->

## Why

## How to test

- [ ] `apps/api`: `ruff check . && ruff format --check . && mypy app tests && pytest`
- [ ] `apps/web`: `npm run lint && npm run typecheck && npm run build`
- [ ] Manual check (describe):

## Checklist

- [ ] Branch is `feat/...` or `fix/...`; commits follow Conventional Commits
- [ ] **API contract changed?** If yes: both owners agreed, and `apps/api/app/schemas/triage.py`, `apps/web/src/types/triage.ts` and `docs/api-contract.md` are updated together
- [ ] No secrets, photos or farmer location data in code, fixtures or logs
- [ ] AI output is not presented as a confirmed diagnosis; missing data is not treated as normal
