#!/usr/bin/env python3
"""ComplianceIQ skill CLI — drive the deployed app's pipeline + deploy API.

This is the executable the ComplianceIQ Copilot skill runs. It talks to the
**deployed** backend *through the frontend's ``/api`` reverse proxy* and
authenticates with the caller's ``az`` login token (ARM audience). It uses only
the Python standard library plus the ``az`` CLI, so no pip install is required.

Typical flow (see SKILL.md for the guided version)::

    ciq.py health
    ciq.py run --pdf regulation.pdf                 # -> prints job_id, waits
    ciq.py artifacts --job-id <id> --out ./out      # saves initiative.json
    ciq.py scopes
    ciq.py validate --job-id <id> --scope /subscriptions/<sub>
    ciq.py deploy   --job-id <id> --scope /subscriptions/<sub> \
                    --assign --location eastus       # audit-only by default

Base URL resolution order:
  1. ``--base-url``
  2. ``$CIQ_BASE_URL``
  3. ``az containerapp show`` on ``--frontend-app``/``--resource-group``
     (or ``$CIQ_FRONTEND_APP``/``$CIQ_RESOURCE_GROUP``) -> ``https://<fqdn>``
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ciq_core as core  # noqa: E402


class CiqError(RuntimeError):
    """User-facing error (printed without a traceback)."""


# ---------------------------------------------------------------------------
# az helpers
# ---------------------------------------------------------------------------

def _az(args: list[str]) -> str:
    """Run an ``az`` command and return trimmed stdout, raising on failure."""
    # shutil.which resolves PATHEXT (.cmd/.bat), so this also works on Windows,
    # where "az" is az.cmd and subprocess.run(["az", ...]) with shell=False
    # raises FileNotFoundError even though "az" is on PATH.
    az_path = shutil.which("az")
    if az_path is None:
        raise CiqError("Azure CLI ('az') not found on PATH. Install it and run 'az login'.")
    try:
        proc = subprocess.run(
            [az_path, *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:  # az not installed
        raise CiqError("Azure CLI ('az') not found on PATH. Install it and run 'az login'.") from exc
    except subprocess.CalledProcessError as exc:
        raise CiqError(f"az {' '.join(args)} failed: {exc.stderr.strip() or exc}") from exc
    return proc.stdout.strip()


def get_token() -> str:
    """Return an ARM-audience access token from the current ``az`` login."""
    token = _az(
        [
            "account",
            "get-access-token",
            "--resource",
            core.ARM_RESOURCE,
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ]
    )
    if not token:
        raise CiqError("Could not obtain an access token. Run 'az login' first.")
    return token


def resolve_base_url(args: argparse.Namespace) -> str:
    """Resolve the frontend base URL from flags, env, or ``az``."""
    if getattr(args, "base_url", None):
        return args.base_url.rstrip("/")
    env = os.getenv("CIQ_BASE_URL")
    if env:
        return env.rstrip("/")

    app = getattr(args, "frontend_app", None) or os.getenv("CIQ_FRONTEND_APP")
    rg = getattr(args, "resource_group", None) or os.getenv("CIQ_RESOURCE_GROUP")
    if app and rg:
        fqdn = _az(
            [
                "containerapp",
                "show",
                "-n",
                app,
                "-g",
                rg,
                "--query",
                "properties.configuration.ingress.fqdn",
                "-o",
                "tsv",
            ]
        )
        if fqdn:
            return f"https://{fqdn}"

    raise CiqError(
        "No base URL. Pass --base-url, set $CIQ_BASE_URL, or provide "
        "--frontend-app/--resource-group (or $CIQ_FRONTEND_APP/$CIQ_RESOURCE_GROUP)."
    )


# ---------------------------------------------------------------------------
# Parameterized built-in resolution
# ---------------------------------------------------------------------------

_REQUIRED_PARAM_CACHE: dict[str, dict] = {}


def _unique_policy_guids(body: dict) -> list[str]:
    props = body.get("properties", body) if isinstance(body, dict) else {}
    guids = []
    for pd in props.get("policyDefinitions") or []:
        if isinstance(pd, dict):
            g = core._guid_of(pd.get("policyDefinitionId"))
            if g and g not in guids:
                guids.append(g)
    return guids


def resolve_required_params(guids: list[str]) -> dict[str, dict]:
    """Map each built-in GUID to its required (no-default) parameter schema.

    Resolved live from ARM (``az policy definition show``) so the skill never
    depends on a bundled snapshot. Unknown/custom GUIDs (not resolvable as a
    built-in) are treated as having no required parameters — matching the backend
    catalog's "never strip a policy we can't positively flag" stance.
    """
    out: dict[str, dict] = {}
    for guid in guids:
        if guid in _REQUIRED_PARAM_CACHE:
            required = _REQUIRED_PARAM_CACHE[guid]
        else:
            try:
                raw = _az(["policy", "definition", "show", "--name", guid, "-o", "json"])
                required = core.required_params_from_definition(json.loads(raw))
            except CiqError:
                required = {}
            _REQUIRED_PARAM_CACHE[guid] = required
        if required:
            out[guid] = required
    return out


def _parse_policy_param(spec: str) -> tuple[str, str, str]:
    """Parse ``GUID:paramName=value`` into ``(guid, name, value)``."""
    if ":" not in spec or "=" not in spec.split(":", 1)[1]:
        raise CiqError(f"--set-policy-param must be 'GUID:paramName=value', got {spec!r}")
    guid, rest = spec.split(":", 1)
    name, value = rest.split("=", 1)
    return guid.strip(), name.strip(), value


def _collect_param_choices(args) -> tuple[dict, set]:
    """Build ``(values, exclude)`` from ``--set-policy-param`` / ``--exclude-policy``."""
    values: dict[str, dict] = {}
    for spec in getattr(args, "set_policy_param", None) or []:
        guid, name, value = _parse_policy_param(spec)
        values.setdefault(guid, {})[name] = value
    exclude = {g.strip() for g in getattr(args, "exclude_policy", None) or []}
    return values, exclude


def _resolve_parameterized(body: dict, args, *, strict: bool) -> dict:
    """Apply the user's parameter choices to ``body`` and report/enforce gaps.

    ``strict`` (deploy) raises when a required-param built-in is left unresolved
    and not excluded; non-strict (validate) only warns and validates the resolved
    subset. Nothing is dropped without being reported.
    """
    guids = _unique_policy_guids(body)
    required_by_guid = resolve_required_params(guids)
    if not required_by_guid:
        return body

    values, exclude = _collect_param_choices(args)
    resolved, unresolved = core.apply_parameter_resolutions(
        body, required_by_guid=required_by_guid, values=values, exclude=exclude
    )

    for guid in exclude:
        if guid in required_by_guid:
            print(f"info: excluding policy {guid} (user choice).", file=sys.stderr)
    for guid, params in values.items():
        if guid in required_by_guid:
            print(f"info: policy {guid} parameterized with {sorted(params)}.", file=sys.stderr)

    if unresolved:
        lines = [
            f"{u['guid']} (ref {u['referenceId']}) needs {u['missing']}"
            for u in unresolved
        ]
        detail = "; ".join(lines)
        if strict:
            raise CiqError(
                "Unresolved required parameters — supply values with "
                "--set-policy-param 'GUID:name=value' or drop with "
                f"--exclude-policy GUID. Pending: {detail}. "
                "Run 'ciq preflight' to see each parameter's schema."
            )
        print(f"warning: validating without {len(unresolved)} parameterized "
              f"policy(ies): {detail}", file=sys.stderr)
    return resolved


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------

def _request(
    method: str,
    url: str,
    token: Optional[str],
    *,
    data: Optional[bytes] = None,
    content_type: Optional[str] = None,
    timeout: int = 120,
) -> Any:
    headers = core.auth_headers(token)
    headers["Accept"] = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise CiqError(f"HTTP {exc.code} {method} {url}: {body[:600]}") from exc
    except urllib.error.URLError as exc:
        raise CiqError(f"Network error {method} {url}: {exc.reason}") from exc
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode("utf-8", "replace")


def get_json(base: str, path: str, token: Optional[str], **kw) -> Any:
    return _request("GET", core.api_url(base, path), token, **kw)


def post_json(base: str, path: str, token: Optional[str], body: dict, **kw) -> Any:
    return _request(
        "POST",
        core.api_url(base, path),
        token,
        data=json.dumps(body).encode(),
        content_type="application/json",
        **kw,
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_health(args: argparse.Namespace) -> int:
    base = resolve_base_url(args)
    token = None if args.no_auth else get_token()
    print(json.dumps(get_json(base, "/health", token), indent=2))
    return 0


def _submit_pdf(base: str, token: Optional[str], pdf: Path, args) -> str:
    fields = core.build_run_fields(args.min_confidence, args.allowed_locations)
    body, ctype = core.encode_multipart(
        fields, "pdf_file", pdf.name, pdf.read_bytes()
    )
    result = _request(
        "POST",
        core.api_url(base, "/pipeline/run"),
        token,
        data=body,
        content_type=ctype,
        timeout=300,
    )
    job_id = result.get("job_id")
    if not job_id:
        raise CiqError(f"No job_id in response: {result}")
    return job_id


def _wait(base: str, token: Optional[str], job_id: str, args) -> dict:
    deadline = time.monotonic() + args.timeout
    last = ""
    while True:
        status = get_json(base, f"/pipeline/status/{job_id}", token)
        summary = core.summarize_status(status)
        if summary != last:
            print(summary, file=sys.stderr)
            last = summary
        if core.is_terminal_status(status.get("status")):
            return status
        if time.monotonic() > deadline:
            raise CiqError(f"Timed out after {args.timeout}s (last: {summary})")
        time.sleep(args.poll_interval)


def cmd_run(args: argparse.Namespace) -> int:
    base = resolve_base_url(args)
    token = None if args.no_auth else get_token()
    pdf = Path(args.pdf)
    if not pdf.is_file():
        raise CiqError(f"PDF not found: {pdf}")
    job_id = _submit_pdf(base, token, pdf, args)
    print(f"job_id={job_id}", file=sys.stderr)
    if args.no_wait:
        print(json.dumps({"job_id": job_id}))
        return 0
    status = _wait(base, token, job_id, args)
    print(json.dumps(status, indent=2))
    return 0 if core.is_success_status(status.get("status")) else 1


def cmd_status(args: argparse.Namespace) -> int:
    base = resolve_base_url(args)
    token = None if args.no_auth else get_token()
    print(json.dumps(get_json(base, f"/pipeline/status/{args.job_id}", token), indent=2))
    return 0


def cmd_artifacts(args: argparse.Namespace) -> int:
    base = resolve_base_url(args)
    token = None if args.no_auth else get_token()
    artifacts = get_json(base, f"/pipeline/artifacts/{args.job_id}", token)
    initiative = core.extract_initiative(artifacts)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "artifacts.json").write_text(json.dumps(artifacts, indent=2))
        if initiative is not None:
            (out / "initiative.json").write_text(json.dumps(initiative, indent=2))
        print(f"Saved artifacts to {out}/ (initiative.json present: {initiative is not None})", file=sys.stderr)
    print(json.dumps(artifacts, indent=2))
    return 0


def cmd_scopes(args: argparse.Namespace) -> int:
    base = resolve_base_url(args)
    token = get_token()
    scopes = core.parse_scopes(get_json(base, "/deploy/scopes", token))
    print(json.dumps(scopes, indent=2))
    return 0


def _load_initiative(base: str, token: Optional[str], args) -> tuple[dict, str]:
    """Return ``(initiative_body, initiative_name)`` from a job id or a file.

    Any ARM-limit clamping (see :func:`ciq_core.arm_safety_warnings`) is reported
    to stderr so the user knows content was trimmed before it is deployed.
    """
    if args.initiative_file:
        raw = json.loads(Path(args.initiative_file).read_text())
        for w in core.arm_safety_warnings(raw) if isinstance(raw, dict) else []:
            print(f"warning: {w}", file=sys.stderr)
        body = core.normalize_initiative_for_deploy(raw) if isinstance(raw, dict) else raw
    elif args.job_id:
        artifacts = get_json(base, f"/pipeline/artifacts/{args.job_id}", token)
        raw = artifacts.get("files", {}).get("initiative") if isinstance(artifacts, dict) else None
        for w in core.arm_safety_warnings(raw) if isinstance(raw, dict) else []:
            print(f"warning: {w}", file=sys.stderr)
        body = core.extract_initiative(artifacts)
        if body is None:
            raise CiqError("No initiative JSON in artifacts for that job.")
    else:
        raise CiqError("Provide --job-id or --initiative-file.")
    name = args.initiative_name or core.default_initiative_name(
        body.get("properties", {}).get("displayName") if isinstance(body, dict) else None
    )
    return body, name


def cmd_validate(args: argparse.Namespace) -> int:
    base = resolve_base_url(args)
    token = get_token()
    body, name = _load_initiative(base, token, args)
    if not core.is_valid_scope(args.scope):
        raise CiqError(f"Invalid ARM scope: {args.scope}")
    body = _resolve_parameterized(body, args, strict=False)
    payload = core.build_validate_body(args.scope, name, body, not args.no_check_references)
    print(json.dumps(post_json(base, "/deploy/validate", token, payload), indent=2))
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    """Report built-ins that need required (no-default) parameters before deploy.

    Prints, per affected policy, the reference id, GUID, and each required
    parameter's schema (type/description/allowedValues) so the user can decide to
    supply a value (``--set-policy-param``) or exclude it (``--exclude-policy``).
    """
    base = resolve_base_url(args)
    token = get_token()
    body, name = _load_initiative(base, token, args)
    guids = _unique_policy_guids(body)
    required_by_guid = resolve_required_params(guids)
    refs = core.parameterized_references(body, required_by_guid)
    print(json.dumps({
        "initiative_name": name,
        "total_policies": len(guids),
        "parameterized_count": len(refs),
        "parameterized": refs,
    }, indent=2))
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    base = resolve_base_url(args)
    token = get_token()
    body, name = _load_initiative(base, token, args)
    if not core.is_valid_scope(args.scope):
        raise CiqError(f"Invalid ARM scope: {args.scope}")
    body = _resolve_parameterized(body, args, strict=True)
    payload = core.build_deploy_body(
        args.scope,
        name,
        body,
        assign=args.assign,
        enforce_mode=args.enforce,
        location=args.location,
        assignment_display_name=args.assignment_display_name,
        assignment_description=args.assignment_description or "",
    )
    print(json.dumps(post_json(base, "/deploy/initiative", token, payload, timeout=180), indent=2))
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--base-url", help="Frontend base URL, e.g. https://<fqdn>")
    p.add_argument("--frontend-app", help="Frontend Container App name (for az lookup)")
    p.add_argument("--resource-group", help="Resource group (for az lookup)")
    p.add_argument("--no-auth", action="store_true", help="Do not send a bearer token")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ciq", description="ComplianceIQ skill CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("health", help="Backend health check")
    _add_common(p)
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("run", help="Submit a PDF through the full pipeline and wait")
    _add_common(p)
    p.add_argument("--pdf", required=True)
    p.add_argument("--min-confidence", type=float, default=0.5)
    p.add_argument("--allowed-locations", help="Comma-separated Azure regions")
    p.add_argument("--no-wait", action="store_true")
    p.add_argument("--poll-interval", type=float, default=5.0)
    p.add_argument("--timeout", type=int, default=1800)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status", help="Poll a pipeline job status once")
    _add_common(p)
    p.add_argument("--job-id", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("artifacts", help="Fetch generated artifacts (initiative JSON)")
    _add_common(p)
    p.add_argument("--job-id", required=True)
    p.add_argument("--out", help="Directory to save artifacts.json / initiative.json")
    p.set_defaults(func=cmd_artifacts)

    p = sub.add_parser("scopes", help="List deployable subscriptions / management groups")
    _add_common(p)
    p.set_defaults(func=cmd_scopes)

    p = sub.add_parser("validate", help="Dry-run validate an initiative at a scope")
    _add_common(p)
    p.add_argument("--scope", required=True)
    p.add_argument("--job-id")
    p.add_argument("--initiative-file")
    p.add_argument("--initiative-name")
    p.add_argument("--no-check-references", action="store_true")
    p.add_argument("--set-policy-param", action="append", metavar="GUID:name=value",
                   help="Supply a required parameter for a built-in (repeatable)")
    p.add_argument("--exclude-policy", action="append", metavar="GUID",
                   help="Exclude a built-in from the initiative (repeatable)")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("preflight",
                       help="List built-ins needing required parameters before deploy")
    _add_common(p)
    p.add_argument("--job-id")
    p.add_argument("--initiative-file")
    p.add_argument("--initiative-name")
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("deploy", help="Deploy an initiative (audit-only unless --enforce)")
    _add_common(p)
    p.add_argument("--scope", required=True)
    p.add_argument("--job-id")
    p.add_argument("--initiative-file")
    p.add_argument("--initiative-name")
    p.add_argument("--assign", action="store_true", help="Also create a policy assignment")
    p.add_argument("--enforce", action="store_true", help="Enforce (default: DoNotEnforce/audit-only)")
    p.add_argument("--location", default="eastus", help="Identity region for DINE/Modify policies")
    p.add_argument("--assignment-display-name")
    p.add_argument("--assignment-description")
    p.add_argument("--set-policy-param", action="append", metavar="GUID:name=value",
                   help="Supply a required parameter for a built-in (repeatable)")
    p.add_argument("--exclude-policy", action="append", metavar="GUID",
                   help="Exclude a built-in from the initiative (repeatable)")
    p.set_defaults(func=cmd_deploy)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except CiqError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
