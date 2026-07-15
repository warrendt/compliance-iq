"""Regression tests for responsive workflow-page content."""

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_PAGE = APP_ROOT / "frontend" / "pages" / "1_📁_Upload_Controls.py"
MAPPING_PAGE = APP_ROOT / "frontend" / "pages" / "2_🤖_AI_Mapping.py"
POLICY_EXPLORER_PAGE = APP_ROOT / "frontend" / "pages" / "6_🔍_Policy_Explorer.py"
EXPORT_POLICY_PAGE = APP_ROOT / "frontend" / "pages" / "4_📦_Export_Policy.py"
REVIEW_EDIT_PAGE = APP_ROOT / "frontend" / "pages" / "3_✏️_Review_Edit.py"


def test_upload_example_uses_a_responsive_dataframe():
    source = UPLOAD_PAGE.read_text()

    assert 'st.dataframe(' in source
    assert "use_container_width=True" in source
    assert "| SAMA-AC-01 |" not in source


def test_mapping_distinguishes_previous_mappings_during_active_run():
    source = MAPPING_PAGE.read_text()

    assert '"Previous Mappings"' in source
    assert (
        "if st.session_state.mappings and not st.session_state.mapping_in_progress:"
        in source
    )


def test_mapping_only_offers_cancellation_for_an_active_job():
    source = MAPPING_PAGE.read_text()

    active_job_section = source.split("# Single control test mode")[0]
    idle_section = source.split("# ── Idle: show start button")[1].split(
        "# Show existing mappings"
    )[0]

    assert 'key=f"cancel_mapping_{job_id}"' in active_job_section
    assert '"⏹️ Cancel"' not in idle_section


def test_pdf_clear_cancels_all_active_backend_jobs_and_mapping_shows_safe_limit():
    pdf_source = (APP_ROOT / "frontend" / "pages" / "5_🚀_PDF_Pipeline.py").read_text()
    mapping_source = MAPPING_PAGE.read_text()

    assert 'get_tasks_by_type("pdf_extraction")' in pdf_source
    assert ".cancel_pipeline_job(" in pdf_source
    assert "for task in active_pdf_tasks:" in pdf_source
    assert "_MAX_SAFE_MAPPING_CONCURRENCY = 10" in mapping_source
    assert "concurrency=concurrency" in mapping_source


def test_policy_explorer_explains_missing_delegated_arm_access():
    source = POLICY_EXPLORER_PAGE.read_text()

    assert "does not include an Azure Resource Manager token" in source
    assert "Sign In** button in the sidebar" not in source


def test_export_uses_south_africa_slz_defaults_and_token_guidance():
    source = EXPORT_POLICY_PAGE.read_text()

    assert 'value="southafricanorth,southafricawest"' in source
    assert "does not include an Azure Resource Manager token" in source
    assert "Sign in with Entra ID to deploy policies to Azure." not in source


def test_review_and_export_restore_the_latest_durable_workflow():
    export_source = EXPORT_POLICY_PAGE.read_text()
    review_source = REVIEW_EDIT_PAGE.read_text()

    assert "restore_workflow_state," in export_source
    assert "init_session_state()\nrestore_workflow_state()\nrender_sidebar()" in export_source
    assert 'st.session_state.pop("workflow_restored_notice", None)' in export_source
    assert "persist_workflow_state()" in export_source

    assert "from utils.state_init import init_session_state, restore_workflow_state" in review_source
    assert "init_session_state()\nrestore_workflow_state()\nrender_sidebar()" in review_source
