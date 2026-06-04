"""
youtube_summarizer.py — JARVIS V01 YouTube Chapter & Full Summarizer
Fetches the transcript of any YouTube video and condenses it into bullet points via Gemini.
JARVIS reads the summary aloud. Extends youtube_video.py with summarization.
Requires: youtube-transcript-api
"""
import json
import re
import sys
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
You are an expert video summarizer. Given a YouTube transcript, produce a structured summary.
Format:
• 1-sentence TL;DR
• Key points as concise bullet points (group by topic/chapter if the content is long)
• 1-sentence main takeaway
Be direct — cut filler, ads mentions, and repetition. Plain text only."""

def _extract_video_id(url_or_id: str) -> str:
    """Extract YouTube video ID from a URL or return as-is if already an ID."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    # Assume it's already an ID
    if re.match(r"^[A-Za-z0-9_-]{11}$", url_or_id):
        return url_or_id
    return url_or_id

def _get_transcript(video_id: str) -> tuple[str, str]:
    """Returns (transcript_text, error)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return "", "youtube-transcript-api is not installed. Run: pip install youtube-transcript-api"

    try:
        entries = YouTubeTranscriptApi.get_transcript(video_id)
        # Merge all text entries into one block
        full_text = " ".join(e["text"] for e in entries)
        # Clean up auto-generated artifacts
        full_text = re.sub(r"\[.*?\]", "", full_text)  # remove [Music], [Applause]
        full_text = re.sub(r"\s{2,}", " ", full_text).strip()
        return full_text, ""
    except Exception as e:
        return "", f"Could not fetch transcript: {e}"

def _get_transcript_with_timestamps(video_id: str) -> tuple[list, str]:
    """Returns (list of {start, text} dicts, error) for chapter-aware summaries."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        return YouTubeTranscriptApi.get_transcript(video_id), ""
    except Exception as e:
        return [], str(e)

def _seconds_to_hms(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def youtube_summarizer(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    url_or_id = parameters.get("url", parameters.get("video_id", "")).strip()
    mode      = parameters.get("mode", "full").lower()  # full | chapters | brief

    if not url_or_id:
        return "Please provide a YouTube URL or video ID, sir."

    video_id = _extract_video_id(url_or_id)

    if player:
        player.write_log(f"[YTSummarizer] Video ID: {video_id} | mode: {mode}")
    if speak:
        speak("Fetching the video transcript and summarizing it now, sir.")

    # ── CHAPTER MODE: chunk transcript into ~5-min segments ──────────────────
    if mode == "chapters":
        entries, error = _get_transcript_with_timestamps(video_id)
        if error:
            return f"Transcript unavailable: {error}"

        # Group into ~5-min (300s) chunks
        chunks = []
        current_chunk = []
        chunk_start = 0.0
        for entry in entries:
            if entry["start"] - chunk_start > 300 and current_chunk:
                chunks.append((chunk_start, current_chunk))
                chunk_start = entry["start"]
                current_chunk = []
            current_chunk.append(entry["text"])
        if current_chunk:
            chunks.append((chunk_start, current_chunk))

        if not chunks:
            return "Transcript appears empty, sir."

        system = (
            "You are a video chapter summarizer. "
            "Summarize the following transcript segment in 1-3 bullet points. "
            "Be very concise. Plain text only."
        )
        try:
            genai.configure(api_key=_get_api_key())
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=system,
            )
            lines = [f"Chapter summary for video {video_id}:\n"]
            for start_sec, texts in chunks:
                chunk_text = " ".join(texts)[:1500]
                resp = model.generate_content(chunk_text)
                timestamp = _seconds_to_hms(start_sec)
                lines.append(f"[{timestamp}]\n{resp.text.strip()}\n")
            summary = "\n".join(lines)
        except Exception as e:
            return f"Summarization failed: {e}"

    else:
        # ── FULL / BRIEF MODE ─────────────────────────────────────────────────
        transcript, error = _get_transcript(video_id)
        if error:
            return f"Transcript unavailable: {error}"

        if len(transcript) < 50:
            return "Transcript is too short to summarize, sir."

        system = _SYSTEM_PROMPT
        if mode == "brief":
            system = (
                "Summarize this YouTube video transcript in 3 bullet points maximum. "
                "Be extremely concise. Plain text only."
            )

        # Trim to ~8000 chars
        transcript = transcript[:8000]

        try:
            genai.configure(api_key=_get_api_key())
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=system,
            )
            response = model.generate_content(
                f"YouTube video ID: {video_id}\n\nTranscript:\n{transcript}"
            )
            summary = response.text.strip()
        except Exception as e:
            return f"Summarization failed: {e}"

    if player:
        player.write_log(f"[YTSummarizer] ✅ {len(summary)} chars")

    if speak:
        spoken = summary[:600] + ("..." if len(summary) > 600 else "")
        speak(spoken)

    return summary
