"""Tests for provider_install_service."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.services.provider_install_service import (
    _FEATURE_PACKAGE_SPECS,
    _FEATURE_PACKAGES,
    _PROVIDER_PACKAGE_SPECS,
    _PROVIDER_PACKAGES,
    _VALID_FEATURE_IDS,
    _VALID_PROVIDER_IDS,
    get_feature_install_command,
    get_feature_uninstall_command,
    get_install_command,
    get_provider_uninstall_command,
    install_feature,
    install_provider,
    uninstall_feature,
    uninstall_provider,
)

# ---------------------------------------------------------------------------
# get_install_command
# ---------------------------------------------------------------------------


def test_get_install_command_known_provider():
    cmd = get_install_command("chromadb")
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "pip"]
    assert "vector-inspector[chromadb]" in cmd[-1]


def test_get_install_command_all_known_providers():
    for pid in _VALID_PROVIDER_IDS:
        cmd = get_install_command(pid)
        assert f"vector-inspector[{pid}]" in cmd[-1]


def test_get_install_command_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_install_command("evil; rm -rf /")


def test_get_install_command_empty_string_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_install_command("")


def test_get_install_command_injection_attempt_raises():
    with pytest.raises(ValueError):
        get_install_command("chromadb && malicious")


# ---------------------------------------------------------------------------
# install_provider
# ---------------------------------------------------------------------------


def _make_fake_process(returncode: int, lines: list[str]):
    """Return a mock Popen that simulates pip output."""
    fake = MagicMock()
    fake.stdout.__iter__ = MagicMock(return_value=iter(lines))
    fake.returncode = returncode
    fake.wait = MagicMock()
    return fake


def test_install_provider_success(monkeypatch):
    fake_proc = _make_fake_process(0, ["Successfully installed chromadb\n"])

    with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
        returncode, output = install_provider("chromadb")

    assert returncode == 0
    assert "Successfully installed" in output
    # Verify the command used sys.executable — never a bare "pip"
    cmd_used = mock_popen.call_args[0][0]
    assert cmd_used[0] == sys.executable
    assert "vector-inspector[chromadb]" in cmd_used[-1]


def test_install_provider_failure(monkeypatch):
    fake_proc = _make_fake_process(1, ["ERROR: some error\n"])

    with patch("subprocess.Popen", return_value=fake_proc):
        returncode, output = install_provider("qdrant")

    assert returncode == 1
    assert "ERROR" in output


def test_install_provider_calls_on_output_callback(monkeypatch):
    lines = ["line1\n", "line2\n"]
    fake_proc = _make_fake_process(0, lines)

    received: list[str] = []
    with patch("subprocess.Popen", return_value=fake_proc):
        install_provider("chromadb", on_output=received.append)

    assert received == lines


def test_install_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        install_provider("not_a_provider")


def test_install_provider_popen_exception_returns_minus_one(monkeypatch):
    with patch("subprocess.Popen", side_effect=OSError("not found")):
        returncode, output = install_provider("chromadb")

    assert returncode == -1
    assert "Failed to launch pip" in output


def test_install_provider_popen_exception_calls_on_output(monkeypatch):
    collected: list[str] = []
    with patch("subprocess.Popen", side_effect=OSError("boom")):
        install_provider("chromadb", on_output=collected.append)

    assert any("Failed to launch pip" in s for s in collected)


# ---------------------------------------------------------------------------
# get_feature_install_command
# ---------------------------------------------------------------------------


def test_get_feature_install_command_known_feature():
    cmd = get_feature_install_command("viz")
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "pip"]
    assert "vector-inspector[viz]" in cmd[-1]


def test_get_feature_install_command_all_known_features():
    for fid in _VALID_FEATURE_IDS:
        cmd = get_feature_install_command(fid)
        assert f"vector-inspector[{fid}]" in cmd[-1]


def test_get_feature_install_command_unknown_raises():
    with pytest.raises(ValueError, match="Unknown feature"):
        get_feature_install_command("hacky; rm -rf /")


def test_get_feature_install_command_empty_string_raises():
    with pytest.raises(ValueError, match="Unknown feature"):
        get_feature_install_command("")


# ---------------------------------------------------------------------------
# install_feature
# ---------------------------------------------------------------------------


def test_install_feature_success(monkeypatch):
    fake_proc = _make_fake_process(0, ["Successfully installed sklearn\n"])

    with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
        returncode, output = install_feature("viz")

    assert returncode == 0
    assert "Successfully installed" in output
    cmd_used = mock_popen.call_args[0][0]
    assert cmd_used[0] == sys.executable
    assert "vector-inspector[viz]" in cmd_used[-1]


def test_install_feature_failure(monkeypatch):
    fake_proc = _make_fake_process(1, ["ERROR: some error\n"])

    with patch("subprocess.Popen", return_value=fake_proc):
        returncode, output = install_feature("embeddings")

    assert returncode == 1
    assert "ERROR" in output


def test_install_feature_unknown_raises():
    with pytest.raises(ValueError, match="Unknown feature"):
        install_feature("not_a_feature")


def test_install_feature_popen_exception_returns_minus_one():
    with patch("subprocess.Popen", side_effect=OSError("not found")):
        returncode, output = install_feature("viz")

    assert returncode == -1
    assert "Failed to launch pip" in output


def test_install_feature_calls_on_output_callback():
    lines = ["line1\n", "line2\n"]
    fake_proc = _make_fake_process(0, lines)

    received: list[str] = []
    with patch("subprocess.Popen", return_value=fake_proc):
        install_feature("viz", on_output=received.append)

    assert received == lines


@pytest.mark.parametrize("feature_id", ["viz", "embeddings", "clip", "documents"])
def test_valid_feature_ids_contain_expected_features(feature_id):
    assert feature_id in _VALID_FEATURE_IDS


# ---------------------------------------------------------------------------
# _FEATURE_PACKAGES
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("feature_id", ["viz", "embeddings", "clip", "documents"])
def test_feature_packages_defined_for_all_features(feature_id):
    assert feature_id in _FEATURE_PACKAGES
    assert len(_FEATURE_PACKAGES[feature_id]) > 0


# ---------------------------------------------------------------------------
# get_feature_uninstall_command
# ---------------------------------------------------------------------------


def test_get_feature_uninstall_command_starts_with_executable():
    cmd = get_feature_uninstall_command("viz")
    assert cmd[0] == sys.executable


def test_get_feature_uninstall_command_uses_pip_uninstall_y():
    cmd = get_feature_uninstall_command("viz")
    assert cmd[1:4] == ["-m", "pip", "uninstall"]
    assert "-y" in cmd


def test_get_feature_uninstall_command_includes_packages():
    cmd = get_feature_uninstall_command("viz")
    # scikit-learn, umap-learn, hdbscan should all appear
    for pkg in _FEATURE_PACKAGES["viz"]:
        assert pkg in cmd


def test_get_feature_uninstall_command_unknown_raises():
    with pytest.raises(ValueError, match="Unknown feature"):
        get_feature_uninstall_command("not_a_feature")


# ---------------------------------------------------------------------------
# uninstall_feature
# ---------------------------------------------------------------------------


def test_uninstall_feature_success():
    fake_proc = _make_fake_process(0, ["Successfully uninstalled scikit-learn\n"])

    with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
        returncode, output = uninstall_feature("viz")

    assert returncode == 0
    assert "Successfully uninstalled" in output
    cmd_used = mock_popen.call_args[0][0]
    assert cmd_used[0] == sys.executable
    assert "-y" in cmd_used


def test_uninstall_feature_failure():
    fake_proc = _make_fake_process(1, ["WARNING: Skipping scikit-learn\n"])

    with patch("subprocess.Popen", return_value=fake_proc):
        returncode, output = uninstall_feature("viz")

    assert returncode == 1


def test_uninstall_feature_unknown_raises():
    with pytest.raises(ValueError, match="Unknown feature"):
        uninstall_feature("not_a_feature")


def test_uninstall_feature_popen_exception_returns_minus_one():
    with patch("subprocess.Popen", side_effect=OSError("gone")):
        returncode, output = uninstall_feature("documents")

    assert returncode == -1
    assert "Failed to launch pip" in output


def test_uninstall_feature_calls_on_output_callback():
    lines = ["Uninstalling pypdf\n", "done\n"]
    fake_proc = _make_fake_process(0, lines)

    received: list[str] = []
    with patch("subprocess.Popen", return_value=fake_proc):
        uninstall_feature("documents", on_output=received.append)

    assert received == lines


# ---------------------------------------------------------------------------
# _PROVIDER_PACKAGES
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider_id", ["chromadb", "qdrant", "pinecone", "lancedb", "pgvector", "weaviate", "milvus"])
def test_provider_packages_defined_for_all_providers(provider_id):
    assert provider_id in _PROVIDER_PACKAGES
    assert len(_PROVIDER_PACKAGES[provider_id]) > 0


# ---------------------------------------------------------------------------
# get_provider_uninstall_command
# ---------------------------------------------------------------------------


def test_get_provider_uninstall_command_starts_with_executable():
    cmd = get_provider_uninstall_command("chromadb")
    assert cmd[0] == sys.executable


def test_get_provider_uninstall_command_uses_pip_uninstall_y():
    cmd = get_provider_uninstall_command("chromadb")
    assert cmd[1:4] == ["-m", "pip", "uninstall"]
    assert "-y" in cmd


def test_get_provider_uninstall_command_includes_packages():
    cmd = get_provider_uninstall_command("lancedb")
    for pkg in _PROVIDER_PACKAGES["lancedb"]:
        assert pkg in cmd


def test_get_provider_uninstall_command_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider_uninstall_command("not_a_provider")


# ---------------------------------------------------------------------------
# uninstall_provider
# ---------------------------------------------------------------------------


def test_uninstall_provider_success():
    fake_proc = _make_fake_process(0, ["Successfully uninstalled chromadb\n"])

    with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
        returncode, output = uninstall_provider("chromadb")

    assert returncode == 0
    assert "Successfully uninstalled" in output
    cmd_used = mock_popen.call_args[0][0]
    assert cmd_used[0] == sys.executable
    assert "-y" in cmd_used


def test_uninstall_provider_failure():
    fake_proc = _make_fake_process(1, ["WARNING: Skipping chromadb\n"])

    with patch("subprocess.Popen", return_value=fake_proc):
        returncode, output = uninstall_provider("chromadb")

    assert returncode == 1


def test_uninstall_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        uninstall_provider("not_a_provider")


def test_uninstall_provider_popen_exception_returns_minus_one():
    with patch("subprocess.Popen", side_effect=OSError("gone")):
        returncode, output = uninstall_provider("qdrant")

    assert returncode == -1
    assert "Failed to launch pip" in output


def test_uninstall_provider_calls_on_output_callback():
    lines = ["Uninstalling qdrant-client\n", "done\n"]
    fake_proc = _make_fake_process(0, lines)

    received: list[str] = []
    with patch("subprocess.Popen", return_value=fake_proc):
        uninstall_provider("qdrant", on_output=received.append)

    assert received == lines


# ---------------------------------------------------------------------------
# _FEATURE_PACKAGE_SPECS and _PROVIDER_PACKAGE_SPECS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("feature_id", ["viz", "embeddings", "clip", "documents"])
def test_feature_package_specs_defined_for_all_features(feature_id):
    assert feature_id in _FEATURE_PACKAGE_SPECS
    assert len(_FEATURE_PACKAGE_SPECS[feature_id]) > 0


@pytest.mark.parametrize("feature_id", ["viz", "embeddings", "clip", "documents"])
def test_feature_package_specs_contain_version_specifiers(feature_id):
    """Every spec should contain a version constraint."""
    for spec in _FEATURE_PACKAGE_SPECS[feature_id]:
        assert ">=" in spec or "==" in spec, f"No version specifier in {spec!r}"


@pytest.mark.parametrize("feature_id", ["viz", "embeddings", "clip", "documents"])
def test_feature_packages_derived_from_specs(feature_id):
    """_FEATURE_PACKAGES bare names must be a subset of the spec package names."""
    spec_names = {s.split(">")[0].split("=")[0].split("<")[0].split("!")[0] for s in _FEATURE_PACKAGE_SPECS[feature_id]}
    assert set(_FEATURE_PACKAGES[feature_id]) == spec_names


@pytest.mark.parametrize("provider_id", ["chromadb", "qdrant", "pinecone", "lancedb", "pgvector", "weaviate", "milvus"])
def test_provider_package_specs_defined_for_all_providers(provider_id):
    assert provider_id in _PROVIDER_PACKAGE_SPECS
    assert len(_PROVIDER_PACKAGE_SPECS[provider_id]) > 0


@pytest.mark.parametrize("provider_id", ["chromadb", "qdrant", "pinecone", "lancedb", "pgvector", "weaviate", "milvus"])
def test_provider_package_specs_contain_version_specifiers(provider_id):
    """Every spec should contain a version constraint."""
    for spec in _PROVIDER_PACKAGE_SPECS[provider_id]:
        assert ">=" in spec or "==" in spec, f"No version specifier in {spec!r}"


@pytest.mark.parametrize("provider_id", ["chromadb", "qdrant", "pinecone", "lancedb", "pgvector", "weaviate", "milvus"])
def test_provider_packages_derived_from_specs(provider_id):
    """_PROVIDER_PACKAGES bare names must match the spec package names."""
    spec_names = {
        s.split(">")[0].split("=")[0].split("<")[0].split("!")[0] for s in _PROVIDER_PACKAGE_SPECS[provider_id]
    }
    assert set(_PROVIDER_PACKAGES[provider_id]) == spec_names
