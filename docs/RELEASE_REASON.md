## Release Notes (0.5.1) — 2026-02-24

- Default left panel: the app now opens on the "Profiles" tab so saved profiles
	are shown first on launch (no more starting on the Active panel).
- New-connection polish: the Create/Edit Profile dialog shows only the fields
	relevant to the selected provider (for example, Weaviate-only options like
	gRPC and Cloud are hidden when another provider is chosen), and labels are
	hidden together with their fields for a cleaner form.
- Connection Type stability: the "Connection Type" group is now pinned to the
	top of the dialog so it no longer shifts down when provider-specific fields
	are toggled (improves visual stability when selecting Pinecone or LanceDB).
- Misc: small UX polish and test updates for the profile panel and connection
	flow.
- Misc: Emphasize the 'Distributions' tab in the UI with a new icon and updated label to make it more discoverable and highlight its importance for understanding vector data characteristics.
- ux: Added setting to allow users to choose accent colors for the app, enhancing personalization and user experience.
---

