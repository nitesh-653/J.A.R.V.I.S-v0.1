"""
webpage_summarizer.py — JARVIS V01 Webpage Summarizer
Fetches any URL, strips it to clean text, and summarizes it with Gemini.
JARVIS reads the summary aloud. Great for articles, docs, and blog posts.
"""
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_api_key() -> str:
    config_path = _base_dir() / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

_SYSTEM_PROMPT = """\
You are a sharp, concise summarizer. Given webpage content, produce a clear summary.
Format:
- 1-sentence TL;DR at the top
- 4-6 key bullet points
- 1-sentence closing takeaway
Keep it tight — no fluff, no filler. Plain text only, no markdown headers."""

def _fetch_clean_text(url: str) -> tuple[str, str]:
    """Returns (clean_text, error). Strips boilerplate, keeps article body."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return "", f"Could not fetch page: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "form", "noscript", "iframe", "figure"]):
        tag.decompose()

    # Prefer <article> or <main> if present
    body = soup.find("article") or soup.find("main") or soup.find("body")
    if body is None:
        return "", "Page has no readable body."

    text = body.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r"\s{2,}", " ", text)
    # Trim to ~6000 chars to stay within token budget
    return text[:6000], ""

def webpage_summarizer(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    url    = parameters.get("url", "").strip()
    detail = parameters.get("detail", "standard").lower()  # standard | detailed | one-liner

    if not url:
        return "Please provide the URL of the page you'd like me to summarize, sir."

    # Ensure protocol
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if player:
        player.write_log(f"[WebSummarizer] Fetching: {url[:70]}")
    if speak:
        speak("Fetching the page and summarizing it now, sir.")

    text, error = _fetch_clean_text(url)
    if error:
        return error

    if len(text) < 100:
        return "The page doesn't appear to have enough readable content to summarize, sir."

    # Adjust prompt for detail level
    system = _SYSTEM_PROMPT
    if detail == "detailed":
        system = system.replace("4-6 key bullet points", "8-10 key bullet points")
    elif detail == "one-liner":
        system = "Summarize the following webpage in exactly one sentence. No bullets, no headers."

    try:
        genai.configure(api_key=_get_api_key())
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system,
        )
        response = model.generate_content(
            f"Page URL: {url}\n\nContent:\n{text}"
        )
        summary = response.text.strip()
    except Exception as e:
        return f"Summarization failed: {e}"

    if player:
        player.write_log(f"[WebSummarizer] ✅ {len(summary)} chars")

    if speak:
        # Read aloud — trim to ~500 chars so it's not overwhelming
        spoken = summary[:500] + ("..." if len(summary) > 500 else "")
        speak(spoken)

    return summary
