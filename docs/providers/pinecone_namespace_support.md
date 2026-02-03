# Pinecone Namespace Support Analysis

**Date:** February 3, 2026  
**Branch:** expand-pinecone-support  
**Issue:** Friend's Pinecone database shows collections but no data loads

## Problem Summary

The current Pinecone integration in Vector Inspector does not support **namespaces**, which are a core organizational feature in Pinecone. When connecting to a Pinecone index that uses namespaces, the application:
- Successfully connects
- Shows the index (collection) in the UI
- Fails to load any data because it queries the default (empty) namespace

## What are Pinecone Namespaces?

In Pinecone's data model:
- **Index** = Top-level container (equivalent to a "collection" in other vector DBs)
- **Namespace** = Logical partition within an index for organizing vectors
- Namespaces are created implicitly when you insert data
- All vector operations support an optional `namespace` parameter
- Default namespace is an empty string `""`
- Common use cases:
  - Multi-tenant applications (one namespace per tenant)
  - Development/staging/production data separation
  - Organizing vectors by category or source

## Current Implementation Issues

### 1. No Namespace Awareness
The `PineconeConnection` class currently treats indexes as flat collections:
- `list_collections()` returns index names only
- All operations (query, fetch, list, upsert, delete) operate on the default namespace
- No way to discover or select namespaces

### 2. Operations Affected
All data operations fail when data is in non-default namespaces:
- **get_all_items()** - Uses `index.list()` without namespace parameter
- **query_collection()** - Uses `index.query()` without namespace parameter  
- **add_items()** - Uses `index.upsert()` without namespace parameter
- **delete_items()** - Uses `index.delete()` without namespace parameter
- **get_items()** - Uses `index.fetch()` without namespace parameter
- **update_items()** - Uses `index.fetch()` and `index.upsert()` without namespace parameter
- **get_collection_info()** - Uses `index.describe_index_stats()` without namespace parameter

### 3. Stats and Metadata
The `describe_index_stats()` call returns:
```python
{
    'namespaces': {
        '': {'vector_count': 0},
        'production': {'vector_count': 1000},
        'staging': {'vector_count': 500}
    },
    'dimension': 384,
    'index_fullness': 0.01,
    'total_vector_count': 1500
}
```

Currently, we only read `total_vector_count`, which is correct, but we're missing the per-namespace breakdown.

## Proposed Solution

### Option A: Treat Namespaces as Sub-Collections (Recommended)

Extend the collection naming convention to include namespaces:
- Format: `{index_name}` or `{index_name}::{namespace}`
- Empty namespace: Just use `{index_name}` 
- Named namespace: Use `{index_name}::production`

**Advantages:**
- Works with existing UI (collections list, selection)
- No breaking changes to base connection interface
- Intuitive for users

**Implementation:**
1. Update `list_collections()` to:
   - Call `describe_index_stats()` for each index
   - Parse namespace information
   - Return entries like: `my-index`, `my-index::production`, `my-index::staging`

2. Update all data methods to:
   - Parse collection_name for `::` separator
   - Extract `(index_name, namespace)` tuple
   - Pass `namespace` parameter to Pinecone API calls

3. Update `get_collection_info()` to:
   - Show per-namespace stats
   - Indicate this is a namespace within an index

### Option B: Add Namespace as First-Class Concept

Add namespace management to the base connection interface:
- `list_namespaces(index_name: str) -> List[str]`
- `set_active_namespace(namespace: str)`
- All operations use the active namespace

**Disadvantages:**
- Requires changes to base class and UI
- More complex for users to understand
- Other providers (Chroma, Qdrant) don't have this concept

## Implementation Plan (Option A)

### Phase 1: Core Namespace Support
1. ✅ Document current state and proposed solution
2. Add helper methods:
   - `_parse_collection_name(name: str) -> Tuple[str, str]`
   - `_format_collection_name(index_name: str, namespace: str) -> str`
3. Update `list_collections()` to discover and list namespaces
4. Update all data operations to use namespace parameter

### Phase 2: Testing
1. Test with indexes containing multiple namespaces
2. Test empty namespace (default behavior)
3. Test namespace creation via add_items
4. Test edge cases (special characters in namespace names)

### Phase 3: UI Considerations
1. Consider visual indication of namespaces (icon, indentation, grouping)
2. Add namespace info to collection info panel
3. Test user workflow with namespaced collections

## Code Changes Required

### Files to Modify
- `src/vector_inspector/core/connections/pinecone_connection.py` (primary changes)
- `tests/test_pinecone_connection.py` (add namespace tests)

### Pinecone API Methods to Update
All methods that accept an index instance need namespace parameter:
- `index.query(vector=..., namespace='...')`
- `index.upsert(vectors=..., namespace='...')`
- `index.fetch(ids=..., namespace='...')`
- `index.delete(ids=..., namespace='...')`
- `index.list(namespace='...')` (list IDs in namespace)
- `index.describe_index_stats(namespace='...')` (for specific namespace stats)

### Backward Compatibility
- Default namespace (empty string) remains default behavior
- Existing connections without namespace in name continue to work
- No breaking changes to API

## Complexity Assessment

**Implementation Complexity: LOW-MEDIUM**

This is straightforward because:
✅ Pinecone API already supports namespaces in all operations  
✅ Just need to add namespace parameter to existing method calls  
✅ Collection naming convention change is clean and backward compatible  
✅ No UI changes required (collections list already exists)  

Primary work:
- Parse and format collection names
- Update ~10 method calls to include namespace parameter
- Add tests for namespace scenarios

**Estimated effort:** 2-3 hours implementation + 1 hour testing

## Next Steps

Since this appears **straightforward**, we should proceed with implementation:
1. Implement helper methods for name parsing/formatting
2. Update list_collections() to discover namespaces
3. Update all data operations to use namespace parameter
4. Test with real Pinecone data

## References

- Pinecone Namespaces Documentation: https://docs.pinecone.io/docs/namespaces
- Pinecone Python SDK: https://github.com/pinecone-io/pinecone-python-client
