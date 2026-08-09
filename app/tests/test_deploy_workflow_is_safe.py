"""Guard the deployment workflow against the failure it actually caused.

Deploy run 31303805011 provisioned infrastructure automatically on a merge to
main. The Bicep template no longer produces the live environment's resource
names, so instead of updating the environment it built a second, parallel set of
resources *inside the live resource group* -- a Log Analytics workspace,
Application Insights, a VNet with three NSGs and a Container Apps environment --
before failing on a name collision. They had to be deleted by hand.

Nothing in the repository prevented that, and nothing would have noticed it
being reintroduced. These tests encode the three properties that stop it:

  1. provisioning never happens unattended,
  2. it requires a typed confirmation,
  3. the container deploy names its targets rather than discovering them.

They are deliberately written against the workflow file, because that is what
GitHub executes. A test that checked a copy of the intent would be the same
class of defect as the one it is guarding against -- and that mistake has
already been made once in this repository, in a test that validated an
``azure.yaml`` nothing loads.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip(
    "yaml", reason="PyYAML unavailable; cannot parse the workflow"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "azure-deploy.yml"


def _workflow() -> dict:
    if not WORKFLOW.is_file():
        pytest.skip(f"{WORKFLOW} not found")
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _job(name: str) -> dict:
    jobs = _workflow().get("jobs", {})
    assert name in jobs, f"expected a '{name}' job in {WORKFLOW.name}, got {sorted(jobs)}"
    return jobs[name]


def test_the_workflow_still_has_the_jobs_these_tests_describe() -> None:
    """Guard the guard: renaming a job must not silently disable these checks."""
    jobs = _workflow().get("jobs", {})
    for required in ("provision", "deploy"):
        assert required in jobs, (
            f"job '{required}' is gone. These tests assert properties of it, so "
            "they would now pass vacuously. Update them alongside the rename."
        )


def test_provisioning_never_runs_unattended() -> None:
    """A push to main must not be able to change infrastructure.

    This is the specific condition that created duplicate live resources.
    """
    condition = " ".join(str(_job("provision").get("if", "")).split())

    assert condition, (
        "the provision job has no 'if' condition, so it runs on every trigger "
        "including push to main -- the exact configuration that duplicated live "
        "infrastructure in run 31303805011"
    )
    assert "workflow_dispatch" in condition, (
        "the provision job must be restricted to manual dispatch; "
        f"got: {condition}"
    )
    assert "github.event_name == 'push'" not in condition, (
        "the provision job runs on push. Provisioning is only safe when someone "
        "is watching, because the template does not currently reproduce the "
        "live environment's resource names."
    )


def test_provisioning_requires_a_typed_confirmation() -> None:
    """Reaching the dispatch form by accident must not be enough."""
    steps = _job("provision").get("steps", [])
    guard = next(
        (s for s in steps if "confirm" in str(s.get("name", "")).lower()), None
    )
    assert guard is not None, (
        "the provision job has no confirmation step; manual dispatch alone is "
        "one mis-click away from re-provisioning"
    )

    body = f"{guard.get('run', '')} {guard.get('env', {})}"
    assert "PROVISION" in body, (
        "the confirmation step does not check for the literal word PROVISION"
    )

    # The guard must be able to stop the job, not merely warn.
    assert "exit 1" in str(guard.get("run", "")), (
        "the confirmation step never exits non-zero, so it cannot actually "
        "block provisioning -- a check that cannot fail is not a check"
    )

    # And it has to run before anything touches Azure.
    names = [str(s.get("name", "")) for s in steps]
    azure_steps = [
        i for i, n in enumerate(names) if "azure" in n.lower() or "azd" in n.lower()
    ]
    assert azure_steps, "expected the provision job to contain Azure steps"
    assert names.index(guard["name"]) < min(azure_steps), (
        "the confirmation step runs after Azure login; it must come first so a "
        "refused run never authenticates"
    )


def test_the_container_deploy_names_its_targets() -> None:
    """The deploy must fail loudly rather than guess which resources it updates.

    Guessing is how provisioning ended up creating a parallel stack: absent
    configuration silently became a default that described a different
    environment.
    """
    steps = _job("deploy").get("steps", [])
    guard = next(
        (s for s in steps if "require" in str(s.get("name", "")).lower()), None
    )
    assert guard is not None, (
        "the deploy job has no step requiring explicit targets, so missing "
        "configuration would fall back to defaults instead of stopping"
    )

    run = str(guard.get("run", ""))
    for var in (
        "AZURE_RESOURCE_GROUP",
        "AZURE_CONTAINER_REGISTRY",
        "AZURE_BACKEND_APP",
        "AZURE_FRONTEND_APP",
    ):
        assert var in run, f"{var} is not required before deploying"

    assert "exit 1" in run, "the target check cannot fail, so it is not a check"

    # It must verify the apps exist, so a typo updates nothing rather than
    # creating a new app alongside the real one.
    assert "containerapp show" in run, (
        "the deploy does not verify the container apps exist before updating "
        "them; a mistyped name should stop the deploy, not create a new app"
    )


def test_the_deploy_updates_existing_apps_rather_than_creating_them() -> None:
    """`containerapp create`/`up` would resurrect the parallel-stack problem."""
    import re

    run_bodies = " ".join(
        str(s.get("run", "")) for s in _job("deploy").get("steps", [])
    )
    # Matched on a word boundary: "containerapp up" is a prefix of the entirely
    # legitimate "containerapp update", and a naive substring check flags it.
    for forbidden in ("containerapp create", "containerapp up", "azd up"):
        pattern = rf"\b{re.escape(forbidden)}\b(?!date)"
        assert not re.search(pattern, run_bodies), (
            f"the deploy job uses '{forbidden}', which can create new resources. "
            "Container deploys must only update apps that already exist."
        )
