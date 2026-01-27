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

- Fix disappearing-row after edit in MetadataView: when an edit regenerates embeddings the row can move to the end of the server-side result set and the UI reload currently shows the last page. Investigate and implement a reliable strategy to keep the edited item visible (e.g., locate its server-side index and load that page, or preserve stable sorting keys). (blocking UX; unscheduled)



