"""Service for installing optional database provider packages via pip.

Runs ``pip install vector-inspector[<provider>]`` in a subprocess using the
same Python executable that is running the app.

Security note
-------------
The ``provider_id`` argument is validated against the known ``PROVIDERS``
registry before any subprocess is launched, so arbitrary package names cannot
be injected through provider selection.
"""

import subprocess
import sys
from collections.abc import Callable
from typing import Optional

from vector_inspector.core.provider_detection import PROVIDERS

# Immutable set of allowed provider IDs — the only values that may appear in
# the pip install command.  Any other value raises ``ValueError`` immediately.
_VALID_PROVIDER_IDS: frozenset[str] = frozenset(p["id"] for p in PROVIDERS)


def get_install_command(provider_id: str) -> list[str]:
    """Return the subprocess argv list for installing a provider.

    Args:
        provider_id: A known provider identifier (e.g. ``"chromadb"``).

    Returns:
        Command list suitable for ``subprocess.Popen``.

    Raises:
        ValueError: If ``provider_id`` is not in the known registry.
    """
    if provider_id not in _VALID_PROVIDER_IDS:
        raise ValueError(f"Unknown provider: {provider_id!r}")
    return [sys.executable, "-m", "pip", "install", f"vector-inspector[{provider_id}]"]


def install_provider(
    provider_id: str,
    on_output: Optional[Callable[[str], None]] = None,
) -> tuple[int, str]:
    """Install a provider package using pip.

    Validates ``provider_id`` against the known registry, then runs pip in a
    subprocess.  Combined stdout+stderr is returned alongside the exit code.

    Args:
        provider_id: A known provider identifier (e.g. ``"chromadb"``).
        on_output: Optional callback invoked with each output line as it
            arrives.  Called from the calling thread (not a background thread).

    Returns:
        ``(returncode, combined_output)`` — ``returncode == 0`` means success.

    Raises:
        ValueError: If ``provider_id`` is not a known provider.
    """
    cmd = get_install_command(provider_id)
    output_lines: list[str] = []

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            output_lines.append(line)
            if on_output:
                on_output(line)
        process.wait()
        return process.returncode, "".join(output_lines)
    except Exception as exc:
        error_msg = f"Failed to launch pip: {exc}"
        if on_output:
            on_output(error_msg + "\n")
        return -1, error_msg


# ---------------------------------------------------------------------------
# Feature group install
# ---------------------------------------------------------------------------

_VALID_FEATURE_IDS: frozenset[str] = frozenset(["viz", "embeddings", "clip", "documents"])

# Maps each feature group to the versioned pip specs (used for tooltip display).
_FEATURE_PACKAGE_SPECS: dict[str, list[str]] = {
    "viz": ["scikit-learn>=1.3.0", "umap-learn>=0.5.5", "hdbscan>=0.8.41"],
    "embeddings": ["sentence-transformers>=2.2.0", "fastembed>=0.7.4", "hf-xet>=1.2.0"],
    "clip": ["torch>=2.0.0", "transformers>=4.40.0", "Pillow>=10.0.0"],
    "documents": ["pypdf>=4.0.0", "python-docx>=1.1.0"],
}

# Maps each feature group to bare package names for pip uninstall (no version specifiers).
_FEATURE_PACKAGES: dict[str, list[str]] = {
    fid: [s.split(">")[0].split("=")[0].split("<")[0].split("!")[0] for s in specs]
    for fid, specs in _FEATURE_PACKAGE_SPECS.items()
}


def get_feature_install_command(feature_id: str) -> list[str]:
    """Return the subprocess argv list for installing a feature group.

    Args:
        feature_id: A known feature identifier (e.g. ``"viz"``).

    Returns:
        Command list suitable for ``subprocess.Popen``.

    Raises:
        ValueError: If ``feature_id`` is not a recognised feature.
    """
    if feature_id not in _VALID_FEATURE_IDS:
        raise ValueError(f"Unknown feature: {feature_id!r}")
    return [sys.executable, "-m", "pip", "install", f"vector-inspector[{feature_id}]"]


def install_feature(
    feature_id: str,
    on_output: Optional[Callable[[str], None]] = None,
) -> tuple[int, str]:
    """Install a feature-group package using pip.

    Validates ``feature_id`` against the known feature registry, then runs pip
    in a subprocess.  Combined stdout+stderr is returned alongside the exit code.

    Args:
        feature_id: A known feature identifier (e.g. ``"viz"``).
        on_output: Optional callback invoked with each output line as it
            arrives.  Called from the calling thread.

    Returns:
        ``(returncode, combined_output)`` — ``returncode == 0`` means success.

    Raises:
        ValueError: If ``feature_id`` is not a recognised feature.
    """
    cmd = get_feature_install_command(feature_id)
    output_lines: list[str] = []

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            output_lines.append(line)
            if on_output:
                on_output(line)
        process.wait()
        return process.returncode, "".join(output_lines)
    except Exception as exc:
        error_msg = f"Failed to launch pip: {exc}"
        if on_output:
            on_output(error_msg + "\n")
        return -1, error_msg


# ---------------------------------------------------------------------------
# Feature group uninstall
# ---------------------------------------------------------------------------


def get_feature_uninstall_command(feature_id: str) -> list[str]:
    """Return the subprocess argv list for uninstalling a feature group's packages.

    Args:
        feature_id: A known feature identifier (e.g. ``"viz"``).

    Returns:
        Command list suitable for ``subprocess.Popen``.

    Raises:
        ValueError: If ``feature_id`` is not a recognised feature.
    """
    if feature_id not in _VALID_FEATURE_IDS:
        raise ValueError(f"Unknown feature: {feature_id!r}")
    packages = _FEATURE_PACKAGES.get(feature_id, [])
    return [sys.executable, "-m", "pip", "uninstall", "-y"] + packages


def uninstall_feature(
    feature_id: str,
    on_output: Optional[Callable[[str], None]] = None,
) -> tuple[int, str]:
    """Uninstall a feature group's packages using pip.

    Validates ``feature_id`` against the known feature registry, then runs
    ``pip uninstall -y`` for each associated package in a subprocess.

    Args:
        feature_id: A known feature identifier (e.g. ``"viz"``).
        on_output: Optional callback invoked with each output line.


    Returns:
        ``(returncode, combined_output)`` — ``returncode == 0`` means success.

    Raises:
        ValueError: If ``feature_id`` is not a recognised feature.
    """
    cmd = get_feature_uninstall_command(feature_id)
    output_lines: list[str] = []

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            output_lines.append(line)
            if on_output:
                on_output(line)
        process.wait()
        return process.returncode, "".join(output_lines)
    except Exception as exc:
        error_msg = f"Failed to launch pip: {exc}"
        if on_output:
            on_output(error_msg + "\n")
        return -1, error_msg


# ---------------------------------------------------------------------------
# Provider uninstall
# ---------------------------------------------------------------------------

# Maps each provider id to the versioned pip specs (used for tooltip display).
_PROVIDER_PACKAGE_SPECS: dict[str, list[str]] = {
    "chromadb": ["chromadb>=0.4.22"],
    "qdrant": ["qdrant-client>=1.7.0"],
    "pinecone": ["pinecone>=8.0.0"],
    "lancedb": ["lancedb>=0.27.0", "pyarrow>=14.0.0"],
    "pgvector": ["psycopg2-binary>=2.9.11", "pgvector>=0.4.2"],
    "weaviate": ["weaviate-client>=4.19.2"],
    "milvus": ["pymilvus>=2.6.8"],
}

# Maps each provider id to bare package names for pip uninstall (no version specifiers).
_PROVIDER_PACKAGES: dict[str, list[str]] = {
    pid: [s.split(">")[0].split("=")[0].split("<")[0].split("!")[0] for s in specs]
    for pid, specs in _PROVIDER_PACKAGE_SPECS.items()
}


def get_provider_uninstall_command(provider_id: str) -> list[str]:
    """Return the subprocess argv list for uninstalling a provider's packages.

    Args:
        provider_id: A known provider identifier (e.g. ``"chromadb"``).

    Returns:
        Command list suitable for ``subprocess.Popen``.

    Raises:
        ValueError: If ``provider_id`` is not a recognised provider.
    """
    if provider_id not in _VALID_PROVIDER_IDS:
        raise ValueError(f"Unknown provider: {provider_id!r}")
    packages = _PROVIDER_PACKAGES.get(provider_id, [])
    return [sys.executable, "-m", "pip", "uninstall", "-y"] + packages


def uninstall_provider(
    provider_id: str,
    on_output: Optional[Callable[[str], None]] = None,
) -> tuple[int, str]:
    """Uninstall a provider's packages using pip.

    Validates ``provider_id`` against the known registry, then runs
    ``pip uninstall -y`` for each associated package in a subprocess.

    Args:
        provider_id: A known provider identifier (e.g. ``"chromadb"``).
        on_output: Optional callback invoked with each output line.

    Returns:
        ``(returncode, combined_output)`` — ``returncode == 0`` means success.

    Raises:
        ValueError: If ``provider_id`` is not a recognised provider.
    """
    cmd = get_provider_uninstall_command(provider_id)
    output_lines: list[str] = []

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            output_lines.append(line)
            if on_output:
                on_output(line)
        process.wait()
        return process.returncode, "".join(output_lines)
    except Exception as exc:
        error_msg = f"Failed to launch pip: {exc}"
        if on_output:
            on_output(error_msg + "\n")
        return -1, error_msg
