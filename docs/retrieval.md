# Crop reference retrieval (DINOv2 + FAISS)

Owner: **Shivansh**. Consumer: the AI triage service (`app/services/triage/references.py`), which
turns matches into a per-cause `reference_score` used in evidence-fit ranking (see
[api-contract.md](api-contract.md)).

Given 1–3 farmer photos and a crop, retrieval returns the most visually similar **labelled
reference photos** of that crop from public datasets. It does not diagnose. The orchestrator
decides how (and whether) to use the references as evidence.

- Model: `facebook/dinov2-small` (revision `ed25f3a`), 384-dimensional L2-normalised CLS embeddings,
  CPU. The same model and preprocessing are used for reference and farmer photos.
- Index: one exact inner-product FAISS index per crop (cosine similarity), so search never crosses
  crops. Supported crops: `rice`, `tomato`, `potato`.
- Data: see [datasets.md](datasets.md). Progress and results: [dataset-embedding-checklist.md](dataset-embedding-checklist.md).

## Using it from the backend

```python
from app.services.retrieval import RetrievalError, get_reference_retriever

async def find_references(crop: str, photos: list[bytes]):
    try:
        retriever = get_reference_retriever()          # process-wide; loads once
        result = await retriever.aretrieve(crop, photos, top_k=5)
    except RetrievalError:
        return None                                    # fall back to image-only analysis
    images = [retriever.reference_image(m) for m in result.matches]  # bytes for Gemini
    return result, images
```

- `get_reference_retriever()` builds the retriever on first use (about 30 s on a laptop: importing
  torch, loading the model, verifying the index) and reuses it afterwards. It takes no arguments,
  so it also works as a FastAPI dependency. Call it once at startup in production to avoid a slow
  first request.
- Use `aretrieve` from async code: embedding is CPU-bound and runs in a worker thread.
  `retrieve` is the synchronous equivalent.
- `reference_image(match)` returns the reference photo's bytes. It raises
  `ReferenceImageUnavailableError` if the image cannot be read.
- `FarmerReport.crop` accepts 13 crops and may be empty; anything other than rice, tomato or potato
  raises `UnsupportedCropError`. Treat every `RetrievalError` as "no reference evidence", not as a
  failed triage.

There is no HTTP endpoint for retrieval. Whether to add one (e.g. `POST /api/v1/retrieval`) is
open decision D2 in the checklist.

### Signatures

```python
from app.services.retrieval import (
    ReferenceMatch, ReferenceRetriever, RetrievalError, RetrievalResult, get_reference_retriever,
)

def get_reference_retriever() -> ReferenceRetriever: ...
class ReferenceRetriever:
    index_version: str  # property
    def retrieve(self, crop_id: str, images: Sequence[bytes], *, top_k: int = 5) -> RetrievalResult: ...
    async def aretrieve(self, crop_id: str, images: Sequence[bytes], *, top_k: int = 5) -> RetrievalResult: ...
    def reference_image(self, match: ReferenceMatch) -> bytes: ...
```

`crop_id` also accepts the API's `Crop` enum (it is a `str`), e.g. `report.crop`.

### Expected quality

Held-out results for index v1 (Recall@5 = at least one same-label reference in the top 5):

| Crop | Field photos: Recall@5 / top-1 | Lab photos: Recall@5 / top-1 |
| --- | --- | --- |
| Rice | 0.986 / 0.861 (72) | — |
| Tomato | 0.781 / 0.406 (128) | 0.253 / 0.200 (75) |
| Potato | 0.972 / 0.750 (36) | 1.000 / 0.909 (22) |

Farmer uploads are field photos, so the field column is the relevant one. DINOv2 matches strongly
on background: tomato lab photos mostly retrieve the lab-only classes (spider mites, target spot).
Tomato top-1 is about 0.4, so references support reasoning; they do not identify the disease.

### Hybrid scoring

Triage asks the model to tag each possible cause with one of the crop's reference labels. The
share of the 10 closest references carrying that label becomes the cause's `reference_score`,
blended into evidence fit with a per-crop weight (rice 30, potato 20, tomato 10; analysis keeps
the rest, weather keeps 10). A best match below 0.35 cosine similarity is ignored: held-out field
photos score at least 0.45, blank or noise images at most 0.21.

`scripts/evaluate_hybrid.py --per-crop 10` (10 held-out field photos per crop, one model call
each, healthy excluded) gave top-cause agreement with the dataset label of:

| Crop | AI only | Ref weight 10 | 20 | 30 | References alone |
| --- | --- | --- | --- | --- | --- |
| Rice (10) | 0.50 | 0.60 | 0.80 | 0.90 | 0.90 |
| Tomato (9) | 0.44 | 0.44 | 0.44 | 0.44 | 0.22 |
| Potato (10) | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 |

Samples are small; re-run before changing weights.

## Contract

`retrieve(crop_id, images, *, top_k=5) -> RetrievalResult`

| Input | Rules |
| --- | --- |
| `crop_id` | `rice`, `tomato` or `potato` |
| `images` | 1–3 image byte strings (JPEG, PNG or WebP; already validated by the triage route) |
| `top_k` | 1–20 references in total across all photos |

| `RetrievalResult` field | Meaning |
| --- | --- |
| `crop_id` | Crop searched |
| `retrieval_model`, `model_revision`, `preprocessing_version`, `index_version` | Provenance; record these with any analysis |
| `top_k` | Requested result count |
| `matches[]` | Best first. Each reference appears once with its best score over the farmer photos |
| `similarity_note` | Must accompany scores wherever they are shown |

| `ReferenceMatch` field | Meaning |
| --- | --- |
| `reference_image_id` | Stable ID, e.g. `tomato-plantdoc-95a9c6ab4bf0` |
| `crop_id`, `disease_label` | Canonical crop and condition (e.g. `late_blight`, `healthy`) |
| `source_label`, `dataset_source` | Original dataset label and source (`plantdoc`, `plantvillage`, `mendeley_rice`) |
| `image_uri` | `local://...` relative to the data directory today; `gs://...` after cloud persistence (1D) |
| `image_style` | `field` or `lab` (plain background) |
| `similarity_score` | Cosine similarity in [-1, 1]. Ranking only; **not** a probability or confidence |
| `query_image_index` | Which farmer photo (0-based) matched best |
| `license`, `attribution`, `source_url` | Must be kept with any displayed reference image |

Example (real output, held-out tomato photo labelled `bacterial_spot`, `top_k=3`, licence fields
omitted):

```json
{
  "crop_id": "tomato",
  "retrieval_model": "facebook/dinov2-small",
  "model_revision": "ed25f3a31f01632728cabb09d1542f84ab7b0056",
  "preprocessing_version": "exif-rgb-short256-bicubic-center224-imagenet-v1",
  "index_version": "v1",
  "top_k": 3,
  "matches": [
    {
      "reference_image_id": "tomato-plantdoc-95a9c6ab4bf0",
      "crop_id": "tomato",
      "disease_label": "bacterial_spot",
      "source_label": "Tomato leaf bacterial spot",
      "dataset_source": "plantdoc",
      "image_uri": "local://references/images/tomato/tomato-plantdoc-95a9c6ab4bf0.jpg",
      "image_style": "field",
      "similarity_score": 0.6914,
      "query_image_index": 0
    },
    { "reference_image_id": "tomato-plantdoc-3be8d7001035", "disease_label": "mosaic_virus", "similarity_score": 0.6807, "...": "..." },
    { "reference_image_id": "tomato-plantdoc-f9c1209dd478", "disease_label": "early_blight", "similarity_score": 0.6694, "...": "..." }
  ],
  "similarity_note": "Similarity ranks visual resemblance to labelled reference images. It is not a diagnostic probability."
}
```

The illustrative contract in the planning prompt used `gcs_uri` and `analysis_id`. Here the field is
`image_uri` (it becomes a `gs://` URI after 1D), and `analysis_id` belongs to the orchestrator,
not to retrieval.

### Errors

All inherit from `RetrievalError`; messages are safe to log.

| Error | When |
| --- | --- |
| `UnsupportedCropError` | Crop is not rice, tomato or potato |
| `InvalidQueryError` | 0 or more than 3 photos, bad `top_k`, or an unreadable photo |
| `IndexUnavailableError` | Retrieval not configured, index version missing, or crop not in the index |
| `IndexCompatibilityError` | Index corrupt, tampered with, or built with a different model/preprocessing |
| `EmbeddingError` | Model weights missing or unverified, or an unusable embedding |
| `ReferenceImageUnavailableError` | A matched reference photo cannot be read |

### Using references in a Gemini prompt

- Present them as "reference photos from public datasets with their dataset labels", separate from
  the farmer's photos.
- A matching label is supporting evidence at most. Never convert similarity into confidence.
- Prefer `field` references; `lab` photos have plain backgrounds and match on background as well as
  symptoms.
- Keep `attribution` with any reference image shown to farmers.

## Running it locally

From `apps/api`, with the venv active:

```bash
pip install -e ".[dev,datasets,retrieval]"
python scripts/prepare_datasets.py --data-dir <DATA_DIR>          # downloads ~500 MB, writes images
python scripts/fetch_dinov2.py --data-dir <DATA_DIR>              # 88 MB model, checksum-verified
python scripts/build_index.py --data-dir <DATA_DIR> --index-version v1
python scripts/inspect_retrieval.py --data-dir <DATA_DIR> --index-version v1   # sanity checks + gallery
```

Then set `ROOTCAUSE_DATA_DIR=<DATA_DIR>` and `ROOTCAUSE_RETRIEVAL_INDEX_VERSION=v1` in the repo-root
`.env` (or `apps/api/.env`). Use a data directory outside Git and synced folders. The API loads the
library in the background at startup; `GET /api/v1/health` reports `reference_photos: ready`.

On macOS the torch and faiss-cpu wheels each bundle OpenMP. Importing `app.services.retrieval`
sets `KMP_DUPLICATE_LIB_OK=TRUE` and `OMP_NUM_THREADS=1` (unless already set) so both can load in
one process; without them the process aborts or segfaults.

The manifests are committed and the model weights are checksum-pinned, so every machine indexes the
same images with the same model. Embedding values can differ in the last decimal places between
CPUs, so index files are not guaranteed to be byte-identical across machines; rankings are
effectively the same.

To test a photo of your own:
`python scripts/inspect_retrieval.py --data-dir <DATA_DIR> --index-version v1 --crop tomato --image leaf.jpg`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ROOTCAUSE_DATA_DIR` | — | Root for datasets, model weights, embedding cache and indexes |
| `ROOTCAUSE_RETRIEVAL_INDEX_VERSION` | — | Index version to serve (e.g. `v1`). Required to enable retrieval |
| `ROOTCAUSE_EMBEDDING_MODEL_DIR` | `DATA_DIR/models/dinov2-small/<revision>` | Local model directory |
| `ROOTCAUSE_RETRIEVAL_INDEX_DIR` | `DATA_DIR/artifacts/faiss/dinov2-small` | Folder holding index versions |

Index versions are immutable. To change the reference set, build a new version and switch the
variable; the old version stays available for rollback.

## Deployment notes (before 1D/1E)

Measured on a Windows laptop CPU (indicative only; Cloud Run's CPUs differ):

| Measure | Value |
| --- | --- |
| Startup (import, model load, index verification) | ~30 s |
| Query, 1 photo / 3 photos | 85 ms / 149 ms |
| FAISS search | ~0.06 ms |
| Process memory after load | ~455 MB |
| Artifacts | model 88 MB; index v1 1.5 MB (763 vectors plus metadata) |

- Install torch from the CPU wheel index in containers; the default Linux wheel bundles CUDA.
- Start with 2 GiB memory and 1–2 vCPU per instance. Embedding is CPU-bound, so keep request
  concurrency modest and load-test before raising it.
- Scale-to-zero means each cold start pays the ~30 s load; keep one warm instance only for demos.
- Until cloud persistence (1D) exists, model and index must be baked into the container image or
  mounted, and `image_uri` values only resolve on machines that have the data directory.

Cloud packaging, GCS layout, index restore, Firestore, IAM and sizing plans:
[cloud-readiness.md](cloud-readiness.md).
