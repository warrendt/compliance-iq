"""Control intent expansion for Azure Policy retrieval.

The retrieval corpus (Azure built-in policy definitions) and the query
(regulatory control text) are written in two different vocabularies, and lexical
retrieval cannot bridge them. Measured against the NCSP v2.0 gold mapping
(``app/tests/test_mapping_recall.py``), querying the 2465-definition catalog with
the control's own words finds the expert's policy for only **15.6%** of gold
(control, policy) pairs at the shipped candidate window — and only **73.3%**
even when the entire catalog is scanned. Widening the candidate window therefore
cannot fix the problem.

The cause is vocabulary mismatch, not ranking depth. NCSP 2.3.2.2 reads "Keys
shall be maintained by the cloud consumer or trusted key management provider.
Key management and key usage shall be separate duties." The expert's answer is
the built-in "Azure Key Vault should use RBAC permission model" — which shares
no content term with the control after stopwording.

This module closes that gap by asking the model to restate the control as Azure
technical intent *before* retrieval: the concrete services, security features
and policy categories an Azure architect would look for. Retrieval then runs
over that restatement, which is written in the catalog's own vocabulary.
Substituting the human expert's equivalent restatement lifts recall at the same
window from 15.6% to 61.1%, which is the target this service aims at.

Design notes:

* Expansion is *additive*: the generated terms are appended to the original
  control text, never substituted for it. A poor expansion degrades toward the
  baseline instead of destroying a query that already worked.
* Failure is non-fatal. Any error returns a passthrough intent carrying the
  original text, so mapping continues with today's behaviour.
* Expansion is only worth its token cost for controls that could plausibly be
  policy-enforceable; the caller decides, driven by the coverage classification.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import openai
from pydantic import BaseModel, Field

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


EXPANSION_SYSTEM_PROMPT = """You are an Azure cloud security architect. You translate compliance control text into the vocabulary used by Azure Policy built-in definitions, so that a search engine can find the right definitions.

You are NOT selecting policies. You are NOT judging whether the control is enforceable. You only restate the control's technical intent in Azure terms.

Given a compliance control, produce:

1. **azure_restatement** — one or two sentences describing what an Azure engineer would actually configure or verify to satisfy this control. Use the phrasing style of Azure Policy display names, e.g. "Storage accounts should use customer-managed keys for encryption", "Diagnostic logs should be enabled and retained", "Accounts with owner permissions should be MFA enabled". Be concrete about the *mechanism*, not the governance objective.

2. **azure_services** — the specific Azure services or resource types involved (e.g. "Storage Account", "Key Vault", "SQL Server", "Virtual Machine", "Kubernetes Service", "App Service", "Log Analytics", "Recovery Services vault", "Microsoft Entra ID"). Empty if the control names no particular service.

3. **security_features** — the security capabilities or settings involved, in Azure's own words (e.g. "customer-managed key", "encryption at rest", "TLS version", "private endpoint", "network security group", "diagnostic setting", "soft delete", "purge protection", "trusted launch", "RBAC permission model", "geo-redundant backup", "zone redundancy").

4. **policy_categories** — likely Azure Policy definition categories, chosen ONLY from this list:
Storage, SQL, Key Vault, Network, Compute, App Service, Kubernetes, Monitoring, Security Center, Backup, Guest Configuration, General, Cosmos DB, Container Registry, Machine Learning, Synapse, Event Hub, Service Bus, Automation, API Management, Cognitive Services, Data Factory, SignalR, Search, Cache, Internet of Things, Resilience, Tags, Regulatory Compliance, Site Recovery, Bot Service, Batch, Data Lake, HDInsight, Managed Application, Media Services, Portal, Stream Analytics, VirtualEnclaves, Custom Provider, Lighthouse, Migrate, Sphere, Virtual Machine Images, Attestation, Mission

Rules:
- Prefer the specific over the generic: "TLS 1.2 minimum on Azure SQL" beats "secure communications".
- Expand abbreviations the way Azure spells them (MFA, CMK, HSM, RBAC, NSG, TDE).
- If a control implies several distinct mechanisms, name them all — recall matters more than precision here.
- If the control is purely procedural with no Azure mechanism at all, return an empty azure_restatement and empty lists rather than inventing a technical angle."""


class ControlIntent(BaseModel):
    """An Azure-vocabulary restatement of a compliance control."""

    azure_restatement: str = Field(
        default="",
        description="What an Azure engineer would configure, in Azure Policy phrasing",
    )
    azure_services: List[str] = Field(
        default_factory=list,
        description="Azure services or resource types the control concerns",
    )
    security_features: List[str] = Field(
        default_factory=list,
        description="Security capabilities/settings involved, in Azure vocabulary",
    )
    policy_categories: List[str] = Field(
        default_factory=list,
        description="Likely Azure Policy definition categories",
    )

    @property
    def is_empty(self) -> bool:
        """True when the model found no Azure mechanism to expand toward."""
        return not (
            self.azure_restatement.strip()
            or self.azure_services
            or self.security_features
        )

    def expansion_text(self) -> str:
        """The generated terms as a single retrieval-ready string."""
        parts = [self.azure_restatement]
        parts.extend(self.azure_services)
        parts.extend(self.security_features)
        return " ".join(p.strip() for p in parts if p and p.strip())

    def build_query(self, control_text: str) -> str:
        """Combine the original control text with the expansion.

        Additive by design: the original wording is retained so a weak expansion
        degrades toward the un-expanded baseline rather than replacing a query
        that already retrieved correctly.
        """
        expansion = self.expansion_text()
        if not expansion:
            return control_text
        return f"{control_text} {expansion}".strip()


def passthrough_intent() -> ControlIntent:
    """An intent that changes nothing, used when expansion is unavailable."""
    return ControlIntent()


class ControlIntentService:
    """Generates Azure-vocabulary restatements of compliance controls."""

    def __init__(self, client=None, model: Optional[str] = None) -> None:
        self._client = client
        self.model = model or settings.azure_openai_deployment_name

    @property
    def client(self):
        """Lazily resolve the Azure OpenAI client.

        Deferred so that constructing the service (and therefore importing the
        mapping service) does not require credentials — the retrieval tests
        exercise query building without ever calling the model.
        """
        if self._client is None:
            from ..auth import get_azure_openai_client

            self._client = get_azure_openai_client()
        return self._client

    async def expand(
        self,
        control_name: str,
        description: str,
        domain: str = "",
    ) -> ControlIntent:
        """Restate a control in Azure vocabulary. Never raises.

        Returns a passthrough intent on any failure so that a degraded expansion
        service reduces retrieval quality to the historical baseline rather than
        failing the mapping run.
        """
        if not settings.policy_catalog_query_expansion:
            return passthrough_intent()

        control_text = " ".join(p for p in (control_name, description, domain) if p)
        if not control_text.strip():
            return passthrough_intent()

        try:
            return await asyncio.to_thread(self._request_expansion, control_text)
        except Exception as exc:  # noqa: BLE001 - expansion is best-effort
            logger.warning(
                "Control intent expansion failed (%s); falling back to the raw "
                "control text for retrieval", exc,
            )
            return passthrough_intent()

    def _request_expansion(self, control_text: str) -> ControlIntent:
        """Blocking model call, run off the event loop by :meth:`expand`."""
        user_prompt = (
            "Restate this compliance control as Azure technical intent so that "
            "Azure Policy built-in definitions can be retrieved for it.\n\n"
            f"Control:\n{control_text}"
        )

        models = [self.model]
        fallback = settings.azure_openai_fallback_model
        if fallback and fallback != self.model:
            models.append(fallback)

        last_error: Optional[Exception] = None
        for model in models:
            try:
                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=[
                        {"role": "system", "content": EXPANSION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=ControlIntent,
                    max_completion_tokens=settings.policy_catalog_expansion_max_tokens,
                )
                intent = completion.choices[0].message.parsed
                if intent is None:
                    raise ValueError("model returned no parsed intent")
                return intent
            except (
                openai.RateLimitError,
                openai.APITimeoutError,
                openai.APIConnectionError,
            ) as exc:
                last_error = exc
                logger.warning(
                    "Control intent expansion with %s failed: %s. %s",
                    model, exc,
                    "Trying fallback model." if model != models[-1] else "No fallback remains.",
                )

        raise RuntimeError(
            f"Control intent expansion failed for all configured models: {last_error}"
        )


_service: Optional[ControlIntentService] = None


def get_control_intent_service() -> ControlIntentService:
    """Get the cached control intent service instance."""
    global _service
    if _service is None:
        _service = ControlIntentService()
    return _service
