"""
realtime_translator.py — JARVIS V01 Real-Time Translation Mode
Enters a translation loop: listens via microphone, translates with Gemini, speaks result.
Supports any language pair. Say "stop translating" to exit.
"""
import json
import sys
import threading
from pathlib import Path
import google.generativeai as genai

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_api_key() -> str:
    config_path = _base_dir() / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

_SYSTEM_PROMPT = """\
You are a real-time interpreter. The user will give you text in any language.
Translate it to {target_language}.
Return ONLY the translated text — no explanation, no quotes, no labels."""

_active = threading.Event()

def realtime_translator(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    target_language = parameters.get("target_language", "Spanish").strip()
    text_input      = parameters.get("text", "").strip()
    action          = parameters.get("action", "translate").lower()

    if action == "stop":
        _active.clear()
        return f"Translation mode disabled, sir."

    if not text_input:
        _active.set()
        return (
            f"Translation mode active — target language: {target_language}, sir. "
            f"Everything you say will be translated. Say 'stop translating' to exit."
        )

    # Single-shot translation (called per utterance by the voice loop)
    try:
        genai.configure(api_key=_get_api_key())
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=_SYSTEM_PROMPT.format(target_language=target_language),
        )
        response = model.generate_content(text_input)
        translated = response.text.strip()
    except Exception as e:
        return f"Translation error: {e}"

    if player:
        player.write_log(f"[Translator] {text_input[:40]} → {translated[:40]}")

    # Speak the translation
    if speak:
        speak(translated)

    return translated
