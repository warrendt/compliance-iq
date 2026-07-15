"""Pure state decisions for replacing a PDF upload."""


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
