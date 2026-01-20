import pytest
from vector_inspector.services.filter_service import apply_client_side_filters

def sample_data():
    return {
        "ids": [1, 2, 3],
        "documents": ["The quick brown fox", "Jumps over the lazy dog", "Hello world!"],
        "metadatas": [
            {"category": "animal", "author": "A"},
            {"category": "animal", "author": "B"},
            {"category": "greeting", "author": "C"},
        ],
        "embeddings": [[0.1], [0.2], [0.3]],
    }

def test_no_filters_returns_all():
    data = sample_data()
    result = apply_client_side_filters(data, [])
    assert result == {
        "ids": [1, 2, 3],
        "documents": ["The quick brown fox", "Jumps over the lazy dog", "Hello world!"],
        "metadatas": [
            {"category": "animal", "author": "A"},
            {"category": "animal", "author": "B"},
            {"category": "greeting", "author": "C"},
        ],
        "embeddings": [[0.1], [0.2], [0.3]],
    }

def test_contains_document():
    data = sample_data()
    filters = [{"field": "document", "op": "contains", "value": "fox"}]
    result = apply_client_side_filters(data, filters)
    assert result["ids"] == [1]
    assert result["documents"] == ["The quick brown fox"]
    assert result["metadatas"] == [{"category": "animal", "author": "A"}]
    assert result["embeddings"] == [[0.1]]

def test_not_contains_metadata():
    data = sample_data()
    filters = [{"field": "category", "op": "not_contains", "value": "animal"}]
    result = apply_client_side_filters(data, filters)
    assert result["ids"] == [3]
    assert result["documents"] == ["Hello world!"]
    assert result["metadatas"] == [{"category": "greeting", "author": "C"}]
    assert result["embeddings"] == [[0.3]]

def test_multiple_filters():
    data = sample_data()
    filters = [
        {"field": "category", "op": "contains", "value": "animal"},
        {"field": "author", "op": "contains", "value": "B"},
    ]
    result = apply_client_side_filters(data, filters)
    assert result["ids"] == [2]
    assert result["documents"] == ["Jumps over the lazy dog"]
    assert result["metadatas"] == [{"category": "animal", "author": "B"}]
    assert result["embeddings"] == [[0.2]]

def test_empty_data():
    result = apply_client_side_filters({}, [])
    assert result == {}

def test_missing_fields():
    data = {"ids": [1], "documents": ["foo"]}
    filters = [{"field": "category", "op": "contains", "value": "animal"}]
    result = apply_client_side_filters(data, filters)
    assert result["ids"] == []
    assert result["documents"] == []
    assert result["metadatas"] == []

def test_case_sensitivity():
    data = {"ids": [1], "documents": ["Hello World"], "metadatas": [{"author": "Alice"}]}
    filters = [{"field": "document", "op": "contains", "value": "hello world"}]
    result = apply_client_side_filters(data, filters)
    assert result["ids"] == [1]

def test_non_string_metadata_value():
    data = {"ids": [1], "documents": ["foo"], "metadatas": [{"num": 123}]}
    filters = [{"field": "num", "op": "contains", "value": "123"}]
    result = apply_client_side_filters(data, filters)
    assert result["ids"] == [1]

def test_unknown_operator():
    data = {"ids": [1], "documents": ["foo"], "metadatas": [{"author": "Bob"}]}
    filters = [{"field": "author", "op": "unknown", "value": "Bob"}]
    result = apply_client_side_filters(data, filters)
    # Unknown op: should not filter out
    assert result["ids"] == [1]

def test_large_input():
    data = {
        "ids": list(range(1000)),
        "documents": ["doc" + str(i) for i in range(1000)],
        "metadatas": [{"author": "A" if i % 2 == 0 else "B"} for i in range(1000)],
        "embeddings": [[i] for i in range(1000)],
    }
    filters = [{"field": "author", "op": "contains", "value": "A"}]
    result = apply_client_side_filters(data, filters)
    assert all(m["author"] == "A" for m in result["metadatas"])
    assert len(result["ids"]) == 500
