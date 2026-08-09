"""Every subnet must carry an NSG, because a subscription policy demands it.

This is a regression lock on the second cause of the deployment failures.

A subscription-level Azure Policy enforces "Subnets must have a Network
Security Group". `app/infra/core/network.bicep` declared three subnets and
attached an NSG to only one, so `azd provision` was rejected with
RequestDisallowedByPolicy before any Container App was touched::

    RequestDisallowedByPolicy: Resource 'vnet-...' was disallowed by policy.
    Reasons: 'Subnets must have a Network Security Group.'

What makes this worth a test rather than a one-line fix is *why* it went
unnoticed. The deployed environment already had all three NSGs, created
out-of-band with names the template never mentions. So the infrastructure code
could no longer reproduce the infrastructure it claimed to describe, and
nothing detected that: the live environment looked healthy, and the template
looked fine in isolation. The drift was only visible when the two were
compared -- which happened by accident, when a deployment was attempted for the
first time in weeks.

The test reads the *compiled ARM*, not the Bicep source, so it checks what
Azure will actually receive rather than what the source appears to say.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NETWORK_BICEP = (
    Path(__file__).resolve().parents[1] / "infra" / "core" / "network.bicep"
)


def _compiled_template() -> dict:
    """Compile network.bicep to ARM JSON.

    Skips rather than passes when the Bicep CLI is unavailable, so a missing
    toolchain can never be mistaken for a clean result -- the exact failure
    mode this file exists to catch.
    """
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        pytest.skip("Azure CLI not available to compile Bicep")
    if not NETWORK_BICEP.exists():
        pytest.fail(f"{NETWORK_BICEP} is missing; this lock would be inert")

    result = subprocess.run(
        [az, "bicep", "build", "--file", str(NETWORK_BICEP), "--stdout"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        pytest.fail(f"bicep build failed:\n{result.stderr.strip()}")
    return json.loads(result.stdout)


def _subnets(template: dict) -> list[dict]:
    return [
        subnet
        for resource in template.get("resources", [])
        if resource.get("type", "").endswith("virtualNetworks")
        for subnet in resource.get("properties", {}).get("subnets", [])
    ]


def test_the_template_declares_subnets_to_check() -> None:
    """Guard the guard: an empty subnet list must not read as success."""
    subnets = _subnets(_compiled_template())
    assert subnets, (
        "no subnets found in the compiled template -- either the network "
        "module changed shape or compilation silently produced nothing, and "
        "this regression lock is now inert"
    )


def test_every_subnet_has_a_network_security_group() -> None:
    """The invariant the subscription policy enforces."""
    missing = [
        subnet.get("name", "<unnamed>")
        for subnet in _subnets(_compiled_template())
        if not subnet.get("properties", {}).get("networkSecurityGroup", {}).get("id")
    ]
    assert not missing, (
        f"subnet(s) {missing} have no NSG. A subscription Azure Policy blocks "
        "this outright ('Subnets must have a Network Security Group'), so "
        "provisioning fails before any application resource is created. Attach "
        "an NSG in network.bicep rather than creating one by hand in the "
        "portal -- an out-of-band NSG is what let this drift go unnoticed."
    )


def test_nsg_names_match_the_deployed_environment() -> None:
    """Names must match live, or provisioning creates a duplicate set.

    The deployed NSGs are `<vnet>-aca-infra-nsg`, `<vnet>-aca-workload-nsg` and
    `<vnet>-pe-nsg`. Matching them means provision adopts the existing
    resources instead of leaving orphans behind.
    """
    template = _compiled_template()
    names = [
        resource.get("name", "")
        for resource in template.get("resources", [])
        if resource.get("type", "").endswith("networkSecurityGroups")
    ]
    for suffix in ("-aca-infra-nsg", "-aca-workload-nsg", "-pe-nsg"):
        assert any(suffix in name for name in names), (
            f"no NSG named '*{suffix}' in the template, but one with that name "
            f"exists in the deployed environment. Declared NSGs: {names}. "
            "A mismatch creates a second NSG rather than adopting the live one."
        )
