# ADR 0001: Monorepo with Next.js web app and FastAPI service

- Status: accepted
- Date: 2026-10-14
- Deciders: Jayesh, Shivansh

## Context

Two developers need to work in parallel on a frontend and an AI-heavy backend, sharing one API
contract, within a 12-day competition timeline.

## Decision

- One repository with `apps/web` (Next.js App Router, TypeScript strict, Tailwind, shadcn/ui)
  and `apps/api` (FastAPI, Pydantic v2).
- No workspace tooling (Turborepo, Nx, pnpm workspaces): each app keeps its own native
  toolchain (`npm`, `pip`). CI runs one job per app.
- Python owns the contract (Pydantic). The TypeScript types are a hand-maintained mirror,
  changed in the same PR. Code generation from OpenAPI can replace this later if drift becomes
  a problem.
- The browser calls the API directly (CORS) rather than through Next.js route handlers, keeping
  uploads and AI keys entirely server-side in Python.
- No database, auth or queue in Milestone 0.

## Consequences

- Simple setup; each developer can run only their app plus the other's with two commands.
- Contract drift is possible; mitigated by the PR checklist and shared ownership.
- A public deployment will need CORS origins configured and rate limiting added.
