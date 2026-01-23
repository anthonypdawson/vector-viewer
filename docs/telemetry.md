# Telemetry & Model Registry Contributions

Purpose: provide a safe, minimal opt-in telemetry flow so users can (optionally) share anonymized information about custom embedding models they register. This helps maintain a central model registry without sending sensitive data.

## Principles
- **Opt-in only**: telemetry is disabled by default. Prompt once when the user first saves a custom model, with clear explanation and link to docs.
- **Minimal payload**: never send credentials, file paths, or user content.
- **Anonymized client id**: use a locally stored UUID; prefer hashing when possible to avoid exposing model IDs directly.
- **User control**: allow viewing queued events, send now, disable, and purge collected telemetry from Settings.

## Telemetry: Embedding Model Metadata (Optional)

The following is the precise telemetry payload we should collect when users opt in to share anonymized model metadata. This form is privacy-safe and minimal — do not send any sensitive fields such as API keys, full local paths, or user-generated content.

### Data to Collect

#### Model Identification
- `model_name`
- `model_source` (e.g., sentence-transformers, nomic, openai, local_path)
- `model_version` (if available)

#### Model Characteristics
- `embedding_dimension`
- `modalities` (e.g., text, image, multimodal)
- `distance_metric` (if detectable)
- `normalization` (e.g., L2, none)

#### Runtime Information
- `load_success` (true/false)
- `inference_success` (true/false)
- `device_type` (cpu/gpu)

#### Privacy-Safe Metadata
- `local_path_hash` (hash of local model path, if applicable)
- `timestamp`

#### Client Identification
- `client_id` (locally generated UUID stored in settings; used only for deduplication/analytics)

### Example Event (JSON)

Complete telemetry event with all fields:

```json
{
  "event_type": "model_registration",
  "model_name": "sentence-transformers/all-mpnet-base-v2",
  "model_source": "sentence-transformers",
  "model_version": "2.1.0",
  "embedding_dimension": 768,
  "modalities": ["text"],
  "distance_metric": "cosine",
  "normalization": "l2",
  "load_success": true,
  "inference_success": true,
  "device_type": "cpu",
  "local_path_hash": null,
  "timestamp": "2026-01-23T12:34:56Z",
  "client_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### Fields Explanation
- `model_name`: public model identifier (HF id or short name). Do NOT include local file paths.
- `model_source`: origin of the model (sentence-transformers, nomic, openai, local_path, etc.)
- `model_version`: version string if available from model metadata.
- `embedding_dimension`: integer vector size.
- `modalities`: array of supported modalities: `["text"]`, `["image"]`, or `["text", "image"]` for multimodal.
- `distance_metric`: detected or configured distance metric (cosine, euclidean, dot, etc.)
- `normalization`: whether vectors are L2-normalized or not (`l2` or `none`).
- `load_success`: boolean indicating whether the model loaded successfully.
- `inference_success`: boolean indicating whether test inference completed successfully.
- `device_type`: `cpu` or `gpu` (or specific GPU identifier if available).
- `local_path_hash`: SHA256 hash of the local file path if model is loaded from disk (null for remote/HF models).
- `timestamp`: ISO 8601 timestamp of when the event was created.
- `client_id`: locally generated UUID stored in settings; used only for deduplication/analytics.

## Client Behaviour
- Queue events locally (append to a small file under settings dir). Send in batches (e.g., daily) or when user clicks "Send now".
- Retry with exponential backoff on network failures.
- Expose settings: `Telemetry Enabled` (bool), `View queued telemetry`, `Send now`, `Purge queued telemetry`, `Client ID` (show only, allow reset but require a startup argument so that reset is intentional and explicit).
- Always allow the user to review what will be sent before enabling.

## Privacy & Legal
- Document exactly what is collected and why; link to a short privacy FAQ inside the app and in docs.
- Do NOT collect user content, API keys, local file paths (only hash), or any PII.
- Provide a clear data deletion/purge flow: both client-side purge (clear queue + reset client_id) and a server-side removal request process for aggregated records if needed.

## Server API (Recommended Minimal Contract)

- Endpoint: `POST https://registry.example.com/api/v1/telemetry`
- Auth: optional API key for controlled ingestion; otherwise protect with rate-limits and CORS restrictions.
- Accepts batch array of event objects (same schema as above).
- Response: 200 OK with simple JSON: `{ "accepted": N, "rejected": M }`

## Security Notes
- Always use HTTPS and validate TLS certs.
- Rate-limit and monitor the endpoint for abuse.
- Consider additional anonymization: hash `model_name` + `client_id` together for server-side deduplication without storing full model names.

## Implementation Steps (Client)
1. Add `TelemetryService` to the codebase:
   - Methods: `queue_event(event)`, `send_batch()`, `purge()`, `get_queue()`.
   - Use `SettingsService` to store `telemetry_enabled` and `client_id`.
2. Wire Settings UI (SettingsService + Settings panel): toggle opt-in, view/purge queue, reset client id.
3. Emit a `model_registration` event whenever user saves a custom model selection (only if telemetry enabled). Before enabling, show consent dialog that lists fields to be sent.
4. Queue events locally and send in background (idle / daily) with retry/backoff.

## Implementation Steps (Server) — Optional
1. Simple ingest endpoint that validates payload and stores aggregated counts.
2. Admin UI to review aggregated models and counts.
3. Policies for data retention and deletion requests.

## Notes for Maintainers
- Keep telemetry opt-in by default and clearly document the flow.
- Consider GDPR/CCPA requirements depending on where users are located — provide data removal request instructions.
- Use hashing approaches to de-duplicate without exposing full model details if desired.
- When implementing, capture all fields during model load/inference and queue the event only if telemetry is enabled.

If you'd like, I can scaffold a `TelemetryService` (client-side) and add the Settings UI entries next.
