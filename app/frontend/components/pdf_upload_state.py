"""Pure state decisions for replacing a PDF upload."""

import hashlib


def pdf_digest(content: bytes | None) -> str:
    """Return a stable content digest used to tie an extraction to its source PDF."""
    if not content:
        return ""
    return hashlib.sha256(content).hexdigest()


def is_replacement_upload(
    current_bytes: bytes | None,
    current_filename: str | None,
    uploaded_bytes: bytes,
    uploaded_filename: str,
) -> bool:
    """Return whether a newly selected file replaces a persisted upload."""
    return (
        current_bytes is not None
        and (current_bytes != uploaded_bytes or current_filename != uploaded_filename)
    )
