"""Tests for version utility."""

import sys

from vector_inspector.utils.version import get_app_version


def test_returns_string():
    version = get_app_version()
    assert isinstance(version, str)


def test_returns_non_empty():
    version = get_app_version()
    assert len(version) > 0  # either real version or "?"


def test_returns_question_mark_when_package_not_found(monkeypatch):
    """PackageNotFoundError from version() → returns '?'."""
    import importlib.metadata as im
    from importlib.metadata import PackageNotFoundError

    def raise_exc(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(im, "version", raise_exc)
    result = get_app_version()
    assert result == "?"


def test_returns_question_mark_when_importlib_metadata_unavailable(monkeypatch):
    """When importlib.metadata is unavailable AND importlib_metadata fallback also missing → '?'."""
    # Hide both importlib.metadata and importlib_metadata
    monkeypatch.setitem(sys.modules, "importlib.metadata", None)
    monkeypatch.setitem(sys.modules, "importlib_metadata", None)
    result = get_app_version()
    assert result == "?"
