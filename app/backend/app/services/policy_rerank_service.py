"""LLM reranking of retrieved Azure Policy candidates.

Retrieval and selection want opposite things. Retrieval should be *wide*, because
a definition that is never retrieved can never be selected: measured on the NCSP
v2.0 gold mapping, hybrid retrieval finds 84.4% of the expert's policies at depth
200 but only 38.9% at depth 15. Selection should be *narrow*, because a 200-item
candidate list buries the right answer in noise and costs a large prompt.

This module bridges the two. It takes the wide shortlist and asks the model to
keep only the definitions that plausibly enforce the control, preserving order,
so the selection stage sees a short high-quality list drawn from a wide sweep.

The reranker is deliberately *recall-oriented*: it is told to keep anything
plausible rather than to pick winners. Precision is the selection stage's job,
and a definition discarded here is unrecoverable.

Failure is non-fatal: any error falls back to the retrieval order truncated to
the candidate window, i.e. today's behaviour.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Sequence

from pydantic import BaseModel, Field

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


RERANK_SYSTEM_PROMPT = """You are an Azure Policy expert filtering a candidate list.

You are given a compliance control and a numbered list of Azure built-in policy definitions retrieved for it. Return the numbers of the definitions that could plausibly help enforce or evidence this control, ordered most relevant first.

This is a RECALL step, not a final selection. Someone else makes the final choice from your shortlist, so:
- Keep anything plausibly related. A wrong keep is cheap; a wrong discard is unrecoverable.
- Discard only definitions that are clearly about an unrelated service or concern.
- Prefer definitions that enforce or audit a concrete configuration over "Regulatory Compliance" entries, which are manual attestation placeholders with no enforcement logic.
- If the control is procedural or organisational and no definition genuinely applies, return an empty list. Do not pad the shortlist.

Return only the numbers, most relevant first."""


class RerankResult(BaseModel):
    """The reranker's shortlist, as 1-based indices into the candidate list."""

    selected: List[int] = Field(
        default_factory=list,
        description="1-based candidate numbers, most relevant first",
    )


class PolicyRerankService:
    """Narrows a wide retrieval shortlist to the selection window."""

    def __init__(self, client=None, model: Optional[str] = None) -> None:
        self._client = client
        self.model = model or settings.azure_openai_deployment_name

    @property
    def client(self):
        """Lazily resolve the Azure OpenAI client (see ControlIntentService)."""
        if self._client is None:
            from ..auth import get_azure_openai_client

            self._client = get_azure_openai_client()
        return self._client

    async def rerank(
        self,
        control_text: str,
        candidates: Sequence,
        top_n: Optional[int] = None,
    ) -> List:
        """Return at most ``top_n`` candidates, reranked. Never raises.

        Args:
            control_text: The control being mapped.
            candidates: Retrieved ``PolicyCandidate`` objects, retrieval order.
            top_n: Size of the returned window. Defaults to the candidate count.

        Returns:
            A sublist of ``candidates``. On any failure, the first ``top_n`` in
            retrieval order, so a reranker outage costs precision, not recall.
        """
        top_n = top_n or settings.policy_catalog_candidate_count
        if not candidates:
            return []
        if not settings.policy_catalog_rerank or len(candidates) <= top_n:
            return list(candidates[:top_n])

        try:
            selected = await asyncio.to_thread(
                self._request_rerank, control_text, candidates, top_n
            )
        except Exception as exc:  # noqa: BLE001 - reranking is best-effort
            logger.warning(
                "Policy candidate reranking failed (%s); falling back to "
                "retrieval order.", exc,
            )
            return list(candidates[:top_n])

        # Map 1-based indices back to candidates, ignoring anything out of range
        # or duplicated rather than trusting the model's arithmetic.
        seen = set()
        reranked = []
        for number in selected:
            idx = number - 1
            if 0 <= idx < len(candidates) and idx not in seen:
                seen.add(idx)
                reranked.append(candidates[idx])
            if len(reranked) >= top_n:
                break

        if not reranked:
            # An empty shortlist is a legitimate answer for a process control,
            # but it is indistinguishable here from a malformed response, so
            # report it and let the (blind) coverage classification decide.
            logger.info(
                "Reranker returned no candidates for this control; passing an "
                "empty shortlist to selection."
            )
        logger.info(
            "Reranked %d retrieved candidates down to %d",
            len(candidates), len(reranked),
        )
        return reranked

    def _request_rerank(
        self, control_text: str, candidates: Sequence, top_n: int
    ) -> List[int]:
        """Blocking model call, run off the event loop by :meth:`rerank`."""
        lines = []
        for i, c in enumerate(candidates, start=1):
            description = (c.description or "").strip().replace("\n", " ")
            if len(description) > 160:
                description = description[:157] + "..."
            lines.append(f"{i}. {c.display_name} [{c.category}] — {description}")

        user_prompt = (
            f"Control:\n{control_text}\n\n"
            f"Candidate Azure Policy definitions:\n" + "\n".join(lines) + "\n\n"
            f"Return at most {top_n} candidate numbers, most relevant first."
        )

        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": RERANK_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=RerankResult,
            max_completion_tokens=settings.policy_catalog_rerank_max_tokens,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("model returned no parsed rerank result")
        return parsed.selected


_service: Optional[PolicyRerankService] = None


def get_policy_rerank_service() -> PolicyRerankService:
    """Get the cached policy rerank service instance."""
    global _service
    if _service is None:
        _service = PolicyRerankService()
    return _service
