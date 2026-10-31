#!/bin/bash
# Deploy GEAP Harness Eval to Cloud Run (your GEAP_PROJECT) behind a global HTTPS load balancer:
#   public read-only dashboard; /admin/* and /api/admin/* behind IAP (admin emails only).
# Idempotent: re-running updates the service to the latest image. Always passes --project explicitly.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a        # GEAP_PROJECT, GEAP_ADMIN_EMAILS (git-ignored)
P=${GEAP_PROJECT:?set GEAP_PROJECT in .env}; R=${GEAP_REGION:-us-central1}; SVC=geap-eval
SA=geap-eval-runner@$P.iam.gserviceaccount.com
BUCKET=${GEAP_ARTIFACT_BUCKET:-$P-geap-eval}; IMAGE=us-central1-docker.pkg.dev/$P/geap-eval/geap-eval:${IMAGE_TAG:-latest}
ADMINS=${GEAP_ADMIN_EMAILS:?set GEAP_ADMIN_EMAILS in .env}
PNUM=$(gcloud projects describe $P --format="value(projectNumber)")

step() { echo; echo "==> $*"; }

step "Cloud Run service (single always-on instance, 8 vCPU / 32 GiB, gen2, LB-only ingress)"
gcloud run deploy $SVC --project $P --region $R --image "$IMAGE" --service-account $SA \
  --cpu 8 --memory 32Gi --min-instances 1 --max-instances 1 --no-cpu-throttling \
  --execution-environment gen2 --timeout 3600 --concurrency 200 --port 8080 \
  --ingress internal-and-cloud-load-balancing --allow-unauthenticated \
  --set-env-vars "^|^GEAP_PROJECT=$P|GOOGLE_CLOUD_PROJECT=$P|GEAP_ARTIFACT_BUCKET=$BUCKET|GEAP_ADMIN_EMAILS=$ADMINS|GEAP_SA_IDENTITY=$SA${IAP_AUD:+|GEAP_IAP_AUDIENCE=$IAP_AUD}" \
  --startup-probe "httpGet.path=/api/health,initialDelaySeconds=5,periodSeconds=5,failureThreshold=60,timeoutSeconds=3" \
  --quiet

step "Serverless NEG + backend services (public, admin+IAP)"
gcloud compute network-endpoint-groups describe $SVC-neg --region $R --project $P >/dev/null 2>&1 || \
  gcloud compute network-endpoint-groups create $SVC-neg --region $R --network-endpoint-type serverless \
    --cloud-run-service $SVC --project $P
for be in $SVC-public $SVC-admin; do
  gcloud compute backend-services describe $be --global --project $P >/dev/null 2>&1 || {
    gcloud compute backend-services create $be --global --load-balancing-scheme EXTERNAL_MANAGED --project $P
    gcloud compute backend-services add-backend $be --global --network-endpoint-group $SVC-neg \
      --network-endpoint-group-region $R --project $P; }
done
gcloud compute backend-services update $SVC-admin --global --iap=enabled --project $P
for a in ${ADMINS//,/ }; do
  gcloud iap web add-iam-policy-binding --resource-type backend-services --service $SVC-admin \
    --member "user:$a" --role roles/iap.httpsResourceAccessor --project $P --condition=None >/dev/null
done
# Cloud Run must accept calls from the IAP service agent on the admin path
gcloud run services add-iam-policy-binding $SVC --region $R --project $P \
  --member "serviceAccount:service-$PNUM@gcp-sa-iap.iam.gserviceaccount.com" --role roles/run.invoker >/dev/null

step "URL map: /admin/* and /api/admin/* -> IAP backend; everything else public"
BASE=https://www.googleapis.com/compute/v1/projects/$P/global/backendServices
cat > /tmp/geap-urlmap.yaml <<YAML
name: $SVC-map
defaultService: $BASE/$SVC-public
hostRules:
- hosts: ['*']
  pathMatcher: admin
pathMatchers:
- name: admin
  defaultService: $BASE/$SVC-public
  pathRules:
  - paths: ['/admin', '/admin/*', '/api/admin/*']
    service: $BASE/$SVC-admin
YAML
gcloud compute url-maps import $SVC-map --global --source /tmp/geap-urlmap.yaml --project $P --quiet

step "HTTPS proxy + forwarding rule on the reserved IP (cert: <ip>.sslip.io, Google-managed)"
gcloud compute target-https-proxies describe $SVC-https --global --project $P >/dev/null 2>&1 || \
  gcloud compute target-https-proxies create $SVC-https --global --url-map $SVC-map --ssl-certificates $SVC-cert --project $P
gcloud compute forwarding-rules describe $SVC-fr --global --project $P >/dev/null 2>&1 || \
  gcloud compute forwarding-rules create $SVC-fr --global --load-balancing-scheme EXTERNAL_MANAGED \
    --address $SVC-ip --target-https-proxy $SVC-https --ports 443 --project $P

BE_ID=$(gcloud compute backend-services describe $SVC-admin --global --project $P --format="value(id)")
echo; echo "IAP audience: /projects/$PNUM/global/backendServices/$BE_ID"
echo "Re-run with IAP_AUD=/projects/$PNUM/global/backendServices/$BE_ID to enable admin JWT verification."
