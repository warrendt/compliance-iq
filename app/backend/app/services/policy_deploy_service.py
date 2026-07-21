"""
Deploy Azure Policy definitions, initiatives, and assignments using the
caller's delegated Entra ID access token (on-behalf-of flow).

The service proxies ARM REST calls so the frontend never talks to ARM directly.
"""

import asyncio
import logging
from typing import Any

import httpx

from app.services.policy_service import _is_valid_policy_guid

logger = logging.getLogger(__name__)

_ARM_BASE = "https://management.azure.com"
_API_VERSION_POLICY = "2023-04-01"
# Policy Insights on-demand evaluation (maps to `az policy state trigger-scan`).
_API_VERSION_POLICY_INSIGHTS = "2019-10-01"
_MGMT_GROUP_PREFIX = "/providers/microsoft.management/managementgroups/"
_TIMEOUT = 30.0

# Characters ARM rejects in a policy set definition name.
_INVALID_NAME_CHARS = set('<>*%&:\\?/#')
# Bound on how many referenced policy definitions we resolve during validation,
# and how many of those reads run concurrently.
_MAX_REFERENCE_CHECKS = 200
_REFERENCE_CONCURRENCY = 8


def _build_assignment_body(
    *,
    policy_set_definition_id: str,
    display_name: str,
    description: str = "",
    enforce_mode: bool = False,
    location: str = "eastus",
) -> dict[str, Any]:
    """Build the ARM policy-assignment request body.

    Always attaches a system-assigned identity + ``location`` because they are
    mandatory when the initiative contains ``DeployIfNotExists``/``Modify``
    policies (ARM 400s otherwise, even under ``DoNotEnforce``) and are harmless
    for audit-only initiatives. ``enforce_mode`` False (default) yields
    ``DoNotEnforce`` so effects are never applied while compliance is still
    assessed.
    """
    return {
        "location": location,
        "identity": {"type": "SystemAssigned"},
        "properties": {
            "policyDefinitionId": policy_set_definition_id,
            "displayName": display_name,
            "description": description,
            "enforcementMode": "Default" if enforce_mode else "DoNotEnforce",
        },
    }


def _scan_supported_scope(scope: str) -> str | None:
    """Return the scope to trigger an on-demand compliance scan on, or None.

    Azure Policy Insights ``triggerEvaluation`` only supports **subscription**
    and **resource-group** scopes — management groups are not supported. Given
    an arbitrary ARM scope this returns the resource-group scope when the input
    names one, otherwise the subscription scope, or ``None`` when no supported
    scan scope can be derived (e.g. a management-group scope).
    """
    s = (scope or "").strip().rstrip("/")
    if not s or s.lower().startswith(_MGMT_GROUP_PREFIX):
        return None
    parts = [p for p in s.split("/") if p]
    if len(parts) >= 2 and parts[0].lower() == "subscriptions":
        sub = f"/subscriptions/{parts[1]}"
        if len(parts) >= 4 and parts[2].lower() == "resourcegroups":
            return f"{sub}/resourceGroups/{parts[3]}"
        return sub
    return None


class PolicyDeployService:
    """Thin wrapper around Azure Resource Manager policy APIs."""

    def __init__(self, access_token: str):
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Scope helpers
    # ------------------------------------------------------------------

    async def list_subscriptions(self) -> list[dict[str, Any]]:
        """Return subscriptions visible to the caller."""
        url = f"{_ARM_BASE}/subscriptions?api-version=2022-12-01"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json().get("value", [])

    async def list_management_groups(self) -> list[dict[str, Any]]:
        """Return management groups visible to the caller."""
        url = f"{_ARM_BASE}/providers/Microsoft.Management/managementGroups?api-version=2021-04-01"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json().get("value", [])

    # ------------------------------------------------------------------
    # Validate (non-destructive)
    # ------------------------------------------------------------------

    async def validate_initiative(
        self,
        scope: str,
        initiative_name: str,
        body: dict[str, Any],
        *,
        check_references: bool = True,
    ) -> dict[str, Any]:
        """Validate an initiative definition WITHOUT writing to the tenant.

        This performs structural validation of the policy set definition body
        (the same rules ARM enforces on a PUT) and, when ``check_references`` is
        set, verifies each referenced policy definition resolves via a read-only
        GET. Nothing is created or modified — unlike a PUT, this is safe to run
        as a dry run.

        Returns a structured result::

            {
                "valid": bool,
                "errors": [str, ...],
                "warnings": [str, ...],
                "summary": {
                    "policy_count": int,
                    "unique_policy_count": int,
                    "group_count": int,
                    "references_checked": int,
                    "unresolved_references": int,
                },
            }
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Accept either the ARM resource wrapper ({"properties": {...}}) or a
        # bare properties object.
        if isinstance(body, dict) and isinstance(body.get("properties"), dict):
            props = body["properties"]
        elif isinstance(body, dict) and "policyDefinitions" in body:
            props = body
        else:
            props = {}
            errors.append("Initiative body is missing a 'properties' object.")

        # --- Initiative name ---
        if not initiative_name or len(initiative_name) > 128:
            errors.append("Initiative name must be 1–128 characters.")
        elif _INVALID_NAME_CHARS.intersection(initiative_name) or initiative_name[-1] in " .":
            errors.append(
                "Initiative name contains characters ARM does not allow "
                "(no <>*%&:\\?/# and it may not end with a space or period)."
            )

        if not props.get("displayName"):
            warnings.append("Initiative has no displayName.")

        # --- Groups ---
        raw_groups = props.get("policyDefinitionGroups") or []
        group_names: set[str] = set()
        for group in raw_groups:
            name = group.get("name") if isinstance(group, dict) else None
            if not name:
                errors.append("A policyDefinitionGroups entry is missing 'name'.")
            elif name in group_names:
                errors.append(f"Duplicate policyDefinitionGroups name: '{name}'.")
            else:
                group_names.add(name)

        # --- Policy definitions ---
        definitions = props.get("policyDefinitions")
        if not isinstance(definitions, list) or not definitions:
            errors.append("Initiative must contain at least one policyDefinitions entry.")
            definitions = []

        seen_refs: set[str] = set()
        seen_ids: set[str] = set()
        unique_ids: list[str] = []
        for i, pd in enumerate(definitions):
            if not isinstance(pd, dict):
                errors.append(f"policyDefinitions[{i}] is not an object.")
                continue

            pid = pd.get("policyDefinitionId")
            if not pid or not isinstance(pid, str):
                errors.append(f"policyDefinitions[{i}] is missing 'policyDefinitionId'.")
            else:
                if not _is_valid_policy_guid(pid):
                    errors.append(
                        f"policyDefinitions[{i}] has a non-GUID policyDefinitionId: "
                        f"'{pid.rstrip('/').rsplit('/', 1)[-1]}'."
                    )
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    unique_ids.append(pid)

            ref = pd.get("policyDefinitionReferenceId")
            if not ref:
                errors.append(
                    f"policyDefinitions[{i}] is missing 'policyDefinitionReferenceId'."
                )
            elif ref in seen_refs:
                errors.append(f"Duplicate policyDefinitionReferenceId: '{ref}'.")
            else:
                seen_refs.add(ref)

            for gn in pd.get("groupNames") or []:
                if gn not in group_names:
                    errors.append(
                        f"policyDefinitions[{i}] references undefined group '{gn}'."
                    )

        # --- Read-only reference resolution ---
        references_checked = 0
        unresolved = 0
        if check_references and unique_ids:
            to_check = unique_ids[:_MAX_REFERENCE_CHECKS]
            if len(unique_ids) > _MAX_REFERENCE_CHECKS:
                warnings.append(
                    f"Only the first {_MAX_REFERENCE_CHECKS} of {len(unique_ids)} "
                    "referenced policy definitions were verified."
                )
            statuses = await self._resolve_references(to_check)
            references_checked = len(statuses)
            for pid, status in statuses.items():
                guid = pid.rstrip("/").rsplit("/", 1)[-1]
                if status == 404:
                    unresolved += 1
                    errors.append(
                        f"Referenced policy definition not found in tenant: {guid}."
                    )
                elif status != 200:
                    warnings.append(
                        f"Could not verify policy definition {guid} (HTTP {status})."
                    )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "policy_count": len(definitions),
                "unique_policy_count": len(unique_ids),
                "group_count": len(group_names),
                "references_checked": references_checked,
                "unresolved_references": unresolved,
            },
        }

    async def _resolve_references(
        self, policy_ids: list[str]
    ) -> dict[str, Any]:
        """GET each policy definition (read-only) and return {id: status}.

        A status of ``200`` means the definition resolved, ``404`` means it does
        not exist at the requested scope, and any other value (an HTTP status or
        the string ``"error"``) means it could not be verified.
        """
        sem = asyncio.Semaphore(_REFERENCE_CONCURRENCY)
        statuses: dict[str, Any] = {}

        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            async def _check(pid: str) -> None:
                url = f"{_ARM_BASE}/{pid.lstrip('/')}?api-version={_API_VERSION_POLICY}"
                async with sem:
                    try:
                        resp = await c.get(url, headers=self._headers)
                        statuses[pid] = resp.status_code
                    except Exception:  # pragma: no cover - network failure path
                        statuses[pid] = "error"

            await asyncio.gather(*(_check(pid) for pid in policy_ids))

        return statuses

    # ------------------------------------------------------------------
    # Deploy initiative (definition + optional assignment)
    # ------------------------------------------------------------------

    async def deploy_initiative(
        self,
        scope: str,
        initiative_name: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or update a policy set definition at *scope*."""
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policySetDefinitions/{initiative_name}?api-version={_API_VERSION_POLICY}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.put(url, headers=self._headers, json=body)
            resp.raise_for_status()
            return resp.json()

    async def create_assignment(
        self,
        scope: str,
        assignment_name: str,
        policy_set_definition_id: str,
        display_name: str,
        description: str = "",
        enforce_mode: bool = False,
        location: str = "eastus",
    ) -> dict[str, Any]:
        """Assign a policy set definition at *scope*.

        A system-assigned identity + location are always attached: they are
        mandatory when the initiative contains ``DeployIfNotExists``/``Modify``
        policies (ARM rejects the assignment otherwise, even under
        ``DoNotEnforce``) and are harmless for audit-only initiatives. When
        *enforce_mode* is False (default) the assignment uses ``DoNotEnforce``
        so effects are never applied — compliance is still assessed.
        """
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policyAssignments/{assignment_name}?api-version={_API_VERSION_POLICY}"
        )
        body = _build_assignment_body(
            policy_set_definition_id=policy_set_definition_id,
            display_name=display_name,
            description=description,
            enforce_mode=enforce_mode,
            location=location,
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.put(url, headers=self._headers, json=body)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Trigger on-demand compliance scan (best-effort)
    # ------------------------------------------------------------------

    async def trigger_compliance_scan(self, scope: str) -> dict[str, Any]:
        """Trigger an on-demand Azure Policy compliance evaluation at *scope*.

        Equivalent to ``az policy state trigger-scan`` (Policy Insights
        ``triggerEvaluation``). This nudges Azure Policy to re-evaluate resources
        against their assignments now instead of waiting for the ~24h automatic
        cycle, refreshing the compliance results that Defender for Cloud's
        Regulatory-compliance dashboard consumes.

        Only subscription and resource-group scopes are supported by ARM
        (management groups are not), so an unsupported scope is *skipped* rather
        than erroring. The evaluation is a long-running async operation: ARM
        returns ``202 Accepted`` immediately and we do not poll it to completion.

        Best-effort by design — it NEVER raises. A failed or unsupported scan
        must not fail the deploy that triggered it. Returns a structured result::

            {"triggered": bool, "skipped": bool, "scope": str | None,
             "status_code": int | None, "location": str | None, "reason": str}
        """
        scan_scope = _scan_supported_scope(scope)
        if scan_scope is None:
            return {
                "triggered": False,
                "skipped": True,
                "scope": None,
                "reason": (
                    "On-demand compliance scan supports only subscription and "
                    "resource-group scopes; management groups are not supported "
                    "by Azure Policy Insights."
                ),
            }

        url = (
            f"{_ARM_BASE}/{scan_scope.lstrip('/')}/providers/Microsoft.PolicyInsights"
            f"/policyStates/latest/triggerEvaluation"
            f"?api-version={_API_VERSION_POLICY_INSIGHTS}"
        )
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(url, headers=self._headers)
                resp.raise_for_status()
            return {
                "triggered": True,
                "skipped": False,
                "scope": scan_scope,
                "status_code": resp.status_code,
                "location": resp.headers.get("location"),
            }
        except Exception as exc:  # noqa: BLE001 — best-effort, never fail the deploy
            logger.warning(
                "trigger_compliance_scan_failed scope=%s", scan_scope, exc_info=exc
            )
            return {
                "triggered": False,
                "skipped": False,
                "scope": scan_scope,
                "reason": str(exc),
            }

    # ------------------------------------------------------------------
    # Read existing policies (for explorer)
    # ------------------------------------------------------------------

    async def list_policy_definitions(
        self, scope: str, *, custom_only: bool = True
    ) -> list[dict[str, Any]]:
        """List policy definitions at *scope*."""
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policyDefinitions?api-version={_API_VERSION_POLICY}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            items = resp.json().get("value", [])
        if custom_only:
            items = [
                d for d in items
                if d.get("properties", {}).get("policyType") == "Custom"
            ]
        return items

    async def list_policy_set_definitions(
        self, scope: str, *, custom_only: bool = True
    ) -> list[dict[str, Any]]:
        """List policy set (initiative) definitions at *scope*."""
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policySetDefinitions?api-version={_API_VERSION_POLICY}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            items = resp.json().get("value", [])
        if custom_only:
            items = [
                d for d in items
                if d.get("properties", {}).get("policyType") == "Custom"
            ]
        return items

    async def list_policy_assignments(
        self, scope: str
    ) -> list[dict[str, Any]]:
        """List policy assignments at *scope*."""
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policyAssignments?api-version={_API_VERSION_POLICY}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json().get("value", [])
