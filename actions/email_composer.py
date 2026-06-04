"""
email_composer.py — Mark XXXIX Email Composer & Sender
Drafts emails using Gemini, shows preview, then sends via SMTP (Gmail).
"""
import json
import re
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import google.generativeai as genai

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_config() -> dict:
    config_path = _base_dir() / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

_DRAFT_PROMPT = """\
You are a professional email writer. Draft a clear, polished email based on the user's request.
Return ONLY a JSON object with keys: "subject", "body"
No markdown, no extra text, just valid JSON."""

_pending_draft: dict = {}

def _draft_email(context: str, tone: str, api_key: str) -> dict:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=_DRAFT_PROMPT,
    )
    response = model.generate_content(
        f"Tone: {tone}\nContext: {context}"
    )
    text = response.text.strip()
    text = re.sub(r"^```json?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()
    return json.loads(text)

def _send_email(to: str, subject: str, body: str, cfg: dict) -> str:
    smtp_user     = cfg.get("gmail_address", "").strip()
    smtp_password = cfg.get("gmail_app_password", "").strip()
    if not smtp_user or not smtp_password:
        return (
            "Gmail credentials not configured. "
            "Add 'gmail_address' and 'gmail_app_password' to config/api_keys.json."
        )
    msg = MIMEMultipart("alternative")
    msg["From"]    = smtp_user
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to, msg.as_string())
        return f"Email sent to {to}."
    except smtplib.SMTPAuthenticationError:
        return "Gmail authentication failed. Check your app password in config/api_keys.json."
    except Exception as e:
        return f"Failed to send email: {e}"

def email_composer(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    global _pending_draft

    action  = parameters.get("action", "draft").lower()
    to      = parameters.get("to", "").strip()
    context = parameters.get("context", "").strip()
    tone    = parameters.get("tone", "professional").strip()

    if action == "send" and _pending_draft:
        draft = _pending_draft.copy()
        _pending_draft.clear()
        if not to:
            to = draft.get("to", "")
        if not to:
            return "Please provide a recipient email address."
        try:
            cfg    = _get_config()
            result = _send_email(to, draft["subject"], draft["body"], cfg)
            if player:
                player.write_log(f"[Email] {result}")
            return result
        except Exception as e:
            return f"Send failed: {e}"

    if not context:
        return "Please describe what you'd like to email."

    if speak:
        speak("Drafting your email now, sir.")
    if player:
        player.write_log(f"[Email] Drafting: {context[:50]}")

    try:
        cfg   = _get_config()
        draft = _draft_email(context, tone, cfg["gemini_api_key"])
    except Exception as e:
        return f"Could not draft email: {e}"

    _pending_draft = {"subject": draft["subject"], "body": draft["body"], "to": to}

    preview = (
        f"Draft ready, sir.\n\n"
        f"Subject: {draft['subject']}\n\n"
        f"{draft['body']}\n\n"
        f"Say 'send the email' to send, or 'discard email' to cancel."
    )
    if player:
        player.write_log("[Email] ✅ Draft ready — awaiting confirmation")
    return preview

def discard_email() -> str:
    global _pending_draft
    _pending_draft.clear()
    return "Email discarded, sir."
