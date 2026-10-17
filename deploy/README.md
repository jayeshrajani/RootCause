# Deploying to Google Cloud Run

Two services: `rootcause-api` (FastAPI) and `rootcause-web` (Next.js). Reference retrieval
(DINOv2/FAISS) is not included yet; see [docs/cloud-readiness.md](../docs/cloud-readiness.md).
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

Verify: `curl <api-url>/health` should report `analysis_mode: ai` and `satellite_imagery: configured`.

## Before going public

`POST /transcribe` has no auth or rate limit and bills Speech-to-Text per call. Add a budget alert
and abuse protection first (see section 9 of the cloud-readiness doc).
