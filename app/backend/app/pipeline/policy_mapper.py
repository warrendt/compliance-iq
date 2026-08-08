"""
Azure Policy mapping for the PDF pipeline.

This module used to carry its own prompt with a hand-written menu of 34 policy
GUIDs, of which 6 did not exist. Against a catalog of ~2,467 shipped definitions
that is an effective reach of **1.38%**, and it asked the model to recall GUIDs
from memory - the exact failure the manual process budgets 1-2 hours of GUID
validation to catch.

There is nothing to fix in that prompt. The services path already does this
properly: retrieval over the whole catalog, blind classification into the
coverage taxonomy, validation of every identifier against the catalog, and
explicit reporting of anything it cannot ground. So this module now does no
model work of its own. It converts the pipeline's types, delegates to
``AIMappingService``, and converts back.

One engine, one taxonomy, both entry points.
"""

import asyncio
import logging
import threading
from typing import Any, Optional

from .models import (
    ExtractedControl,
    ControlExtractionResult,
    ControlPolicyMapping,
    AzurePolicyMapping,
)
from .config import PipelineConfig

logger = logging.getLogger(__name__)


# -- Loop safety --------------------------------------------------------------

def _run_coroutine(coro):
    """Run a coroutine from a synchronous caller, whatever the caller is.

    This function has two callers with opposite properties. ``pipeline.py``
    calls it from a background task with no running loop, where ``asyncio.run``
    is correct. ``comparison.py`` calls it inside ``asyncio.to_thread`` from a
    live request, and although that worker thread has no loop of its own today,
    assuming so is exactly the kind of assumption that turns into an
    intermittent "this event loop is already running" months later.

    So: use the current thread when it is free, and otherwise hand the
    coroutine to a thread that is.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}

    def _worker():
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:  # re-raised on the calling thread
            result["error"] = exc

    thread = threading.Thread(target=_worker, name="policy-mapper", daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result["value"]


# -- Type conversion ----------------------------------------------------------

def _to_external_control(control: ExtractedControl):
    """Pipeline ``ExtractedControl`` -> services ``ExternalControl``."""
    from app.models.control import ExternalControl

    return ExternalControl(
        control_id=control.control_id,
        control_name=control.control_title,
        description=control.control_description,
        domain=control.domain,
        control_type=control.control_type,
        requirements="; ".join(control.sub_controls) if control.sub_controls else None,
    )


def _policy_entries(policy_ids: list[str], catalog) -> list[AzurePolicyMapping]:
    """Resolve names and descriptions from the catalog, never from the model.

    ``ControlMapping`` carries validated GUIDs only. The display name and
    description are catalog facts, so asking a model to supply them can only
    introduce error - which is how the old prompt produced policy names
    describing something the GUID did not do.

    Relevance is deliberately reported as ``high``: these identifiers already
    survived retrieval, reranking and catalog validation. A second, ungrounded
    judgement here would add noise, not information.
    """
    entries: list[AzurePolicyMapping] = []
    for policy_id in policy_ids:
        definition = catalog.get(policy_id) if catalog else None
        entries.append(
            AzurePolicyMapping(
                policy_definition_id=policy_id,
                policy_name=(definition or {}).get("display_name") or policy_id,
                policy_description=(definition or {}).get("description") or "",
                relevance="high",
            )
        )
    return entries


def _placeholder(control: ExtractedControl, reason: str) -> ControlPolicyMapping:
    """A control the engine could not map, said out loud.

    Dropping it would shorten the output and make the run look cleaner while
    quietly removing a control the customer is legally bound by. It is carried
    through with zero confidence and a coverage gap so it appears in the
    register and the deployment guide.
    """
    return ControlPolicyMapping(
        control_id=control.control_id,
        control_title=control.control_title,
        domain=control.domain,
        mcsb_control_id="",
        mcsb_control_name="",
        confidence_score=0.0,
        mapping_rationale=reason,
        azure_policies=[],
        defender_recommendations=[],
        is_automatable=False,
        manual_attestation_note=reason,
        coverage_gap=True,
        coverage_reason=reason,
        azure_enforceable=False,
    )


def _to_pipeline_mapping(
    mapping,
    control: Optional[ExtractedControl],
    catalog,
) -> ControlPolicyMapping:
    """Services ``ControlMapping`` -> pipeline ``ControlPolicyMapping``."""
    from app.services import coverage as coverage_module

    policies = _policy_entries(list(mapping.azure_policy_ids or []), catalog)
    category = getattr(mapping, "coverage_category", None)

    manual_note = None
    if category in (coverage_module.COVERAGE_C, coverage_module.COVERAGE_D):
        manual_note = mapping.coverage_reason or mapping.reasoning
    elif getattr(mapping, "outside_step", None):
        manual_note = (
            f"Partial Azure coverage; complete it with: {mapping.outside_step}"
        )

    return ControlPolicyMapping(
        control_id=mapping.external_control_id,
        control_title=mapping.external_control_name,
        domain=(control.domain if control else None) or mapping.mcsb_domain or "",
        mcsb_control_id=mapping.mcsb_control_id or "",
        mcsb_control_name=mapping.mcsb_control_name or "",
        confidence_score=mapping.confidence_score,
        mapping_rationale=mapping.reasoning,
        azure_policies=policies,
        defender_recommendations=list(mapping.defender_recommendations or []),
        # "Automatable" here means what the taxonomy means by it: mapped to
        # Azure. It is derived from the category rather than asked of the model.
        is_automatable=bool(getattr(mapping, "azure_enforceable", False)),
        manual_attestation_note=manual_note,
        coverage_category=category,
        coverage_display=getattr(mapping, "coverage_display", None),
        coverage_reason=getattr(mapping, "coverage_reason", None),
        azure_enforceable=bool(getattr(mapping, "azure_enforceable", False)),
        coverage_gap=bool(getattr(mapping, "coverage_gap", False)),
        outside_step=getattr(mapping, "outside_step", None),
        responsibility=getattr(mapping, "responsibility", None),
        enforcement_plane=getattr(mapping, "enforcement_plane", None),
        policy_effects=list(getattr(mapping, "policy_effects", None) or []),
        available_effects=list(getattr(mapping, "available_effects", None) or []),
        policy_type=getattr(mapping, "policy_type", None),
        evidence_source=getattr(mapping, "evidence_source", None),
        attestation=getattr(mapping, "attestation", None),
        attestation_gap=bool(getattr(mapping, "attestation_gap", False)),
        dropped_policy_ids=list(getattr(mapping, "dropped_policy_ids", None) or []),
    )


# -- Entry point --------------------------------------------------------------

def map_controls_to_azure_policies(
    extraction: ControlExtractionResult,
    config: PipelineConfig,
    progress_callback=None,
) -> list[ControlPolicyMapping]:
    """Map extracted controls to Azure Policy definitions.

    Delegates to ``AIMappingService``, so the pipeline reaches the whole policy
    catalog and produces the same coverage taxonomy, attestation citations and
    gap reporting as the services path.

    Args:
        extraction: Controls extracted from the PDF.
        config: Pipeline configuration; ``batch_size`` is reused as the mapping
            concurrency, since mapping is now per-control rather than batched.
        progress_callback: Optional ``callable(current, total)``.

    Returns:
        One ``ControlPolicyMapping`` per extracted control, in the order the
        controls were extracted. Controls the engine could not map are returned
        as explicit gaps rather than omitted.
    """
    from app.services.ai_mapping_service import get_ai_mapping_service
    from app.services.policy_catalog_service import get_policy_catalog_service

    controls = list(extraction.controls)
    if not controls:
        logger.info("No controls to map")
        return []

    service = get_ai_mapping_service()
    catalog = get_policy_catalog_service()

    # Retrieval reads the full catalog, so a missing snapshot means every
    # mapping comes back empty and is reported as a gap. That is honest but
    # useless; say why instead.
    if not catalog.available():
        raise RuntimeError(
            "The Azure Policy catalog is unavailable, so controls cannot be "
            "mapped. Regenerate the snapshot with "
            "scripts/generate_policy_catalog.py."
        )

    logger.info(
        "Mapping %d control(s) against %d catalog definition(s)",
        len(controls),
        catalog.count(),
    )

    external = [_to_external_control(control) for control in controls]
    concurrency = max(1, getattr(config, "batch_size", 1) or 1)

    batch = _run_coroutine(
        service.map_controls_batch(
            external,
            progress_callback=progress_callback,
            concurrency=concurrency,
        )
    )

    by_id = {m.external_control_id: m for m in batch.mappings}
    results: list[ControlPolicyMapping] = []
    for control in controls:
        mapping = by_id.get(control.control_id)
        if mapping is None:
            results.append(
                _placeholder(
                    control,
                    "The mapping engine could not process this control. It is "
                    "reported here rather than omitted; map it manually or "
                    "re-run.",
                )
            )
            continue
        results.append(_to_pipeline_mapping(mapping, control, catalog))

    enforceable = sum(1 for m in results if m.azure_enforceable)
    gaps = sum(1 for m in results if m.coverage_gap)
    logger.info(
        "Mapped %d control(s): %d Azure-enforceable, %d gap(s)",
        len(results),
        enforceable,
        gaps,
    )
    return results
