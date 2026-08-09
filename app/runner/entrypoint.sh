#!/bin/bash
#
# Registers this container as an ephemeral GitHub Actions runner, waits for
# exactly one job, then exits.
#
# Ephemeral matters here. A long-lived self-hosted runner is a standing offer to
# execute arbitrary workflow code inside the VNet, next to a private endpoint
# that fronts the OpenAI account. This one exists for the duration of a single
# job and takes its registration with it when it goes.
#
# POSIX note: this runs under bash deliberately, but avoid bashisms that dash
# would reject anyway -- an earlier defect in this repo was a `&>` redirect in a
# hook that made the Azure CLI look absent while printing its own path.

set -euo pipefail

: "${GH_URL:?GH_URL (the repository URL to register against) is required}"
: "${RUNNER_TOKEN:?RUNNER_TOKEN (a registration token) is required}"

RUNNER_LABELS="${RUNNER_LABELS:-ciq-vnet}"
RUNNER_NAME="${RUNNER_NAME:-ciq-vnet-$(hostname)}"

echo "registering ${RUNNER_NAME} against ${GH_URL} with labels [${RUNNER_LABELS}]"

# If the job is cancelled or the replica is evicted, deregister rather than
# leaving an offline runner behind that a later workflow could queue against
# forever. Failure here is not worth aborting on -- an ephemeral runner usually
# removes itself first, making this a no-op.
cleanup() {
  ./config.sh remove --token "${RUNNER_TOKEN}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# --disableupdate: the runner would otherwise try to self-update mid-job and
# restart, which an ephemeral single-job container handles badly.
./config.sh \
  --url "${GH_URL}" \
  --token "${RUNNER_TOKEN}" \
  --name "${RUNNER_NAME}" \
  --labels "${RUNNER_LABELS}" \
  --unattended \
  --ephemeral \
  --replace \
  --disableupdate

echo "registered; waiting for one job"
./run.sh
