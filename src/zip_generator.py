from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile


def build_zip(files: dict[str, bytes]) -> bytes:
    """Return a ZIP file as bytes from a filename -> content mapping."""
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as zip_file:
        for filename, content in files.items():
            zip_file.writestr(filename, content)
    buffer.seek(0)
    return buffer.getvalue()
