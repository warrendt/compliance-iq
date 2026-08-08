"""Regression tests for the PDF upload / extraction restore rules.

These cover the state decisions behind two reported bugs:

* Selecting a different PDF displayed the *previous* document's controls, with
  the Extract button disabled, so the new file could never be scanned.
* "Clear & Start Over" cleared the UI only; re-uploading immediately restored
  the same stale extraction.

Both hinged on tying a completed extraction to the file it came from, which is
what :func:`pdf_digest` provides.
"""

from components.pdf_upload_state import is_replacement_upload, pdf_digest


ALPHA = b"%PDF-alpha-framework"
BETA = b"%PDF-beta-framework"


def test_digest_is_stable_for_identical_content():
    assert pdf_digest(ALPHA) == pdf_digest(b"%PDF-alpha-framework")


def test_digest_differs_across_documents():
    assert pdf_digest(ALPHA) != pdf_digest(BETA)


def test_digest_of_empty_or_missing_content_is_blank():
    assert pdf_digest(None) == ""
    assert pdf_digest(b"") == ""


def test_blank_digest_never_matches_a_completed_extraction():
    """No PDF loaded must not auto-restore anything."""
    assert pdf_digest(None) != pdf_digest(ALPHA)


def test_first_upload_is_not_a_replacement():
    assert not is_replacement_upload(None, None, ALPHA, "alpha.pdf")


def test_same_file_reselected_is_not_a_replacement():
    assert not is_replacement_upload(ALPHA, "alpha.pdf", ALPHA, "alpha.pdf")


def test_different_content_is_a_replacement():
    assert is_replacement_upload(ALPHA, "alpha.pdf", BETA, "beta.pdf")


def test_same_content_under_a_new_name_is_a_replacement():
    assert is_replacement_upload(ALPHA, "alpha.pdf", ALPHA, "renamed.pdf")
