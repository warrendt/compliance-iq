# A GitHub Actions runner that lives inside the VNet.
#
# Why this exists
# ---------------
# The Azure OpenAI account that serves embeddings refuses public traffic. It is
# reachable only through a private endpoint at 10.20.3.6, inside
# vnet-complianceiq-dev-kz2jze. A GitHub-hosted runner therefore cannot
# regenerate catalog embeddings -- verified, not assumed: it receives
# "403 Public access is disabled".
#
# The catalog and its embeddings must ship together. A catalog-only refresh
# silently drops hybrid retrieval to lexical, taking recall@200 from 84.4% to
# 72.2% with nothing failing to indicate it. So the refresh has to run somewhere
# inside the VNet, and this image is that somewhere.
#
# The alternative was to open the endpoint to the public internet, which would
# trade a compliance product's network posture for CI convenience. Not done.
#
# The runner is ephemeral: it registers, executes exactly one job, then
# deregisters and exits. Nothing persists between runs, and no idle runner sits
# holding a live registration waiting to be used by something else.

FROM ubuntu:22.04

ARG RUNNER_VERSION=2.336.0
ENV DEBIAN_FRONTEND=noninteractive

# libicu70 is not optional -- the runner is .NET and fails at startup without it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      jq \
      libicu70 \
      python3 \
      python3-pip \
      python3-venv \
      unzip \
 && rm -rf /var/lib/apt/lists/*

# The workflow authenticates to ARM and Cognitive Services with this job's
# managed identity, so the Azure CLI has to be present.
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# The runner refuses to execute as root.
RUN useradd -m -s /bin/bash runner \
 && mkdir -p /actions-runner \
 && chown runner:runner /actions-runner

USER runner
WORKDIR /actions-runner

RUN curl -fsSL -o runner.tar.gz \
      "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
 && tar xzf runner.tar.gz \
 && rm runner.tar.gz

COPY --chown=runner:runner entrypoint.sh /actions-runner/entrypoint.sh

# The build context comes from a Windows checkout, where neither the executable
# bit nor LF line endings survive the trip. A CRLF shebang fails with the
# famously unhelpful "no such file or directory" naming a file that plainly
# exists, so strip them here rather than depend on how the file was checked out.
RUN sed -i 's/\r$//' /actions-runner/entrypoint.sh \
 && chmod +x /actions-runner/entrypoint.sh

ENTRYPOINT ["/actions-runner/entrypoint.sh"]
