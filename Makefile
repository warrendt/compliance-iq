# ComplianceIQ developer tasks.

.PHONY: refresh-mcsb refresh-mcsb-arm

# Regenerate the MCSB dataset offline (initiative GUIDs + ASB v3 xlsx + AI overlay).
# Fetches the canonical sources over HTTPS; no Azure credentials required.
refresh-mcsb:
	cd app/backend && python -m scripts.generate_mcsb_dataset --source offline

# Regenerate and refresh control text from ARM policyMetadata.
# Requires a delegated ARM token, e.g.:
#   ARM_ACCESS_TOKEN=$$(az account get-access-token \
#     --resource https://management.azure.com --query accessToken -o tsv) \
#     make refresh-mcsb-arm
refresh-mcsb-arm:
	cd app/backend && python -m scripts.generate_mcsb_dataset --source arm
