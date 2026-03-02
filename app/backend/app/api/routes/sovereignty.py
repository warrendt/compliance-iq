"""
Sovereign Landing Zone (SLZ) policy endpoints.
Provides access to sovereignty control objectives, policies, archetypes,
and an admin sync endpoint.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging
import subprocess
import sys
from pathlib import Path

from app.services import get_sovereignty_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sovereignty", tags=["sovereignty"])


@router.get("/summary")
async def get_sovereignty_summary():
    """
    Get a high-level summary of loaded SLZ data.

    Returns counts of policies, initiatives, archetypes, and objectives,
    plus breakdowns by level and service category.
    """
    try:
        service = get_sovereignty_service()
        return service.get_summary()
    except Exception as e:
        logger.error(f"Failed to get sovereignty summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/levels")
async def get_sovereignty_levels():
    """
    Get sovereignty level descriptions (L1, L2, L3).

    Returns:
        List of sovereignty levels with descriptions and scope.
    """
    return {
        "levels": [
            {
                "level": "L1",
                "name": "Global",
                "description": "Data locality + in-transit encryption + Trusted Launch",
                "objectives": ["SO-1", "SO-5"],
                "archetype": "sovereign_root",
            },
            {
                "level": "L2",
                "name": "CMK (Customer-Managed Keys)",
                "description": "All L1 controls + encryption at rest with customer-managed keys",
                "objectives": ["SO-1", "SO-3", "SO-5"],
                "archetype": "sovereign_root",
            },
            {
                "level": "L3",
                "name": "Confidential Computing",
                "description": "All L1+L2 controls + encryption in-use via confidential computing",
                "objectives": ["SO-1", "SO-3", "SO-4", "SO-5"],
                "archetype": "confidential_corp",
            },
        ]
    }


@router.get("/objectives")
async def get_sovereignty_objectives():
    """
    Get all five Sovereignty Control Objectives (SO-1 through SO-5).

    Returns:
        Dictionary of objectives with associated policies.
    """
    try:
        service = get_sovereignty_service()
        objectives = service.get_all_objectives()

        result = []
        for obj_id, obj in objectives.items():
            policies = service.get_policies_by_objective(obj_id)
            result.append({
                "id": obj.id,
                "name": obj.name,
                "description": obj.description,
                "applicable_levels": obj.applicable_levels,
                "procedural_only": obj.procedural_only,
                "policy_count": len(policies),
                "policies": [
                    {"name": p.name, "display_name": p.display_name, "effect": p.effect}
                    for p in policies
                ],
            })

        return {"objectives": result, "count": len(result)}

    except Exception as e:
        logger.error(f"Failed to get sovereignty objectives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies")
async def get_sovereignty_policies(
    level: Optional[str] = Query(None, description="Filter by sovereignty level (L1, L2, L3)"),
    service_category: Optional[str] = Query(None, alias="service", description="Filter by Azure service category"),
    objective: Optional[str] = Query(None, description="Filter by sovereignty objective (SO-1 through SO-5)"),
    q: Optional[str] = Query(None, description="Full-text search query"),
):
    """
    Get SLZ policies with optional filters.

    Example:
        GET /sovereignty/policies?level=L2&service=Storage
        GET /sovereignty/policies?objective=SO-3
        GET /sovereignty/policies?q=customer-managed+key
    """
    try:
        svc = get_sovereignty_service()

        if q:
            policies = svc.search_policies(q)
        elif objective:
            policies = svc.get_policies_by_objective(objective)
        elif level:
            policies = svc.get_policies_by_level(level)
        elif service_category:
            policies = svc.get_policies_by_service(service_category)
        else:
            policies = svc.get_all_policies()

        # Apply additional filters on combined results
        if level and not q:
            valid_levels = {"L1": {"L1"}, "L2": {"L1", "L2"}, "L3": {"L1", "L2", "L3"}}
            allowed = valid_levels.get(level, {level})
            policies = [p for p in policies if p.sovereignty_level in allowed]

        if service_category and not q:
            policies = [p for p in policies if service_category.lower() in p.service_category.lower()]

        return {
            "policies": [p.model_dump() for p in policies],
            "count": len(policies),
            "filters": {
                "level": level,
                "service": service_category,
                "objective": objective,
                "query": q,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get sovereignty policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/archetypes")
async def get_sovereignty_archetypes():
    """
    Get all SLZ management group archetypes.

    Returns the four archetypes (sovereign_root, confidential_corp,
    confidential_online, public) with their policy assignments.
    """
    try:
        svc = get_sovereignty_service()
        archetypes = svc.get_all_archetypes()

        result = []
        for arch in archetypes:
            assignments = svc.get_archetype_assignments(arch.name)
            result.append({
                **arch.model_dump(),
                "assignment_details": [a.model_dump() for a in assignments],
            })

        return {"archetypes": result, "count": len(result)}

    except Exception as e:
        logger.error(f"Failed to get archetypes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/initiatives")
async def get_sovereignty_initiatives():
    """
    Get all SLZ initiatives including built-in Sovereignty Baselines.
    """
    try:
        svc = get_sovereignty_service()
        initiatives = svc.get_all_initiatives()
        built_in = svc.get_built_in_initiatives()

        return {
            "initiatives": [i.model_dump() for i in initiatives],
            "built_in_initiatives": built_in,
            "total_count": len(initiatives) + len(built_in),
        }

    except Exception as e:
        logger.error(f"Failed to get initiatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/sync-slz")
async def sync_slz_policies(fallback: bool = Query(False, description="Use fallback data instead of cloning repo")):
    """
    Re-sync SLZ policy data from Azure-Landing-Zones-Library.

    Args:
        fallback: If True, generate data from known built-in policies without cloning.

    Returns:
        Summary of sync results.
    """
    try:
        scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
        cmd = [sys.executable, "-m", "scripts.sync_slz_policies"]
        if fallback:
            cmd.append("--fallback")

        logger.info(f"Running SLZ sync: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=str(scripts_dir.parent),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.error(f"Sync failed: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Sync failed: {result.stderr}")

        # Reload the service
        from app.services.sovereignty_service import get_sovereignty_service
        # Clear the lru_cache
        get_sovereignty_service.cache_clear()
        svc = get_sovereignty_service()

        return {
            "status": "success",
            "message": "SLZ policies synced successfully",
            "summary": svc.get_summary(),
            "output": result.stdout[-500:] if result.stdout else "",
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Sync timed out after 120 seconds")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
