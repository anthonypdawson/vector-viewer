"""Helpers to convert common Python objects into JSON-safe types."""

import datetime
import decimal
import enum
import json
import pathlib
import uuid
from collections.abc import Mapping

try:
    import numpy as _np
except Exception:
    _np = None


def make_json_safe(obj, _seen=None):
    """Recursively convert ``obj`` into JSON-serializable Python types.

    Handles common types we encounter in metadata: ``uuid.UUID``, datetimes,
    ``decimal.Decimal``, ``pathlib.Path``, ``enum.Enum``, numpy scalars/arrays,
    bytes-like objects, sets/frozensets, and ensures mapping keys are strings.

    Circular references are guarded against using an ``_seen`` id set and
    will be stringified when encountered again.
    """
    if _seen is None:
        _seen = set()

    # Primitives that are already JSON-safe
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    oid = id(obj)
    if oid in _seen:
        return str(obj)
    _seen.add(oid)

    # Common conversions
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        try:
            return float(obj)
        except Exception:
            return str(obj)
    if isinstance(obj, pathlib.Path):
        return str(obj)
    if isinstance(obj, enum.Enum):
        return make_json_safe(obj.value, _seen)

    # Mappings: ensure string keys
    if isinstance(obj, Mapping):
        return {str(k): make_json_safe(v, _seen) for k, v in obj.items()}

    # Sequences / sets (include frozenset)
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [make_json_safe(v, _seen) for v in obj]

    # Bytes-like
    if isinstance(obj, (bytes, bytearray, memoryview)):
        try:
            return bytes(obj).decode("utf-8", errors="replace")
        except Exception:
            return str(obj)

    # numpy support (optional)
    if _np is not None:
        if isinstance(obj, _np.ndarray):
            try:
                return obj.tolist()
            except Exception:
                return [make_json_safe(v, _seen) for v in obj]
        if isinstance(obj, _np.generic):
            try:
                return obj.item()
            except Exception:
                return str(obj)

    # Last resort: accept if json.dumps can handle it, otherwise stringify
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)
