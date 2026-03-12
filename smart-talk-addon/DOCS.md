# Smart Talk — Home Assistant Add-on

## Overview

The **Smart Talk** add-on turns Home Assistant into a fully voice-capable AI assistant by bundling three services in a single container:

| Service | Protocol | Port |
|---|---|---|
| **STT server** | Wyoming (TCP) | 10300 |
| **TTS server** | Wyoming (TCP) | 10301 |
| **Conversation proxy** | HTTP REST | 8080 |

- The **STT server** uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) to transcribe speech.
- The **TTS server** uses [piper-tts](https://github.com/rhasspy/piper) to generate natural-sounding speech.
- The **Conversation proxy** bridges HA's conversation integration to the Smart Talk AI Agent over WebSocket.

---

## Requirements

- A running [Smart Talk Agent](https://github.com/your-org/smart-talk-agent) reachable from HA.
- Home Assistant with the **Wyoming** integration available (Core 2023.9+).

---

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**.
2. Click the **⋮ menu → Repositories** and add the URL of this repository.
3. Find **Smart Talk** in the store and click **Install**.
4. Configure the add-on (see below) then click **Start**.

---

## Configuration

| Option | Default | Description |
|---|---|---|
| `agent_url` | `ws://localhost:8765/ws` | WebSocket URL of the Smart Talk Agent |
| `stt_model` | `tiny` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3` |
| `stt_language` | `auto` | Language code for STT (e.g. `en`, `fr`) or `auto` for automatic detection |
| `tts_voice` | `en_US-lessac-medium` | Piper voice name (see [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices)) |
| `tts_language` | `en` | Language tag reported to HA for the TTS output |

### Example configuration

```yaml
agent_url: "ws://192.168.1.100:8765/ws"
stt_model: "small"
stt_language: "auto"
tts_voice: "en_US-lessac-medium"
tts_language: "en"
```

> **Tip:** Larger Whisper models are more accurate but slower. On a Raspberry Pi 4, `tiny` or `base` is recommended. On an x86 machine, `small` gives a good balance.

> **Voice models** are downloaded automatically from HuggingFace on first use and cached in `/share/smart_talk/piper_models/`. This requires an internet connection on first boot.

---

## Setting up the HA integrations

### 1 — Wyoming STT

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Wyoming** and add it.
3. Set **Host** to the HA host (or `localhost` if running locally) and **Port** to `10300`.
4. Select this entry as the STT provider in your voice assistant pipeline.

### 2 — Wyoming TTS

1. Add another **Wyoming** integration instance.
2. Set **Port** to `10301`.
3. Select this entry as the TTS provider in your voice assistant pipeline.

### 3 — Conversation proxy

In your voice assistant pipeline, set the **Conversation agent** to the custom integration that points to `http://<ha-host>:8080/conversation`.

If you use the companion Smart Talk HA integration, it will configure this automatically.

---

## Troubleshooting

### Add-on fails to start
- Check the add-on logs in **Settings → Add-ons → Smart Talk → Logs**.
- Ensure no other service is using ports 10300, 10301, or 8080.

### STT always returns empty text
- The Whisper model may still be downloading. Wait a minute and check the logs for "Whisper model loaded".
- Try a larger model (`base` or `small`) for better accuracy on noisy audio.

### TTS voice model download fails
- The container needs internet access. Verify HA's network settings.
- You can pre-download model files and place them in `/share/smart_talk/piper_models/` manually.

### Conversation proxy returns 504 Gateway Timeout
- The Smart Talk Agent at `agent_url` is not reachable. Verify the URL and that the agent is running.
- Check firewall rules between the HA host and the agent host.

### High memory usage
- Whisper models are loaded into RAM. Use `tiny` if memory is constrained.
- Piper voice models are small (~60 MB) and should not cause issues.
