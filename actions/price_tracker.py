"""
price_tracker.py — JARVIS V01 Price Tracker
Track product prices via web scraping. Notifies with a toast when price drops below target.
Stores tracked items persistently in config/price_targets.json.
Uses BeautifulSoup + requests for scraping, win10toast for notifications.
"""
import json
import re
import sys
import threading
import time
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _targets_path() -> Path:
    p = _base_dir() / "config" / "price_targets.json"
    if not p.exists():
        p.write_text("[]", encoding="utf-8")
    return p

def _load_targets() -> list:
    try:
        return json.loads(_targets_path().read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_targets(targets: list) -> None:
    _targets_path().write_text(json.dumps(targets, indent=2), encoding="utf-8")

def _toast(title: str, message: str) -> None:
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(title, message, duration=8, threaded=True)
    except Exception:
        pass  # Non-Windows or not installed — silent fallback

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

def _scrape_price(url: str) -> float | None:
    """Scrape the first plausible price from any product page."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts/styles
        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(" ", strip=True)

        # Find all price-like patterns: $1,299.99 or 1299.99
        prices = re.findall(r"\$\s?([\d,]+(?:\.\d{1,2})?)", text)
        if not prices:
            prices = re.findall(r"(?<!\w)([\d,]{2,7}(?:\.\d{1,2})?)(?!\w)", text)

        candidates = []
        for p in prices:
            try:
                val = float(p.replace(",", ""))
                if 0.5 < val < 100_000:
                    candidates.append(val)
            except ValueError:
                pass

        return min(candidates) if candidates else None
    except Exception:
        return None

# Background checker — runs as a daemon thread
_checker_started = False
_checker_lock = threading.Lock()

def _start_background_checker(speak=None) -> None:
    global _checker_started
    with _checker_lock:
        if _checker_started:
            return
        _checker_started = True

    def _loop():
        while True:
            time.sleep(1800)  # Check every 30 minutes
            targets = _load_targets()
            updated = False
            for item in targets:
                if item.get("alerted"):
                    continue
                price = _scrape_price(item["url"])
                if price is None:
                    continue
                item["last_price"] = price
                item["last_checked"] = datetime.now().isoformat()
                updated = True
                if price <= item["target_price"]:
                    msg = (
                        f"{item['name']} is now ${price:.2f} "
                        f"(target: ${item['target_price']:.2f})"
                    )
                    _toast("💰 Price Alert — JARVIS", msg)
                    if speak:
                        speak(f"Price alert, sir. {item['name']} has dropped to {price:.2f} dollars.")
                    item["alerted"] = True
            if updated:
                _save_targets(targets)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()

def price_tracker(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    action = parameters.get("action", "track").lower().strip()

    # Start background checker
    _start_background_checker(speak=speak)

    # ── LIST ──────────────────────────────────────────────────────────────────
    if action in ("list", "show", "status"):
        targets = _load_targets()
        if not targets:
            return "No products are being tracked, sir."
        lines = ["Currently tracking:"]
        for item in targets:
            last = f"${item['last_price']:.2f}" if item.get("last_price") else "not yet checked"
            alerted = " ✅ alerted" if item.get("alerted") else ""
            lines.append(
                f"  • {item['name']} — target ${item['target_price']:.2f} | last seen {last}{alerted}"
            )
        return "\n".join(lines)

    # ── REMOVE ────────────────────────────────────────────────────────────────
    if action in ("remove", "stop", "delete", "untrack"):
        name = parameters.get("name", "").strip().lower()
        targets = _load_targets()
        before = len(targets)
        targets = [t for t in targets if name not in t["name"].lower()]
        _save_targets(targets)
        removed = before - len(targets)
        return (
            f"Removed {removed} item(s) matching '{name}' from tracking, sir."
            if removed else f"No tracked item matched '{name}', sir."
        )

    # ── CHECK NOW ─────────────────────────────────────────────────────────────
    if action in ("check", "refresh"):
        targets = _load_targets()
        if not targets:
            return "No products are being tracked, sir."
        if speak:
            speak("Checking prices now, sir.")
        results = []
        for item in targets:
            price = _scrape_price(item["url"])
            if price:
                item["last_price"] = price
                item["last_checked"] = datetime.now().isoformat()
                status = "🎯 below target!" if price <= item["target_price"] else "above target"
                results.append(f"{item['name']}: ${price:.2f} ({status})")
                if price <= item["target_price"] and not item.get("alerted"):
                    _toast("💰 Price Alert — JARVIS",
                           f"{item['name']} is ${price:.2f} — target reached!")
                    item["alerted"] = True
            else:
                results.append(f"{item['name']}: could not retrieve price")
        _save_targets(targets)
        return "\n".join(results)

    # ── TRACK (default) ───────────────────────────────────────────────────────
    url          = parameters.get("url", "").strip()
    name         = parameters.get("name", "Product").strip()
    target_price = parameters.get("target_price", 0)

    if not url:
        return "Please provide the product URL to track."
    try:
        target_price = float(str(target_price).replace("$", "").replace(",", ""))
    except ValueError:
        return "Please provide a valid target price."

    if player:
        player.write_log(f"[PriceTracker] Adding: {name} @ ${target_price:.2f}")
    if speak:
        speak(f"Tracking {name}. I'll notify you when it drops below {target_price:.0f} dollars, sir.")

    # Scrape current price immediately
    current_price = _scrape_price(url)
    targets = _load_targets()
    targets.append({
        "name":          name,
        "url":           url,
        "target_price":  target_price,
        "last_price":    current_price,
        "last_checked":  datetime.now().isoformat(),
        "alerted":       False,
    })
    _save_targets(targets)

    current_str = f"Current price: ${current_price:.2f}." if current_price else "Could not fetch current price."
    return (
        f"Now tracking '{name}'. {current_str} "
        f"I'll alert you when it drops below ${target_price:.2f}, sir."
    )
