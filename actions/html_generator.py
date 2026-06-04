"""
html_generator.py — Mark XXXIX HTML Webpage Generator
Generates beautiful, modern HTML/CSS/JS files using Gemini and opens them in the browser.
"""
import json
import re
import subprocess
import sys
import webbrowser
from datetime import datetime
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
You are an expert frontend web developer.
Generate a single, self-contained HTML file with embedded CSS and JS.
Requirements:
- Modern, beautiful design with gradients, shadows, and animations
- Fully responsive (mobile-friendly)
- Use CSS variables for theming
- Smooth animations and hover effects
- Professional typography (use Google Fonts via @import)
- Dark mode support where appropriate
Return ONLY the raw HTML. No explanation, no markdown fences, no comments outside the file."""

def html_generator(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    prompt  = parameters.get("prompt", "").strip()
    title   = parameters.get("title", "").strip()
    style   = parameters.get("style", "modern").strip()

    if not prompt:
        return "Please describe what webpage you'd like me to generate."

    if player:
        player.write_log(f"[HTMLGen] Generating: {prompt[:60]}")
    if speak:
        speak("Generating your webpage now, sir.")

    try:
        genai.configure(api_key=_get_api_key())
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=_SYSTEM_PROMPT,
        )
        user_prompt = f"Create a {style} webpage: {prompt}"
        if title:
            user_prompt += f"\nPage title: {title}"
        response = model.generate_content(user_prompt)
        html = response.text.strip()
        html = re.sub(r"^```html?\s*", "", html, flags=re.IGNORECASE)
        html = re.sub(r"\s*```$", "", html).strip()
    except Exception as e:
        return f"Could not generate HTML: {e}"

    # Save to Desktop
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            desktop = Path(winreg.QueryValueEx(key, "Desktop")[0])
        except Exception:
            desktop = Path.home()

    safe_name = re.sub(r"[^\w\s-]", "", prompt[:30]).strip().replace(" ", "_") or "webpage"
    timestamp = datetime.now().strftime("%H%M%S")
    file_path = desktop / f"{safe_name}_{timestamp}.html"

    try:
        file_path.write_text(html, encoding="utf-8")
    except Exception as e:
        return f"Generated HTML but could not save: {e}"

    try:
        webbrowser.open(file_path.as_uri())
    except Exception:
        pass

    if player:
        player.write_log(f"[HTMLGen] ✅ Saved: {file_path.name}")
    return f"Webpage generated and saved to Desktop as '{file_path.name}', sir."
