# Sweep image: the shipped backend plus the reference PDFs and the harness.
#
# The backend image cannot carry the reference documents (they are not part of
# the product), and the harness cannot run outside the VNet because Azure
# OpenAI and Cosmos both have public network access disabled. Build context is
# the repo root.
ARG BACKEND_IMAGE=crcomplianceiqdevkz2jze.azurecr.io/backend:latest
FROM ${BACKEND_IMAGE}

COPY reference_documents /sweep/reference_documents
COPY ops/sweep_reference_pdfs.py /sweep/sweep_reference_pdfs.py

WORKDIR /app
ENTRYPOINT ["python", "/sweep/sweep_reference_pdfs.py"]
