"""Source-level regressions for separated semantic Version History."""

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PAGE = APP_ROOT / "frontend" / "pages" / "9_Version_History.py"


def test_version_history_separates_mcsb_slz_and_full_union_streams():
    source = PAGE.read_text()

    assert '"mcsb_initiative", "🛡️ MCSB Initiatives"' in source
    assert '"slz_initiative", "🏛️ SLZ Initiatives"' in source
    assert '"comparison_union", "🎯 Full-Union Initiatives"' in source
    assert 'semantic_version = v.get("semantic_version", "1.0.0")' in source
    assert 'f"📦 {policy_name} · v{semantic_version}' in source
