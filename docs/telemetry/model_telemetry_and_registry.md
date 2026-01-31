
## Telemetry: App Launch Event (Ping)

In addition to model registry telemetry, you can send a simple telemetry event to indicate that the app has launched successfully. This is a minimal 'ping' event for usage analytics and reliability monitoring.

**Minimal payload structure for app launch telemetry:**

```
{
  "hwid": <client or hardware identifier>,
  "event_name": "app_launch",
  "app_version": <application version>,
  "client_type": "vector-inspector" // optional
  "metadata": { "os": <operating system> } // optional, include only if OS info is available
}
```

- The `event_name` must be set to `app_launch` for this event type.
- The `metadata` object is optional. Include it only if you want to record the OS or other launch context. Timestamp and session ID are not required, as the server records the timestamp automatically and session tracking is not needed for a simple launch ping.

**Example (minimal):**

```json
{
  "hwid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_name": "app_launch",
  "app_version": "1.2.3",
  "client_type": "vector-inspector"
}
```

**Example (with OS):**

```json
{
  "hwid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_name": "app_launch",
  "app_version": "1.2.3",
  "client_type": "vector-inspector",
  "metadata": {
    "os": "Windows-10"
  }
}
```

This event should be sent once per application launch, as a POST to the production endpoint:

`POST https://api.divinedevops.com/api/v1/telemetry`

The server will record the client’s IP address and timestamp automatically.
# Telemetry & Model Registry Contributions

Purpose: provide a safe, minimal opt-in telemetry flow so users can (optionally) share anonymized information about custom embedding models they register. This helps maintain a central model registry without sending sensitive data.

## Principles
- **Opt-in only**: telemetry is disabled by default. Prompt once when the user first saves a custom model, with clear explanation and link to docs.
- **Minimal payload**: never send credentials, file paths, or user content.
- **Anonymized client id**: use a locally stored UUID; prefer hashing when possible to avoid exposing model IDs directly.
- **User control**: allow viewing queued events, send now, disable, and purge collected telemetry from Settings.


## Telemetry: Embedding Model Metadata (Optional)

For model registry telemetry, all model metadata should be included in the `metadata` field of the telemetry payload. The `event_name` field should use a standard value, such as `model_registration`, to indicate a model information event. This approach ensures compatibility with the production telemetry endpoint and keeps the payload schema flexible for future event types.

**Payload structure for model registry telemetry:**

```
{
  "hwid": <client or hardware identifier>,
  "event_name": "model_registration",
  "app_version": <application version>,
  "client_type": "vector-inspector", // optional
  "metadata": {
    // All model metadata fields go here (see below)
    "model_name": ...,
    "model_source": ...,
    "model_version": ...,
    "embedding_dimension": ...,
    "modalities": ...,
    "distance_metric": ...,
    "normalization": ...,
    "load_success": ...,
    "inference_success": ...,
    "device_type": ...,
    "local_path_hash": ...,
    "timestamp": ...,
    "client_id": ...
  }
}
```

All model metadata fields previously described should be placed inside the `metadata` object. The top-level fields are reserved for telemetry routing and event type identification.

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

```json
{
  "hwid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_name": "model_registration",
  "app_version": "1.2.3",
  "client_type": "vector-inspector",
  "metadata": {
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
}
```


### Fields Explanation
All model metadata fields (such as `model_name`, `model_source`, etc.) should be included inside the `metadata` object. The top-level fields are:
- `hwid`: hardware or client identifier
- `event_name`: use `model_registration` for model registry events
- `app_version`: application version
- `client_type`: (optional) client type string
- `metadata`: object containing all model metadata fields

## Client Behaviour
- Queue events locally (append to a small file under settings dir). Send in batches (e.g., daily) or when user clicks "Send now".
- Retry with exponential backoff on network failures.
- Expose settings: `Telemetry Enabled` (bool), `View queued telemetry`, `Send now`, `Purge queued telemetry`, `Client ID` (show only, allow reset but require a startup argument so that reset is intentional and explicit).
- Always allow the user to review what will be sent before enabling.

## Privacy & Legal
- Document exactly what is collected and why; link to a short privacy FAQ inside the app and in docs.
- Do NOT collect user content, API keys, local file paths (only hash), or any PII.
- Provide a clear data deletion/purge flow: both client-side purge (clear queue + reset client_id) and a server-side removal request process for aggregated records if needed.


## Server API (Production Endpoint)

- Endpoint: `POST https://api.divinedevops.com/api/v1/telemetry`
- Auth: none required (rate-limited and CORS protected)
- Accepts a single event object (fields: `hwid`, `event_name`, `app_version`, optional `client_type`, `metadata`)
- Response: 201 Created with `{ "status": "success" }` or error JSON
- The server records the client’s IP address from the `X-Forwarded-For` header or `remote_addr`.

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

### Export Workflow
1. User clicks "Export Model Metadata" button in Settings
2. Application generates a JSON file with all queued telemetry events
3. User can review the file and manually submit it via GitHub issue, email, or other channel
4. Maintainers can aggregate these contributions into the known_embedding_models registry

### Export File Format

Example `model_telemetry_export.json`:

```json
{
  "export_version": "1.0",
  "export_timestamp": "2026-01-23T14:22:10Z",
  "client_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "events": [
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
  ]
}
```

### Implementation Updates

Add to `TelemetryService`:
- `export_to_file(path)` method that writes queued events to JSON file with export metadata

Add to Settings UI:
- "Export Model Metadata" button that saves export file via file dialog
- Clear indication that this is for manual contribution before automated backend is available

