#!/usr/bin/env bash

set -euo pipefail

echo "Installing Vector Inspector..."

# Prefer python3, then python
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "Python is required but not installed." >&2
    exit 1
fi

echo "Using interpreter: $PY"

# If not inside a virtualenv, install with --user as a safe fallback
USER_FLAG=""
if [ -z "${VIRTUAL_ENV:-}" ]; then
    USER_FLAG="--user"
fi

echo "Upgrading pip and installing/upgrading vector-inspector..."
# Try to upgrade pip; if it fails we warn and still attempt to install the
# package with the detected interpreter. This avoids a half-installed state on
# systems where pip cannot be upgraded, while still surfacing the pip error.
PIP_UPGRADE_FAILED=0
if ! "$PY" -m pip install --upgrade pip --no-cache-dir; then
    echo "Warning: pip upgrade failed; will attempt package install anyway." >&2
    PIP_UPGRADE_FAILED=1
fi

if ! "$PY" -m pip install --upgrade vector-inspector $USER_FLAG --no-cache-dir; then
    echo "Failed to install vector-inspector." >&2
    if [ "$PIP_UPGRADE_FAILED" -eq 1 ]; then
        echo "Install failed and pip upgrade previously failed; aborting." >&2
    fi
    exit 1
fi

echo "Launch: preferring console entrypoint if present."
if command -v vector-inspector >/dev/null 2>&1; then
    if command -v nohup >/dev/null 2>&1; then
        nohup vector-inspector >/dev/null 2>&1 &
    else
        vector-inspector >/dev/null 2>&1 &
    fi
else
    # Fall back to running the module with the same interpreter
    if command -v nohup >/dev/null 2>&1; then
        nohup "$PY" -m vector_inspector >/dev/null 2>&1 &
    else
        "$PY" -m vector_inspector >/dev/null 2>&1 &
    fi
fi

echo "Installation finished."

