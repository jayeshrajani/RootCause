# Deploying to Google Cloud Run

Two services: `rootcause-api` (FastAPI, including DINOv2/FAISS reference retrieval) and
`rootcause-web` (Next.js). Reference data is mounted read-only from a private bucket; see
[docs/cloud-readiness.md](../docs/cloud-readiness.md) for the longer-term plan.
Nothing here has been run yet (no Docker or gcloud on the authoring machine).

## One-time setup

```bash
PROJECT=<project-id>; REGION=asia-south1
gcloud config set project $PROJECT
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com speech.googleapis.com earthengine.googleapis.com

gcloud artifacts repositories create rootcause --repository-format=docker --location=$REGION

# Dedicated runtime identity (not the default compute account).
SA=rootcause@$PROJECT.iam.gserviceaccount.com
gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$SA --role=roles/speech.client
gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$SA --role=roles/serviceusage.serviceUsageConsumer
gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$SA --role=roles/earthengine.viewer
# The project must also be registered for Earth Engine, and $SA added there.

# Secrets (do not commit keys).
printf '%s' "<gemini-key>"   | gcloud secrets create gemini-api-key --data-file=-
printf '%s' "<cerebras-key>" | gcloud secrets create cerebras-api-key --data-file=-
for s in gemini-api-key cerebras-api-key; do
  gcloud secrets add-iam-policy-binding $s --member=serviceAccount:$SA --role=roles/secretmanager.secretAccessor
done
```

The Cloud Build service account also needs `roles/run.admin`, `roles/iam.serviceAccountUser` on
`$SA`, and `roles/artifactregistry.writer`. The deployment recipe tags images with the Cloud Build
`$BUILD_ID`, so it also works when submitting source directly from a local checkout.

### Reference data bucket (DINOv2 weights + FAISS index + reference photos, ~211 MB)

```bash
BUCKET=$PROJECT-rootcause-data
gcloud storage buckets create gs://$BUCKET --location=$REGION \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$SA --role=roles/storage.objectViewer
```

Upload these folders from the local `ROOTCAUSE_DATA_DIR`, keeping their paths (the API reads the
bucket as its data directory, so no index rebuild is needed):

| Bucket path | Contents |
| --- | --- |
| `models/dinov2-small/<revision>/` | Weights (`model.safetensors`, configs), SHA-256 checked at load |
| `artifacts/faiss/dinov2-small/v1/` | FAISS index, metadata, `index_manifest.json` |
| `references/images/` | 763 reference photos |

```bash
gcloud storage cp -r <data-dir>/models/dinov2-small gs://$BUCKET/models/
gcloud storage cp -r <data-dir>/artifacts <data-dir>/references gs://$BUCKET/
```

Another bucket name or index version: pass `_DATA_BUCKET=...` / `_INDEX_VERSION=...` as
substitutions. Missing or invalid data never blocks startup; triage runs without references.

## Deploy

The web bundle needs the API URL and the API needs the web URL, so deploy twice the first time:

```bash
# 1st run with empty URLs creates both services; read their URLs, then re-run with them.
gcloud builds submit --config deploy/cloudbuild.yaml
gcloud run services describe rootcause-api --region asia-south1 --format='value(status.url)'
gcloud run services describe rootcause-web --region asia-south1 --format='value(status.url)'
gcloud builds submit --config deploy/cloudbuild.yaml \
  --substitutions=_API_URL=<api-url>,_WEB_URL=<web-url>
```

Verify: `curl <api-url>/api/v1/health` should report `analysis_mode: ai`,
`satellite_imagery: configured` and, about 30–60 s after a cold start, `reference_photos: ready`.

## Before going public

`POST /transcribe` has no auth or rate limit and bills Speech-to-Text per call. Add a budget alert
and abuse protection first (see section 9 of the cloud-readiness doc).
