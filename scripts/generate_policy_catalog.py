#!/usr/bin/env python3
"""Generate the Azure built-in Policy definition catalog snapshot.

The snapshot is the retrieval corpus used by ``PolicyCatalogService`` to map
external framework controls to *real* Azure Policy definition GUIDs (instead of
being limited to the small MCSB control set).

Two data sources are supported:

* ``--source az`` (default): shell out to the Azure CLI. Requires an
  authenticated ``az`` session (``az login`` / OIDC in CI). Used by the
  scheduled refresh workflow and for local regeneration.
* ``--raw <file>``: transform a previously captured ``az policy definition
  list`` JSON dump. Handy for offline regeneration and unit tests.

Deprecated definitions (``[Deprecated]`` display names / ``*-deprecated``
versions) are dropped: they must not be recommended for new governance.

Usage::

    python scripts/generate_policy_catalog.py                 # from live az
    python scripts/generate_policy_catalog.py --raw dump.json # from a dump
    python scripts/generate_policy_catalog.py --subscription <sub-id>
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# ARM api-version kept in sync with app/backend/app/services/policy_deploy_service.py
API_VERSION = "2023-04-01"

# Default output location: shipped inside the backend package so it is copied
# into the container image and resolved relative to the package at runtime.
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "app" / "backend" / "app" / "data" / "policy_catalog"
    / "azure_policy_catalog.json"
)

# Server-side projection keeps the CLI payload small and stable.
# ``policyRule`` is included so the enforcement ``effect`` can be resolved: a
# control mapped to a Manual/Disabled-effect placeholder policy enforces nothing.
#
# Deliberately NOT filtered to ``policyType=='BuiltIn'`` server-side. The
# built-in corpus is the only thing that becomes recommendable, but the
# Static "Microsoft Managed Control" definitions have to arrive too, or the
# generator cannot name them - and they account for every one of the 327
# initiative members that would otherwise look unresolvable. ``normalize`` and
# its siblings do the filtering, so each index says what it means.
_AZ_QUERY = (
    "[].{name:name, display_name:displayName, "
    "description:description, category:metadata.category, mode:mode, "
    "policyType:policyType, "
    "version:metadata.version, parameters:parameters, policyRule:policyRule}"
)

# Matches an ARM parameter reference such as ``[parameters('effect')]`` so the
# concrete effect can be resolved from the parameter's ``defaultValue``.
_EFFECT_PARAM_RE = re.compile(r"^\[+\s*parameters\('([^']+)'\)\s*\]+$")

# A built-in policy definition name is *usually* a GUID, but not always: Azure
# ships 17k78e20-9358-41c9-923c-fb736d382a12 as a real BuiltIn. Kept only for
# reporting how many members are non-GUID-shaped, never to filter them out.
_GUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

_AZ_INITIATIVE_QUERY = (
    "[?policyType=='BuiltIn'].{name:name, display_name:displayName, "
    "description:description, category:metadata.category, "
    "version:metadata.version, policyDefinitions:policyDefinitions}"
)


def _field(item: Dict[str, Any], *names: str, nested: Optional[str] = None) -> Any:
    """Read a field that the two input shapes spell differently.

    The ``az`` path projects definitions through a JMESPath query, flattening
    ``metadata.category`` to ``category`` and renaming ``displayName``. A
    ``--raw`` dump keeps the ARM spelling, with ``category`` and ``version``
    still inside ``metadata``. Reading both here keeps the two sources producing
    the *same* corpus — before this, a raw dump silently lost every category (all
    3473 definitions came out "Uncategorized"), which would have disabled
    category boosting without any error.

    The ``properties`` envelope is handled earlier, by ``_unwrap``.
    """
    for name in names:
        value = item.get(name)
        if value not in (None, ""):
            return value
    if nested:
        container = item.get(nested)
        if isinstance(container, dict):
            for name in names:
                value = container.get(name)
                if value not in (None, ""):
                    return value
    return None


def _unwrap(item: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten an ARM ``properties`` envelope up to the top level.

    ``az policy definition list`` returns an SDK-serialised, already-flat shape,
    but the ARM REST API nests everything except ``name`` and ``id`` under
    ``properties``. Reading only the flat shape meant a REST-shaped dump lost its
    display name on every record and was silently dropped in full — the generator
    would happily write a catalog of zero definitions and exit 0. Merging here
    means one shape reaches the rest of the module.

    Top-level keys win, so ``name`` (the GUID, which ARM keeps outside
    ``properties``) is never shadowed.
    """
    properties = item.get("properties")
    if not isinstance(properties, dict):
        return item
    merged = dict(properties)
    merged.update({k: v for k, v in item.items() if k != "properties"})
    return merged


def _is_builtin(item: Dict[str, Any]) -> bool:
    """True unless the definition is positively identified as non-built-in.

    The ``az`` query filters on ``policyType=='BuiltIn'`` server-side and drops
    the field, so an absent ``policyType`` means "already filtered". A raw dump
    keeps it, and includes Custom and Static definitions that must not enter the
    retrieval corpus: Custom definitions belong to whichever subscription was
    queried and would not exist in a customer's tenant.
    """
    policy_type = item.get("policyType") or item.get("policy_type")
    if not policy_type:
        return True
    return str(policy_type).strip().casefold() == "builtin"


def _is_deprecated(item: Dict[str, Any]) -> bool:
    display = (item.get("display_name") or item.get("displayName") or "")
    version = (item.get("version") or "")
    return display.startswith("[Deprecated]") or "deprecated" in version.lower()


def _requires_parameters(item: Dict[str, Any]) -> bool:
    """True if the definition has at least one parameter without a default value.

    A built-in whose parameters all carry a ``defaultValue`` can be referenced in
    a custom policy set with no ``parameters`` block. One that has a parameter
    *without* a default cannot: ARM rejects the set definition with
    ``MissingPolicyParameter`` unless a value (or pass-through) is supplied.
    Because the generator has no way to invent resource-specific values (vault
    names, regions, workspace IDs), such built-ins are excluded at generation so
    the emitted initiative stays deployable. This flag makes that detectable.
    """
    return bool(_required_parameter_schema(item))


def _required_parameter_schema(item: Dict[str, Any]) -> Dict[str, Any]:
    """Schema for the parameters that a caller MUST supply (no ``defaultValue``).

    Returns ``{paramName: {"type": ..., "description": ..., "allowed_values": [...]}}``
    for every parameter lacking a ``defaultValue``. This is what the UI prompts
    for so the built-in can be included with concrete, user-supplied values
    instead of being excluded. Parameters that already have a default are omitted
    — ARM fills those in, so we never need to ask.
    """
    params = _field(item, "parameters") or {}
    if not isinstance(params, dict):
        return {}
    schema: Dict[str, Any] = {}
    for pname, spec in params.items():
        if not isinstance(spec, dict):
            continue
        if "defaultValue" in spec:
            continue
        meta = spec.get("metadata") or {}
        entry: Dict[str, Any] = {"type": spec.get("type") or "String"}
        desc = (meta.get("description") or meta.get("displayName") or "").strip()
        if desc:
            entry["description"] = desc
        allowed = spec.get("allowedValues")
        if isinstance(allowed, list) and allowed:
            entry["allowed_values"] = allowed
        schema[pname] = entry
    return schema


def _extract_effect(item: Dict[str, Any]) -> str:
    """Resolve the concrete enforcement effect of a policy definition.

    The effect lives at ``policyRule.then.effect``. It is frequently an ARM
    parameter reference (``[parameters('effect')]``); in that case the effective
    default is taken from ``parameters.<name>.defaultValue``. Returns the
    resolved effect string (e.g. ``Audit``, ``Deny``, ``Manual``, ``Disabled``),
    or ``""`` when it cannot be determined (parameterized with no default).

    The value matters because Manual/Disabled-effect built-ins carry no
    enforcement logic: a control mapped to one *looks* covered but enforces
    nothing. Downstream classification uses this to avoid attaching such
    placeholders as Azure-Policy coverage.
    """
    rule = _field(item, "policyRule", "policy_rule")
    if not isinstance(rule, dict):
        return ""
    then = rule.get("then")
    if not isinstance(then, dict):
        return ""
    effect = then.get("effect")
    if not isinstance(effect, str):
        return ""
    effect = effect.strip()
    match = _EFFECT_PARAM_RE.match(effect)
    if match:
        params = _field(item, "parameters")
        spec = params.get(match.group(1)) if isinstance(params, dict) else None
        default = spec.get("defaultValue") if isinstance(spec, dict) else None
        return default.strip() if isinstance(default, str) else ""
    return effect


def _allowed_effects(item: Dict[str, Any]) -> List[str]:
    """The effect values the definition permits, when it is parameterised.

    The resolved default effect alone understates a policy: the gold mapping
    records that "Storage accounts should restrict network access" can be set to
    ``Deny`` even though its default is ``Audit``, and that is the difference
    between blocking a deployment and merely reporting it. Surfacing the allowed
    set lets the enrichment stage report what the policy *can* do rather than
    asserting one effect.
    """
    rule = _field(item, "policyRule", "policy_rule")
    if not isinstance(rule, dict):
        return []
    then = rule.get("then")
    if not isinstance(then, dict):
        return []
    effect = then.get("effect")
    if not isinstance(effect, str):
        return []
    match = _EFFECT_PARAM_RE.match(effect.strip())
    if not match:
        return []
    params = _field(item, "parameters") or {}
    spec = params.get(match.group(1)) if isinstance(params, dict) else None
    allowed = spec.get("allowedValues") if isinstance(spec, dict) else None
    return [str(v) for v in allowed] if isinstance(allowed, list) else []


def normalize(raw: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Project raw definitions to the lean, deduplicated catalog schema.

    Pure function: no I/O, so it is unit-testable. Drops non-built-in entries
    and anything without a name (GUID) or display name.

    Deprecated definitions are excluded from the recommendable corpus but are
    *recorded* rather than forgotten - see :func:`normalize_deprecated`. A
    policy Microsoft has retired and a policy that never existed demand
    different answers from a customer, and a catalog that drops both makes them
    look identical.
    """
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for raw_item in raw:
        item = _unwrap(raw_item)
        name = (item.get("name") or "").strip()
        display = (item.get("display_name") or item.get("displayName") or "").strip()
        if not name or not display:
            continue
        if not _is_builtin(item):
            continue
        version = _field(item, "version", nested="metadata")
        if _is_deprecated({"display_name": display, "version": version}):
            continue
        if name in seen:
            continue
        seen.add(name)
        schema = _required_parameter_schema(item)
        allowed = _allowed_effects(item)
        entry = {
            "name": name,
            "display_name": display,
            "description": (item.get("description") or "").strip(),
            "category": str(
                _field(item, "category", nested="metadata") or "Uncategorized"
            ).strip(),
            "mode": (item.get("mode") or "All").strip(),
            "effect": _extract_effect(item),
            "requires_parameters": bool(schema),
            "required_parameters": schema,
        }
        if allowed:
            entry["allowed_effects"] = allowed
        out.append(entry)
    out.sort(key=lambda d: d["name"])
    return out


def normalize_deprecated(raw: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The built-ins Microsoft has retired, kept so they can be named.

    :func:`normalize` excludes these from the recommendable corpus, which is
    right - a retired definition must never be proposed for new governance.
    But excluding them silently makes "Microsoft withdrew this policy" and
    "this policy never existed" produce the same answer, and those call for
    different things from a customer: the first is a migration, the second is a
    fabricated citation. Keeping the retired names lets the product tell them
    apart, which is the whole difference between a reported gap and a wrong
    answer.

    Only the name and display name are kept - enough to identify and explain
    it, and deliberately not enough to deploy it.
    """
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for raw_item in raw:
        item = _unwrap(raw_item)
        name = (item.get("name") or "").strip()
        display = (item.get("display_name") or item.get("displayName") or "").strip()
        if not name or not display:
            continue
        if not _is_builtin(item):
            continue
        version = _field(item, "version", nested="metadata")
        if not _is_deprecated({"display_name": display, "version": version}):
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "display_name": display})
    out.sort(key=lambda d: d["name"])
    return out


def normalize_managed_controls(raw: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Microsoft Managed Controls - ``policyType: Static``.

    These are not built-ins and are deliberately absent from the recommendable
    corpus: they carry no deployable effect, because the control they describe
    is operated and attested by Microsoft rather than enforced in the
    customer's tenant.

    They still have to be *nameable*, because Azure's own compliance
    initiatives are full of them. Every one of the 327 initiative members that
    the definitions array could not resolve turned out to be a Static managed
    control - not a deprecation and not a bad identifier. Without this index
    the product reports a third of MCSB's membership as unresolvable, which
    reads as broken data when it is in fact Microsoft attestation: precisely
    the Category D answer the customer is owed.
    """
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for raw_item in raw:
        item = _unwrap(raw_item)
        name = (item.get("name") or "").strip()
        display = (item.get("display_name") or item.get("displayName") or "").strip()
        policy_type = str(item.get("policyType") or item.get("policy_type") or "").strip()
        if not name or not display:
            continue
        if policy_type.casefold() != "static":
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "display_name": display})
    out.sort(key=lambda d: d["name"])
    return out


def _fetch_via_az(subscription: Optional[str]) -> List[Dict[str, Any]]:
    cmd = ["az", "policy", "definition", "list", "--query", _AZ_QUERY, "-o", "json"]
    if subscription:
        cmd += ["--subscription", subscription]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"az failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
    return json.loads(proc.stdout or "[]")


def _fetch_initiatives_via_az(subscription: Optional[str]) -> List[Dict[str, Any]]:
    cmd = [
        "az", "policy", "set-definition", "list",
        "--query", _AZ_INITIATIVE_QUERY, "-o", "json",
    ]
    if subscription:
        cmd += ["--subscription", subscription]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"az failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
    return json.loads(proc.stdout or "[]")


def build_catalog(raw: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
    definitions = normalize(raw)
    deprecated = normalize_deprecated(raw)
    managed = normalize_managed_controls(raw)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "api_version": API_VERSION,
        "count": len(definitions),
        "definitions": definitions,
        "deprecated_count": len(deprecated),
        "deprecated": deprecated,
        "managed_control_count": len(managed),
        "managed_controls": managed,
    }


# The order top-level keys are written in, so a refresh diff shows what changed.
#
# Without this the order is a function of which code path last wrote the file:
# build_catalog() ends at managed_controls and the initiative keys are assigned
# afterwards, so a fresh run appends them at the end -- but re-writing a catalog
# that already had them keeps their original position, because assigning to an
# existing dict key does not move it. The two orderings are semantically
# identical and textually catastrophic: a refresh where exactly one policy
# description changed produced a 19,202-line diff, because whole sections
# shifted past each other. Nobody reviews that, which defeats the point of
# routing the refresh through a pull request at all.
CATALOG_KEY_ORDER = (
    "generated_at",
    "source",
    "api_version",
    "count",
    "definitions",
    "initiative_count",
    "initiatives",
    "deprecated_count",
    "deprecated",
    "managed_control_count",
    "managed_controls",
)


def canonicalize(catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Return the catalog with its top-level keys in a fixed order.

    Unknown keys are kept, sorted, after the known ones rather than dropped --
    silently discarding a field a future version adds would be the same class of
    bug this function exists to prevent.
    """
    ordered = {k: catalog[k] for k in CATALOG_KEY_ORDER if k in catalog}
    for key in sorted(set(catalog) - set(CATALOG_KEY_ORDER)):
        ordered[key] = catalog[key]
    return ordered


def _definition_name(ref: str) -> str:
    """The definition name at the end of a policy definition resource id.

    Initiative members arrive as full ARM paths; the catalog keys on the
    trailing segment everywhere else.

    Deliberately **not** GUID-validated. Azure ships at least one real built-in
    whose definition name is not GUID-shaped -
    ``17k78e20-9358-41c9-923c-fb736d382a12`` ("Transparent Data Encryption on
    SQL databases should be enabled"), verified live as ``policyType: BuiltIn``.
    A format filter here would quietly drop a genuine member and understate the
    coverage an initiative actually gives the customer.
    """
    return (ref or "").rstrip("/").rsplit("/", 1)[-1].strip()


def normalize_initiatives(raw: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Project raw policy set definitions to the initiative catalog schema.

    Initiatives are how Azure actually ships compliance coverage - MCSB, NIST
    SP 800-53 R5, ISO 27001, CIS Foundations are all initiatives, not
    definitions. Holding only definitions meant the product could never say
    "this is already covered by an initiative you have assigned", and would
    report a perfectly real initiative GUID as an unresolvable identifier.

    ``policy_definition_names`` is the join key: it is what lets a control's
    mapped GUIDs be tested for membership of an initiative the customer already
    runs.
    """
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for raw_item in raw:
        item = _unwrap(raw_item)
        name = (item.get("name") or "").strip()
        display = (item.get("display_name") or item.get("displayName") or "").strip()
        if not name or not display:
            continue
        version = _field(item, "version", nested="metadata")
        if _is_deprecated({"display_name": display, "version": version}):
            continue
        if name in seen:
            continue
        seen.add(name)

        members = item.get("policyDefinitions") or item.get("policy_definitions") or []
        guids: List[str] = []
        for member in members:
            if isinstance(member, dict):
                ref = member.get("policyDefinitionId") or member.get("policy_definition_id") or ""
            else:
                ref = str(member)
            guid = _definition_name(ref)
            if guid and guid not in guids:
                guids.append(guid)

        out.append(
            {
                "name": name,
                "display_name": display,
                "description": (item.get("description") or "").strip(),
                "category": str(
                    _field(item, "category", nested="metadata") or "Uncategorized"
                ).strip(),
                "policy_definition_names": guids,
                "policy_definition_count": len(guids),
            }
        )
    out.sort(key=lambda d: d["name"])
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw", type=Path, help="Transform a captured az JSON dump instead of calling az.")
    parser.add_argument("--subscription", help="Subscription to query (defaults to az context).")
    parser.add_argument(
        "--initiatives-raw",
        type=Path,
        help="Captured az policy set-definition JSON dump to fold in as initiatives.",
    )
    parser.add_argument(
        "--initiatives-only",
        action="store_true",
        help="Refresh only the initiatives of an existing catalog, leaving definitions untouched.",
    )
    args = parser.parse_args(argv)

    if args.initiatives_only:
        if not args.initiatives_raw:
            print("--initiatives-only requires --initiatives-raw.", file=sys.stderr)
            return 1
        if not args.output.exists():
            print(f"No existing catalog at {args.output} to update.", file=sys.stderr)
            return 1
        catalog = json.loads(args.output.read_text(encoding="utf-8"))
        initiatives = normalize_initiatives(
            json.loads(args.initiatives_raw.read_text(encoding="utf-8"))
        )
        if not initiatives:
            print("Refusing to write an empty initiative list.", file=sys.stderr)
            return 1
        catalog["initiatives"] = initiatives
        catalog["initiative_count"] = len(initiatives)
        args.output.write_text(
            json.dumps(canonicalize(catalog), indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {len(initiatives)} initiatives to {args.output}")
        return 0

    if args.raw:
        raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
        source = f"file:{args.raw.name}"
    else:
        raw = _fetch_via_az(args.subscription)
        source = "az"

    catalog = build_catalog(raw, source)
    if catalog["count"] == 0:
        print("Refusing to write an empty catalog.", file=sys.stderr)
        return 1

    if args.initiatives_raw:
        initiatives_raw = json.loads(args.initiatives_raw.read_text(encoding="utf-8"))
    else:
        initiatives_raw = _fetch_initiatives_via_az(args.subscription)
    initiatives = normalize_initiatives(initiatives_raw)
    catalog["initiatives"] = initiatives
    catalog["initiative_count"] = len(initiatives)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(canonicalize(catalog), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {catalog['count']} policy definitions and "
        f"{len(initiatives)} initiatives to {args.output} (source={source})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
