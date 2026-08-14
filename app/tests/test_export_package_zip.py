"""
Tests for deterministic ZIP packaging of policy export downloads.

Regression cover for the broken "Download Complete Package (ZIP)" button.
Streamlit serves download payloads from its MediaFileManager, keyed by
``sha224(content + mimetype + filename)``, and deletes the file previously
registered at the same widget coordinates. The export page rebuilt its archive
on every rerun with member timestamps taken from the wall clock (and a
``Generated on:`` line in the README), so each rerun produced different bytes,
evicted the prior archive, and the browser's download URL 404'd with
``MediaFileHandler: Missing file <hash>.zip``.

Run from app/ with:
  PYTHONPATH=frontend python -m pytest tests/test_export_package_zip.py -q -p no:cacheprovider
"""

import time
import zipfile
from io import BytesIO

from utils.packaging import ZIP_MEMBER_TIMESTAMP, build_deterministic_zip


_MEMBERS = {
    "framework_initiative.json": '{"name": "demo"}',
    "Deploy-frameworkInitiative.ps1": "Write-Host 'deploy'",
    "README.md": "# Demo package",
}


def test_same_inputs_produce_byte_identical_zip_across_time():
    """The whole point: identical inputs must hash to the same media file ID.

    Sleeping past a clock tick is what broke the old implementation, because
    ``writestr`` stamped each member with the current local time.
    """
    first = build_deterministic_zip(_MEMBERS)
    time.sleep(1.1)
    second = build_deterministic_zip(_MEMBERS)

    assert first == second


def test_member_timestamps_are_pinned_not_wall_clock():
    archive = zipfile.ZipFile(BytesIO(build_deterministic_zip(_MEMBERS)))

    assert archive.namelist(), "archive should not be empty"
    for info in archive.infolist():
        assert info.date_time == ZIP_MEMBER_TIMESTAMP


def test_member_order_does_not_affect_output():
    reordered = dict(reversed(list(_MEMBERS.items())))

    assert build_deterministic_zip(_MEMBERS) == build_deterministic_zip(reordered)


def test_changed_content_still_changes_the_bytes():
    """Determinism must not become staleness: new content must produce a new ID."""
    changed = {**_MEMBERS, "README.md": "# Different package"}

    assert build_deterministic_zip(_MEMBERS) != build_deterministic_zip(changed)


def test_contents_round_trip_intact():
    archive = zipfile.ZipFile(BytesIO(build_deterministic_zip(_MEMBERS)))

    assert sorted(archive.namelist()) == sorted(_MEMBERS)
    for name, content in _MEMBERS.items():
        assert archive.read(name).decode() == content
