# Dataset, embedding and reference retrieval checklist

Owner: **Shivansh** · Branch: `shivansh_dev` · Source of truth for the Crop Reference Retrieval Engine.

`[x]` = implemented **and verified**. `[ ]` = not done or not yet verified. Only record results from
commands that were actually run.

Status categories: **COMPLETE** (implemented and locally verified) · **PARTIAL** (implemented, not
fully tested) · **DEFERRED** (intentionally postponed) · **NOT STARTED** · **BLOCKED** (unable
to proceed on a required step).

## Status (verified 2026-10-15)

| Phase | Status | Notes |
| --- | --- | --- |
| 0. Repository audit | COMPLETE | Re-verified: branch `shivansh_dev`, uncommitted work intact |
| 1. Dataset preparation | COMPLETE | Manifests validate; images on disk match |
| 1A. Audit for DINOv2 + FAISS and GCP/Firebase | COMPLETE | |
| 1B. DINOv2 embedding pipeline | COMPLETE | Determinism, normalisation, cache and checksum tests pass |
| 1C. FAISS retrieval and evaluation | COMPLETE | Evaluation now reports field vs lab queries and macro recall |
| 1D. Cloud persistence (GCS, Firestore) | **DEFERRED by team decision** | Not failed. Plan in [cloud-readiness.md](cloud-readiness.md); needs C1–C3, D1, D3 |
| 1E. Cloud Run readiness | PARTIAL | API image includes retrieval (CPU torch); data mounted from a bucket ([deploy/README.md](../deploy/README.md)). Build and deploy not yet run (needs a personal machine with GCP access) |
| 1F. Firebase readiness | DEFERRED (deployment) | Rendering review done (D4); static-export build test pending |
| 1G. Integration handoff | COMPLETE | Public API verified end to end for all three crops; HTTP endpoint pending D2 |
| Tomato retrieval quality | PARTIAL | Investigated; isolated experiments run; no production change yet (needs approval) |
| Voice input (speech-to-text) | PARTIAL | Implemented and tested with mocks (2026-10-16); 55 s cap, UI-language default, empty-recording message. Pending: live Google test (Chrome desktop, Android Chrome), abuse protection before public deployment. iOS/Safari deferred |
| Commit and push | COMPLETE | `shiv1214` has write access; pushes to `shivansh_dev` only, after approval |

### Status history

Status before the 2026-10-15 verification run:

| Phase | Status |
| --- | --- |
| 0. Inspect existing implementation | Complete |
| 1. Dataset preparation | Complete |
| 1A. Audit for DINOv2 + FAISS and GCP/Firebase | Complete |
| 1B. DINOv2 embedding pipeline | Complete |
| 1C. FAISS retrieval and evaluation | Complete |
| 1D. Cloud persistence (GCS, Firestore) | Deferred (agreed 2026-10-15) · needs C1–C3, D1–D3 |
| 1E. Cloud Run readiness | Not started |
| 1F. Firebase readiness | Not started · needs D4 |
| 1G. Integration handoff | Complete (library contract; HTTP endpoint pending D2) · awaiting review |

The earlier Gemini Embedding 2 phases (2–5) were superseded on 2026-10-15: retrieval uses
DINOv2 (`facebook/dinov2-small`) for both reference and query images. No Gemini embedding code
had been written, so nothing was removed.

## Blockers and open decisions

| ID | Item | Needed for |
| --- | --- | --- |
| B1 | The Gemini Developer API is intercepted by the LSEG Zscaler gateway. No longer needed for retrieval (DINOv2 runs locally); still relevant to Jayesh's Gemini reasoning. | Jayesh |
| B2 | Superseded: Gemini Embedding 2 is not used for the production index. | — |
| B3 | See C1–C3 below. | Phase 1D |
| B4 | Resolved: PlantDoc/PlantVillage images are fetched from `github.com` by object ID at pinned commits; rice comes from Mendeley (no login). Paddy Doctor not used (paid IEEE subscription). | Phase 1 |
| B5 | Resolved: data lives in `ROOTCAUSE_DATA_DIR` (`C:\rootcause-data` locally), outside OneDrive and Git. | Phase 1 |
| B6 | Approved and added: `pillow`, `numpy` (runtime); `py7zr` (`datasets` extra); `torch==2.14.1`, `transformers==5.19.0`, `safetensors`, `faiss-cpu==1.15.1` (`retrieval` extra, so CI's `.[dev]` install stays light). Phase 1D will add `google-cloud-storage` and `firebase-admin`. | Phases 1B–1D |
| B7 | GitHub push denied (HTTP 403) for account `shiv1214`; needs collaborator access to `jayeshrajani/RootCause`. | Sharing work |
| B8 | Add `scripts` to the mypy command in CI (`mypy app tests scripts`)? Shared CI change. | CI |
| B9 | Resolved: Hugging Face's file CDN is blocked by Zscaler (403). Weights come from Meta's official host and are converted locally; the result is byte-identical to `facebook/dinov2-small` (SHA-256 `ae1e99fc…`). Cloud builds can use either source. | Phase 1B |
| B10 | No `gcloud`, Docker or Firebase CLI on this machine, so container builds and deploys cannot be tested locally. Use Cloud Build/Cloud Shell, or install the tools. | Phases 1D–1F |
| C1 | GCP project ID and region. | Phase 1D |
| C2 | Existing GCS bucket name (and its current folder layout). | Phase 1D |
| C3 | Credentials for local testing (`gcloud auth application-default login`) or a test project; never committed. | Phase 1D |
| D1 | Storing farmer uploads in GCS changes the current privacy design (photos are not stored after the request). Needs team agreement, retention period and user consent. | Phase 1D |
| D2 | Retrieval is a Python library today. Add an HTTP endpoint (e.g. `POST /api/v1/retrieval`) or keep it internal to the orchestrator? | Phase 1G |
| D3 | Ownership of the `analyses` and `users` Firestore collections (written by Jayesh's triage/ADK flow). | Phase 1D |
| D4 | The web app uses Next.js 16 with `cacheComponents` (server features). Plain Firebase Hosting serves static files; this may need Firebase App Hosting (Blaze plan) or a static-export review with Jayesh. | Phase 1F |

---

## Phase 0 — Inspect existing implementation

**Objective:** Understand the current API and plan the retrieval subsystem without changing application
behaviour.

Baseline commit: `5b1c2ba` (Jayesh's Cerebras AI triage and UX redesign, fast-forwarded from `main`).

### Tasks

- [x] Branch is `shivansh_dev` (`git branch --show-current`).
- [x] Working tree clean: `git status --short` empty. Ignored local files only: `.env`,
  `apps/api/.venv/`, `apps/web/node_modules/`.
- [x] API package structure inspected.
- [x] Existing AI adapters identified: `app/integrations/cerebras.py` (Cerebras chat completions via
  `httpx` + `truststore`), used by `app/services/triage/ai.py` (`AiTriageService`) and selected in
  `app/api/deps.py`. No Gemini code exists.
- [x] Existing retrieval code: none.
- [x] Existing dataset scripts or manifests: none (no `scripts/`, `data/` or manifest files).
- [x] Existing Google Cloud integration: none.
- [x] Dependency management and test conventions reviewed.
- [x] Official Gemini Embedding 2 documentation reviewed.
- [x] Network reachability of required services checked (unauthenticated, no cost).
- [x] Files to add or update proposed.
- [x] This checklist created.
- [x] Backend baseline checks run.

### Acceptance criteria

- [x] Existing implementation documented; no duplicate functionality planned.
- [x] Exact file plan proposed.
- [x] Persistent checklist created.
- [x] No application code changed.

### Changed files

- `docs/dataset-embedding-checklist.md` (new)

### Verification (2026-10-15 · Windows · Python 3.12.4 · `apps/api/.venv`)

| Command (in `apps/api`) | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 35 files already formatted |
| `mypy app tests` | Success: no issues found in 34 source files |
| `pytest` | 36 passed, 1 warning (pre-existing Starlette deprecation for the `httpx` test client) |

Web checks were not run: the frontend is out of scope for this assignment and unchanged.

### Findings

**Existing API**

- `POST /api/v1/triage`: `crop` is optional and the `Crop` enum has 13 values. Retrieval will validate
  its own subset (`rice`, `tomato`, `potato`) and raise an explicit error for anything else or `None`.
  No triage contract change is needed.
- Retrieval input can reuse `ReportImage(media_type, data)` from `app/models/report.py`; uploads are
  already validated as JPEG/PNG/WebP by magic bytes, ≤ 5 MB each, 1–3 images.
- Conventions: external adapters live in `app/integrations/`, configured through `Settings` in
  `app/core/config.py` (`ROOTCAUSE_` prefix, secrets as `SecretStr`, unprefixed aliases such as
  `CEREBRAS_API_KEY`). Services sit behind protocols in `app/services/`. Client-facing errors use
  `AppError`. Logs never include farmer descriptions, locations or image bytes.
- Tooling: hatchling; dependencies in `apps/api/pyproject.toml` with a `dev` extra; ruff (line length
  100); mypy `strict` with the pydantic plugin; pytest with `anyio`; HTTP mocked with
  `httpx.MockTransport`; test settings use `_env_file=None`. CI (Ubuntu, Python 3.12) runs
  `ruff check .`, `ruff format --check .`, `mypy app tests`, `pytest`.
- Corporate TLS: `truststore` is already a runtime dependency and should be reused for Google clients.

**Gemini Embedding 2** (ai.google.dev embeddings guide, page updated 2026-10-09)

- `gemini-embedding-2` (stable) embeds text, images, video, audio and PDF into one space.
- Images: **PNG and JPEG only**, at most 6 per request, 8,192 input tokens in total. Farmer WebP uploads
  must be converted before embedding.
- Output dimensions 128–3072; 768 is recommended, and truncated outputs are normalised automatically.
- Several parts in one request produce **one aggregated embedding**. Wrap each image in its own
  `Content` to get independent per-image embeddings.
- `task_type` is not supported; prefixes are discouraged for multimodal input. Embed reference and query
  images identically (image only, same dimensions, same preprocessing).
- Vectors are incompatible with `gemini-embedding-001`.
- The Batch API is priced at 50% of standard; actual pricing will be checked in Phase 2.
- Not yet verified: `gemini-embedding-2` availability on Vertex AI.

**Network reachability** (unauthenticated GET, no key, no cost)

| Host | Result | Meaning |
| --- | --- | --- |
| `generativelanguage.googleapis.com` | 307 → `gateway.zscloud.net` | Intercepted by Zscaler (B1) |
| `aiplatform.googleapis.com`, `us-central1-aiplatform.googleapis.com` | 404 from service | Reachable; permission to use it to be confirmed (B1) |
| `oauth2.googleapis.com` | 404 from service | Reachable |
| `storage.googleapis.com` | 400 (`UploadServer`) | Reachable |
| `github.com`, `api.github.com` | 200 | Reachable |
| `codeload.github.com` | 301 | Reachable |
| `raw.githubusercontent.com` | Connection error | Blocked (B4) |
| `www.kaggle.com` | 200 | Reachable |

### Proposed file plan

Follows existing conventions (external adapters in `app/integrations/`, services in `app/services/`)
where they differ from the suggested layout. All paths below are relative to `apps/api` unless noted.

| Path | Phase | Purpose |
| --- | --- | --- |
| `app/services/retrieval/dataset_registry.py` | 1 | Supported crops, dataset sources, licence and attribution metadata, label normalisation, manifest schema and validation |
| `scripts/prepare_datasets.py` | 1 | Filter crops, normalise labels, hash, deduplicate, split reference/evaluation, write manifests |
| `data/manifests/{crop}.csv` | 1 | Lightweight manifests (committed only if licences allow) |
| `../../docs/datasets.md` | 1 | Sources, licences, attribution, class coverage, limitations |
| `../../.gitignore` (update) | 1 | Ignore raw datasets, embedding caches and indexes |
| `tests/test_dataset_registry.py` | 1 | Label normalisation, manifest validation, split separation |
| `app/services/retrieval/embedding_client.py` | 2 | `EmbeddingClient` protocol, preprocessing (WebP → JPEG), cache keyed by SHA-256 + model + dimensions + preprocessing version |
| `app/integrations/gemini_embeddings.py` | 2 | `google-genai` adapter: one `Content` per image, 768 dimensions, retries with backoff |
| `scripts/precompute_embeddings.py` | 2 | Resumable, cached, atomic offline embedding job with usage report |
| `tests/test_embedding_pipeline.py` | 2 | Mocked client: validation, caching, resume, atomic writes |
| `app/core/config.py` and `../../.env.example` (update) | 2–3 | Embedding model and dimensions, Gemini/Vertex settings, storage backend, data directory, bucket, index version, top-k |
| `app/services/retrieval/index_builder.py` | 3 | Build, validate, save and load `{crop}.npz` plus metadata JSON |
| `app/services/retrieval/storage.py` | 3 | `ArtifactStorage` protocol and local filesystem backend |
| `app/integrations/gcs_storage.py` | 3 | Private GCS backend with configurable bucket |
| `scripts/build_indexes.py` | 3 | Combine cached vectors into per-crop indexes; optional GCS upload |
| `tests/test_index_builder.py`, `tests/test_storage.py` | 3 | Index round-trip and validation; local backend; GCS backend with a fake client |
| `app/services/retrieval/reference_retriever.py` | 4 | `retrieve_references(crop_id, images, top_k=5)`: crop-filtered cosine search, multi-image merge, dedupe and diversity, explicit errors |
| `app/services/retrieval/__init__.py` | 4 | Public typed API and errors for Jayesh |
| `tests/test_reference_retriever.py` | 4 | Crop isolation, ranking, dedupe, error cases |
| `scripts/evaluate_retrieval.py` | 5 | Held-out evaluation, leakage check, latency and usage |
| `README.md`, `docs/architecture.md` (update) | 5 | Handoff notes and integration example |

Notes:

- Tests generate tiny images in code; no dataset images are committed.
- `scripts/` is outside CI's `mypy app tests` (decision B8).
- Retrieval is a library called by the orchestrator; no new HTTP endpoint and no change to the triage
  response contract. The existing triage flow stays the image-only baseline.

### Blockers

None for Phase 0. See B1–B8 for later phases.

### Status

Complete. Approved and closed.

---

## Phase 1 — Dataset preparation

**Objective:** Validated, reproducible manifests for rice, tomato and potato.

Sources, licences, counts and limitations: [datasets.md](datasets.md).

### Tasks

- [x] Verify the three dataset distributions and download methods.
- [x] Document licences and attribution.
- [x] Identify disease classes per selected crop.
- [x] Download only approved samples (rice archive; PlantDoc tomato/potato; 40 PlantVillage per class).
- [x] Filter supported crop images.
- [x] Normalise disease labels; preserve original labels and source identifiers.
- [x] Validate file readability and image types (Pillow full decode).
- [x] Calculate SHA-256 hashes.
- [x] Check duplicates and near-duplicates (incl. rotations/flips).
- [x] Separate reference and held-out evaluation samples.
- [x] Create crop-specific manifests with all required fields.
- [x] Report image counts per crop and class.
- [x] Document missing classes and limitations.
- [x] Run dataset validation tests.

### Acceptance criteria

- [x] Validated manifests exist for rice, tomato and potato.

### Changed files

- `apps/api/app/services/retrieval/__init__.py`, `dataset_registry.py`, `dataset_prep.py`, `downloads.py` (new)
- `apps/api/scripts/prepare_datasets.py` (new)
- `apps/api/data/manifests/rice.csv`, `tomato.csv`, `potato.csv`, `summary.json` (new)
- `apps/api/tests/test_dataset_registry.py`, `test_dataset_prep.py`, `test_downloads.py` (new)
- `apps/api/pyproject.toml` (`pillow`, `numpy`; `datasets` extra with `py7zr`)
- `apps/api/app/core/config.py` (`data_dir` / `ROOTCAUSE_DATA_DIR`)
- `.env.example`, `.gitignore` (data directory; only manifests versioned)
- `docs/datasets.md` (new), this checklist

### Verification (2026-10-15 · Windows · Python 3.12.4)

| Command (in `apps/api`) | Result |
| --- | --- |
| `python scripts/prepare_datasets.py --data-dir C:\rootcause-data` | Exit 0; all three manifests passed `validate_manifest` (no duplicate IDs/hashes, no group or near-duplicate in both splits) |
| `ruff check app tests scripts` | All checks passed |
| `ruff format --check app tests scripts` | 42 files already formatted |
| `mypy app tests scripts` | Success: no issues found in 42 source files |
| `pytest` | 80 passed, 1 warning (pre-existing Starlette deprecation) |

Image files on disk match the manifests exactly (rice 234/72, tomato 300/203, potato 229/58).

### Results

| Crop | Reference (field/lab) | Evaluation (field/lab) | Valid candidates | Copies dropped |
| --- | --- | --- | --- | --- |
| Rice | 234 (234/0) | 72 (72/0) | 5,932 | 5,571 |
| Tomato | 300 (242/58) | 203 (128/75) | 1,146 | 17 |
| Potato | 229 (165/64) | 58 (36/22) | 339 | 2 |

### Limitations

- Rice: 4 diseases only, no healthy class; about 360 distinct photos, so 234 references (target ~300).
- No field images for tomato target spot or potato healthy; tomato spider mites has 2.
- 7 tomato and 7 potato PlantDoc groups with conflicting labels excluded; 1 MPO image rejected.
- `scripts/` is type-checked locally but not by CI (B8).

### Blockers

None for Phase 1.

### Status

Complete.

---

## Phase 1A — Audit for DINOv2 + FAISS and GCP/Firebase

- [x] Branch `shivansh_dev`; uncommitted Phase 1 work preserved.
- [x] Existing retrieval code: dataset registry, preparation pipeline and manifests only. No embedding, index, GCS, Firestore or Firebase code existed, so no migration was needed.
- [x] Conflicts with the new architecture: Gemini Embedding 2 plan (superseded, no code); NumPy-only index plan (now FAISS); farmer photos are currently not stored (D1); no HTTP retrieval endpoint agreed (D2); frontend has no Firebase and uses Next.js server features (D4).
- [x] Environment: all packages available via Artifactory; Hugging Face CDN blocked (B9); no cloud CLIs locally (B10).

## Phase 1B — DINOv2 embedding pipeline

- [x] Reusable embedder (`app/services/retrieval/embeddings.py`): loaded once per process, thread-safe, CPU, `inference_mode`, eval mode, never downloads at request time.
- [x] One preprocessing path for reference and farmer images: EXIF orientation, RGB, short edge 256 (bicubic), centre-crop 224, ImageNet normalisation (`exif-rgb-short256-bicubic-center224-imagenet-v1`).
- [x] 384-dimensional pooled (CLS) output, L2-normalised, finite-checked.
- [x] Pinned model revision and weights checksum; loading refuses unverified weights.
- [x] Resumable embedding cache keyed by image SHA-256, model revision and preprocessing version; atomic writes; per-item failure reporting.
- [x] Deterministic output verified (same input twice, identical within 1e-6).
- [x] Weights fetched and converted by `scripts/fetch_dinov2.py`; byte-identical to the published file.

## Phase 1C — FAISS retrieval and evaluation

- [x] One exact inner-product index (`IndexFlatIP`) per crop, so search never crosses crops.
- [x] Row-aligned metadata per crop; index version folder with checksummed artifacts and a manifest written last.
- [x] Loading verifies format, version folder, embedding spec, checksums, dimension, counts, metric and crop; stale or mismatched indexes are refused.
- [x] Index versions are immutable: rebuilding with identical contents is a no-op; different contents need a new version (or `--force`).
- [x] `ReferenceRetriever.retrieve(crop_id, images, top_k)`: validates crop, 1–3 images and top-k; merges query images keeping each reference's best score; returns metadata, licence and attribution.
- [x] Held-out evaluation script with Recall@5, Precision@5, top-1, random baseline and latency.

### Changed files (1A–1C)

- `apps/api/app/services/retrieval/errors.py`, `embeddings.py`, `faiss_index.py`, `reference_retriever.py` (new)
- `apps/api/scripts/fetch_dinov2.py`, `build_index.py`, `evaluate_retrieval.py` (new)
- `apps/api/tests/test_embeddings.py`, `test_reference_retriever.py` (new)
- `apps/api/app/core/config.py` (`embedding_model_dir`, `retrieval_index_dir`, `retrieval_index_version`)
- `apps/api/pyproject.toml` (`retrieval` extra; mypy treats optional ML libraries as untyped)
- `.env.example`, this checklist

### Verification (2026-10-15 · Windows · Python 3.12.4 · CPU)

| Command (in `apps/api`) | Result |
| --- | --- |
| `python scripts/fetch_dinov2.py --data-dir C:\rootcause-data` | Weights written; SHA-256 matches published `facebook/dinov2-small` |
| `python scripts/build_index.py --data-dir C:\rootcause-data --index-version v1` | 1,096 images embedded in 90 s, 0 failed; v1: rice 234, tomato 300, potato 229 vectors |
| Same command again | 1,096 cached, 0 new; "already built with identical contents" |
| `python scripts/evaluate_retrieval.py --data-dir C:\rootcause-data --index-version v1` | See results below |
| `ruff check`, `ruff format --check`, `mypy app tests scripts` | All passed (51 files) |
| `pytest` with `ROOTCAUSE_DATA_DIR` set | 102 passed (incl. real DINOv2 and end-to-end tomato smoke test) |
| `pytest` without data (as in CI) | 100 passed, 2 skipped (model-dependent tests) |

### Results (index v1, K=5, held-out evaluation images)

| Crop | Queries | Recall@5 | Precision@5 | Random P@5 | Top-1 |
| --- | --- | --- | --- | --- | --- |
| Rice | 72 | 0.986 | 0.822 | 0.249 | 0.861 |
| Tomato | 203 | 0.586 | 0.273 | 0.100 | 0.330 |
| Potato | 58 | 0.983 | 0.659 | 0.394 | 0.810 |

Latency on this laptop CPU: embedding p50 80.7 ms per image; FAISS search about 0.06 ms per query.

### Embedding sanity checks (`python scripts/inspect_retrieval.py --data-dir C:\rootcause-data --index-version v1`)

| Check | Result |
| --- | --- |
| Same image embedded twice | Identical (max difference 0) |
| Same photo after edits (cosine to original, 20 photos) | mirrored 0.975, JPEG q50 0.980, half resolution 0.962, 90% crop 0.948, +20% brightness 0.997 (means) |
| Different held-out photos, same crop | same label 0.514 vs different label 0.439 (mean cosine) |
| Mean cosine between crops' references | rice vs tomato/potato about 0.03; tomato vs potato 0.415 (within: rice 0.445, tomato 0.438, potato 0.540) |
| Visual gallery (2 held-out photos per label, top 5) | Top-1 label match 23/34; `DATA_DIR/reports/retrieval_gallery_v1.html` |

Tomato and potato leaves look alike to DINOv2, so crop-filtered search (one index per crop) is
required, not optional.

Caveats: lab-only classes (tomato target spot, tomato spider mites, potato healthy) score 1.0,
likely because of their plain backgrounds rather than symptoms. Rice is a single, uniform dataset,
so its scores are optimistic; only 3% of held-out rice images have a reference with cosine ≥ 0.95.
Tomato field classes are hard (Recall@5 0.42–0.64). Recall@5 counts at least one same-label
reference in the top 5; labels are dataset annotations, not field diagnoses.

### Status

Complete. Awaiting approval and inputs (C1–C3, D1–D3) for Phase 1D.

---

## Phase 1D — Cloud persistence (GCS, Firestore)

**DEFERRED by team decision (2026-10-15).** Not attempted, not failed. Design:
[cloud-readiness.md](cloud-readiness.md) sections 2–4.

- [ ] Configurable GCS adapter (bucket and prefixes from settings; ADC; no public objects; safe object keys).
- [ ] Upload reference images and versioned index artifacts; restore an index version from GCS with checksum verification and in-memory caching.
- [ ] Firestore `reference_images` metadata (batched writes, server timestamps); `analyses`/`users` per D3.
- [ ] Local fallback when cloud credentials are absent; tests with mocked GCS and Firestore.

## Phase 1E — Cloud Run readiness

**DEFERRED (execution)**: no Docker or cloud access on the company laptop.

- [x] Packaging, startup loading, sizing and benchmark plan documented ([cloud-readiness.md](cloud-readiness.md) sections 1, 7, 8).
- [ ] Dockerfile (CPU torch), `.dockerignore`, `PORT` binding, readiness that reports model/index state.
- [ ] Model and index loaded at startup, not per request (warm-up hook in `app/main.py`; shared file, needs agreement).
- [ ] Benchmarks on Cloud Run; cost and free-tier notes from current pricing.

## Phase 1F — Firebase readiness

**DEFERRED (deployment).**

- [x] Frontend rendering review: no server actions, route handlers, cookies/headers, proxy or dynamic segments; `cacheComponents` + static export compatibility unknown ([cloud-readiness.md](cloud-readiness.md) section 11).
- [ ] Static-export test build by the frontend owner; choose Firebase Hosting, App Hosting or Cloud Run (D4).
- [ ] Firebase ID-token verification on the backend; CORS limited to configured origins.

## Phase 1G — Integration handoff

- [x] Retrieval contract, errors and real example response for Jayesh: [retrieval.md](retrieval.md).
- [x] Public API in `app.services.retrieval`: `get_reference_retriever()` (process-wide, FastAPI-dependency compatible), `ReferenceRetriever.retrieve`/`aretrieve` (worker thread for async code), `reference_image(match)` for reference bytes, `RetrievalError` hierarchy incl. `ReferenceImageUnavailableError`.
- [x] Local setup and configuration documented; deployment notes from measurements (startup ~30 s, 85/149 ms for 1/3 photos, ~455 MB memory, index 1.5 MB).
- [x] Linked from README and architecture overview.
- [ ] HTTP endpoint (D2), cloud deployment, IAM and secrets checklists: depend on 1D–1F.

### Verification (2026-10-15)

| Command (in `apps/api`) | Result |
| --- | --- |
| `ruff check app tests scripts`, `ruff format --check`, `mypy app tests scripts` | All passed (52 files) |
| `pytest tests/test_reference_retriever.py` | 15 passed, 1 skipped (smoke test needs data dir) |
| Measurement run via `load_reference_retriever` (local data, index v1) | Startup 30.0 s; query 85 ms (1 photo), 149 ms (3 photos); working set 455 MB |

### Status

Complete for the library integration. Remaining items wait for 1D–1F decisions.

---

## Verification and retrieval quality investigation (2026-10-15)

Run on the restricted company laptop; only local, read-only use of production artifacts.

### Integration re-verification

- [x] Importing `app.services.retrieval` loads no Gemini, ADK, Cerebras, triage, HTTP or ML modules (checked via `sys.modules`); torch/FAISS load lazily on first use.
- [x] New end-to-end tests drive the exact public path (`get_reference_retriever()` → `aretrieve()` → `reference_image()`) with real DINOv2 and index v1 for rice (1 photo), tomato (3) and potato (2): 5 matches, only the requested crop, sorted scores in [-1, 1], label and licence present, returned image bytes match manifest SHA-256, no evaluation image returned.
- [x] Unsupported crop, an unreadable photo among valid ones, and 4 photos are rejected with `UnsupportedCropError`/`InvalidQueryError`.
- Proposed, not implemented: `get_reference_retriever()` retries loading on every call after a failure; consider caching the failure briefly (behaviour change, needs agreement).

### Tomato findings (`scripts/retrieval_diagnostics.py`, index v1)

| Finding | Evidence |
| --- | --- |
| Lab/field mismatch drives the low overall score | Field queries Recall@5 0.781, top-1 0.406 (128); lab queries 0.253 / 0.200 (75) |
| Background dominates similarity | Lab queries retrieve lab references 97.3% of the time (field queries 2.8%); the index is 19.3% lab |
| Tomato references are field-only except two classes | Lab references exist only for spider mites (28 of 30) and target spot (30 of 30); 59 of 75 lab evaluation photos belong to other conditions and land on these two |
| Visually similar diseases | Top confusions: bacterial spot ↔ target spot, early blight ↔ leaf mold/target spot, late blight → early blight, septoria → early blight |
| More classes, lower raw scores | 10 tomato conditions (random P@5 0.10) vs 4 rice, 3 potato; Precision@5 lift over random: tomato 2.7×, rice 3.3×, potato 1.7× |
| Labels normalised consistently | 19 source labels (9 PlantDoc, 10 PlantVillage) map to 10 conditions as intended |
| No leakage | 0 shared SHA-256, 0 shared groups; median best-match cosine 0.768; none ≥ 0.95 |
| Metric definitions | Recall@5 = share of queries with ≥ 1 same-label reference in top 5; Precision@5 = share of top-5 with the query's label; macro recall 0.638 |

Removing lab references for field queries changes little (Recall@5 0.781 → 0.789), so lab
references do not crowd out field matches; the issue is lab *queries*.

### Isolated experiments (tomato, in memory)

Isolation: same pinned weights (checksum-verified), production manifests and images read-only;
embeddings computed in memory and searched exactly with NumPy; nothing written to the embedding
cache, indexes or manifests (all production files hashed before and after: unchanged). The
baseline reproduced the production cache exactly (max difference 0.0). Results in
`DATA_DIR/reports/experiments/tomato_v1_experiments.json`.

| Variant | Recall@5 | Top-1 | Field Recall@5 | Field top-1 | Cost per image |
| --- | --- | --- | --- | --- | --- |
| Baseline (production: CLS, crop 224) | 0.586 | 0.330 | 0.781 | 0.406 | ~74 ms |
| Flip test-time augmentation (image + mirror) | 0.611 | 0.335 | 0.812 | 0.406 | 2× |
| CLS + mean patch tokens (768-d) | 0.581 | 0.315 | 0.773 | 0.398 | same |
| Full image, no crop (224×224) | 0.571 | 0.305 | 0.766 | 0.383 | same |
| Higher resolution (crop 448) | 0.626 | 0.369 | 0.836 | 0.469 | ~3.7× |

With 128 field queries, differences of 3–5 points are 4–7 photos: promising but not conclusive.
Neither variant has been adopted; both would require a new embedding spec and index version.

### Recommendations (benefit vs effort)

1. **Report field-query metrics as the headline** (done in `evaluate_retrieval.py`); farmer uploads are field photos. Effort: none further.
2. **Exclude lab photos from tomato evaluation, or add lab references for every tomato condition** (PlantVillage has them) in a new index version, so lab queries are judged fairly. Effort: low; needs approval for a manifest/index v2.
3. **Test 448 px input** on all crops with more field evaluation data before adopting; it costs ~3.7× CPU per photo. Effort: medium.
4. **More tomato field references** (PlantDoc has ~746 valid tomato field images; v1 uses 30 per condition). Effort: medium; new manifests and index version.
5. **Flip test-time augmentation**: small gain, 2× cost; consider only alongside 3. Effort: low.
6. Not recommended: CLS+patch concatenation, whole-image resizing (no gain).

### Verification commands (2026-10-15, in `apps/api`)

| Command | Result |
| --- | --- |
| `git branch --show-current`; `git status --short` | `shivansh_dev`; Phase 1 and 1A–1G work uncommitted, intact |
| `python scripts/evaluate_retrieval.py --data-dir C:\rootcause-data --index-version v1` | Matches previous results; field/lab breakdown above |
| `python scripts/retrieval_diagnostics.py --data-dir C:\rootcause-data --index-version v1 --crop tomato [--experiments]` | Diagnostics and experiments above; production files unchanged |
| Full checks and tests | See the final report for the run on this date |
