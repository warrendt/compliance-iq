#!/usr/bin/env python3
"""Generate sentence embeddings for the Azure Policy catalog snapshot.

Lexical retrieval structurally cannot map regulatory prose onto Azure Policy
display names, because the two rarely share vocabulary. NCSP control 2.3.2.2 --
"Keys shall be maintained by the cloud consumer or trusted key management
provider. Key management and key usage shall be separate duties." -- maps to the
built-in "Azure Key Vault should use RBAC permission model", with which it shares
no content term after stopwording.

This script precomputes an embedding per definition so ``PolicyCatalogService``
can fuse a dense ranking with its TF-IDF ranking. Measured on the NCSP v2.0 gold
mapping, that lifts micro-recall@500 from 86.7% (lexical) to 95.6% (hybrid).

Vectors are L2-normalised (so cosine similarity is a plain dot product) and
stored as float16, which is lossless for ranking purposes and keeps the shipped
artifact around 2.5 MB. Dimensionality is reduced via the embedding API's
``dimensions`` parameter; text-embedding-3-large is Matryoshka-trained, so 512
dims measured within noise of the full 3072 while being 6x smaller:

    dims   recall@200   recall@500   size (fp16)
    3072       82.2%        95.6%        15.1 MB
    1024       82.2%        94.4%         5.0 MB
     512       83.3%        94.4%         2.5 MB
     256       84.4%        91.1%         1.3 MB

Usage::

    python scripts/generate_policy_catalog_embeddings.py
    python scripts/generate_policy_catalog_embeddings.py --dimensions 1024
    python scripts/generate_policy_catalog_embeddings.py --endpoint https://... \
        --deployment text-embedding-3-large

Requires an authenticated Azure identity with ``Cognitive Services OpenAI User``
on the target account (``az login`` locally, OIDC in CI).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = REPO_ROOT / "app" / "backend" / "app" / "data" / "policy_catalog"
DEFAULT_CATALOG = CATALOG_DIR / "azure_policy_catalog.json"
DEFAULT_OUTPUT = CATALOG_DIR / "azure_policy_catalog_embeddings.npz"

DEFAULT_DEPLOYMENT = "text-embedding-3-large"
DEFAULT_DIMENSIONS = 512
# The embeddings API caps inputs per request; 96 stays well inside both the item
# and token limits for texts of this length.
BATCH_SIZE = 96
API_VERSION = "2024-10-21"


def embedding_text(definition: Dict[str, str]) -> str:
    """The text embedded for a definition.

    Display name first because it carries the most signal and is what an analyst
    would recognise; category is included so that domain words ("Key Vault",
    "Kubernetes") are present even when the description omits them.
    """
    return (
        f"{definition.get('display_name', '')}. "
        f"Category: {definition.get('category', '')}. "
        f"{definition.get('description', '')}"
    ).strip()


def load_definitions(path: Path) -> List[Dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    definitions = data.get("definitions") if isinstance(data, dict) else data
    return [
        d for d in (definitions or [])
        if (d.get("name") or "").strip() and (d.get("display_name") or "").strip()
    ]


def build_client(endpoint: str):
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=API_VERSION,
    )


def embed_all(client, deployment: str, texts: List[str], dimensions: int):
    import numpy as np

    vectors: List[List[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = [t[:7000] or " " for t in texts[start:start + BATCH_SIZE]]
        response = client.embeddings.create(
            model=deployment, input=batch, dimensions=dimensions
        )
        # The API does not guarantee response ordering, only the echoed index.
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
        print(f"  embedded {min(start + BATCH_SIZE, len(texts))}/{len(texts)}", flush=True)

    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        help="Azure OpenAI endpoint (defaults to $AZURE_OPENAI_ENDPOINT)",
    )
    parser.add_argument(
        "--deployment",
        default=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", DEFAULT_DEPLOYMENT),
    )
    parser.add_argument("--dimensions", type=int, default=DEFAULT_DIMENSIONS)
    args = parser.parse_args()

    if not args.endpoint:
        parser.error("--endpoint or $AZURE_OPENAI_ENDPOINT is required")
    if not args.catalog.exists():
        parser.error(
            f"catalog not found at {args.catalog}; "
            "run scripts/generate_policy_catalog.py first"
        )

    import numpy as np

    definitions = load_definitions(args.catalog)
    print(f"embedding {len(definitions)} definitions "
          f"({args.deployment}, {args.dimensions} dims)")

    client = build_client(args.endpoint)
    matrix = embed_all(
        client, args.deployment,
        [embedding_text(d) for d in definitions],
        args.dimensions,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        vectors=matrix.astype(np.float16),
        names=np.array([d["name"] for d in definitions]),
        model=np.array(args.deployment),
        dimensions=np.array(args.dimensions),
    )
    size_mb = args.output.stat().st_size / 1e6
    print(f"wrote {args.output} ({matrix.shape[0]}x{matrix.shape[1]}, {size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
