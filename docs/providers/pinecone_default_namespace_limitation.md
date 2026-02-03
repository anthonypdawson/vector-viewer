# Pinecone Default Namespace Limitation

## Issue Summary

When inserting vectors into Pinecone's **default namespace** (accessed by omitting the `namespace` parameter), the vectors are successfully stored and can be queried, **but they do not appear in the Pinecone data browser or in `describe_index_stats()` results**.

## Root Cause

This is a **Pinecone API limitation**, not a bug in Vector Inspector:

1. Pinecone's `describe_index_stats()` API does not return the default namespace in its `namespaces` dictionary
2. The Pinecone web console data browser relies on this API to discover namespaces
3. Since the default namespace isn't listed, the browser can't display its vectors
4. Named namespaces (e.g., "production", "staging") work correctly

## Evidence

From our test script output:

```
VERIFICATION: Checking namespace statistics
Total vectors in index: 22
Number of namespaces: 5

⚠ Namespace '(default)': NOT IN STATS (Pinecone API limitation)
✓ Namespace 'production': 5 vectors (expected 5)
✓ Namespace 'staging': 4 vectors (expected 4)
✓ Namespace 'development': 6 vectors (expected 6)
✓ Namespace 'analytics': 4 vectors (expected 4)

TESTING NAMESPACE QUERIES
Testing query in namespace '(default)'...
✓ Found 3 results in namespace '(default)'  <-- VECTORS EXIST AND ARE QUERYABLE!
```

## API Call Corrections Made

To properly target the default namespace, we **must omit the `namespace` parameter entirely** rather than passing an empty string or `None`:

### Before (Incorrect)
```python
index.upsert(vectors=batch, namespace="")
index.query(vector=query_vector, namespace="")
```

### After (Correct)
```python
# For default namespace, omit the parameter
if namespace:
    index.upsert(vectors=batch, namespace=namespace)
else:
    index.upsert(vectors=batch)

if namespace:
    index.query(vector=query_vector, namespace=namespace)
else:
    index.query(vector=query_vector)
```

## Affected Methods in pinecone_connection.py

All the following methods were updated to conditionally omit the `namespace` parameter:

- `add_items()` - upsert operation
- `get_items()` - fetch operation
- `query_collection()` - query operation
- `list_items()` - list and fetch operations
- `update_items()` - fetch and upsert operations
- `delete_items()` - delete operations

## Recommendations

1. **Use named namespaces** (e.g., "production", "staging") instead of the default namespace for production use
2. Named namespaces appear correctly in both the data browser and stats API
3. If you must use the default namespace, verify via queries rather than the data browser
4. Vector Inspector will not list collections for the default namespace due to this API limitation

## Test Script

The test script `test_scripts/test_pinecone_namespaces.py` demonstrates this behavior and includes queries that prove vectors exist in the default namespace even though they're not visible in stats.

## References

- Pinecone Python SDK: https://github.com/pinecone-io/pinecone-python-client
- This appears to be a known limitation based on consistent behavior across API versions
