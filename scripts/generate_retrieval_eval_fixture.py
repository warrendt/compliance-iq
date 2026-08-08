#!/usr/bin/env python3
"""Generate the offline retrieval-evaluation fixture for the gold mapping.

The recall claims behind the mapping engine's retrieval design (see
``app/backend/app/services/policy_catalog_service.py``) depend on two things that
normally require live Azure OpenAI calls: the LLM's Azure-vocabulary expansion of
each control, and the embedding of the resulting query.

CI has no Azure OpenAI credentials, so this script captures both once and commits
them. ``app/tests/test_mapping_recall.py`` can then reproduce the *entire*
hybrid retrieval pipeline offline and assert recall floors, which turns the
measured improvement into a regression test rather than a claim in a PR
description.

The fixture is a frozen snapshot of one model's output, not a live measurement.
Regenerate it when the expansion prompt, the embedding model, or the catalog
changes materially.

Usage::

    python scripts/generate_retrieval_eval_fixture.py \
        --endpoint https://<account>.openai.azure.com/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "app" / "backend"))
sys.path.insert(0, str(REPO_ROOT / "app" / "tests"))

FIXTURE_DIR = REPO_ROOT / "app" / "tests" / "fixtures"
DEFAULT_INTENTS = FIXTURE_DIR / "ncsp_v2_control_intents.json"
DEFAULT_VECTORS = FIXTURE_DIR / "ncsp_v2_query_embeddings.npz"

EMBEDDING_DIMENSIONS = 512
API_VERSION = "2024-10-21"


def build_client(endpoint: str):
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=endpoint, azure_ad_token_provider=provider, api_version=API_VERSION
    )


async def expand_all(client, model, controls, concurrency: int = 6):
    from app.services.control_intent_service import ControlIntentService

    service = ControlIntentService(client=client, model=model)
    semaphore = asyncio.Semaphore(concurrency)

    async def one(control):
        async with semaphore:
            intent = await service.expand(
                control["control_name"], control["description"], control.get("domain", "")
            )
        if intent.is_empty:
            print(f"  warning: empty expansion for {control['control_id']}")
        return control["control_id"], intent.model_dump()

    return dict(await asyncio.gather(*(one(c) for c in controls)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    )
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--embedding-deployment", default="text-embedding-3-large")
    parser.add_argument("--intents-out", type=Path, default=DEFAULT_INTENTS)
    parser.add_argument("--vectors-out", type=Path, default=DEFAULT_VECTORS)
    args = parser.parse_args()

    if not args.endpoint:
        parser.error("--endpoint or $AZURE_OPENAI_ENDPOINT is required")

    os.environ.setdefault("AZURE_OPENAI_ENDPOINT", args.endpoint)
    os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", args.model)
    os.environ.setdefault("ENABLE_AUTH", "false")

    import numpy as np

    from app.services.control_intent_service import ControlIntent
    from mapping_recall import QUERY_REALISTIC, controls_with_policies, load_gold

    controls = controls_with_policies(load_gold())
    client = build_client(args.endpoint)

    print(f"expanding {len(controls)} gold controls with {args.model}")
    intents = asyncio.run(expand_all(client, args.model, controls))

    payload = {
        "description": (
            "LLM Azure-vocabulary expansions of the NCSP v2.0 gold controls that "
            "carry policy GUIDs. Frozen so retrieval recall is reproducible in CI "
            "without Azure OpenAI credentials."
        ),
        "model": args.model,
        "intents": intents,
    }
    args.intents_out.parent.mkdir(parents=True, exist_ok=True)
    args.intents_out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.intents_out}")

    control_ids = [c["control_id"] for c in controls]
    queries = [
        ControlIntent(**intents[c["control_id"]]).build_query(QUERY_REALISTIC(c))
        for c in controls
    ]
    print(f"embedding {len(queries)} expanded queries ({args.embedding_deployment})")
    response = client.embeddings.create(
        model=args.embedding_deployment,
        input=[q[:7000] for q in queries],
        dimensions=EMBEDDING_DIMENSIONS,
    )
    matrix = np.asarray(
        [d.embedding for d in sorted(response.data, key=lambda d: d.index)],
        dtype=np.float32,
    )
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms

    np.savez_compressed(
        args.vectors_out,
        vectors=matrix.astype(np.float16),
        control_ids=np.array(control_ids),
        model=np.array(args.embedding_deployment),
    )
    print(f"wrote {args.vectors_out} ({matrix.shape[0]}x{matrix.shape[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
