import pytest

# Skip entire module if lancedb or pyarrow not installed
pytest.importorskip("lancedb")
pytest.importorskip("pyarrow")

import threading
import time
from unittest.mock import MagicMock

import pandas as pd
import pyarrow as pa

from vector_inspector.core.connections.lancedb_connection import LanceDBConnection


def _make_df():
    return pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "vector": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            "document": ["d1", "d2", "d3"],
            "metadata": ["{}", "{}", "{}"],
        }
    )


def test_lancedb_rewrite_concurrent_no_crash(tmp_path):
    """Simulate two concurrent delete_items calls that both take the rewrite path.

    This verifies no uncaught exceptions and that at least one creator completes.
    """
    conn = LanceDBConnection(uri=str(tmp_path))
    conn._connected = True

    # Force rewrite path by providing a tbl without `delete` attribute
    tbl = MagicMock(spec=["to_pandas"])
    tbl.to_pandas.return_value = _make_df()

    # Shared DB mock
    db = MagicMock()
    db.open_table.return_value = tbl

    created_states = []
    dropped = []

    def drop_table(name):
        # small sleep to increase interleaving window
        time.sleep(0.05)
        dropped.append(name)

    def create_table(name, data=None):
        # emulate work and record created ids
        time.sleep(0.1)
        try:
            df = data.to_pandas() if hasattr(data, "to_pandas") else pa.Table.from_pandas(data).to_pandas()
        except Exception:
            # try converting pyarrow Table if passed directly
            df = pa.Table.from_pandas(data).to_pandas()
        created_states.append(df["id"].tolist())

    db.drop_table.side_effect = drop_table
    db.create_table.side_effect = create_table

    conn._db = db

    results = []

    def runner(del_id):
        ok = conn.delete_items("coll", ids=[del_id])
        results.append(ok)

    t1 = threading.Thread(target=runner, args=("b",))
    t2 = threading.Thread(target=runner, args=("c",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Both threads should complete and at least one create_table should have been called
    assert all(isinstance(r, bool) for r in results)
    assert len(created_states) >= 1
    assert len(dropped) >= 1


def test_lancedb_rewrite_concurrent_one_failure(tmp_path):
    """Simulate concurrent rewrites where the first create_table raises and the second succeeds.

    Expect one False and one True return value; ensure drop/create were invoked.
    """
    conn = LanceDBConnection(uri=str(tmp_path))
    conn._connected = True

    tbl = MagicMock(spec=["to_pandas"])
    tbl.to_pandas.return_value = _make_df()

    db = MagicMock()
    db.open_table.return_value = tbl

    calls = {"create": 0}
    dropped = []

    def drop_table(name):
        time.sleep(0.02)
        dropped.append(name)

    def create_table(name, data=None):
        calls["create"] += 1
        # first call fails, second succeeds after slight delay
        if calls["create"] == 1:
            time.sleep(0.05)
            raise RuntimeError("simulated create failure")
        time.sleep(0.05)
        # record created ids
        df = data.to_pandas() if hasattr(data, "to_pandas") else pa.Table.from_pandas(data).to_pandas()
        return df["id"].tolist()

    db.drop_table.side_effect = drop_table
    db.create_table.side_effect = create_table

    conn._db = db

    results = []

    def runner(del_id):
        ok = conn.delete_items("coll", ids=[del_id])
        results.append(ok)

    t1 = threading.Thread(target=runner, args=("b",))
    t2 = threading.Thread(target=runner, args=("c",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Expect at least one success and one possible failure
    assert any(results)
    # At least one drop attempted and create was called at least once
    assert len(dropped) >= 1
    assert calls["create"] >= 1
