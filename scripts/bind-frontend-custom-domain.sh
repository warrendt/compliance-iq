#!/usr/bin/env bash
#
# Bind the ComplianceIQ frontend Container App to a custom domain with a free,
# auto-renewing managed TLS certificate.
#
# This is the imperative counterpart to the Bicep in app/infra (param
# `frontendCustomDomain` + core/frontend-custom-domain.bicep). It exists because
# the dev environment's Easy Auth was configured manually (azd env has no
# AUTH_CLIENT_*), so a full `azd provision` would risk disturbing the live auth
# config. This script converges the SAME end state without a reprovision.
#
# PREREQUISITE — DNS (hosted on Cloudflare, external to Azure). These records
# MUST exist and have propagated BEFORE running this script, or managed
# certificate issuance will fail:
#
#   CNAME  app          -> <frontend FQDN>                (DNS only / grey cloud)
#   TXT    asuid.app     -> <customDomainVerificationId>
#
# Get the verification id with:
#   az containerapp show -n "$APP" -g "$RG" --query customDomainVerificationId -o tsv
#
# Usage:
#   ./scripts/bind-frontend-custom-domain.sh \
#     [DOMAIN] [APP] [RESOURCE_GROUP] [ENVIRONMENT]
#
# Defaults target the dev environment.
set -euo pipefail

DOMAIN="${1:-app.compliance-iq.net}"
APP="${2:-ca-frontend-ciq-dev-kz2jze}"
RG="${3:-rg-complianceiq-dev-southafricanorth}"
ENVIRONMENT="${4:-cae-complianceiq-dev-kz2jze}"

echo "Binding ${DOMAIN} -> ${APP} (rg=${RG}, env=${ENVIRONMENT})"

# Step 1 — add the hostname to the app first. A managed certificate cannot be
# issued until the hostname exists on a container app in the environment
# (otherwise: RequireCustomHostnameInEnvironment). This validates ownership via
# the asuid TXT + CNAME records and creates the binding in 'Disabled' state.
# Idempotent: re-adding an existing hostname is a no-op.
az containerapp hostname add \
  --name "$APP" \
  --resource-group "$RG" \
  --hostname "$DOMAIN" || true

# Step 2 — issue + bind a free managed certificate (SniEnabled). With no
# --certificate supplied, 'hostname bind' looks for or creates the managed
# certificate and binds it in a single call. Issuance can take up to ~20 min.
az containerapp hostname bind \
  --name "$APP" \
  --resource-group "$RG" \
  --hostname "$DOMAIN" \
  --environment "$ENVIRONMENT" \
  --validation-method CNAME

echo "Bound. Custom domains now on ${APP}:"
az containerapp show -n "$APP" -g "$RG" \
  --query "properties.configuration.ingress.customDomains[].{name:name,binding:bindingType}" -o table
