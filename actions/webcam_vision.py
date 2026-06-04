"""
webcam_vision.py — JARVIS V01 Gemini Vision via Webcam
Captures a frame from the webcam and sends it to Gemini Vision with the user's question.
Mirrors screen_processor.py but uses the webcam instead of a screenshot.
"""
import base64
import json
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

def _capture_webcam_frame() -> bytes:
    """Capture a single frame from the default webcam and return as JPEG bytes."""
    try:
        import cv2
    except ImportError:
        raise RuntimeError("opencv-python is not installed. Run: pip install opencv-python")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Make sure it is connected and not in use.")

    # Warm up — discard first few frames so exposure settles
    for _ in range(3):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise RuntimeError("Failed to capture a frame from the webcam.")

    success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise RuntimeError("Failed to encode webcam frame as JPEG.")

    return buffer.tobytes()

def webcam_vision(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    question = parameters.get("question", "What do you see?").strip()

    if player:
        player.write_log(f"[WebcamVision] Capturing frame — question: {question[:60]}")
    if speak:
        speak("Let me take a look, sir.")

    # Capture frame
    try:
        frame_bytes = _capture_webcam_frame()
    except RuntimeError as e:
        return str(e)

    # Encode to base64
    frame_b64 = base64.b64encode(frame_bytes).decode("utf-8")

    # Send to Gemini Vision
    try:
        genai.configure(api_key=_get_api_key())
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        response = model.generate_content([
            {
                "mime_type": "image/jpeg",
                "data": frame_b64,
            },
            question,
        ])
        answer = response.text.strip()
    except Exception as e:
        return f"Gemini Vision error: {e}"

    if player:
        player.write_log(f"[WebcamVision] ✅ {answer[:80]}")

    return answer
