"""The Azure OpenAI IaC must reproduce the live environment, not a different one.

A regression lock on a drift found on 2026-09-28. The live backend ran
``gpt-5.6-luna`` at 412K TPM, content filter ``Microsoft.DefaultV2``, and API-key
auth disabled. Every layer that decides what ``azd provision`` builds said
something else:

    main.parameters.json / main.bicep / openai.bicep   gpt-5.2, gpt-5.4-mini
    azure.yaml preprovision hook (default branch)      gpt-5.2
    openai.bicep deployment capacity                   10
    openai.bicep raiPolicyName                         Microsoft.Default
    openai.bicep disableLocalAuth                      (omitted -> keys on)
    backend/pipeline config.py fallbacks               gpt-5.6-sol

`main.bicep` wires the backend's ``AZURE_OPENAI_DEPLOYMENT_NAME`` to
``openai.outputs.deploymentName``, so a provision would have silently repointed
production to another model, cut throughput by ~97%, weakened the content
filter and re-enabled key auth. None of that would have raised an error. A
what-if against the live resource group confirmed each change before the fix
and ``NoChange`` on all four resources after it.

It went unnoticed because routine releases use ``azd deploy`` (image only),
which never re-applies the template. The only thing that exposes this kind of
drift is comparing the code with live, which is what these tests pin down.

Most checks read committed files, so they run in CI, which has no Bicep CLI.
The compile check additionally proves the committed ``main.json`` is not stale.

Run:
    cd app && PYTHONPATH=backend:frontend python -m pytest tests/test_openai_iac_matches_live.py -q
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
INFRA = APP / "infra"

# The live dev environment, as read from ARM on 2026-09-28. Changing the model
# is a deliberate act: update these and the IaC together.
LIVE_MODEL = "gpt-5.6-luna"
LIVE_MODEL_VERSION = "2026-07-09"
LIVE_FALLBACK = "gpt-4.1"
LIVE_FALLBACK_VERSION = "2025-04-14"
LIVE_FALLBACK_DEPLOYMENT = "gpt-4.1-fallback"
LIVE_CAPACITY = 412
LIVE_RAI = "Microsoft.DefaultV2"
LIVE_FALLBACK_RAI = "Microsoft.Default"


def _openai_module(template: dict) -> dict:
    for resource in template.get("resources", []):
        if (
            resource.get("type") == "Microsoft.Resources/deployments"
            and resource.get("name") == "openai"
        ):
            return resource["properties"]["template"]
    pytest.fail("no 'openai' module in main.json; this lock would be inert")


def _param_default(template: dict, name: str):
    try:
        return template["parameters"][name]["defaultValue"]
    except KeyError:
        pytest.fail(f"parameter {name!r} has no default in the template")


def _committed_main() -> dict:
    return json.loads((INFRA / "main.json").read_text())


def test_main_template_defaults_match_live() -> None:
    main = _committed_main()
    assert _param_default(main, "openAiModelName") == LIVE_MODEL
    assert _param_default(main, "openAiModelVersion") == LIVE_MODEL_VERSION
    assert _param_default(main, "openAiFallbackModel") == LIVE_FALLBACK
    assert _param_default(main, "openAiFallbackVersion") == LIVE_FALLBACK_VERSION
    assert _param_default(main, "openAiDeploymentCapacity") == LIVE_CAPACITY


def test_capacity_actually_reaches_the_openai_module() -> None:
    """A top-level default is worthless if the module never receives it."""
    params = next(
        r["properties"]["parameters"]
        for r in _committed_main()["resources"]
        if r.get("name") == "openai"
    )
    assert "deploymentCapacity" in params, (
        "main.bicep does not pass deploymentCapacity to the openai module, so "
        "the module's own default applies regardless of openAiDeploymentCapacity"
    )


def test_openai_module_defaults_match_live() -> None:
    module = _openai_module(_committed_main())
    assert _param_default(module, "modelName") == LIVE_MODEL
    assert _param_default(module, "fallbackModel") == LIVE_FALLBACK
    assert _param_default(module, "deploymentCapacity") == LIVE_CAPACITY
    assert _param_default(module, "raiPolicyName") == LIVE_RAI
    assert _param_default(module, "fallbackRaiPolicyName") == LIVE_FALLBACK_RAI


def test_fallback_deployment_name_matches_live() -> None:
    """The fallback is named '<model>-fallback'; live is 'gpt-4.1-fallback'.

    A different name makes provision create a second deployment rather than
    adopting the live one, and the backend env would point at the new name.
    """
    source = (INFRA / "core" / "openai.bicep").read_text()
    match = re.search(r"resource fallbackDeployment [^\n]*\n(?:[^\n]*\n)*?\s*name: '([^']+)'", source)
    assert match, "could not find the fallbackDeployment name in openai.bicep"
    rendered = match.group(1).replace("${fallbackModel}", LIVE_FALLBACK)
    assert rendered == LIVE_FALLBACK_DEPLOYMENT


def test_local_auth_stays_disabled() -> None:
    module = _openai_module(_committed_main())
    accounts = [
        r
        for r in module.get("resources", [])
        if r.get("type") == "Microsoft.CognitiveServices/accounts"
        and "existing" not in r
    ]
    assert accounts, "no Cognitive Services account resource found in the module"
    for account in accounts:
        assert account["properties"].get("disableLocalAuth") is True, (
            "disableLocalAuth is not true: provisioning would re-enable API-key "
            "auth on an account that is Entra-only in production"
        )


def test_azd_parameter_defaults_match_live() -> None:
    """main.parameters.json defaults win over Bicep defaults under azd."""
    params = json.loads((INFRA / "main.parameters.json").read_text())["parameters"]

    def default(name: str) -> str:
        match = re.fullmatch(r"\$\{[A-Z0-9_]+=(.*)\}", params[name]["value"])
        assert match, f"{name} has no ${{VAR=default}} fallback"
        return match.group(1)

    assert default("openAiModelName") == LIVE_MODEL
    assert default("openAiModelVersion") == LIVE_MODEL_VERSION
    assert default("openAiFallbackModel") == LIVE_FALLBACK
    assert default("openAiFallbackVersion") == LIVE_FALLBACK_VERSION
    assert default("openAiDeploymentCapacity") == str(LIVE_CAPACITY)


def test_preprovision_hook_default_matches_live() -> None:
    """The hook runs before the template and sets AZURE_OPENAI_MODEL_NAME.

    Its catch-all branch is taken on Enter *and* on a non-interactive run
    (read gets EOF), so it overrides every default above. It must pick the
    live model, or the Bicep fix is bypassed.
    """
    hook = (APP / "azure.yaml").read_text()
    default_branch = re.search(
        r"\*\)\s*(?:#[^\n]*\n\s*)*MODEL_NAME=\"([^\"]+)\"\s*MODEL_VERSION=\"([^\"]+)\"",
        hook,
    )
    assert default_branch, "could not find the hook's default (*) model branch"
    assert default_branch.groups() == (LIVE_MODEL, LIVE_MODEL_VERSION)


def test_python_fallback_defaults_match_live() -> None:
    """Used only when AZURE_OPENAI_DEPLOYMENT_NAME is unset, but must not name a
    third model."""
    for path in ("backend/app/config.py", "backend/app/pipeline/config.py"):
        source = (APP / path).read_text()
        assert "gpt-5.6-sol" not in source, f"{path} still defaults to gpt-5.6-sol"
        assert f'"{LIVE_MODEL}"' in source, f"{path} does not default to {LIVE_MODEL}"


def test_committed_main_json_is_not_stale() -> None:
    """The committed ARM must be what main.bicep compiles to.

    Skips rather than passes without a Bicep toolchain, so a missing CLI is
    never mistaken for a clean result.
    """
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        pytest.skip("Azure CLI not available to compile Bicep")
    result = subprocess.run(
        [az, "bicep", "build", "--file", str(INFRA / "main.bicep"), "--stdout"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        pytest.fail(f"bicep build failed:\n{result.stderr.strip()}")
    compiled = json.loads(result.stdout)
    committed = _committed_main()
    compiled.get("metadata", {}).pop("_generator", None)
    committed.get("metadata", {}).pop("_generator", None)
    assert compiled == committed, (
        "app/infra/main.json is stale: recompile with "
        "`az bicep build --file app/infra/main.bicep --outfile app/infra/main.json`"
    )
