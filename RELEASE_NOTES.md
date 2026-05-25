## v0.0.3 — Vision Token Counting Fallback Fix

### Changes

- Fixed local prompt token fallback for vision requests so image `data:` URLs and base64 payloads are no longer counted as plain text.
- Unified the non-stream fallback with the message-based estimator to avoid undercounting or overcounting when multiple prompt messages are present.
- Preserved server-reported usage when available; only the local fallback behavior changed.

## v0.0.2 — Structured Output Fix, Local Packaging and Signature Verification

### Changes

- Fixed structured output compatibility for `format=json` with LM Studio.
- Generic JSON mode now uses a permissive `json_schema` fallback because LM Studio accepts `json_schema` and `text`, not `json_object`.
- Explicit `json_schema` input still overrides the generic JSON fallback for stricter structured output.
- Added local packaging and third-party signature verification release flow for GitHub Releases.

### Release Assets

Upload these files to the GitHub release page for this version:

- `lm_studio_plus-0.0.2.difypkg`
- `lm_studio_plus-0.0.2.signed.difypkg`
- `lm_studio_plus.public.pem`

### Installation

For Dify Community Edition with third-party signature verification enabled:

1. Download `lm_studio_plus-0.0.2.signed.difypkg` and `lm_studio_plus.public.pem` from GitHub Releases.
2. Copy the public key into `docker/volumes/plugin_daemon/public_keys/`.
3. Configure `plugin_daemon` with:

	```yaml
	FORCE_VERIFYING_SIGNATURE: true
	THIRD_PARTY_SIGNATURE_VERIFICATION_ENABLED: true
	THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS: /app/storage/public_keys/lm_studio_plus.public.pem
	```

4. Restart Dify and upload the signed package in **Settings → Plugins**.

If third-party signature verification is disabled, you can also install `lm_studio_plus-0.0.2.difypkg` directly.

### Local Build and Sign

```bash
dify plugin package . -o lm_studio_plus-0.0.2.difypkg
dify signature generate -f certs/lm_studio_plus
dify signature sign lm_studio_plus-0.0.2.difypkg -p certs/lm_studio_plus.private.pem
dify signature verify lm_studio_plus-0.0.2.signed.difypkg -p certs/lm_studio_plus.public.pem
```

## v0.0.1 — Initial Release

**LM Studio Plus** is a Dify model provider plugin for [LM Studio](https://lmstudio.ai/), built from scratch as a reliable alternative to the existing plugin.

### Features

- **LLM support** — Chat and Completion modes via LM Studio's OpenAI-compatible `/v1/chat/completions` API
- **Text Embedding** — Embedding models via `/v1/embeddings`
- **Streaming** — Real-time token streaming with full event support
- **Reasoning / Thinking content** — Supports `reasoning_content` field and `<think>` tag stripping for multi-turn conversations
- **Tool / Function calling** — Aggregates streamed tool call chunks correctly
- **Vision** — Multimodal image input support
- **Structured output** — JSON mode and JSON Schema with automatic system prompt injection
- **API Key authentication** — Optional Bearer token auth for secured LM Studio instances
- **Rich model parameters** — `temperature`, `top_p`, `top_k`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `repeat_penalty`, `seed`, `format`

### Requirements

- LM Studio 0.3.x or later (with server enabled)
- Dify 1.3.x or later

### Installation

Install via Dify Marketplace, or download `lm_studio_plus-0.0.1.difypkg` from the assets below and upload manually in Dify → Settings → Plugins.

> **Note:** If your Dify instance has third-party plugin signature verification enabled, you need to sign the package with your own key before installing. See: [Third-Party Signature Verification](https://docs.dify.ai/en/develop-plugin/publishing/standards/third-party-signature-verification)
