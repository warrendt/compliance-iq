"""Blind coverage classification of compliance controls.

Most compliance controls cannot be enforced by Azure Policy, and pretending
otherwise is the mapping engine's worst failure mode: attaching a plausible
policy to a governance control produces false confidence, and the resulting
initiative claims coverage the organisation does not have.

The scale of it is measurable. In the expert-built NCSP v2.0 mapping
(``app/tests/fixtures/ncsp_v2_gold_mapping.json``) only 24 of 137 controls (17.5%)
are directly Azure-Policy enforceable. 71 (52%) are process, contractual or
organisational controls that *no* Azure Policy can assert, and 21 are Microsoft's
responsibility under the shared responsibility model. Nearly seven controls in
ten are not policy-enforceable at all.

This service reproduces the expert's judgement. It runs **before** retrieval and
is shown **no policy candidates**, which is the whole point: a model handed a
ranked list of plausible-looking policies will attach one to almost anything.
Deciding the control's nature first, blind, removes that anchor. Retrieval then
runs only for controls that could plausibly be enforced, which also avoids
spending expansion and rerank calls on the ~69% that cannot.

The output is deliberately more than a label. ``reason`` must explain *why* a
policy can or cannot assert the control, and ``evidence_source`` must say what
satisfies it instead — that is what makes a "no policy" answer actionable rather
than an admission of failure.

Failure is non-fatal: any error returns an unknown classification, and the
deterministic ``coverage`` layer falls back to its keyword heuristics.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from pydantic import BaseModel, Field

from ..config import get_settings
from . import coverage

logger = logging.getLogger(__name__)
settings = get_settings()


CLASSIFICATION_SYSTEM_PROMPT = """You are a cloud compliance expert deciding how a control can be evidenced on Microsoft Azure. You are NOT selecting policies and you have not been shown any. Judge the control on its own terms.

Your primary decision is binary: **can any Azure or Entra configuration evidence part of this control (A/B), or is it a purely human, contractual or Microsoft-operated matter (C/D)?** Get that right first, then pick the finer label.

Assign exactly one coverage category:

**A_AzurePolicy** — Azure Policy built-in definitions can directly enforce or continuously audit this control today. The control names a concrete, machine-evaluable resource configuration: encryption at rest, TLS version, public network access, MFA on privileged roles, diagnostic settings, backup configuration, allowed regions. Pick this when you could describe the resource property a policy would evaluate.

**B_AzureConfig** — Azure or Microsoft Entra configuration covers a substantial part of the control, but full coverage needs configuration a policy cannot assert on its own: Conditional Access design, Entra entitlement management, Purview labelling schemes, network architecture decisions, or a policy that covers only one of several requirements the control states.

**C_Process** — a process, contractual, organisational or human control. Risk assessments, training, background checks, supplier contracts, incident response procedures, board oversight, documented policies, exercises and reviews. **No Azure Policy can assert these.** Evidence lives in the customer's GRC system, not in Azure. This is the largest category in real frameworks — roughly half of all controls — so do not strain to avoid it.

**D_MicrosoftAttestation** — Microsoft's responsibility under the shared responsibility model, which the customer **cannot configure at all**. Physical datacentre security, hypervisor and tenant isolation, Microsoft personnel vetting, hardware disposal, the platform's own certifications. The customer evidences these by citing Microsoft's audited attestations (ISO/IEC 27001, SOC 1/2/3, Service Trust Portal). If the customer has *any* knob to turn — a setting, a policy, a tenant configuration — it is not D.

Also decide:

- **responsibility** — "Customer" for anything the customer configures, operates or documents. "Microsoft" for D_MicrosoftAttestation controls. "Shared" only when both parties demonstrably act.

- **reason** — two or three sentences of substantive justification, in the register a compliance consultant would use in a report. For A/B, explain what makes the control *measurable* by Azure and what a policy would evaluate. For C/D, explain specifically why no Azure Policy can assert it — because the control governs human or contractual behaviour, or because the underlying system is Microsoft-operated. Never write a generic sentence that would fit any control; name what this control actually requires.

- **evidence_source** — what satisfies the control instead of, or alongside, a policy. For D, cite the attestation (e.g. "ISO/IEC 27001:2022 clause 9.2 audit programme; SOC 2 Type II report"). For C, name the GRC artefact (e.g. "Approved risk management framework and risk register with review minutes"). For A/B, name the Azure evidence (e.g. "Azure Policy compliance state; Defender for Cloud regulatory compliance dashboard"). Never leave this empty.

Decision discipline:
- Judge what the control *requires*, not the technology it mentions. "Maintain a documented cryptographic key management policy" is C_Process even though it says cryptographic; "keys must be stored in a managed HSM" is A_AzurePolicy.
- If a control requires both a documented process and a technical setting, classify by what it primarily obliges. Requiring only the process makes it C. If it also obliges the technical setting, it is A or B — the process part does not erase the enforceable part.
- **A versus B is provisional.** Retrieval, not you, establishes whether a built-in policy actually exists, and a later stage will settle the split. Do not agonise over it: if a concrete resource property is named, say A; if Azure covers the control only in part or mainly through Entra/tenant configuration, say B. Choosing either one keeps the control in scope for retrieval, so the costly mistake is putting an enforceable control in C or D, not picking the wrong one of A/B.
- Before answering C or D, ask explicitly: is there any Azure resource property, identity setting, or platform signal that would evidence even part of this control? If yes, the answer is A or B.

This wording is calibrated, not arbitrary. Measured against the NCSP v2.0 gold mapping, loosening the D definition to catch more Microsoft-operated controls raised D recall from 38% to 71% but pulled genuinely enforceable controls into D, so the controls wrongly excluded from retrieval doubled (7 to 15) and overall in-scope accuracy fell. Losing an enforceable control is unrecoverable — retrieval never runs for it — whereas mislabelling an attested control as "partial" still surfaces it for review, so the definition is deliberately tight."""


class ControlClassification(BaseModel):
    """A control's coverage category, ownership, and the reasoning behind them."""

    coverage_category: str = Field(
        default="",
        description="A_AzurePolicy, B_AzureConfig, C_Process or D_MicrosoftAttestation",
    )
    responsibility: str = Field(
        default="",
        description="Customer, Microsoft or Shared",
    )
    reason: str = Field(
        default="",
        description="Why this control is (or is not) assertable by Azure Policy",
    )
    evidence_source: str = Field(
        default="",
        description="What evidences the control: attestation, GRC artefact, or Azure signal",
    )

    @property
    def is_valid(self) -> bool:
        """True when the model returned a category we recognise."""
        return self.coverage_category in coverage.VALID_COVERAGE_CATEGORIES

    @property
    def may_have_policies(self) -> bool:
        """True when retrieval is worth running for this control.

        Only A and B controls can plausibly carry policy IDs, so C/D controls
        skip retrieval entirely — both to avoid anchoring the selection stage and
        because expansion plus rerank on ~69% of controls is wasted spend.
        """
        return self.coverage_category in (coverage.COVERAGE_A, coverage.COVERAGE_B)


def unknown_classification() -> ControlClassification:
    """A classification that asserts nothing, used when the stage is unavailable."""
    return ControlClassification()


class ControlClassificationService:
    """Classifies controls by how they can be covered, without seeing any policies."""

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

    async def classify(
        self,
        control_name: str,
        description: str,
        domain: str = "",
        control_type: Optional[str] = None,
    ) -> ControlClassification:
        """Classify a control's coverage category. Never raises.

        Args:
            control_name: The control's title.
            description: The control's requirement text.
            domain: Optional framework domain, useful context for the model.
            control_type: The extractor's guess at the control's nature. Passed as
                a *hint* only — it is a single upstream signal and must not be
                the sole determinant, which is the failure mode of the
                keyword-driven classifier this stage replaces.

        Returns:
            A :class:`ControlClassification`, or an empty one on failure.
        """
        if not settings.coverage_classification:
            return unknown_classification()

        control_text = " ".join(p for p in (control_name, description, domain) if p)
        if not control_text.strip():
            return unknown_classification()

        try:
            classification = await asyncio.to_thread(
                self._request_classification, control_text, control_type
            )
        except Exception as exc:  # noqa: BLE001 - classification is best-effort
            logger.warning(
                "Coverage classification failed (%s); falling back to the "
                "deterministic keyword classifier.", exc,
            )
            return unknown_classification()

        if not classification.is_valid:
            logger.warning(
                "Coverage classification returned an unrecognised category %r; "
                "ignoring it.", classification.coverage_category,
            )
            return unknown_classification()
        return classification

    def _request_classification(
        self, control_text: str, control_type: Optional[str]
    ) -> ControlClassification:
        """Blocking model call, run off the event loop by :meth:`classify`."""
        hint = (
            f"\n\nThe control extractor typed this control as '{control_type}'. "
            "Treat that as one weak signal; the control text is authoritative."
            if control_type else ""
        )
        user_prompt = (
            "Classify how this compliance control can be covered on Azure.\n\n"
            f"Control:\n{control_text}{hint}"
        )

        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ControlClassification,
            max_completion_tokens=settings.coverage_classification_max_tokens,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("model returned no parsed classification")
        return parsed


_service: Optional[ControlClassificationService] = None


def get_control_classification_service() -> ControlClassificationService:
    """Get the cached control classification service instance."""
    global _service
    if _service is None:
        _service = ControlClassificationService()
    return _service
