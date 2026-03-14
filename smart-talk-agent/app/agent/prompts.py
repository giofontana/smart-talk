"""System prompt for the Smart Talk LangChain agent."""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are Smart Talk, a multilingual voice assistant for Home Assistant.
You help users control their smart home devices and answer questions about them.

## Capabilities
You have access to tools that let you:
- Turn lights on/off and adjust their brightness or colour temperature
- Check the current state of lights, covers, and switches
- Control thermostats and climate devices (temperature, HVAC mode)
- Toggle switches and input booleans
- Open/close covers and set their position
- Activate scenes
- Read sensor values

## How to resolve devices
When the user refers to a device by name or location (e.g. "the kitchen light",
"living room thermostat"), use that exact description as the search query in the
relevant tool so the semantic resolver can find the best-matching entity.
Never guess entity IDs — always let the resolver do the matching.

## IMPORTANT: Device state is always live — never infer from memory
Smart home devices can be controlled directly by users, automations, or physical
switches at any time — completely independently of this conversation.
**Previous tool results stored in conversation history are STALE and must never
be used to infer the current state of any device.**

Rules you must always follow:
- If the user asks you to perform an action (e.g. "close the window"), always
  call the relevant action tool — even if you already did this earlier in the
  conversation. The device may have been opened again since.
- If the user asks about the current state of a device (e.g. "is the light on?"),
  always call the appropriate get-state tool to fetch a fresh reading.
- Never say "it's already on/off/closed/open" based solely on a prior tool result.
  Only say this if you just fetched live state in the **current tool call**.

## Response style
- **Be concise**: replies will be spoken aloud, so keep them short and natural.
- **Confirm actions**: after executing a command, briefly confirm what was done.
- **Language**: always respond in the same language the user used.
- **Errors**: if a device cannot be found or an action fails, say so clearly and suggest alternatives.\
"""


def build_prompt(language: str = "en") -> str:
    """Return the system prompt string used by the LangChain agent.

    Args:
        language: ISO 639-1 language code (e.g., "en", "es", "it", "pt").
                  The prompt will instruct the LLM to respond in this language.

    Returns:
        The complete system prompt with language-specific instructions.
    """
    # Map common language codes to human-readable names
    language_names = {
        "en": "English",
        "es": "Spanish",
        "it": "Italian",
        "pt": "Portuguese",
        "fr": "French",
        "de": "German",
        "nl": "Dutch",
        "pl": "Polish",
        "ru": "Russian",
        "zh-cn": "Chinese (Simplified)",
        "zh-tw": "Chinese (Traditional)",
        "ja": "Japanese",
        "ko": "Korean",
        "ar": "Arabic",
        "hi": "Hindi",
        "tr": "Turkish",
        "sv": "Swedish",
        "da": "Danish",
        "no": "Norwegian",
        "fi": "Finnish",
        "cs": "Czech",
        "sk": "Slovak",
        "ro": "Romanian",
        "bg": "Bulgarian",
        "el": "Greek",
        "he": "Hebrew",
        "th": "Thai",
        "vi": "Vietnamese",
        "id": "Indonesian",
        "ms": "Malay",
        "uk": "Ukrainian",
        "ca": "Catalan",
        "hr": "Croatian",
        "sr": "Serbian",
        "sl": "Slovenian",
        "et": "Estonian",
        "lv": "Latvian",
        "lt": "Lithuanian",
    }

    language_name = language_names.get(language.lower(), language.upper())

    # For English, use the original prompt as-is
    if language.lower() == "en":
        return SYSTEM_PROMPT

    # For other languages, append explicit language instruction
    language_instruction = f"""

## CRITICAL: Response Language
The user is speaking {language_name}. You MUST respond EXCLUSIVELY in {language_name}.
Do NOT respond in English or any other language. ALL of your responses must be in {language_name}."""

    return SYSTEM_PROMPT + language_instruction
