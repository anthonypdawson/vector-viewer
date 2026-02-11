# Project TODOs (Unscheduled)

This file tracks fixes, features, and improvements that are not yet assigned to a specific phase or release.

Add new items below as needed. When an item is scheduled for a phase or release, move it to the appropriate planning document.
---
## Unscheduled Items

- Add user-selectable embedding model for import/export and backup/restore
- Track generic feature requests and improvements
- Add defaults for each database provider in the new collection view
  - E.g., default port numbers, default connection settings
  - Probably should store as a dict of defaults somewhere
- Improve error handling and user feedback for database connection issues


- Refactor UI MainWindow as suggested here https://copilot.microsoft.com/shares/2657KN5vHbc1qNwLHQMc3
- Continue testing search similar feature and fix any bugs found
- Allow create collections
  - Precreate sample data that can be used for quick collection creation and testing
- Add right click menu in Data browser "Go to cluster" that takes you to the cluster view for that item
- Allow adding test data from the UI for demo purposes (leverage code in create_test_data.py)
  - Allow types of data: text, images, audio, mixed
  - Allow specifying number of items, metadata fields, embedding dimensions
  - Use the data from create_test_data.py if the user wants just demo data quickly
  - See sample_data.md for more details
- Move basic clustering to vector-inspector (non-paid)
  - Keep advanced options in Vector Studio (paid)
  - Additional clustering features outlined in the clustering doc will be in Vector Studio only, but basic clustering (e.g., KMeans with default settings) can be in the free version to provide a taste of the feature and support basic use cases.
- Expand telemetry
  - Examples:
  EVENTS = {
    'db.connected': {'db_type', 'connection_time_ms'},
    'collection.loaded': {'db_type', 'vector_count', 'dimension'},
    'search.performed': {'db_type', 'result_count', 'has_filters'},
    'feature.used': {'feature_name', 'session_duration'},
    'upgrade.shown': {'trigger', 'feature_blocked'},
    'upgrade.clicked': {'plan', 'source'}
}
- Implement cluster visualization with HDBSCAN (Premium) — moved to: ../vector-studio/docs/CLUSTER_VISUALIZATION_HDBSCAN.md
- When catching an exception on connecting to a database, classify the error and show a more specific message to the user (e.g., authentication failure, network unreachable, timeout, problem with database etc.). Remove the loading dialog when an error occurs.
  - Example of a database failure
    ```
    try:
      self._client = chromadb.PersistentClient(path=path_to_use)
    except Exception as e:
      msg = str(e).lower()

    # Detect Rust-level corruption signals
    if (
        "pyo3_runtime.panic" in msg
        or "range start index" in msg
        or "slice of length" in msg
        or "rust" in msg and "panic" in msg
        or "bindings" in msg and "panic" in msg
    ):
        self._last_error = (
            "The Chroma database could not be opened because its internal "
            "metadata or index files appear to be corrupted. "
            "If you have a backup, try restoring it."
        )
        return False

    # Otherwise treat it as a normal connection error
    self._last_error = f"Failed to open Chroma database: {e}"
    return False
    ```


### Update available flow (Partially completed)
 - Implement a user notification system for available updates
 - Query github releases API (https://api.github.com/repos/anthonypdawson/vector-inspector/releases/latest) to check for new versions (once per day/launch) and save to file
 - Return structure
   ```json
   {
    "tag_name": "1.2.3",
    "nname": "1.2.3",
    "body": "Release notes...",
    "html_url": "https://github.com/anthonypdawson/vector-inspector/releases/tag/1.2.3"
   }
   ```
 - Add error handling for network failures and API rate limits; cache the last successful check to avoid false negatives.
 - Store the timestamp of the last check and the last notified version to prevent repeated notifications for the same update.
 - Add a manual "Check for updates" button in the help menu.
 - If distributed via multiple channels (e.g., PyPI, standalone), show both update methods in the notification:
   - Display the pip update command (e.g., pip install --upgrade vector-inspector).
   - Provide a link to the latest GitHub release page.
 - Optionally, allow users to dismiss or snooze update notifications.
 - On about screen compare version to latest release and show notification if newer version is available
 - If an update is available show "Update available" on the notification area of the main screen
 - The About screen and status bar/notification area should show a simple “Update available” indicator if a new version is detected.
   - When the user clicks the indicator, “Check for updates,” or update available in about screen, open a dedicated popup/modal that displays:
     - The new version number
     - Release notes
     - Update instructions (pip command and GitHub link)
     - Option to dismiss or snooze the notification
