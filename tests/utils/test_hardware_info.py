"""Tests for hardware_info module."""

import sys

from vector_inspector.utils.hardware_info import get_hardware_info


def test_returns_dict():
    info = get_hardware_info()
    assert isinstance(info, dict)


def test_has_cpu_info():
    info = get_hardware_info()
    assert "cpu_count" in info
    assert "cpu_model" in info


def test_has_ram_key():
    info = get_hardware_info()
    assert "ram_total_gb" in info


def test_has_gpu_key():
    info = get_hardware_info()
    assert "gpu" in info


def test_does_not_raise():
    # Should complete without raising even if optional deps are absent
    try:
        get_hardware_info()
    except Exception as exc:
        raise AssertionError(f"get_hardware_info raised unexpectedly: {exc}") from exc


def test_cpu_fallback_without_psutil(monkeypatch):
    """Without psutil, falls back to os.cpu_count() for CPU info."""
    monkeypatch.setitem(sys.modules, "psutil", None)
    info = get_hardware_info()
    assert "cpu_count" in info
    assert "ram_total_gb" in info  # should be None when psutil unavailable


def test_gpu_fallback_without_gputil(monkeypatch):
    """Without GPUtil, info['gpu'] is None."""
    monkeypatch.setitem(sys.modules, "GPUtil", None)
    info = get_hardware_info()
    assert info["gpu"] is None


def test_gpu_fallback_gputil_raises(monkeypatch):
    """If GPUtil raises an unexpected exception, info['gpu'] is None."""
    import types

    fake_gputil = types.ModuleType("GPUtil")
    fake_gputil.getGPUs = lambda: (_ for _ in ()).throw(RuntimeError("gpu error"))
    monkeypatch.setitem(sys.modules, "GPUtil", fake_gputil)
    info = get_hardware_info()
    assert info["gpu"] is None
