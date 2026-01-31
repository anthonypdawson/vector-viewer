# Unified Telemetry Architecture: Model Metadata & Persistence

This document combines the privacy-focused telemetry payload from `model_telemetry_and_registry.md` with the practical Netlify Function and GitHub NDJSON persistence patterns from `netlify.md` and `netlify-to-github.md`.

---

## 1. Telemetry Payload (Opt-In, Privacy-Safe)

**Fields to Collect:**
- `model_name`
- `model_source` (e.g., sentence-transformers, nomic, openai, local_path)
- `model_version` (if available)
- `embedding_dimension`
- `modalities` (e.g., text, image, multimodal)
- `distance_metric` (if detectable)
- `normalization` (e.g., L2, none)
- `load_success` (true/false)
- `inference_success` (true/false)
- `device_type` (cpu/gpu)
- `local_path_hash` (hash of local model path, if applicable)
- `timestamp`
- `client_id` (locally generated UUID, for deduplication/analytics)

**Principles:**
- Opt-in only, disabled by default
- Never send credentials, file paths, or user content
- User can view, send, or purge queued events

---


## 2. Telemetry Submission Flow

- App POSTs telemetry payload to the production endpoint:

	**POST https://api.divinedevops.com/api/v1/telemetry**

- Payload (JSON):
	- `hwid` (required): hardware or client identifier
	- `event_name` (required): event type/name
	- `app_version` (required): application version
	- `client_type` (optional, defaults to "vector-inspector")
	- `metadata` (optional, object)

- The server records the client’s IP address from the `X-Forwarded-For` header or `remote_addr`.

- No user identity, credentials, or sensitive data are sent.

---


## 3. Server Endpoint Details

- Endpoint: `https://api.divinedevops.com/api/v1/telemetry`
- Method: POST
- Content-Type: application/json
- Required fields: `hwid`, `event_name`, `app_version`
- Optional fields: `client_type`, `metadata`
- The server will record the client’s IP address automatically.

---


## 4. Implementation Checklist

- [ ] Implement telemetry payload as above
- [ ] Store queued events locally until user opts in
- [ ] POST events to `https://api.divinedevops.com/api/v1/telemetry`
- [ ] Document opt-in, privacy, and user controls

---

**References:**
- See `model_telemetry_and_registry.md` for payload details
- See `netlify.md` and `netlify-to-github.md` for endpoint and persistence patterns
