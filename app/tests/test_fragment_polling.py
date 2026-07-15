"""Regression tests for isolated workflow progress polling."""

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = APP_ROOT / "frontend"
PDF_PAGE = FRONTEND_ROOT / "pages" / "5_🚀_PDF_Pipeline.py"
MAPPING_PAGE = FRONTEND_ROOT / "pages" / "2_🤖_AI_Mapping.py"


def test_streamlit_version_supports_fragments():
    requirements = (FRONTEND_ROOT / "requirements.txt").read_text()

    assert "streamlit==1.37.0" in requirements


def test_pdf_progress_uses_fragment_without_blocking_sleep():
    source = PDF_PAGE.read_text()

    assert "@st.fragment(run_every=_PDF_STATUS_POLL_INTERVAL)" in source
    assert "def _render_active_pdf_extraction_shell(" in source
    assert "with st.container(border=True):" in source
    assert 'st.markdown(f"#### 📄 Scanning {file_name}")' in source
    assert "_render_active_pdf_extraction_shell(" in source
    assert "_render_active_pdf_extraction(" in source
    assert "progress_slot = st.empty()" in source
    assert "activity_slot = st.empty()" in source
    assert "log_slot = st.empty()" in source
    assert "time.sleep(" not in source


def test_mapping_progress_uses_fragment_without_blocking_sleep():
    source = MAPPING_PAGE.read_text()

    assert "@st.fragment(run_every=_MAPPING_STATUS_POLL_INTERVAL)" in source
    assert "def _render_active_mapping_shell(" in source
    assert "with st.container(border=True):" in source
    assert 'st.markdown(f"#### 🤖 Mapping {st.session_state.framework_name}")' in source
    assert "_render_active_mapping_shell(" in source
    assert "_render_active_mapping_job(" in source
    assert "progress_slot = st.empty()" in source
    assert "activity_slot = st.empty()" in source
    assert "log_slot = st.empty()" in source
    assert "time.sleep(" not in source


def test_live_progress_shells_keep_static_labels_outside_fragment_slots():
    mapping_source = MAPPING_PAGE.read_text()
    pdf_source = PDF_PAGE.read_text()

    assert 'st.markdown("**Recent backend events**")' in mapping_source
    assert 'st.markdown("**Recent backend events**")' in pdf_source
    assert 'st.markdown("**Recent backend events**")' not in (
        mapping_source.split("def _render_mapping_progress")[1].split(
            "def _render_active_mapping_shell"
        )[0]
    )


def test_job_activity_uses_a_bounded_scroll_container():
    source = (FRONTEND_ROOT / "components" / "backend_log_viewer.py").read_text()

    assert "with st.container(height=200):" in source
    assert "for event in events[-12:]" in source


def test_workflow_start_reruns_are_not_caught_as_request_errors():
    mapping_source = MAPPING_PAGE.read_text()
    pdf_source = PDF_PAGE.read_text()

    assert (
        '            except Exception as e:\n'
        '                st.error(f"❌ Error starting batch mapping: {str(e)}")\n'
        '            else:\n'
        '                st.rerun()'
    ) in mapping_source
    assert (
        '        except Exception as e:\n'
        '            st.session_state.pdf_extracting = False\n'
        '            st.session_state.pdf_extraction_error = str(e)\n'
        '            update_task(task_id, status="failed", stage="failed", error=str(e))\n'
        '            st.error(f"❌ Could not submit PDF extraction: {e}")\n'
        '        else:\n'
        '            st.rerun()'
    ) in pdf_source
