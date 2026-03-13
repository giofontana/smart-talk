"""Constants for the Smart Talk integration."""

DOMAIN = "smart_talk"

CONF_AGENT_URL = "agent_url"                    # REST URL  http://host:8765/conversation
CONF_AGENT_NAME = "agent_name"
CONF_ADDON_HOST = "addon_host"                  # Hostname/IP of the Smart Talk add-on
CONF_STT_PORT = "stt_port"                      # Wyoming STT TCP port (default 10300)
CONF_TTS_PORT = "tts_port"                      # Wyoming TTS TCP port (default 10301)

DEFAULT_AGENT_URL = "http://localhost:8765/conversation"
DEFAULT_AGENT_NAME = "Smart Talk"
DEFAULT_ADDON_HOST = "localhost"
DEFAULT_STT_PORT = 10300
DEFAULT_TTS_PORT = 10301
