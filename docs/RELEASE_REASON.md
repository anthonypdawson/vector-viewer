# Latest updates

## February 10, 2026 — Release Reason
- Moved basic clustering visualization to OSS tier
- Modularized visualization view: split into ClusteringPanel, DRPanel, PlotPanel
- Implemented full clustering and dimensionality reduction logic with threading
- Added advanced clustering parameters, collapsible advanced settings for Vector Studio
- Refactored clustering controls to dict-based mapping for maintainability
- Restored original clustering workflow: clustering auto-loads data, no visualization required
- Cluster ID now shown in visualization hover tooltips
- Feature gating for sample size: Vector Inspector limits to 500, disables "Use all data"; Vector Studio allows full range

---