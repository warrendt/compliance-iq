"""The azd lifecycle hooks declare `shell: sh`, so they must actually be POSIX.

This is a regression lock on a defect that blocked every automated deployment.

`app/azure.yaml` used `command -v az &> /dev/null` inside a hook declared as
`shell: sh`. `&>` is a bashism. Under dash -- which is /bin/sh on the GitHub
runners -- it does not redirect both streams; it parses as "run the command in
the background" followed by a separate, bare `> /dev/null` redirect. The `if`
condition then evaluates the exit status of that bare redirect, which is always
0, so the failure branch fired unconditionally.

The result was the signature of this class of bug: a checker that reports the
opposite of what it measured. CI printed

    Error: Azure CLI is not installed
    /usr/bin/az

-- the refutation of its own claim on the very next line, because the
backgrounded `command -v az` still wrote its answer to stdout.

The consequence is what makes it worth a test. `azd provision` runs
`preprovision` first, so provisioning could never start; the deploy job is
gated on it, so containers never shipped either. Every deployment had to be
done by hand. Nothing was broken in Azure, in the Bicep or in the credentials,
which is exactly why it was expensive to find.

These tests assert the property (hooks are POSIX-clean) rather than the fixed
line, so any future hook that reintroduces a bashism fails here rather than in
a deployment.

One further trap, recorded because this test fell into it: there are **two**
azd configs, `azure.yaml` and `app/azure.yaml`, and azd has no include or
delegation mechanism, so they are independent duplicates. The workflows run azd
from the repository root, so the root file is the one that executes. The first
fix was applied to `app/azure.yaml` only; CI went green, the deployment ran
again, and failed with byte-identical output. The scan below therefore
discovers every azure.yaml in the repo instead of naming one.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories that never contain a deployable azd config.
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}


def _azure_yaml_files() -> list[Path]:
    """Every azd config in the repository -- discovered, never hardcoded.

    This matters more than it looks. The first version of this test pointed at
    a single hardcoded `app/azure.yaml`, so it went green while the file azd
    actually loads (the one at the repo root, because the workflows run azd
    from there) still carried the defect. The deployment then failed again with
    byte-identical output. A test that checks a file nothing reads is the same
    class of bug as a checker that cannot tell "fine" from "never happened".
    """
    return sorted(
        p
        for p in REPO_ROOT.rglob("azure.yaml")
        if not _SKIP_DIRS & set(p.relative_to(REPO_ROOT).parts)
    )

# Constructs that bash accepts and dash does not. Each would change the meaning
# of a hook silently rather than failing loudly at parse time.
BASHISMS: tuple[tuple[str, str], ...] = (
    (r"&>", "`&>` backgrounds the command under dash instead of redirecting stderr"),
    (r"\[\[", "`[[ ]]` is a bash keyword; use `[ ]`"),
    (r"\bfunction\s+\w+\s*\(", "`function name()` is bash-only; use `name()`"),
    (r"\$\{[A-Za-z_][A-Za-z0-9_]*\[[@*]\]\}", "arrays are bash-only"),
    (r"\becho\s+-e\b", "`echo -e` is not portable; use printf"),
    (r"\bsource\s+", "`source` is bash-only; use `.`"),
)


def _hooks() -> dict[str, str]:
    """Return {"<relative path>::<hook>": script} for every POSIX hook found.

    Keyed by file *and* hook so a failure names which of the duplicated azd
    configs is broken.
    """
    found: dict[str, str] = {}
    for path in _azure_yaml_files():
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rel = path.relative_to(REPO_ROOT).as_posix()
        for name, spec in (doc.get("hooks") or {}).items():
            posix = (spec or {}).get("posix") or {}
            if posix.get("shell") == "sh" and posix.get("run"):
                found[f"{rel}::{name}"] = posix["run"]
    return found


def _strip_full_line_comments(script: str) -> str:
    """Drop whole-line `#` comments before scanning for bashisms.

    Comments cannot change shell semantics, and the comment explaining this very
    defect necessarily quotes `&>`. Only full-line comments are removed --
    stripping trailing ones correctly would require tracking quoting, and a
    trailing comment that happens to contain a bashism is a false positive worth
    accepting over a parser that could wrongly discard real code.
    """
    return "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    )


def test_there_is_at_least_one_posix_hook_to_check() -> None:
    """Guard the guard: if the hooks move, these tests must not silently pass."""
    files = _azure_yaml_files()
    assert files, "no azure.yaml found anywhere in the repo -- this lock is inert"

    hooks = _hooks()
    assert hooks, (
        "no `shell: sh` hooks found in any azure.yaml -- either the hooks were "
        "removed or their shape changed, and this regression lock is now inert"
    )

    # The root config is the one azd loads, because the workflows run azd from
    # the repository root. If it ever stops carrying a preprovision hook this
    # assertion should be revisited deliberately, not deleted to get to green.
    assert any(k.startswith("azure.yaml::preprovision") for k in hooks), (
        "the root azure.yaml has no preprovision hook; it is the config azd "
        f"actually reads. Hooks discovered: {sorted(hooks)}"
    )


def test_every_duplicated_azd_config_is_checked() -> None:
    """azd has no include mechanism, so duplicated configs drift independently.

    A fix applied to one copy is silently inert. This asserts the scan covers
    every copy, so the next person cannot fix one and believe they are done.
    """
    files = [p.relative_to(REPO_ROOT).as_posix() for p in _azure_yaml_files()]
    checked = {k.split("::", 1)[0] for k in _hooks()}
    missing = [f for f in files if f not in checked]
    assert not missing, (
        f"azd config(s) {missing} declare no POSIX hooks and so are unchecked; "
        "confirm that is intentional rather than a hook that lost its shell"
    )


@pytest.mark.parametrize("hook_name", sorted(_hooks()))
def test_posix_hook_contains_no_bashisms(hook_name: str) -> None:
    script = _strip_full_line_comments(_hooks()[hook_name])
    for pattern, why in BASHISMS:
        match = re.search(pattern, script)
        assert match is None, (
            f"hook `{hook_name}` declares `shell: sh` but uses a bash-only "
            f"construct {match.group(0)!r} at offset {match.start()}: {why}. "
            "Under dash this changes the meaning of the script instead of "
            "failing, which is how a deployment-blocking bug hides."
        )


@pytest.mark.parametrize("hook_name", sorted(_hooks()))
def test_posix_hook_parses_under_a_real_posix_shell(hook_name: str) -> None:
    """Parse each hook with an actual POSIX shell, not a bash approximation.

    `sh -n` parses without executing, so this is safe: no Azure calls are made.
    Skips rather than passes where no POSIX shell exists (e.g. a bare Windows
    dev box), so absence of a shell can never be mistaken for a clean result.
    """
    shell = shutil.which("dash") or shutil.which("sh")
    if not shell:
        pytest.skip("no POSIX shell available to parse-check the hook")

    script = _hooks()[hook_name].replace("\r\n", "\n")
    result = subprocess.run(
        [shell, "-n"],
        input=script,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"hook `{hook_name}` is not valid POSIX shell:\n{result.stderr.strip()}"
    )


def test_the_specific_regression_the_az_check_is_posix() -> None:
    """Pin the exact construction, in *every* copy of the hook.

    Checked across all discovered configs rather than one, because fixing a
    single copy is exactly the mistake that made this defect recur.
    """
    checks = (
        ("command -v az", "command -v az >/dev/null 2>&1"),
        ("az account show", "az account show >/dev/null 2>&1"),
    )
    seen = 0
    for key, script in _hooks().items():
        for fragment, required in checks:
            if fragment not in script:
                continue
            seen += 1
            assert required in script, (
                f"{key}: `{fragment}` must use POSIX redirection "
                f"(`{required}`). This is the check that reported "
                "'Azure CLI is not installed' while printing /usr/bin/az on "
                "the next line, and it blocked every automated deployment."
            )
    assert seen, (
        "no az presence/login check found in any hook -- the regression this "
        "pins has moved or been removed; do not assume it is safe"
    )
