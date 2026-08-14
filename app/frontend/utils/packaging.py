"""
Deterministic ZIP packaging for Streamlit downloads.

Streamlit serves ``st.download_button`` payloads from its in-memory
MediaFileManager. A file's ID is ``sha224(content + mimetype + filename)`` and
files are tracked per (session, widget coordinates): when the file at a given
set of coordinates is replaced, the previous one is deleted. An archive whose
bytes change on every rerun therefore registers a new ID at the same
coordinates each run, evicting the file the browser is still pointing at. The
download then fails with ``MediaFileHandler: Missing file <hash>.zip`` and a
404 on ``/media/<hash>.zip``.

Building the archive deterministically keeps the ID stable, so the file is
reused across reruns and the download URL stays valid.
"""

from __future__ import annotations

import io
import zipfile
from typing import Mapping

# ``ZipFile.writestr`` stamps members with the current local time when handed a
# plain filename, which on its own would make every rebuild byte-different.
# 1980-01-01 is the earliest instant the ZIP format can represent.
ZIP_MEMBER_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def build_deterministic_zip(members: Mapping[str, str]) -> bytes:
    """Return ZIP bytes that are byte-identical for identical ``members``.

    ``members`` maps archive filename to text content. Members are written in
    sorted name order so that dict ordering cannot change the output.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=ZIP_MEMBER_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, members[name])
    return buffer.getvalue()
