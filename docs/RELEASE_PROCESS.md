Release process and how the assistant will help

This project uses `docs/RELEASE_REASON.md` as the short release notes file. The `publish` workflow prepends the contents
of `docs/RELEASE_REASON.md` to the package README when building and uses it as the release body when creating the GitHub release.

How to add release notes

- Manual: edit `docs/RELEASE_REASON.md` and add entries at the top.
- Scripted: run `scripts/add_release_reason.py --message "Short summary" --type fix` to prepend a structured entry.

Assistant behaviour

- When I make code changes or fixes in the repo on your behalf, I will proactively suggest a short release-note entry and can automatically run `scripts/add_release_reason.py` if you approve.
- The script captures the current commit and git user (if available) and prepends a dated, structured entry to `docs/RELEASE_REASON.md`.

Suggested workflow

1. When preparing a release, review `docs/RELEASE_REASON.md` and refine entries as needed.
2. Run the publish workflow (it will include the `docs/RELEASE_REASON.md` content in the release body).
3. After publishing, consider archiving old entries in a permanent changelog if desired.
