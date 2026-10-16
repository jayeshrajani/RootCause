# Cloud readiness: reference retrieval on Google Cloud (planning only)

Status: **documentation only**. Nothing here has been deployed or tested on Google Cloud. The
company laptop has no Docker, cloud SDKs or GCP credentials, so cloud persistence (Phase 1D) is
deferred by team decision and Cloud Run/Firebase execution (1E/1F) is deferred. Items marked
**verify** must be checked on an unrestricted machine against current Google documentation.

Related: [retrieval.md](retrieval.md) (library contract), [datasets.md](datasets.md),
[dataset-embedding-checklist.md](dataset-embedding-checklist.md).

## 1. Packaging DINOv2 for Cloud Run

| Option | Pros | Cons |
| --- | --- | --- |
| **Bake weights into the image (recommended)** | Immutable, versioned with the code; no startup download; works offline | Larger image; new image to change model |
| Download from GCS at startup | Smaller image | Cloud Run's `/tmp` is in-memory and counts against the memory limit; slower cold start |
| Cloud Storage volume mount (read-only) | No copy at startup | Extra configuration; read latency on first load |

Recommended build steps (to implement in 1E):

1. Install CPU-only torch first, from `https://download.pytorch.org/whl/cpu` (`torch==2.14.1`). The
   default Linux wheel bundles CUDA and is much larger.
2. `pip install ".[retrieval]"` (pinned `transformers`, `faiss-cpu`, `safetensors`).
3. Fetch weights during the build: `python scripts/fetch_dinov2.py --model-dir /app/models/...`
   (Meta's host, checksum-pinned) or copy them from a GCS mirror (`models/dinov2-small/<revision>/`).
4. Set `ROOTCAUSE_EMBEDDING_MODEL_DIR` to that folder. `Dinov2Embedder.load()` re-verifies the
   SHA-256 at startup and never downloads at request time.

## 2. Storing FAISS indexes in GCS

Proposed layout in the existing private bucket (prefixes configurable; check the bucket's current
layout first and adapt rather than migrate):

```text
gs://<bucket>/artifacts/faiss/dinov2-small/<index_version>/index_manifest.json
gs://<bucket>/artifacts/faiss/dinov2-small/<index_version>/<crop>.faiss
gs://<bucket>/artifacts/faiss/dinov2-small/<index_version>/<crop>.metadata.json
gs://<bucket>/artifacts/manifests/<index_version>/<crop>.csv, summary.json
gs://<bucket>/datasets/<crop>/<condition>/<reference_id>.<ext>      # reference images
gs://<bucket>/models/dinov2-small/<revision>/                         # optional weights mirror
```

Rules:

- Upload data files first and `index_manifest.json` last, so a version is only visible once complete.
- Versions are write-once: upload with an "object must not exist" precondition (`if_generation_match=0`).
  To change anything, build a new version.
- Bucket stays private: uniform bucket-level access, public access prevention enforced. Farmers
  never get direct object links; the backend reads objects (or issues short-lived signed URLs if a
  UI needs them).
- Index v1 metadata stores `local://references/images/...` URIs. For cloud use, build a new index
  version whose metadata stores `gs://` URIs (preferred, keeps checksums honest) rather than
  rewriting v1.

## 3. Restoring a versioned index at startup

1. Read `ROOTCAUSE_RETRIEVAL_INDEX_VERSION`.
2. Download `index_manifest.json` for that version, then each file it lists (about 1.5 MB for v1).
3. Verify every file's SHA-256 against the manifest.
4. Call the existing `load_reference_index`, which re-checks the embedding spec, dimension,
   counts, metric and crop.
5. Keep the loaded index in memory for the life of the instance.

Fail closed: if any step fails, retrieval raises `RetrievalError` and triage continues image-only.
Roll out a new version by deploying a new Cloud Run revision with the new variable; roll back by
routing traffic to the previous revision. Never swap versions inside a running instance.

## 4. Firestore metadata (future)

| Collection | Owner | Document fields | Notes |
| --- | --- | --- | --- |
| `reference_images/{reference_id}` | Shivansh | crop, condition, source_label, dataset_source, dataset_version, gcs_uri, sha256, image_style, license, attribution, source_url, embedding_model, model_revision, preprocessing_version, index_versions[], status, updated_at (server timestamp) | 763 documents for v1; batched writes (max 500 per batch); no vectors |
| `analyses/{analysis_id}` | Jayesh (decision D3) | retrieval fields only: retrieved reference_ids, similarity scores, index_version, model_revision | Image paths only if storing uploads is approved (D1) |
| `users/{uid}` | Jayesh (D3) | Minimal: what auth needs | Avoid personal data |

Firestore holds metadata only. Vectors stay in the FAISS files. Clients get no write access to
`reference_images` (security rules); the backend uses the Admin SDK.

## 5. Environment variables

| Variable | State | Purpose |
| --- | --- | --- |
| `ROOTCAUSE_DATA_DIR` | Implemented | Local data root (dev, offline tooling) |
| `ROOTCAUSE_EMBEDDING_MODEL_DIR` | Implemented | Model folder (in the image on Cloud Run) |
| `ROOTCAUSE_RETRIEVAL_INDEX_DIR` | Implemented | Folder holding index versions |
| `ROOTCAUSE_RETRIEVAL_INDEX_VERSION` | Implemented | Version to serve; unset disables retrieval |
| `ROOTCAUSE_GCS_BUCKET` | Proposed (1D) | Private artifact bucket |
| `ROOTCAUSE_GCS_ARTIFACT_PREFIX`, `ROOTCAUSE_GCS_DATASET_PREFIX` | Proposed (1D) | Default `artifacts/`, `datasets/` |
| `GOOGLE_CLOUD_PROJECT` | Proposed (1D) | Project for Firestore/Firebase Admin |
| `OMP_NUM_THREADS` | Proposed (1E) | Match torch threads to the vCPU count |
| `ROOTCAUSE_SPEECH_PROJECT_ID`, `ROOTCAUSE_SPEECH_LOCATION`, `ROOTCAUSE_SPEECH_MODEL`, `ROOTCAUSE_SPEECH_LANGUAGES` | Implemented | Voice input; project falls back to `GOOGLE_CLOUD_PROJECT_ID`; `us`, `chirp_3`, `["en-IN","hi-IN"]` by default |

Secrets (e.g. Gemini keys, Jayesh) go in Secret Manager and are exposed to Cloud Run as
environment variables. Nothing secret uses the `NEXT_PUBLIC_` prefix.

## 6. Service accounts and permissions (least privilege, verify)

| Identity | Roles | Scope |
| --- | --- | --- |
| Cloud Run runtime service account (dedicated, not the default compute account) | `roles/storage.objectViewer` | The artifact bucket (or prefixes via IAM conditions) |
| | `roles/datastore.user` | Only if the backend writes Firestore |
| | `roles/secretmanager.secretAccessor` | Only the specific secrets it needs |
| | `roles/speech.client` | Voice input (`POST /transcribe`); Speech-to-Text API enabled in the project |
| Index publisher (person or CI job) | `roles/storage.objectCreator` | `artifacts/` and `datasets/` (write-once publishes) |
| | `roles/datastore.user` | Syncing `reference_images` metadata |
| Cloud Build service account | `roles/artifactregistry.writer` | The backend image repository |
| | `roles/run.developer` + `roles/iam.serviceAccountUser` on the runtime account | Only if Cloud Build deploys |

Firebase ID-token verification with the Admin SDK needs the project ID, not extra roles.

## 7. Cloud Run sizing to benchmark later

Local measurements (Windows laptop CPU; indicative only): about 455 MB process memory after
loading; about 30 s startup, mostly importing torch; 49–131 ms per photo depending on load;
149 ms for 3 photos; FAISS search well under 1 ms.

| Config | vCPU | Memory | Concurrency | Purpose |
| --- | --- | --- | --- | --- |
| A | 1 | 2 GiB | 2 | Cheapest viable |
| B | 2 | 2 GiB | 4 | Expected default |
| C | 2 | 4 GiB | 8 | Headroom check |

Also: startup CPU boost on; a startup probe that waits for the retriever to load; request timeout
about 60 s; minimum instances 0 for cost, 1 only during demos. Measure cold start, p50/p95 latency for
1 and 3 photos, peak memory and error rate per config. Billing must be enabled for Cloud Run,
Artifact Registry and Cloud Build; check current pricing and free-tier limits rather than assuming
zero cost.

## 8. Integration with Jayesh's API

- One Cloud Run service: the retrieval library runs inside the FastAPI backend process.
- Warm-up (proposal for 1E, shared `app/main.py`): when `ROOTCAUSE_RETRIEVAL_INDEX_VERSION` is set,
  call `get_reference_retriever()` during startup and report `retrieval: ready|unavailable` from a
  readiness endpoint, so the 30 s load never lands on a farmer's request.
- Triage flow: `await retriever.aretrieve(report.crop, [img.data for img in report.images])`,
  then pass matches and `reference_image(match)` bytes to Gemini. Any `RetrievalError` means
  image-only analysis.
- Later extraction: the embedder sits behind the `ImageEmbedder` protocol, so DINOv2 can move to a
  separate service by swapping in a remote client without changing callers.
- An HTTP retrieval endpoint is optional (decision D2).

## 9. Must be tested on an unrestricted machine

- Docker build with CPU torch; image size; container start; `PORT` binding.
- Cloud Run cold start, memory, latency and concurrency (section 7).
- GCS publish (write-once) and restore with checksum verification, including missing/corrupt files.
- Firestore batched writes, queries and security rules.
- Firebase ID-token verification end to end.
- Frontend hosting choice (section 11).
- Gemini/ADK use of retrieved references (Jayesh).
- Live Speech-to-Text: `en-IN` and `hi-IN` recordings from Chrome/Android (WebM/Opus) and Safari/iOS
  (WAV fallback); latency; credentials via ADC and via the Cloud Run service account.

## 10. Needs GCP credentials or cloud access

Confirming the bucket and its layout; enabling APIs (Cloud Run, Artifact Registry, Cloud Build,
Firestore, Secret Manager, Speech-to-Text); creating service accounts and IAM bindings; uploading artifacts and
reference images; Firestore setup; building and pushing images; deploying Cloud Run; linking
Firebase and deploying hosting; creating secrets; enabling billing.

## 11. Frontend hosting (Firebase) review

Checked in `apps/web` (Next.js 16.4.0, App Router):

- No server actions, route handlers, cookies/headers, proxy/middleware, dynamic route segments
  or `next/image` (searched `apps/web/src`). These are the features the installed Next.js
  static-export guide lists as unsupported.
- `next/font/google` downloads fonts at build time (the build machine needs internet access).
- `NEXT_PUBLIC_API_BASE_URL` is inlined at build time, so each environment needs its own build.
- `next.config.ts` enables `cacheComponents` and `partialPrefetching`. The installed guide does not
  say whether these work with `output: 'export'`. **Verify** with a test build (frontend owner).

Decision path: if a static export builds and works, use Firebase Hosting (static). If not, use
Firebase App Hosting (server rendering; requires the Blaze pay-as-you-go plan) or serve the web app
from Cloud Run.
