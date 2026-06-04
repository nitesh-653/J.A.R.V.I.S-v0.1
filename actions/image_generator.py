"""
image_generator.py — Mark XXXIX AI Image Generator (Imagen 3 via Gemini API)
Generates images from text prompts and saves them to Desktop.
"""
import base64
import json
import re
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_api_key() -> str:
    config_path = _base_dir() / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

def _get_desktop() -> Path:
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            desktop = Path(winreg.QueryValueEx(key, "Desktop")[0])
        except Exception:
            desktop = Path.home()
    return desktop

def image_generator(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    prompt       = parameters.get("prompt", "").strip()
    aspect_ratio = parameters.get("aspect_ratio", "1:1").strip()
    count        = int(parameters.get("count", 1))

    if not prompt:
        return "Please describe the image you'd like me to generate."

    if player:
        player.write_log(f"[ImageGen] Prompt: {prompt[:60]}")
    if speak:
        speak("Generating your image now, sir.")

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=_get_api_key())
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=min(count, 4),
                aspect_ratio=aspect_ratio,
                output_mime_type="image/png",
            ),
        )
    except Exception as e:
        return f"Image generation failed: {e}"

    desktop = _get_desktop()
    safe_name = re.sub(r"[^\w\s-]", "", prompt[:25]).strip().replace(" ", "_") or "image"
    ts = datetime.now().strftime("%H%M%S")
    saved = []

    for i, img in enumerate(response.generated_images):
        suffix = f"_{i+1}" if len(response.generated_images) > 1 else ""
        out_path = desktop / f"{safe_name}{suffix}_{ts}.png"
        try:
            out_path.write_bytes(img.image.image_bytes)
            saved.append(str(out_path))
        except Exception as e:
            print(f"[ImageGen] ❌ Save failed: {e}")

    if not saved:
        return "Image generated but could not be saved."

    try:
        if sys.platform == "win32":
            subprocess.Popen(["start", "", saved[0]], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", saved[0]])
        else:
            subprocess.Popen(["xdg-open", saved[0]])
    except Exception:
        pass

    if player:
        player.write_log(f"[ImageGen] ✅ {len(saved)} image(s) saved to Desktop")
    plural = f"{len(saved)} images" if len(saved) > 1 else "image"
    return f"Generated {plural} and saved to Desktop, sir."
