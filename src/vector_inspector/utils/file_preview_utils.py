"""Utilities for detecting file paths in metadata and loading file previews."""

import mimetypes
import os
import pathlib
from typing import Any, Literal

IMAGE_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"})

CANDIDATE_KEYS: tuple[str, ...] = (
    "file_path",
    "frame_path",
    "source",
    "path",
    "filename",
    "image_path",
    "thumbnail",
)


def is_text_file(path: str) -> bool:
    """Return True if the file should be treated as plain text.

    Uses mimetypes first; falls back to a null-byte sniff of the first 8 KB.
    Never raises on read errors — returns False instead.
    """
    mime, _ = mimetypes.guess_type(path)
    if mime is not None:
        return mime.startswith("text/")
    # Null-byte sniff fallback (same heuristic as git)
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(8192)
        return b"\x00" not in chunk
    except OSError:
        return False


def file_type(path: str) -> Literal["image", "text", "unknown"]:
    """Classify a path as 'image', 'text', or 'unknown'.

    Images are matched against IMAGE_EXTENSIONS.
    Text is detected via mimetypes.guess_type; falls back to a null-byte sniff
    of the first 8 KB if mimetypes returns None or a non-text/ MIME type.
    .pdf and .docx are classified as 'unknown' here — the ingestion service
    handles them separately.
    """
    suffix = pathlib.Path(path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in {".pdf", ".docx"}:
        return "unknown"
    if is_text_file(path):
        return "text"
    return "unknown"


def _looks_like_path(value: str) -> bool:
    """Return True if value structurally resembles a file path."""
    if not value or len(value) >= 1024:
        return False
    return pathlib.Path(value).is_absolute() or ("/" in value or "\\" in value)


def find_preview_paths(metadata: dict[str, Any]) -> list[str]:
    """Return up to 3 valid, existing file paths found in metadata.

    Candidate keys are checked first for a fast path; if none match, the
    remaining string-valued fields are scanned (capped at 20 fields).
    """
    found: list[str] = []

    # Priority: candidate keys first
    for key in CANDIDATE_KEYS:
        if key in metadata:
            value = metadata[key]
            if isinstance(value, str) and _looks_like_path(value) and os.path.isfile(value):
                if value not in found:
                    found.append(value)
                if len(found) == 3:
                    return found

    # Broader scan over remaining string fields (cap at 20)
    scanned = 0
    for key, value in metadata.items():
        if key in CANDIDATE_KEYS:
            continue
        if scanned >= 20:
            break
        if isinstance(value, str) and _looks_like_path(value) and os.path.isfile(value):
            if value not in found:
                found.append(value)
            if len(found) == 3:
                return found
        scanned += 1

    return found


def read_text_preview(path: str, max_lines: int = 100, max_bytes: int = 8192) -> tuple[str, bool]:
    """Return (content, truncated).  Raises OSError on failure."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines: list[str] = []
        total_bytes = 0
        truncated = False
        for line in fh:
            line_bytes = len(line.encode("utf-8"))
            if total_bytes + line_bytes > max_bytes:
                truncated = True
                break
            lines.append(line)
            total_bytes += line_bytes
            if len(lines) >= max_lines:
                # Check if there is more content
                remaining = fh.read(1)
                truncated = bool(remaining)
                break
    return "".join(lines), truncated


def load_image_pixmap(path: str, max_w: int = 320, max_h: int = 240):  # -> QPixmap
    """Load, decode, and scale an image.  Raises OSError or ValueError on failure.

    Returns a QPixmap.  Qt must be available when this function is called.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap

    pixmap = QPixmap(path)
    if pixmap.isNull():
        raise ValueError(f"Could not load image: {path}")
    if pixmap.width() > max_w or pixmap.height() > max_h:
        pixmap = pixmap.scaled(
            max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    return pixmap
