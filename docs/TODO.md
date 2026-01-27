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

 - Fix my workflow using the file "publish copy.yml", rename the file to have no spaces and update tags on the site and in my readme. Update the pypi trusted publishing.  Remove the old publish workflows.

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

