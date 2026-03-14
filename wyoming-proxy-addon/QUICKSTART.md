# Quick Start Guide - Wyoming Polyglot Proxy

This guide will help you get the Wyoming Polyglot Proxy up and running quickly.

## Prerequisites

1. **Running Whisper instance** (for STT)
   ```bash
   podman run -d --name wyoming-whisper \
     --userns=keep-id \
     -p 10300:10300 \
     -v ~/.local/share/wyoming/whisper:/data:z \
     -e HF_HOME=/data \
     docker.io/rhasspy/wyoming-whisper \
     --model small-int8 --uri tcp://0.0.0.0:10300 \
     --data-dir /data --download-dir /data
   ```
   **Note:** Omit `--language en` to allow auto-detection (though proxy doesn't use it).

2. **Running Piper instance** (for TTS)
   ```bash
   podman run -d --name wyoming-piper \
     --userns=keep-id \
     -p 10200:10200 \
     -v ~/.local/share/wyoming/piper:/data:z \
     docker.io/rhasspy/wyoming-piper \
     --uri tcp://0.0.0.0:10200 \
     --data-dir /data --download-dir /data
   ```
   **Note:** NO `--voice` flag - let Piper serve any voice dynamically!

## Development Testing (Without Home Assistant)

### 1. Build the image

```bash
cd /gfontana/Dev/projects/personal/ai-ml/smart-talk/wyoming-proxy-addon
podman build -t wyoming-polyglot-proxy .
```

### 2. Create test configuration

```bash
mkdir -p /tmp/wyoming-proxy-test
cat > /tmp/wyoming-proxy-test/options.json <<EOF
{
  "whisper_url": "tcp://localhost:10300",
  "piper_url": "tcp://localhost:10200",
  "voice_mapping": {
    "en": "en_US-lessac-medium",
    "es": "es_ES-mls-medium",
    "it": "it_IT-riccardo-x_low",
    "pt": "pt_BR-faber-medium",
    "fr": "fr_FR-siwis-medium"
  },
  "log_level": "debug"
}
EOF
```

### 3. Run the proxy

```bash
podman run --rm -it \
  --name wyoming-proxy \
  --network=host \
  -v /tmp/wyoming-proxy-test:/data:z \
  wyoming-polyglot-proxy
```

You should see:
```
INFO: Starting Wyoming Polyglot Proxy
INFO: Whisper upstream: tcp://localhost:10300
INFO: Piper upstream: tcp://localhost:10200
INFO: Voice mapping: 5 languages
INFO: STT proxy listening on 0.0.0.0:10300
INFO: TTS proxy listening on 0.0.0.0:10200
DEBUG: Voice mapping: {'en': 'en_US-lessac-medium', 'es': 'es_ES-mls-medium', ...}
```

### 4. Test TTS language detection

In another terminal:

```bash
# Test English
echo '{"type":"synthesize","data":{"text":"Hello, how are you today?"}}' | nc localhost 10200

# Test Spanish
echo '{"type":"synthesize","data":{"text":"Hola, ¿cómo estás hoy?"}}' | nc localhost 10200

# Test Italian
echo '{"type":"synthesize","data":{"text":"Ciao, come stai oggi?"}}' | nc localhost 10200
```

Check the proxy logs - you should see:
```
DEBUG: TTS request: Hola, ¿cómo estás hoy?
DEBUG: Detected language: es (confidence: 0.99)
INFO: Language 'es' → Voice 'es_ES-mls-medium'
```

## Home Assistant Installation

### Option 1: Local Add-on (Quick Testing)

1. Copy the add-on directory to HA:
   ```bash
   scp -r wyoming-proxy-addon homeassistant@your-ha-ip:/addons/
   ```

2. In HA UI:
   - Go to **Settings → Add-ons → Local Add-ons**
   - Click **Wyoming Polyglot Proxy**
   - Click **Install**
   - Configure (see Configuration section below)
   - Click **Start**

### Option 2: GitHub Repository (Production)

1. Create a new GitHub repository for your add-on

2. Push the add-on:
   ```bash
   cd wyoming-proxy-addon
   git init
   git add .
   git commit -m "Initial Wyoming Polyglot Proxy"
   git remote add origin https://github.com/YOUR_USERNAME/ha-wyoming-polyglot-proxy.git
   git push -u origin main
   ```

3. In HA UI:
   - Go to **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
   - Add: `https://github.com/YOUR_USERNAME/ha-wyoming-polyglot-proxy`
   - Install **Wyoming Polyglot Proxy** from the store

## Configuration

After installing, configure the add-on:

```yaml
whisper_url: "tcp://192.168.1.100:10300"  # IP of your Whisper instance
piper_url: "tcp://192.168.1.100:10200"    # IP of your Piper instance
voice_mapping:
  en: "en_US-lessac-medium"
  es: "es_ES-mls-medium"
  it: "it_IT-riccardo-x_low"
  pt: "pt_BR-faber-medium"
  fr: "fr_FR-siwis-medium"
  de: "de_DE-thorsten-medium"
log_level: "info"
```

**Important:** Replace `192.168.1.100` with the actual IP address where Whisper and Piper are running.

## Register Wyoming Services in HA

1. **Add STT Service:**
   - Go to **Settings → Devices & Services → + Add Integration**
   - Search for **Wyoming Protocol**
   - Enter:
     - Host: `localhost` (or the add-on's hostname)
     - Port: `10300`
   - HA will detect it as a Speech-to-Text service

2. **Add TTS Service:**
   - Repeat the process
   - Enter:
     - Host: `localhost`
     - Port: `10200`
   - HA will detect it as a Text-to-Speech service

## Create Voice Assistant

1. Go to **Settings → Voice Assistants → + Add Assistant**

2. Configure:
   - **Name:** "Polyglot Assistant" (or any name)
   - **Conversation Agent:** Smart Talk (or your preferred agent)
   - **Speech-to-text:** Select the Wyoming Proxy STT entity
   - **Text-to-speech:** Select the Wyoming Proxy TTS entity
   - **Language:** Any (will be auto-detected)

3. Click **Create**

## Testing End-to-End

### Test in HA

1. Use the voice assistant interface in HA
2. Speak in different languages:
   - English: "Hello, turn on the kitchen light"
   - Spanish: "Hola, enciende la luz de la cocina"
   - Italian: "Ciao, accendi la luce della cucina"

3. Check the add-on logs:
   - Go to **Settings → Add-ons → Wyoming Polyglot Proxy → Log**
   - You should see language detection logs

### Expected Flow

```
1. User speaks (Spanish): "Hola, enciende la luz"
2. Whisper transcribes: "Hola, enciende la luz"
3. Smart Talk detects Spanish, responds: "¡Hecho! He encendido la luz."
4. TTS Proxy detects Spanish from response text
5. TTS Proxy selects voice: es_ES-mls-medium
6. Piper synthesizes audio with Spanish voice
7. User hears response in Spanish voice
```

## Troubleshooting

### Proxy won't start

- **Check ports:** Ensure ports 10300 and 10200 aren't already in use
- **Check URLs:** Verify `whisper_url` and `piper_url` point to running services
- **Check logs:** View add-on logs for specific error messages

### TTS always uses English

- **Voice mapping:** Ensure voice mappings are configured correctly in add-on config
- **Text length:** Very short text (<5 chars) defaults to English
- **Check logs:** Set `log_level: "debug"` to see detected language

### STT not working

- **Whisper running:** Verify Whisper is accessible at the configured URL
- **Test directly:** Try connecting directly to Whisper to confirm it works
- **Network:** Ensure the proxy can reach Whisper (check firewall/network)

### Wrong voice selected

- **Language codes:** Check that voice mapping uses correct ISO 639-1 codes (en, es, it, etc.)
- **Voice names:** Verify voice names match Piper voice IDs exactly
- **Case sensitive:** Voice names are case-sensitive

## Monitoring

### View Logs

```bash
# In HA UI
Settings → Add-ons → Wyoming Polyglot Proxy → Log

# Or via CLI
ha addons logs wyoming-polyglot-proxy
```

### Debug Mode

Set `log_level: "debug"` in configuration to see:
- Every TTS request text
- Detected language and confidence
- Selected voice for each request
- STT forwarding activity

## What's Next?

- Add more languages to your `voice_mapping`
- Fine-tune voice selection for your preferences
- Monitor which languages are most used in your logs
- Consider contributing improvements back to the project!

## Support

For issues or questions:
- Check the main [README.md](README.md) for detailed documentation
- Review [Smart Talk README](../README.md) for overall system architecture
- Open an issue on GitHub if you find bugs
