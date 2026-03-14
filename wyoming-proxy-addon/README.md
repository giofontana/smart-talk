# Wyoming Polyglot Proxy

A Home Assistant add-on that provides a Wyoming protocol proxy with automatic language detection and dynamic voice selection for text-to-speech.

## Features

- **Automatic Language Detection**: Detects the language of TTS text and selects the appropriate voice
- **Single Piper Instance**: Works with one Piper instance serving multiple voices dynamically
- **Transparent STT Proxy**: Forwards speech-to-text requests to your Whisper instance unchanged
- **Easy Configuration**: Configure language→voice mappings via the HA UI
- **BYOW**: Bring Your Own Whisper/Piper - proxy forwards to your existing instances

## How It Works

```
Home Assistant Voice Pipeline
        ↓
Wyoming Proxy Add-on (ports 10300 STT / 10200 TTS)
├─ STT: Transparent forwarding to your Whisper instance
└─ TTS: Language detection → Voice selection → Forward to Piper
```

### Architecture

**STT Flow (Transparent):**
```
HA → Proxy (10300) → Your Whisper → Proxy → HA
```

**TTS Flow (With Language Detection):**
```
HA → Proxy (10200)
      ↓
  Detect language from text
      ↓
  Select voice from mapping (en→en_US-lessac-medium, es→es_ES-mls-medium, etc.)
      ↓
  Your Piper (with voice parameter)
      ↓
  Proxy → HA (with audio)
```

## Installation

### Option 1: Local Add-on (Development)

1. Copy this directory to your Home Assistant addons folder:
   ```bash
   cp -r wyoming-proxy-addon /path/to/homeassistant/addons/
   ```

2. Restart Home Assistant

3. Go to **Settings → Add-ons → Local Add-ons**

4. Install "Wyoming Polyglot Proxy"

### Option 2: GitHub Repository (Recommended)

1. Push this add-on to a GitHub repository

2. In Home Assistant:
   - Go to **Settings → Add-ons → Add-on Store → ⋮ (menu) → Repositories**
   - Add your repository URL
   - Install "Wyoming Polyglot Proxy" from the add-on store

## Configuration

### Add-on Configuration

Configure the add-on with your Whisper and Piper instance URLs and voice mappings:

```yaml
whisper_url: "tcp://192.168.1.100:10300"  # Your Whisper instance
piper_url: "tcp://192.168.1.100:10200"    # Your Piper instance
voice_mapping:
  en: "en_US-lessac-medium"
  es: "es_ES-mls-medium"
  it: "it_IT-riccardo-x_low"
  pt: "pt_BR-faber-medium"
  fr: "fr_FR-siwis-medium"
  de: "de_DE-thorsten-medium"
log_level: "info"  # debug, info, warning, or error
```

### Finding Piper Voices

Available Piper voices can be found at:
- https://huggingface.co/rhasspy/piper-voices/tree/main

Piper will automatically download voices on first use.

### Register Wyoming Services in Home Assistant

After starting the add-on:

1. Go to **Settings → Devices & Services → + Add Integration**

2. Search for **Wyoming Protocol**

3. Add STT service:
   - Host: `localhost` (or add-on hostname)
   - Port: `10300`

4. Add TTS service:
   - Host: `localhost` (or add-on hostname)
   - Port: `10200`

### Create Voice Assistant

1. Go to **Settings → Voice Assistants → + Add Assistant**

2. Configure:
   - **Conversation Agent**: Your conversation agent (e.g., Smart Talk)
   - **Speech-to-text**: Wyoming Proxy (the STT entity you just added)
   - **Text-to-speech**: Wyoming Proxy (the TTS entity you just added)
   - **Language**: Any language (will be auto-detected)

## Testing

### Test TTS Language Detection

You can test the proxy's language detection using `nc` (netcat):

```bash
# English
echo '{"type":"synthesize","data":{"text":"Hello, how are you today?"}}' | nc localhost 10200

# Spanish
echo '{"type":"synthesize","data":{"text":"Hola, ¿cómo estás?"}}' | nc localhost 10200

# Italian
echo '{"type":"synthesize","data":{"text":"Ciao, come stai?"}}' | nc localhost 10200
```

### Check Logs

View logs in Home Assistant:
- Go to **Settings → Add-ons → Wyoming Polyglot Proxy → Log**

Expected logs:
```
INFO: TTS request: Hola, ¿cómo estás?
DEBUG: Detected language: es (confidence: 0.99)
INFO: Language 'es' → Voice 'es_ES-mls-medium'
```

## How It Works with Smart Talk

This add-on is designed to work with the [Smart Talk](../README.md) conversational AI agent:

1. **User speaks** (in any language) → Whisper transcribes via proxy
2. **Smart Talk** detects language from text → Responds in detected language
3. **TTS Proxy** detects language from response → Selects appropriate voice
4. **Piper** synthesizes audio with correct voice → User hears response in their language

The entire flow is automatic - no language selection needed!

## Troubleshooting

### Proxy won't start

- Check that ports 10300 and 10200 are not in use
- Verify `whisper_url` and `piper_url` are correct
- Check add-on logs for specific errors

### TTS always uses English voice

- Check that voice mappings are configured correctly
- Verify the text being sent to TTS is long enough for detection (>5 characters)
- Check logs to see what language was detected

### STT not working

- Verify your Whisper instance is running and accessible
- Check that `whisper_url` is correct
- The proxy transparently forwards - if Whisper works directly, it should work through the proxy

## Advanced Configuration

### Confidence Threshold (Future)

Currently, the proxy uses any language detection result. A future enhancement will add a confidence threshold setting to fall back to English for low-confidence detections.

### Voice Caching (Future)

For very short responses where language detection might be unreliable, a future version will cache the last-used voice per client.

## Technical Details

- **Language Detection**: Uses `langdetect` library (Google's language-detection algorithm)
- **Wyoming Protocol**: Implements Wyoming protocol JSONL message format
- **Stateless Design**: No session tracking or shared state between requests
- **Performance**: Language detection adds ~1-5ms latency per TTS request

## License

Same as Smart Talk project.

## Contributing

Issues and pull requests welcome!
