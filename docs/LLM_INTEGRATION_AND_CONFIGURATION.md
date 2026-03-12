# LLM Integration and Configuration

Vector Inspector supports multiple LLM providers through a unified, provider‑agnostic interface.  
This guide explains how to enable providers, manage privacy, and configure local or cloud runtimes for the **Ask the AI** feature.

---

## Quick start

- Open **Vector Inspector → Settings → AI Providers** to add or enable a provider.  
- Alternatively, open the **Ask the AI** dialog and click **Configure LLM…** to jump directly to the same Settings page.  
- After configuring a provider, return to the dialog and send a request. The dialog’s **Context Preview** shows exactly what will be sent.  
- Changes take effect immediately — no restart required.

---

## Privacy & data handling

- The Ask the AI dialog includes a **Context Preview** so you can inspect and remove any sensitive fields before sending.  
- Use **local providers** (e.g., `llama‑cpp` or other on‑device runtimes) to keep all data on‑device; these providers do **not** transmit your context to remote servers.  
- When using **hosted providers** (OpenAI, Azure OpenAI, etc.), treat outgoing context as data that may be stored or processed by the provider. Redact or remove PII using the Context Preview when appropriate.  
- Vector Inspector never sends data automatically — nothing is transmitted until you explicitly click **Send**.

---

## Supported provider types

Vector Inspector supports three categories of LLM providers:

- **On‑device runtimes** (no server):  
  `llama‑cpp`, GGUF models, and other local inference libraries.

- **Local host servers** (HTTP):  
  Ollama, LM Studio, and other self‑hosted OpenAI‑compatible gateways.

- **Cloud OpenAI‑compatible APIs**:  
  OpenAI, Azure OpenAI, and any service implementing the OpenAI API schema.

All providers use the same unified interface through `app_state.llm_provider`.

---

## Configuration notes and examples

The canonical place to configure providers is **Settings → AI Providers**.  
Each provider exposes its own options, including:

- **Model selection dropdown**  
- **Base URL / Host / Port** (required for *all* providers, including OpenAI)  
- **API key or credentials**  
- **Model parameters** (when supported)

**Examples (illustrative):**

- **Ollama (local host):**  
  Set the Base URL (e.g., `http://localhost:11434`) and choose a model from the model dropdown.

- **llama‑cpp (on‑device):**  
  Set the local model path and any runtime flags required by your build. Select the model from the dropdown.

- **OpenAI / Azure OpenAI / LM Studio:**  
  - Set the **Base URL**:  
    - OpenAI: `https://api.openai.com/v1`  
    - Azure OpenAI: your Azure endpoint (e.g., `https://<resource>.openai.azure.com/openai/deployments/<model>/`)  
    - LM Studio: local server URL (e.g., `http://localhost:1234/v1`)  
  - Provide API credentials in Settings or via environment variables.  
  - Choose the model from the provider’s model dropdown.

Environment variables override UI settings when both are present, which is useful for CI, containers, and scripted deployments.

---

## Environment variables

These variables allow scripted or portable configuration of LLM providers:

- **`VI_LLM_PROVIDER`**  
  Override provider selection.  
  Values: `auto`, `ollama`, `llama-cpp`, `openai-compatible`, `fake`.

- **`VI_LLM_MODEL`**  
  Override the model name used by the selected provider  
  (e.g., `gpt-4o`, `llama3:8b-instruct`).

- **`VI_OLLAMA_URL`**  
  URL for a running Ollama server (default: `http://localhost:11434`).  
  Used by auto‑detection and the Ollama provider.

- **`OPENAI_API_KEY`**  
  OpenAI‑style API key used by OpenAI‑compatible providers.  
  The runtime also reads the `llm.openai_api_key` Settings value when this variable is not present.

- **`VI_LLM_DEBUG`**  
  When set (any non‑empty value), enables verbose provider‑selection debug logging (`selection_debug`) to help diagnose selection and fallback behavior.

**Note:** Most provider options are configurable from the Settings dialog.  
Environment variables provide a convenient way to override provider selection and model choices for CI, containers, or portable deployments.

---

## Context budgeting recommendations

- The UI clamps context to the top **N** results by default to avoid exceeding model windows.  
  The dialog shows a live token estimate as you change the selection — use it to keep prompts small.  
- Prefer sending **small, focused contexts** for explanation tasks (5–10 results or the default top‑N selection).  
- Smaller local models may require tighter context limits than cloud models; use the token estimate as a guide.

---

## Troubleshooting

- If requests fail with context‑related errors, reduce the number of selected results or shorten snippets via the **Context Preview**.  
- Check provider connectivity in Settings (test or refresh provider). Local providers must be running and accessible to the host.  
- If a provider is available but requests fail immediately, verify that a **model is selected** in the provider’s configuration.  