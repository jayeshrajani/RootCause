# Deploying to Google Cloud Run

Two services: `rootcause-api` (FastAPI) and `rootcause-web` (Next.js). Reference retrieval uses a
FAISS index of the dataset photos embedded with **Gemini Embedding 2** (index `v2`), mounted
read-only from a bucket; farmer photos are embedded with the same model at request time. The API
image contains FAISS but no torch/DINOv2 (DINOv2 `v1` remains for local development).

## One-time setup

```bash
PROJECT=<project-id>; REGION=asia-south1
gcloud config set project $PROJECT
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com speech.googleapis.com earthengine.googleapis.com

gcloud artifacts repositories create rootcause --repository-format=docker --location=$REGION

# Dedicated runtime identity (not the default compute account).
gcloud iam service-accounts create rootcause
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

The Gemini key's project must be able to pay for Gemini calls (Prepay credits in AI Studio, or the
free tier on a project without billing). With $0 Prepay credit every call fails with HTTP 402.

## Reference index with Gemini Embedding 2 (once, in Cloud Shell)

The dataset photos are embedded once; vectors are cached, so an interrupted run resumes without
re-paying. 1,096 images (763 references + 333 held-out evaluation photos) = 183 API calls.

```bash
BUCKET=$PROJECT-rootcause-data
gcloud storage buckets create gs://$BUCKET --location=$REGION \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$SA --role=roles/storage.objectViewer

# Dataset photos: upload rootcause-gemini-dataset.zip (references/ + evaluation/) with
# Cloud Shell's More > Upload, then:
unzip -q ~/rootcause-gemini-dataset.zip -d ~/rcdata

cd apps/api
python3 -m venv ~/venv && source ~/venv/bin/activate && pip install -q ".[index]"
read -s -p "Gemini key: " GEMINI_API_KEY && export GEMINI_API_KEY; echo

python scripts/gemini_embedding_smoke.py --data-dir ~/rcdata          # 1 call, 3 images
python scripts/build_index.py --data-dir ~/rcdata --index-version v2 --embedder gemini
python scripts/evaluate_retrieval.py --data-dir ~/rcdata --index-version v2 --embedder gemini

gcloud storage cp -r ~/rcdata/artifacts gs://$BUCKET/
```

Compare the evaluation with DINOv2 `v1` (Recall@5: rice 0.986, tomato 0.586, potato 0.983). To
serve DINOv2 instead, deploy with `_EMBEDDER=dinov2,_INDEX_VERSION=v1` and an image that installs
the `retrieval` extra.

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
`satellite_imagery: configured` and `reference_photos: ready`.

## Before going public

`POST /transcribe` has no auth or rate limit and bills Speech-to-Text per call. Add a budget alert
and abuse protection first (see section 9 of the cloud-readiness doc).
