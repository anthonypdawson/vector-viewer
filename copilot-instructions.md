# GitHub Copilot Workspace Instructions (Stub)

Authoritative instructions live in the private pro repo: [vector-viewer-pro/copilot-instructions.md](../vector-viewer-pro/copilot-instructions.md).

## Memory Persistence Policy

- **Transient learnings** (session logs, temporary notes) are recorded in the pro repo: [vector-viewer-pro/docs/copilot-working-notes.md](../vector-viewer-pro/docs/copilot-working-notes.md).
- **Persistent memory** (facts, preferences, or data that must be remembered across sessions, e.g., last-used directories, user settings, project conventions) is now stored in the MCP server (Model Context Protocol memory server). The Markdown file [vector-viewer-pro/docs/copilot-working-notes.md](../vector-viewer-pro/docs/copilot-working-notes.md) is generated from the MCP server data for human readability.

**When you are asked to persist memory, or you determine something is worth persisting, you must record it in the MCP server, and then update the Markdown file to reflect the current state. Do not use the JSON file for memory persistence.**

For full details and conventions, always refer to the authoritative instructions in the pro repo.

## Required Persistence Checklist (always present)

Whenever a decision is made or new project information should be remembered, follow these steps exactly:

- **Record to MCP**: Create a structured observation in the MCP server describing the fact/decision, include rationale, tags, and an ISO timestamp.
- **Mirror machine-readable**: Add or update the corresponding entry in `vector-viewer-pro/docs/copilot-memory.json` (key, value, ts) if your tooling requires a JSON mirror.
- **Regenerate human-readable**: Ensure `vector-viewer-pro/docs/copilot-working-notes.md` is regenerated or edited to reflect the MCP change so humans can read it.
- **Tag & Partition**: Tag the observation (e.g., `strategy`, `ux`, `policy`) and mark the project partition (`Vector Inspector` or `Vector Studio`) — do not use `vector-viewer` for new entries.
- **Commit message convention**: Use a clear commit message like `copilot-memory: add <short-key> — <one-line>` when committing JSON/MD changes.
- **Confirm**: If the change is destructive or irreversible (migrations, deletions, major policy changes), request explicit confirmation before persisting.

Keep this checklist in the file so it's always visible when contributors read the instructions.

## Import Style

- Prefer absolute imports within the project (for example: `from vector_inspector.core.embedding_utils import ...`) over relative imports. Absolute paths make code easier to edit across repositories and work better with editors and static analysis tools. Use relative imports only for very small, tightly-coupled internal modules when clearly justified.