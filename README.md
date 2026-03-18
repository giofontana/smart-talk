# Smart Talk — AI Voice Agent for Home Assistant

Smart Talk turns Home Assistant's voice pipeline into a fully local, context-aware AI assistant. It replaces the built-in conversation agent with a LangChain-powered agent that understands natural language, controls devices by semantic similarity rather than exact entity IDs, and works with any OpenAI-compatible LLM (Ollama, LM Studio, OpenAI, etc.).

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     Home Assistant                             │
│                                                                │
│  ┌───────────────────────────────────────────────────────┐    │
│  │              HA Voice Pipeline                         │    │
│  │   Mic → STT ──► Conversation Agent ──► TTS → Speaker  │    │
│  └──────────┬──────────────┬───────────────┬─────────────┘    │
│             │ Wyoming      │ Smart Talk    │ Wyoming           │
│             │ integration  │ integration   │ integration       │
└─────────────┼──────────────┼───────────────┼───────────────── ┘
              │              │               │
   ┌──────────▼──────┐       │    ┌──────────▼──────┐
   │ wyoming-faster- │       │    │  wyoming-piper  │
   │ whisper         │       │    │  (podman)       │
   │ (podman)        │       │    │  :10200         │
   │ :10300          │       │    └─────────────────┘
   └─────────────────┘       │
                             │ HTTP POST /conversation
              ┌──────────────▼──────────────────────────┐
              │       Smart Talk Agent (podman / K8s)    │
              │  FastAPI · LangChain · :8765             │
              └──────────────────────────────────────────┘
```

---

## Components

| Component | Description |
|---|---|
| **smart-talk-agent** | Standalone Python service. FastAPI REST server, LangChain ReAct agent, sentence-transformers entity resolver, HA WebSocket client. |
| **smart-talk-integration** | HA Custom Integration. Registers Smart Talk as a HA Conversation Agent and forwards requests directly to the agent. |
| **wyoming-faster-whisper** | Standalone STT service (podman). Registered in HA via the built-in Wyoming integration. |
| **wyoming-piper** | Standalone TTS service (podman). Registered in HA via the built-in Wyoming integration. |
| **docker-compose.yml** | Deploys the agent standalone for non-Kubernetes setups. |
| **k8s/** | Kustomize manifests for Kubernetes deployment of the agent. |

---

## Requirements

- **Home Assistant** 2024.1 or later (with Voice Pipeline support)
- **Python** 3.12+ (for the agent; the add-on uses its own container)
- **An OpenAI-compatible LLM endpoint**, e.g.:
  - [Ollama](https://ollama.com) (local, recommended)
  - [LM Studio](https://lmstudio.ai)
  - OpenAI API
- **Docker** (or a Kubernetes cluster) for the agent
- **HA Supervisor** (HA OS or Supervised install) for the add-on

---

## Quick Start

### Step 1 — Deploy the Smart Talk Agent

```bash
# Clone the repository
git clone https://github.com/your-org/smart-talk.git
cd smart-talk

# Create your local config file
cp smart-talk-agent/example-config.yaml config.yaml

# Edit config.yaml — at minimum set ha_token, ha_url, and llm_base_url
$EDITOR config.yaml

# Start the agent
docker compose up -d

# Verify it is healthy
curl http://localhost:8765/health
# → {"status": "ok"}
```

### Step 2 — Run STT (faster-whisper) with Podman

```bash
mkdir -p ~/.local/share/wyoming/whisper
podman run -d --name wyoming-whisper \
  --userns=keep-id \
  -p 10300:10300 \
  -v ~/.local/share/wyoming/whisper:/data:z \
  -e HF_HOME=/data \
  docker.io/rhasspy/wyoming-whisper \
  --model small-int8 --uri tcp://0.0.0.0:10300 \
  --data-dir /data --download-dir /data
```

Change `--model` to `base-int8`, `small-int8`, or `medium-int8` for better accuracy.  
Omit `--language en` to enable auto-detection.

### Step 3 — Run TTS (piper) with Podman

```bash
mkdir -p ~/.local/share/wyoming/piper
podman run -d --name wyoming-piper \
  --userns=keep-id \
  -p 10200:10200 \
  -v ~/.local/share/wyoming/piper:/data:z \
  docker.io/rhasspy/wyoming-piper \
  --voice en_US-lessac-medium --uri tcp://0.0.0.0:10200 \
  --data-dir /data --download-dir /data
```

### Step 4 — Register Wyoming services in HA

For each service (STT and TTS):
1. Go to **Settings → Devices & Services → + Add Integration**.
2. Search for **Wyoming Protocol** and click it.
3. Enter the host (`localhost` or the machine's IP) and port (`10300` for STT, `10200` for TTS).
4. Click **Submit** — HA will detect whether it's an STT or TTS service automatically.

### Step 5 — Install the Custom Integration

Copy (or symlink) the integration folder into your HA config:

```bash
cp -r smart-talk-integration/custom_components/smart_talk \
      /path/to/homeassistant/config/custom_components/
```

Then restart Home Assistant.

### Step 6 — Configure the Integration in the HA UI

1. Go to **Settings → Devices & Services → + Add Integration**.
2. Search for **Smart Talk** and click it.
3. Enter:
   - **Agent URL**: `http://<agent-host>:8765/conversation`
   - **Agent name**: e.g. `Smart Talk`
4. Click **Submit**.
5. Go to **Settings → Voice Assistants**, select your assistant, and set:
   - **Conversation Agent** → **Smart Talk**
   - **Speech-to-text** → the faster-whisper entity (added via Wyoming)
   - **Text-to-speech** → the piper entity (added via Wyoming)

---

## Configuration Reference

### Agent (`config.yaml` / environment variables)

All environment variables use the prefix `ST_`.

| Key | Env var | Default | Description |
|---|---|---|---|
| `llm_base_url` | `ST_LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible endpoint |
| `llm_api_key` | `ST_LLM_API_KEY` | `sk-no-key` | API key (omit for local LLMs) |
| `llm_model` | `ST_LLM_MODEL` | `gpt-4o-mini` | Model name |
| `llm_temperature` | `ST_LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `llm_max_tokens` | `ST_LLM_MAX_TOKENS` | `2048` | Max LLM response tokens |
| `ha_url` | `ST_HA_URL` | `http://homeassistant.local:8123` | HA base URL |
| `ha_token` | `ST_HA_TOKEN` | _(required)_ | HA Long-Lived Access Token |
| `ha_ssl_verify` | `ST_HA_SSL_VERIFY` | `true` | Verify TLS certs |
| `server_host` | `ST_SERVER_HOST` | `0.0.0.0` | Bind address |
| `server_port` | `ST_SERVER_PORT` | `8765` | HTTP REST port |
| `log_level` | `ST_LOG_LEVEL` | `INFO` | `DEBUG\|INFO\|WARNING\|ERROR` |
| `embedding_model` | `ST_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `similarity_threshold` | `ST_SIMILARITY_THRESHOLD` | `0.35` | Min cosine similarity for entity match |
| `device_refresh_interval` | `ST_DEVICE_REFRESH_INTERVAL` | `300` | Seconds between HA entity cache refreshes |

### Add-on options

Not applicable — STT and TTS are provided by standalone `wyoming-faster-whisper` and `wyoming-piper` podman containers configured via their CLI arguments. See **Quick Start** above for the recommended options.

---

## Adding Custom Tools

Extend `SmartTalkTool` (from `app/agent/tools/base.py`) and register the tool in `app/agent/tools/registry.py`.

```python
# smart-talk-agent/app/agent/tools/ha_custom.py
from langchain.tools import tool
from pydantic import Field

from app.agent.tools.base import SmartTalkTool
from app.ha.client import HAClient
from app.search.device_resolver import DeviceResolver


class MyCustomTool(SmartTalkTool):
    """Example: sends a custom HA service call."""

    name: str = "custom_action"
    description: str = (
        "Use this tool when the user asks to perform MY_CUSTOM_ACTION. "
        "Input: device name as a plain string."
    )

    async def _arun(self, device: str) -> str:
        entity = await self._resolve_entity(device, domain_filter=["my_domain"])
        if entity is None:
            return f"Could not find a device matching '{device}'."

        await self.ha_client.call_service(
            domain="my_domain",
            service="my_service",
            entity_id=entity.entity_id,
        )
        return f"Done! Called my_service on {entity.attributes.get('friendly_name', entity.entity_id)}."
```

Then add an instance of `MyCustomTool` to the list returned by `build_tools()` in `registry.py`.

---

## Supported LLMs

Smart Talk works with any OpenAI-compatible endpoint. Tested models:

| Model | Provider | Notes |
|---|---|---|
| `qwen2.5:7b` | Ollama (local) | Recommended for home servers |
| `qwen2.5:14b` | Ollama (local) | Better reasoning, needs ≥16 GB RAM |
| `llama3.1:8b` | Ollama (local) | Good general performance |
| `mistral:7b` | Ollama (local) | Fast, lower memory use |
| `gpt-4o-mini` | OpenAI API | Cloud; best tool-calling accuracy |
| `gpt-4o` | OpenAI API | Cloud; highest quality |
| Any GGUF via LM Studio | Local | Use the LM Studio server URL |

---

## Kubernetes Deployment

```bash
# Apply all manifests (creates namespace, configmap, secret, deployment, service)
kubectl apply -k k8s/

# Check rollout
kubectl rollout status deployment/smart-talk-agent -n smart-talk

# Tail logs
kubectl logs -f deployment/smart-talk-agent -n smart-talk

# Verify health
kubectl port-forward svc/smart-talk-agent 8765:8765 -n smart-talk &
curl http://localhost:8765/health
```

> **Secrets**: The `k8s/secret.yaml` file contains placeholder base64 values.
> Replace them with your real values before applying, or use
> [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) /
> [External Secrets Operator](https://external-secrets.io) to manage them
> safely in git.

---

## Architecture Deep Dive

### Agent REST API

The Smart Talk agent exposes a REST endpoint at `POST http://<host>:8765/conversation`.

**Request**
```json
{ "session_id": "uuid", "text": "Turn off the kitchen lights", "language": "en" }
```

**Response**
```json
{ "session_id": "uuid", "text": "Done, kitchen lights are off.", "language": "en" }
```

The Smart Talk integration connects directly to the agent's REST endpoint and forwards the response back to HA.

### Agent → HA: WebSocket API

The Smart Talk agent communicates with Home Assistant exclusively through the **HA WebSocket API** (`ws://ha:8123/api/websocket`):

1. On startup, the agent opens a persistent authenticated WebSocket connection to HA.
2. Each tool call (e.g. `call_service`, `get_states`) sends a JSON command with an incrementing `id` and awaits the matching `result` message.
3. The connection auto-reconnects with exponential backoff on disconnection.

This provides lower latency than REST and enables future features like real-time state-change subscriptions.

### Wyoming Protocol (STT / TTS)

STT and TTS are provided by standalone services registered in HA via the built-in **Wyoming** integration:

- **`wyoming-faster-whisper`** — TCP server on port `10300`. Receives raw PCM audio from HA, returns transcription.
- **`wyoming-piper`** — TCP server on port `10200`. Receives text from HA, returns synthesised audio.

Both run as podman containers (see Quick Start). HA discovers their capabilities automatically when you add them via **Settings → Devices & Services → Wyoming Protocol**.

### Semantic Entity Resolution

Instead of requiring exact entity IDs, Smart Talk resolves natural-language device references using cosine similarity on sentence-transformer embeddings:

1. On startup (and every `device_refresh_interval` seconds) all HA entities are fetched and their `friendly_name` strings are embedded via `sentence-transformers`.
2. When a tool receives a query like `"the lamp in the living room"`, `DeviceResolver.resolve()` computes the query embedding and returns the top-k entities above `similarity_threshold`.
3. The tool acts on the best match, making commands robust to paraphrasing, typos, and language variations.
