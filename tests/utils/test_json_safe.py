import datetime
import decimal
import enum
import json
import pathlib
import uuid

import pytest

from vector_inspector.utils.json_safe import make_json_safe


class Color(enum.Enum):
    RED = "red"


def test_make_json_safe_common_types():
    data = {
        "id": uuid.UUID(int=12345),
        "path": pathlib.Path("/tmp/file.txt"),
        "enum": Color.RED,
        "set": frozenset([1, 2, 3]),
        "bytes": b"hello\xc3\xa9",
        "decimal": decimal.Decimal("12.34"),
        "date": datetime.date(2020, 1, 2),
    }

    safe = make_json_safe(data)

    # Should be JSON-serializable
    s = json.dumps(safe)
    assert isinstance(s, str)

    parsed = json.loads(s)
    assert parsed["id"] == str(data["id"])
    assert parsed["path"] == str(data["path"])
    assert parsed["enum"] == data["enum"].value


def test_make_json_safe_cycles_and_numpy_optional():
    # cyclic structure shouldn't raise
    a = {}
    a["self"] = a
    safe = make_json_safe(a)
    assert json.dumps(safe)

    # numpy is optional — just ensure function doesn't crash when numpy exists
    try:
        import numpy as np
    except ImportError:
        pytest.skip("numpy not available")

    arr = np.array([1, 2, 3])
    safe_arr = make_json_safe({"arr": arr})
    assert json.loads(json.dumps(safe_arr))["arr"] == [1, 2, 3]
