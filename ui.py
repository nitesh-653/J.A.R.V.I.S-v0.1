"""
J.A.R.V.I.S — Premium Ambient AI UI  (MARK XLI)
=================================================
Gemini × Apple Intelligence aesthetic:
- Animated soft-blob gradient background (blue / violet / cyan)
- Frosted glass chat panel (right)
- Full-width JarvisChatBox (bottom)
- Zero orb, zero HUD, zero monitoring
"""

from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
from pathlib import Path

from PyQt6.QtCore import (
    QPointF, QRectF, QSize, Qt, QUrl,
    QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QKeySequence,
    QLinearGradient, QPainter, QPainterPath, QPen,
    QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QPushButton,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink, QVideoFrame
from PyQt6.QtGui import QImage, QPixmap

from jarvis_chatbox import JarvisChatBox


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 1100, 720
_MIN_W,     _MIN_H     = 880,  600
_OS = platform.system()


# ── Video background ──────────────────────────────────────────────────────────

class VideoBackground(QWidget):
    """
    Paints video frames directly via QPainter using QVideoSink.
    This avoids QVideoWidget which is a native widget that always
    renders on top of all Qt widgets regardless of Z-order.
    """

    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self._pixmap: QPixmap | None = None

        # Media player outputs frames to a QVideoSink (pure Qt, no native window)
        self._player = QMediaPlayer(self)
        self._audio  = QAudioOutput(self)
        self._audio.setVolume(0.0)
        self._player.setAudioOutput(self._audio)

        self._sink = QVideoSink(self)
        self._sink.videoFrameChanged.connect(self._on_frame)
        self._player.setVideoOutput(self._sink)

        video_file = Path(video_path)
        if video_file.exists():
            self._player.setSource(QUrl.fromLocalFile(str(video_file.resolve())))
            self._player.playbackStateChanged.connect(self._on_state_changed)
            self._player.play()

    def _on_frame(self, frame: QVideoFrame) -> None:
        """Convert each decoded frame to a QPixmap and trigger a repaint."""
        img = frame.toImage()
        if not img.isNull():
            self._pixmap = QPixmap.fromImage(
                img.convertToFormat(QImage.Format.Format_RGB32)
            )
            self.update()

    def _on_state_changed(self, state) -> None:
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self._player.setPosition(0)
            self._player.play()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        W, H = self.width(), self.height()

        # Draw video frame scaled to fill, preserving aspect ratio
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                W, H,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Centre-crop
            x = (scaled.width()  - W) // 2
            y = (scaled.height() - H) // 2
            p.drawPixmap(0, 0, scaled, x, y, W, H)
        else:
            # Fallback: dark background when no frame available yet
            p.fillRect(self.rect(), QColor(8, 10, 30))

        # Dark veil so UI text is legible
        p.fillRect(self.rect(), QColor(4, 6, 20, 110))

        # Edge vignette
        for cx, cy in [(0, 0), (W, 0), (0, H), (W, H)]:
            vg = QRadialGradient(cx, cy, W * 0.55)
            vg.setColorAt(0.0, QColor(4, 5, 20, 130))
            vg.setColorAt(1.0, QColor(4, 5, 20,   0))
            p.fillRect(self.rect(), QBrush(vg))

        p.end()


# Keep AmbientBackground as an alias so nothing else breaks
AmbientBackground = VideoBackground


# ── Frosted glass chat panel ──────────────────────────────────────────────────

class GlassChatPanel(QWidget):
    """Floating frosted-glass activity log panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(310)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._inner = QWidget(self)
        self._inner.setStyleSheet("""
            QWidget {
                background: transparent;
                border-radius: 20px;
            }
        """)
        layout.addWidget(self._inner)

        inner_layout = QVBoxLayout(self._inner)
        inner_layout.setContentsMargins(20, 18, 20, 18)
        inner_layout.setSpacing(10)

        # Header
        header = QLabel("Activity")
        f = QFont("SF Pro Display" if _OS == "Darwin" else "Segoe UI", 13,
                  QFont.Weight.Medium)
        header.setFont(f)
        header.setStyleSheet("color: rgba(220,235,255,0.90); background: transparent; border: none;")
        inner_layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: rgba(100,160,255,0.18); border: none; max-height: 1px;")
        sep.setFixedHeight(1)
        inner_layout.addWidget(sep)

        # Log area
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: rgba(190, 215, 255, 0.85);
                font-family: 'SF Mono', 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 0px;
                selection-background-color: rgba(100,160,255,0.25);
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: rgba(100,180,255,0.30);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        inner_layout.addWidget(self._log, stretch=1)

        # Typing engine
        self._queue: list[tuple[str, str]] = []
        self._typing = False
        self._cur_text = ""
        self._cur_pos = 0
        self._cur_color = "rgba(190,215,255,0.85)"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step_type)

    def append_log(self, text: str):
        tl = text.lower()
        if tl.startswith("you:"):
            color = "#E8F0FF"
        elif tl.startswith("jarvis:"):
            color = "#70C8FF"
        elif "err" in tl:
            color = "#FF7090"
        elif tl.startswith("sys:"):
            color = "#9090CC"
        else:
            color = "#A0B8E0"
        self._queue.append((text, color))
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._cur_text, self._cur_color = self._queue.pop(0)
        self._cur_pos = 0
        self._tmr.start(7)

    def _step_type(self):
        if self._cur_pos < len(self._cur_text):
            ch = self._cur_text[self._cur_pos]
            cur = self._log.textCursor()
            fmt = cur.charFormat()
            fmt.setForeground(QBrush(QColor(self._cur_color)))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self._log.setTextCursor(cur)
            self._log.ensureCursorVisible()
            self._cur_pos += 1
        else:
            self._tmr.stop()
            cur = self._log.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self._log.setTextCursor(cur)
            self._log.ensureCursorVisible()
            QTimer.singleShot(20, self._next)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        rect = QRectF(1, 1, W - 2, H - 2)
        path = QPainterPath()
        path.addRoundedRect(rect, 20, 20)

        # Frosted glass fill
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(18, 22, 60, 155)))
        p.drawPath(path)

        # Top gloss sheen
        hl = QLinearGradient(0, 0, 0, H * 0.45)
        hl.setColorAt(0.0, QColor(255, 255, 255, 22))
        hl.setColorAt(1.0, QColor(255, 255, 255,  0))
        p.setBrush(QBrush(hl))
        p.drawPath(path)

        # Subtle inner cyan tint at bottom
        bt = QLinearGradient(0, H * 0.6, 0, H)
        bt.setColorAt(0.0, QColor(60, 120, 255, 0))
        bt.setColorAt(1.0, QColor(60, 120, 255, 18))
        p.setBrush(QBrush(bt))
        p.drawPath(path)

        # Border
        p.setPen(QPen(QColor(120, 170, 255, 55), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        p.end()


# ── Setup overlay ─────────────────────────────────────────────────────────────

class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            SetupOverlay {
                background: rgba(14, 18, 50, 235);
                border: 1px solid rgba(100, 160, 255, 0.35);
                border-radius: 18px;
            }
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(_OS.lower(), "linux")
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(10)

        def _lbl(txt, fs=10, bold=False, color="rgba(200,220,255,0.9)",
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Segoe UI" if _OS == "Windows" else "SF Pro Display",
                            fs, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("Configure JARVIS", 16, True, "rgba(220,235,255,0.95)"))
        layout.addWidget(_lbl("Enter your Gemini API key to begin.", 10,
                               color="rgba(140,165,220,0.80)"))
        layout.addSpacing(8)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: rgba(100,160,255,0.18); border: none;")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color="rgba(120,160,220,0.70)",
                               align=Qt.AlignmentFlag.AlignLeft))

        from PyQt6.QtWidgets import QLineEdit
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Segoe UI", 11))
        self._key_input.setFixedHeight(38)
        self._key_input.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.07);
                color: rgba(220,235,255,0.95);
                border: 1px solid rgba(100,160,255,0.30);
                border-radius: 10px;
                padding: 4px 14px;
            }
            QLineEdit:focus { border: 1.5px solid rgba(100,200,255,0.70); }
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(14)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background: rgba(100,160,255,0.18); border: none;")
        sep2.setFixedHeight(1)
        layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color="rgba(120,160,220,0.70)",
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 9,
                               color="rgba(80,190,255,0.85)",
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(8)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows", "Windows"), ("mac", "macOS"), ("linux", "Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 10))
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(14)

        init_btn = QPushButton("Initialize JARVIS")
        init_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        init_btn.setFixedHeight(42)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(80,140,255,0.85), stop:1 rgba(130,80,255,0.85));
                color: rgba(230,240,255,0.95);
                border: none;
                border-radius: 10px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(100,160,255,0.95), stop:1 rgba(150,100,255,0.95));
            }
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        for k, btn in self._os_btns.items():
            if k == key:
                btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(80,140,255,0.55);
                        color: rgba(220,235,255,0.95);
                        border: 1px solid rgba(100,180,255,0.50);
                        border-radius: 8px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(255,255,255,0.05);
                        color: rgba(150,180,230,0.75);
                        border: 1px solid rgba(100,160,255,0.20);
                        border-radius: 8px;
                    }
                    QPushButton:hover {
                        background: rgba(80,140,255,0.18);
                        color: rgba(200,225,255,0.90);
                    }
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                " QLineEdit { border: 1.5px solid rgba(255,80,100,0.80); }"
            )
            return
        self.done.emit(key, self._sel_os)


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self._muted           = False
        self._current_file: str | None = None

        central = QWidget()
        self.setCentralWidget(central)

        # Video background — pure QPainter widget, safe to layer under Qt widgets
        _video_path = BASE_DIR / "ai_assistant_remix_scene (1).mp4"
        self._bg = VideoBackground(str(_video_path), central)
        self._bg.lower()

        # Root layout sits on top of the background (transparent)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Body: center label + right panel ──────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Center: empty spacer
        center_widget = QWidget()
        center_widget.setStyleSheet("background: transparent;")
        self._assist_label = QLabel("")   # kept for _apply_state compatibility
        self._assist_label.hide()
        self._sub_label = QLabel("")      # kept for _apply_state compatibility
        self._sub_label.hide()

        body.addWidget(center_widget, stretch=1)

        # Right panel
        right_margin = QWidget()
        right_margin.setStyleSheet("background: transparent;")
        rm_layout = QVBoxLayout(right_margin)
        rm_layout.setContentsMargins(0, 28, 24, 20)
        rm_layout.setSpacing(0)

        self._chat_panel = GlassChatPanel()
        rm_layout.addWidget(self._chat_panel)

        body.addWidget(right_margin)

        root.addLayout(body, stretch=1)

        # ── Bottom chatbox ─────────────────────────────────────────────────────
        bottom_strip = QWidget()
        bottom_strip.setStyleSheet("background: transparent;")
        bl = QVBoxLayout(bottom_strip)
        bl.setContentsMargins(28, 0, 28, 24)
        bl.setSpacing(0)

        self._chatbox = JarvisChatBox()
        self._chatbox.messageSent.connect(self._send_from_chatbox)
        self._chatbox.micPressed.connect(self._toggle_mute)
        bl.addWidget(self._chatbox)

        root.addWidget(bottom_strip)

        # ── Wire signals ──────────────────────────────────────────────────────
        self._log_sig.connect(self._chat_panel.append_log)
        self._state_sig.connect(self._apply_state)

        # ── Setup overlay ──────────────────────────────────────────────────────
        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._bg.setGeometry(self.centralWidget().rect())
        if self._overlay and self._overlay.isVisible():
            ow, oh = 480, 420
            cw = self.centralWidget()
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _send_from_chatbox(self, txt: str):
        self._chat_panel.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _send(self):
        self._chatbox._on_send()

    def _toggle_mute(self):
        self._muted = not self._muted
        if self._muted:
            self._apply_state("MUTED")
            self._chat_panel.append_log("Sys: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._chat_panel.append_log("Sys: Microphone active.")

    def _apply_state(self, state: str):
        labels = {
            "LISTENING":  ("Listening…",          "Ready when you are"),
            "SPEAKING":   ("Speaking…",            ""),
            "THINKING":   ("Thinking…",            "Processing your request"),
            "MUTED":      ("Microphone Muted",     "Press F4 to unmute"),
            "IDLE":       ("How Can I Assist You?","Your AI is ready"),
        }
        main_txt, sub_txt = labels.get(state, ("How Can I Assist You?", "Your AI is ready"))
        self._assist_label.setText(main_txt)
        self._sub_label.setText(sub_txt)

        if hasattr(self, "_chatbox"):
            if state == "LISTENING":
                self._chatbox.setListening(True)
            elif state == "SPEAKING":
                self._chatbox.setSpeaking(True)
            elif state == "THINKING":
                self._chatbox.setThinking(True)
            elif state == "MUTED":
                self._chatbox.setIdle()
                self._chatbox.setPlaceholder("Microphone muted…")
            else:
                self._chatbox.setIdle()

    def _check_config(self) -> bool:
        if not API_FILE.exists():
            return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 480, 420
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(
            json.dumps({"gemini_api_key": key, "os_system": os_name}, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._chat_panel.append_log(f"Sys: Initialised. OS={os_name.upper()}. JARVIS online.")


# ── Public API (unchanged interface) ─────────────────────────────────────────

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app

    def mainloop(self):
        self._app.exec()

    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._current_file

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def set_thinking(self, active: bool):
        if active:
            self._win._chatbox.setThinking(True)
        else:
            self._win._chatbox.setIdle()

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")
