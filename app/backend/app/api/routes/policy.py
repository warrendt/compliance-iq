"""
Azure Policy generation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
import json
import uuid
from datetime import datetime, timezone

from app.models import PolicyGenerationRequest, PolicyGenerationResponse, ControlMapping
from app.services import get_policy_service
from app.services import version_service
from app.services import coverage
from app.services.jurisdiction_profile_service import get_jurisdiction_profile_service
from app.auth.azure_ad_auth import User, get_current_user
from app.db import cosmos_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/policy", tags=["policy"])


def _cosmos_ready() -> bool:
    """Check if Cosmos DB is initialized."""
    return bool(cosmos_client and cosmos_client.database)


def _file_stem(value: str) -> str:
    """Return a filesystem-safe artifact name while preserving readable labels."""
    stem = "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
    return stem.strip("_") or "initiative"


def _json_file(name: str, value: object) -> dict[str, str]:
    """Build a formatted JSON artifact file."""
    return {"name": name, "content": json.dumps(value, indent=2, default=str)}


def _deploy_readme(
    stem: str,
    framework_name: str,
    has_standard: bool,
    coverage_counts: Optional[dict] = None,
) -> dict[str, str]:
    """Build a README documenting deploy order and prerequisites for the bundle."""
    standard_line = (
        f"3. **Defender for Cloud standard** — `Deploy-{stem}DefenderStandard.ps1` "
        f"(or the `az rest` step in `deploy-{stem}-initiative.sh`) registers a "
        "`Microsoft.Security/securityStandards` resource so the initiative appears "
        "under **Defender for Cloud > Regulatory compliance**.\n"
        if has_standard
        else ""
    )
    prereq = (
        "\n## Prerequisite\n\n"
        "The Defender for Cloud custom standard requires the **Microsoft Defender CSPM** "
        "plan enabled on the target scope. Without it, the first two steps still work; "
        "only the Regulatory-compliance surfacing is unavailable.\n"
        if has_standard
        else ""
    )
    coverage_section = ""
    if coverage_counts:
        total = coverage_counts.get("total", 0)
        pct = coverage_counts.get("azure_enforceable_pct", 0.0)
        rows = [
            ("A — Azure Policy enforceable", coverage_counts.get("A_AzurePolicy", 0)),
            ("B — Azure configurable (no policy)", coverage_counts.get("B_AzureConfig", 0)),
            ("C — Process / legal / organisational", coverage_counts.get("C_Process", 0)),
            ("D — Microsoft-operated (attestation)", coverage_counts.get("D_MicrosoftAttestation", 0)),
        ]
        if coverage_counts.get("unclassified", 0):
            rows.append(("Unclassified (legacy)", coverage_counts["unclassified"]))
        table = "\n".join(f"| {label} | {count} |" for label, count in rows)
        coverage_section = (
            "\n## Coverage summary\n\n"
            f"Of {total} control(s), **{coverage_counts.get('A_AzurePolicy', 0)} "
            f"({pct}%)** are enforceable via Azure Policy and included in the "
            "initiative. The rest are not Azure-Policy enforceable and are listed "
            f"in `{stem}_manual_controls.csv` for manual attestation — they are "
            "**not** false-mapped to a catch-all policy.\n\n"
            "| Coverage category | Controls |\n"
            "| --- | --- |\n"
            f"{table}\n"
        )
    content = (
        f"# {framework_name} — deployment bundle\n\n"
        "Deploy the resources in this order (audit-only by default — nothing is "
        "enforced, blocked, created, or modified):\n\n"
        "1. **Policy set definition (initiative)** — creates the initiative from "
        f"`{stem}_initiative.json` / `.bicep`. Its metadata carries `\"ASC\":\"true\"`, "
        "the flag that onboards the initiative to **Defender for Cloud > Regulatory "
        "compliance** (controls surface 24-48h after the assignment below).\n"
        "2. **Assignment** — assigns the initiative with `DoNotEnforce` and a "
        "**system-assigned managed identity + location**. The identity is mandatory "
        "even in audit mode because Regulatory Compliance initiatives typically "
        "contain DeployIfNotExists / Modify policies, which Azure refuses to assign "
        "without one.\n"
        f"{standard_line}"
        f"{prereq}"
        f"{coverage_section}"
        "\n## Automatic exclusions\n\n"
        "Built-in policies that cannot live in a custom policy set are dropped during "
        "generation so the deploy does not fail:\n\n"
        "- **System Policy** built-ins (Azure rejects them from custom sets).\n"
        "- **Parameterized** built-ins with a required parameter that has no default "
        "value (e.g. vault name/region/workspace). ARM rejects the set definition "
        "with `MissingPolicyParameter` unless a value is supplied, and it cannot be "
        "invented safely. To include one, supply its required values on the Export "
        "Policy page (Deploy to Azure section) and re-generate — the values are baked "
        "into the initiative as literal reference parameters.\n\n"
        "See `excluded_builtin_policies` and `excluded_parameterized_policies` in the "
        "generation response for the counts.\n"
    )
    return {"name": "README.md", "content": content}


def _mcsb_version_payload(
    request: PolicyGenerationRequest,
    initiative_id: str,
    initiative_json: dict,
    bicep_template: str,
    scripts: dict,
    standard: Optional[dict] = None,
) -> dict:
    """Create a complete, immutable download bundle for an MCSB generation."""
    stem = _file_stem(request.framework_name)
    coverage_counts = coverage.coverage_summary(request.mappings)
    files = [
        _deploy_readme(
            stem, request.framework_name, standard is not None, coverage_counts
        ),
        _json_file(f"{stem}_initiative.json", initiative_json),
        {"name": f"{stem}_initiative.bicep", "content": bicep_template},
        {
            "name": f"Deploy-{stem}Initiative.ps1",
            "content": scripts["powershell"],
        },
        {
            "name": f"deploy-{stem}-initiative.sh",
            "content": scripts.get("cli", ""),
        },
        _json_file(
            f"{stem}_mappings.json",
            [mapping.model_dump(mode="json") for mapping in request.mappings],
        ),
        {
            "name": f"{stem}_manual_controls.csv",
            "content": coverage.manual_controls_csv(request.mappings),
        },
    ]
    if standard:
        files.extend(
            [
                {
                    "name": f"{stem}_defender_standard.json",
                    "content": standard["arm_template"],
                },
                {
                    "name": f"Deploy-{stem}DefenderStandard.ps1",
                    "content": standard["powershell"],
                },
            ]
        )
    return {
        "artifact_type": "mcsb_initiative",
        "framework_name": request.framework_name,
        "initiative_id": initiative_id,
        "files": files,
        "omitted_files": [],
    }


def _slz_version_payload(
    framework_name: str,
    archetypes: dict,
    allowed_locations: Optional[List[str]],
) -> dict:
    """Create a complete, immutable download bundle for an SLZ generation."""
    artifact_map = archetypes.get("archetype_artifacts", archetypes)
    files: list[dict[str, str]] = []

    for archetype_name, artifact in sorted(artifact_map.items()):
        stem = _file_stem(f"slz_{archetype_name}")
        scripts = artifact.get("deployment_scripts") or artifact.get("scripts") or {}
        files.extend(
            [
                _json_file(f"{stem}_initiative.json", artifact.get("initiative_json", {})),
                {
                    "name": f"{stem}_initiative.bicep",
                    "content": artifact.get("bicep_template", artifact.get("bicep", "")),
                },
                {"name": f"deploy_{stem}.sh", "content": scripts.get("cli", "")},
                {"name": f"Deploy-{stem}.ps1", "content": scripts.get("powershell", "")},
            ]
        )

    files.append(
        _json_file(
            "slz_sovereignty_manifest.json",
            archetypes.get("summary", {}),
        )
    )

    return {
        "artifact_type": "slz_initiative",
        "framework_name": framework_name,
        "allowed_locations": allowed_locations or [],
        "files": files,
        "omitted_files": [],
    }


async def _persist_artifact(artifact: dict) -> Optional[str]:
    """Persist a generated artifact to Cosmos DB. Returns artifact_id or None."""
    if not _cosmos_ready():
        return None
    try:
        await cosmos_client.upsert_document(
            cosmos_client.GENERATED_ARTIFACTS,
            artifact,
        )
        logger.info("artifact_persisted", extra={"artifact_id": artifact["id"]})
        return artifact["id"]
    except Exception as exc:
        logger.warning(f"Failed to persist artifact: {exc}")
        return None


@router.post("/generate")
async def generate_policy_initiative(request: PolicyGenerationRequest,
                                      http_request: Request,
                                      user: User = Depends(get_current_user)):
    """
    Generate Azure Policy initiative from control mappings.

    Returns an enriched response including the initiative JSON in Azure
    format, a Bicep template, and PowerShell / CLI deployment scripts.
    Artifacts are persisted to Cosmos DB when available.
    """
    logger.info(f"Generating policy initiative for {request.framework_name}")

    try:
        policy_service = get_policy_service()
        response = policy_service.generate_initiative(request)

        logger.info(
            f"Generated initiative with {response.included_policies} policies"
        )

        # Build enriched response with all artifacts the frontend needs
        initiative_name = request.framework_name.replace(" ", "_").lower()
        initiative_json = response.initiative.to_azure_json()
        bicep_template = policy_service.export_as_bicep(
            response.initiative, initiative_name
        )
        scripts = policy_service.generate_deployment_script(
            response.initiative, initiative_name, enforce_mode=request.enforce_mode
        )
        standard = policy_service.generate_security_standard(
            response.initiative, initiative_name
        )

        result = response.model_dump()
        result["initiative_id"] = f"{initiative_name}-compliance"
        result["initiative_json"] = initiative_json
        result["bicep_template"] = bicep_template
        result["powershell_script"] = scripts["powershell"]
        result["cli_script"] = scripts.get("cli", "")
        result["defender_standard_name"] = standard["standard_name"]
        result["defender_standard_template"] = standard["arm_template"]
        result["defender_standard_script"] = standard["powershell"]

        version = await version_service.create_version(
            user_id=user.email,
            artifact_payload=_mcsb_version_payload(
                request=request,
                initiative_id=result["initiative_id"],
                initiative_json=initiative_json,
                bicep_template=bicep_template,
                scripts=scripts,
                standard=standard,
            ),
            metadata={
                "source": "mcsb_initiative",
                "framework_name": request.framework_name,
                "policy_name": request.framework_name,
                "mappings_count": len(request.mappings),
                "included_policies": response.included_policies,
                "enforce_mode": request.enforce_mode,
            },
        )
        result["version_id"] = version["id"]
        result["version_number"] = version["version_number"]
        result["semantic_version"] = version["semantic_version"]

        # Persist to Cosmos DB
        session_id = http_request.headers.get("X-Session-ID", "anonymous")
        artifact_id = str(uuid.uuid4())
        artifact_doc = {
            "id": artifact_id,
            "session_id": session_id,
            "type": "mcsb_initiative",
            "framework_name": request.framework_name,
            "initiative_id": result["initiative_id"],
            "initiative_json": initiative_json,
            "bicep_template": bicep_template,
            "powershell_script": scripts["powershell"],
            "cli_script": scripts.get("cli", ""),
            "defender_standard_name": standard["standard_name"],
            "defender_standard_template": standard["arm_template"],
            "defender_standard_script": standard["powershell"],
            "enforce_mode": request.enforce_mode,
            "mappings_count": len(request.mappings),
            "included_policies": response.included_policies,
            "excluded_policies": response.excluded_policies,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        persisted_id = await _persist_artifact(artifact_doc)
        if persisted_id:
            result["artifact_id"] = persisted_id

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate policy initiative: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/json")
async def generate_policy_json(
    request: PolicyGenerationRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
):
    """
    Generate Azure Policy initiative and return as JSON file.

    Returns:
        JSON file download with initiative definition
    """
    logger.info(f"Generating policy JSON for {request.framework_name}")

    try:
        result = await generate_policy_initiative(request, http_request, user)
        json_content = json.dumps(result["initiative_json"], indent=2)

        # Create filename
        filename = f"{request.framework_name.replace(' ', '_')}_initiative.json"

        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate policy JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/bicep")
async def generate_policy_bicep(
    request: PolicyGenerationRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
):
    """
    Generate Azure Policy initiative as Bicep template.

    Returns:
        Bicep template file download
    """
    logger.info(f"Generating Bicep template for {request.framework_name}")

    try:
        result = await generate_policy_initiative(request, http_request, user)
        bicep_content = result["bicep_template"]

        # Create filename
        filename = f"{_file_stem(request.framework_name)}_initiative.bicep"

        return Response(
            content=bicep_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate Bicep template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/scripts")
async def generate_deployment_scripts(
    request: PolicyGenerationRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
):
    """
    Generate deployment scripts (Azure CLI and PowerShell).

    Returns:
        Dictionary with CLI and PowerShell scripts
    """
    logger.info(f"Generating deployment scripts for {request.framework_name}")

    try:
        result = await generate_policy_initiative(request, http_request, user)

        return {
            "initiative_name": result["initiative_id"],
            "cli_script": result["cli_script"],
            "powershell_script": result["powershell_script"],
            "version_id": result["version_id"],
            "version_number": result["version_number"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate deployment scripts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- SLZ Initiative Generation ---

class SLZGenerationRequest(BaseModel):
    """Request to generate SLZ-specific policy initiatives per archetype."""
    framework_name: str = Field(..., description="Compliance framework name")
    mappings: List[ControlMapping] = Field(..., description="Control mappings with sovereignty data")
    allowed_locations: Optional[List[str]] = Field(
        default=None,
        description="Confirmed Azure regions for data residency",
    )
    country_or_region: Optional[str] = Field(
        default=None,
        description="Jurisdiction detected from the source document and confirmed by the operator",
    )
    jurisdiction_profile: Optional[dict] = Field(
        default=None,
        description="Source-backed regional recommendation selected or overridden by the operator",
    )
    resolution_choices: List[dict] = Field(
        default_factory=list,
        description="Recorded sovereignty policy, configuration, evidence, or exception choices",
    )


@router.get("/jurisdiction-profile")
async def get_jurisdiction_profile(
    country_or_region: str = Query(..., min_length=1, max_length=200),
):
    """Return a source-backed regional recommendation for a scanned jurisdiction."""
    return get_jurisdiction_profile_service().recommend(country_or_region)


@router.post("/generate/slz")
async def generate_slz_initiatives(request: SLZGenerationRequest,
                                    http_request: Request,
                                    user: User = Depends(get_current_user)):
    """
    Generate Sovereign Landing Zone policy initiatives per archetype.

    Produces per-archetype artifacts (JSON initiative, Bicep template,
    deployment scripts) based on sovereignty mappings in each control.

    Returns:
        Dictionary keyed by archetype with JSON, Bicep, CLI, and PS artifacts
    """
    logger.info(
        f"Generating SLZ initiatives for {request.framework_name} "
        f"({len(request.mappings)} mappings)"
    )

    try:
        policy_service = get_policy_service()

        # Filter to mappings that have sovereignty data
        sov_mappings = [m for m in request.mappings if m.sovereignty is not None]
        if not sov_mappings:
            raise HTTPException(
                status_code=400,
                detail="No mappings contain sovereignty data. Run AI mapping first."
            )

        result = policy_service.generate_slz_initiatives(
            mappings=sov_mappings,
            framework_name=request.framework_name,
            allowed_locations=request.allowed_locations,
            country_or_region=request.country_or_region,
            jurisdiction_profile=request.jurisdiction_profile,
            resolution_choices=request.resolution_choices,
        )

        response_data = {
            "framework_name": request.framework_name,
            "total_mappings": len(request.mappings),
            "sovereignty_mappings": len(sov_mappings),
            "archetypes": result,
            "manual_controls": coverage.manual_register_rows(request.mappings),
            "coverage_summary": coverage.coverage_summary(request.mappings),
        }

        version = await version_service.create_version(
            user_id=user.email,
            artifact_payload=_slz_version_payload(
                framework_name=request.framework_name,
                archetypes=result,
                allowed_locations=request.allowed_locations,
            ),
            metadata={
                "source": "slz_initiative",
                "framework_name": request.framework_name,
                "policy_name": f"{request.framework_name} SLZ",
                "mappings_count": len(request.mappings),
                "sovereignty_mappings_count": len(sov_mappings),
                "archetype_count": len(
                    result.get("archetype_artifacts", result)
                ),
                "country_or_region": request.country_or_region,
                "sovereignty_coverage_state": (
                    result.get("summary", {}).get("sovereignty_coverage_state")
                ),
            },
        )
        response_data["version_id"] = version["id"]
        response_data["version_number"] = version["version_number"]
        response_data["semantic_version"] = version["semantic_version"]

        # Persist to Cosmos DB
        session_id = http_request.headers.get("X-Session-ID", "anonymous")
        artifact_id = str(uuid.uuid4())
        artifact_doc = {
            "id": artifact_id,
            "session_id": session_id,
            "type": "slz_initiative",
            "framework_name": request.framework_name,
            "archetypes": result,
            "mappings_count": len(request.mappings),
            "sovereignty_mappings_count": len(sov_mappings),
            "country_or_region": request.country_or_region,
            "jurisdiction_profile": request.jurisdiction_profile or {},
            "resolution_choices": request.resolution_choices,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        persisted_id = await _persist_artifact(artifact_doc)
        if persisted_id:
            response_data["artifact_id"] = persisted_id

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate SLZ initiatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Artifact Retrieval ---


@router.get("/artifacts")
async def list_artifacts(
    http_request: Request,
    artifact_type: str = Query(None, description="Filter by type (mcsb_initiative, slz_initiative)"),
    limit: int = Query(20, ge=1, le=100),
):
    """List recently generated policy artifacts for the current session."""
    if not _cosmos_ready():
        return {"artifacts": [], "total": 0}

    session_id = http_request.headers.get("X-Session-ID", "anonymous")
    query = "SELECT c.id, c.type, c.framework_name, c.initiative_id, c.mappings_count, c.included_policies, c.created_at FROM c WHERE c.session_id = @sid"
    params: list[dict] = [{"name": "@sid", "value": session_id}]

    if artifact_type:
        query += " AND c.type = @atype"
        params.append({"name": "@atype", "value": artifact_type})

    query += " ORDER BY c.created_at DESC OFFSET 0 LIMIT @lim"
    params.append({"name": "@lim", "value": limit})

    try:
        items = await cosmos_client.query_documents(
            cosmos_client.GENERATED_ARTIFACTS, query, params, session_id
        )
        return {"artifacts": items, "total": len(items)}
    except Exception as e:
        logger.warning(f"Failed to list artifacts: {e}")
        return {"artifacts": [], "total": 0}


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, http_request: Request):
    """Retrieve a single generated policy artifact by ID."""
    if not _cosmos_ready():
        raise HTTPException(status_code=503, detail="Cosmos DB not available")

    session_id = http_request.headers.get("X-Session-ID", "anonymous")
    try:
        doc = await cosmos_client.get_document(
            cosmos_client.GENERATED_ARTIFACTS, artifact_id, session_id
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve artifact {artifact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Policy Details (cached lookup) ---

class PolicyDetailsRequest(BaseModel):
    """Request to look up Azure Policy details by GUID."""
    policy_ids: List[str] = Field(
        ...,
        description="List of Azure Policy definition GUIDs",
        min_length=1,
        max_length=100,
    )


@router.post("/details")
async def get_policy_details(request: PolicyDetailsRequest):
    """
    Batch-lookup Azure Policy details by GUID.

    Returns cached results from Cosmos DB with Microsoft Learn fallback.
    """
    from app.services.policy_cache_service import get_policy_cache_service

    logger.info(f"Looking up {len(request.policy_ids)} policy details")

    try:
        cache_service = get_policy_cache_service()
        details = await cache_service.get_policy_details(request.policy_ids)

        return {
            "requested": len(request.policy_ids),
            "found": len(details),
            "policies": details,
        }

    except Exception as e:
        logger.error(f"Failed to look up policy details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Azure Policy catalog (retrieval corpus) ---


@router.get("/catalog/status")
async def policy_catalog_status():
    """Return the size and source of the Azure Policy retrieval catalog."""
    from app.services import get_policy_catalog_service

    catalog = get_policy_catalog_service()
    return {"count": catalog.count, "source": catalog.source}


@router.post("/catalog/refresh")
async def refresh_policy_catalog(
    subscription: Optional[str] = Query(None, description="Subscription to query"),
    user: User = Depends(get_current_user),
):
    """Refresh the Azure Policy catalog from ARM using the backend identity.

    Best-effort: requires the backend managed identity to have Reader on a
    subscription. Falls back to the shipped snapshot (unchanged) on failure.
    """
    from app.services import get_policy_catalog_service

    catalog = get_policy_catalog_service()
    try:
        count = await catalog.refresh_from_arm(subscription=subscription)
        return {"status": "refreshed", "count": count, "source": catalog.source}
    except Exception as e:
        logger.error(f"Policy catalog refresh failed: {e}")
        raise HTTPException(status_code=502, detail=f"Catalog refresh failed: {e}")
