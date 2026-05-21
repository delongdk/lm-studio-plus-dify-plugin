# LM Studio Plus — Dify Plugin

**Author:** [delongdk](https://github.com/delongdk)  
**Version:** 0.0.2
**Type:** model  

Connect your [LM Studio](https://lmstudio.ai/) local models to [Dify](https://dify.ai/).

## Background

The existing [LM Studio plugin](https://github.com/stvlynn/lmstudio-Dify-Plugin) on Dify Marketplace encountered runtime errors and appears to be no longer maintained. 
**LM Studio Plus** provides an alternative that runs smoothly and supports more configuration options.

## Features

- **LLM (Chat & Completion)** — both modes route through OpenAI-compatible `/v1/chat/completions`
- **Text Embedding** — via `/v1/embeddings`
- **Streaming** — real-time token streaming with SSE
- **Reasoning / Thinking** — streams `reasoning_content` with `<think>` tag wrapping
- **Tool Calling** — OpenAI function calling format with streaming tool call aggregation
- **Vision** — multi-modal image input support (configurable per model)
- **Structured Output** — generic JSON mode and JSON Schema constraints; schema auto-injected into system prompt
- **API Key Authentication** — optional API key support for secured LM Studio server access
- **Customizable Parameters** — temperature, top_p, top_k, max_tokens, presence_penalty, frequency_penalty, repeat_penalty, seed

## Requirements

- [LM Studio](https://lmstudio.ai/) running with model loaded
- API server mode enabled in LM Studio (default port: `1234`)

## Setup

### 1. LM Studio

1. Install and open [LM Studio](https://lmstudio.ai/)
2. Load a local model (e.g. `lmstudio-community/qwen2.5-7b-instruct`)
3. Start the local server (Developer → Start Server)

![LM Studio](./_assets/lm-studio-plus-02.png)

### 2. Install Plugin

Use one of the following installation paths:

#### Option A. Use prebuilt assets from GitHub Releases

1. Download the latest release assets:
   - `lm_studio_plus-<version>.signed.difypkg`
   - `lm_studio_plus.public.pem`
2. If your Dify Community Edition instance enforces third-party signature verification, place the public key where `plugin_daemon` can read it:

   ```bash
   mkdir -p docker/volumes/plugin_daemon/public_keys
   cp lm_studio_plus.public.pem docker/volumes/plugin_daemon/public_keys/
   ```

3. Configure `plugin_daemon` to trust that public key:

   ```yaml
   services:
     plugin_daemon:
       environment:
         FORCE_VERIFYING_SIGNATURE: true
         THIRD_PARTY_SIGNATURE_VERIFICATION_ENABLED: true
         THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS: /app/storage/public_keys/lm_studio_plus.public.pem
   ```

4. Restart Dify, then upload the signed package in Dify.

   ```bash
   cd docker
   docker compose down
   docker compose up -d
   ```

5. In Dify, go to **Settings → Plugins** and upload `lm_studio_plus-<version>.signed.difypkg`.

If third-party signature verification is disabled, you can also upload the unsigned `lm_studio_plus-<version>.difypkg` asset directly.

#### Option B. Package and sign locally

From the plugin root, generate the package and signature artifacts yourself:

```bash
dify plugin package . -o lm_studio_plus-<version>.difypkg
dify signature generate -f certs/lm_studio_plus
dify signature sign lm_studio_plus-<version>.difypkg -p certs/lm_studio_plus.private.pem
dify signature verify lm_studio_plus-<version>.signed.difypkg -p certs/lm_studio_plus.public.pem
```

Then follow the same Dify public key configuration steps above and upload the signed package.

> **Note:** Third-party signature verification is available in Dify Community Edition only.

### 3. Add Model

1. Go to **Settings → Model Provider → LM Studio Plus → Add Model**

![Add Model](./_assets/lm-studio-plus-01.png)

2. Fill in:
   - **Model Name** — the identifier shown in LM Studio (e.g. `qwen/qwen3-32b`)
   - **Base URL** — your LM Studio server address (default: `http://localhost:1234`)
   - **Completion Mode** — `Chat` (multi-turn) or `Completion` (single prompt)
   - **Context Size** / **Max Tokens** — adjust based on your model
   - **Vision Support** / **Function Call Support** — enable if your model supports them

## Usage

After setup, select any configured LM Studio model from the model dropdown in your Dify applications — Chatbot, Agent, Workflow, etc.

## License

[MIT](LICENSE)

