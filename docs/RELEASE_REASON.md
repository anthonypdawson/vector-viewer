## Release Notes (0.4.3)


- LanceDB provider fixes and improvements
	- Fix: `delete_items` now feature-detects the native LanceDB table delete API and uses it when available (`tbl.delete(predicate)`). If the native call raises, the implementation falls back to a safe rewrite.
	- Fix: Atomic rewrite fallback no longer double-inserts rows. The implementation now creates the table once with Arrow data (`create_table(data=arr)`) and avoids a subsequent `add()` call that caused duplicate inserts.
	- Test: Added unit tests covering the native delete path, fallback-on-error path, and a regression test to ensure the rewrite path does not double-add. See `tests/providers/test_lancedb_connection.py`.
	- Docs: Documented supported versions for `lancedb`/`pyarrow` in `README.md` and added a CI comment in `.github/workflows/ci-tests.yml` to flag where to look if version bumps break delete behavior.
	- Logging: Improved error logging around native delete failures to make fallback behavior easier to diagnose.

---