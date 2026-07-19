#!/bin/sh
# Rewrite the single window.COMPLIANCEIQ_APP_URL line in config.js from the
# COMPLIANCEIQ_APP_URL environment variable at container start.
#
# This lets Warren set the real deployed app URL at deploy time WITHOUT
# rebaking the image and without committing the URL to the public repo.
# If the env var is unset, the committed placeholder is left untouched.
set -eu

CONFIG_FILE="/usr/share/nginx/html/config.js"

if [ -n "${COMPLIANCEIQ_APP_URL:-}" ] && [ -f "$CONFIG_FILE" ]; then
  # Escape characters that are special to sed's replacement.
  escaped=$(printf '%s' "$COMPLIANCEIQ_APP_URL" | sed -e 's/[&/\]/\\&/g')
  sed -i "s|window.COMPLIANCEIQ_APP_URL = \".*\";|window.COMPLIANCEIQ_APP_URL = \"${escaped}\";|" "$CONFIG_FILE"
  echo "[app-url] config.js set to ${COMPLIANCEIQ_APP_URL}"
else
  echo "[app-url] COMPLIANCEIQ_APP_URL not set; using committed placeholder"
fi
