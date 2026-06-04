#!/usr/bin/env bash
#
# acr-build-deploy.sh — one-command, server-side (x86) build + push + deploy.
#
# Builds the backend and/or frontend images with `az acr build` (runs in the
# registry on amd64, avoiding the Apple-Silicon arm64 image trap) and rolls the
# new image onto the corresponding Azure Container App with `az containerapp
# update`.
#
# Usage:
#   app/scripts/acr-build-deploy.sh [backend|frontend|both] [tag]
#
#   ./acr-build-deploy.sh                # build+deploy both, tag = git short sha
#   ./acr-build-deploy.sh backend        # backend only
#   ./acr-build-deploy.sh frontend v3    # frontend only, explicit tag
#
# All resource identifiers can be overridden via environment variables (defaults
# target the wdt-cciq-03 azd environment):
#   REGISTRY        ACR name (without .azurecr.io)   [crnuib2mtsi7po6]
#   RESOURCE_GROUP  Container Apps resource group      [rg-wdt-cciq-03]
#   BACKEND_APP     Backend Container App name         [ca-backend-nuib2mtsi7po6]
#   FRONTEND_APP    Frontend Container App name        [ca-frontend-nuib2mtsi7po6]
#   IMAGE_PREFIX    Image repository prefix            [compliance-iq]
#   IMAGE_SUFFIX    Image name suffix                  [wdt-cciq-03]
#
set -euo pipefail

# ── Resolve repo root (two levels up from this script: app/scripts/..) ────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ── Configuration (env-overridable) ───────────────────────────────────────────
REGISTRY="${REGISTRY:-crnuib2mtsi7po6}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-wdt-cciq-03}"
BACKEND_APP="${BACKEND_APP:-ca-backend-nuib2mtsi7po6}"
FRONTEND_APP="${FRONTEND_APP:-ca-frontend-nuib2mtsi7po6}"
IMAGE_PREFIX="${IMAGE_PREFIX:-compliance-iq}"
IMAGE_SUFFIX="${IMAGE_SUFFIX:-wdt-cciq-03}"

TARGET="${1:-both}"
TAG="${2:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"

LOGIN_SERVER="${REGISTRY}.azurecr.io"

# ── Preflight ─────────────────────────────────────────────────────────────────
if ! command -v az >/dev/null 2>&1; then
  echo "Error: Azure CLI (az) is not installed." >&2
  exit 1
fi
if ! az account show >/dev/null 2>&1; then
  echo "Error: not logged in to Azure. Run 'az login' first." >&2
  exit 1
fi

case "${TARGET}" in
  backend|frontend|both) ;;
  *)
    echo "Error: target must be 'backend', 'frontend', or 'both' (got '${TARGET}')." >&2
    exit 1
    ;;
esac

# ── Build + deploy one service ────────────────────────────────────────────────
build_and_deploy() {
  local service="$1" app_name="$2"
  local image="${IMAGE_PREFIX}/${service}-${IMAGE_SUFFIX}:${TAG}"
  local context="${REPO_ROOT}/app/${service}"
  local dockerfile="${context}/Dockerfile"

  echo "==> [${service}] building ${LOGIN_SERVER}/${image} (server-side, amd64)"
  az acr build \
    --registry "${REGISTRY}" \
    --image "${image}" \
    --file "${dockerfile}" \
    "${context}"

  echo "==> [${service}] updating Container App '${app_name}'"
  az containerapp update \
    --name "${app_name}" \
    --resource-group "${RESOURCE_GROUP}" \
    --image "${LOGIN_SERVER}/${image}"

  echo "==> [${service}] done (${image})"
}

echo "Registry:       ${LOGIN_SERVER}"
echo "Resource group: ${RESOURCE_GROUP}"
echo "Target:         ${TARGET}"
echo "Tag:            ${TAG}"
echo

if [[ "${TARGET}" == "backend" || "${TARGET}" == "both" ]]; then
  build_and_deploy "backend" "${BACKEND_APP}"
fi
if [[ "${TARGET}" == "frontend" || "${TARGET}" == "both" ]]; then
  build_and_deploy "frontend" "${FRONTEND_APP}"
fi

echo
echo "All requested services built and deployed (tag: ${TAG})."
