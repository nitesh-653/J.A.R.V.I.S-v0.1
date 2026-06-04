"""
JarvisChatBox — Production-Quality PyQt6 AI Chat Input Component
=================================================================
A cinematic, JARVIS-style chat input widget with animated gradient borders,
multi-layer glow effects, voice-reactive states, and premium micro-interactions.

Architecture:
  • JarvisChatBox        — Main reusable widget (drop-in component)
  • _BorderPainter       — Handles all QPainter border/glow rendering
  • _AnimationController — Manages all QPropertyAnimation instances
  • _ChatButton          — Reusable circular/pill button with hover/press FX
  • _InputField          — QTextEdit subclass with custom placeholder + cursor
  • Demo (main)          — Standalone runnable showcase

Usage:
    box = JarvisChatBox()
    box.setListening(True)
    box.setThinking(True)
    box.setSpeaking(True)
    box.messageSent.connect(handle_message)
"""

from __future__ import annotations

import math
import sys
from enum import Enum, auto
from typing import Optional

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QTextOption,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ─────────────────────────────────────────────────────────────────────────────
# PALETTE & CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

class Palette:
    """Central color definitions for the JARVIS design system."""
    # Base
    BG_DEEP       = QColor(0x0C, 0x0D, 0x14)        # deepest background
    BG_INNER      = QColor(0x12, 0x13, 0x1A)        # widget interior
    BG_SURFACE    = QColor(0x1A, 0x1B, 0x26)        # subtle lift

    # IDLE gradient: Electric Purple → Neon Violet → Warm Orange → Soft Amber
    PURPLE        = QColor(0x7C, 0x3A, 0xED)
    VIOLET        = QColor(0xA8, 0x55, 0xF7)
    ORANGE        = QColor(0xF9, 0x73, 0x16)
    AMBER         = QColor(0xFB, 0xBF, 0x24)

    # LISTENING: Cyan energy
    CYAN_BRIGHT   = QColor(0x06, 0xEE, 0xE8)
    CYAN_SOFT     = QColor(0x00, 0xB4, 0xD8)
    CYAN_DEEP     = QColor(0x02, 0x56, 0x8A)

    # THINKING: Orange scan
    THINK_HOT     = QColor(0xFF, 0x6B, 0x00)
    THINK_WARM    = QColor(0xFF, 0xA5, 0x00)
    THINK_GLOW    = QColor(0xFF, 0xD6, 0x00)

    # SPEAKING: Arc-reactor pulse — cool blue-white
    SPEAK_CORE    = QColor(0xFF, 0xFF, 0xFF)
    SPEAK_MID     = QColor(0x38, 0xBD, 0xF8)
    SPEAK_OUTER   = QColor(0x1D, 0x4E, 0xD8)

    # Text
    TEXT_PRIMARY  = QColor(0xF1, 0xF5, 0xF9)
    TEXT_DIM      = QColor(0x64, 0x74, 0x8B)
    TEXT_GHOST    = QColor(0x33, 0x3D, 0x50)

    WHITE_10      = QColor(255, 255, 255, 26)
    WHITE_5       = QColor(255, 255, 255, 13)


class State(Enum):
    IDLE      = auto()
    LISTENING = auto()
    THINKING  = auto()
    SPEAKING  = auto()


BORDER_RADIUS   = 28
BORDER_THICK    = 2.5
GLOW_LAYERS     = [
    (8,   0.55),   # tight bright
    (22,  0.22),   # medium bloom
    (55,  0.07),   # atmospheric
]
FRAME_RATE_MS   = 16   # ~60 FPS


# ─────────────────────────────────────────────────────────────────────────────
# ANIMATION CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────

class _AnimationController:
    """
    Owns and coordinates all animation timelines for JarvisChatBox.
    Separates animation logic from rendering and UI concerns.
    """

    def __init__(self, widget: "JarvisChatBox") -> None:
        self._w = widget

        # Continuous border rotation (0.0 → 1.0 loops)
        self._angle: float = 0.0

        # State blend factor (0.0 = old state, 1.0 = new state)
        self._blend: float = 1.0
        self._old_state: State = State.IDLE
        self._cur_state: State = State.IDLE

        # Pulse/scan phase for special states
        self._phase: float = 0.0

        # Hover / focus intensity boosts
        self._hover_boost: float = 0.0
        self._focus_boost: float = 0.0

        # Per-button ripple intensities {btn_id: 0.0-1.0}
        self._ripples: dict[int, float] = {}

        # Master timer drives all frame updates
        self._timer = QTimer()
        self._timer.setInterval(FRAME_RATE_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        # Transition animation
        self._blend_anim = QVariantAnimation()
        self._blend_anim.setDuration(600)
        self._blend_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._blend_anim.valueChanged.connect(self._on_blend)

        # Hover animation
        self._hover_anim = QVariantAnimation()
        self._hover_anim.setDuration(250)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

        # Focus animation
        self._focus_anim = QVariantAnimation()
        self._focus_anim.setDuration(300)
        self._focus_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._focus_anim.valueChanged.connect(self._on_focus)

    # ── Public API ────────────────────────────────────────────────────────────

    def transition_to(self, state: State) -> None:
        self._old_state = self._cur_state
        self._cur_state = state
        self._blend = 0.0
        self._blend_anim.stop()
        self._blend_anim.setStartValue(0.0)
        self._blend_anim.setEndValue(1.0)
        self._blend_anim.start()

    def set_hover(self, active: bool) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(float(self._hover_boost))
        self._hover_anim.setEndValue(1.0 if active else 0.0)
        self._hover_anim.start()

    def set_focus(self, active: bool) -> None:
        self._focus_anim.stop()
        self._focus_anim.setStartValue(float(self._focus_boost))
        self._focus_anim.setEndValue(1.0 if active else 0.0)
        self._focus_anim.start()

    def trigger_ripple(self, btn_id: int) -> None:
        self._ripples[btn_id] = 1.0

    # ── Properties read by renderer ──────────────────────────────────────────

    @property
    def angle(self) -> float:
        return self._angle

    @property
    def phase(self) -> float:
        return self._phase

    @property
    def blend(self) -> float:
        return self._blend

    @property
    def old_state(self) -> State:
        return self._old_state

    @property
    def cur_state(self) -> State:
        return self._cur_state

    @property
    def hover_boost(self) -> float:
        return self._hover_boost

    @property
    def focus_boost(self) -> float:
        return self._focus_boost

    def get_ripple(self, btn_id: int) -> float:
        return self._ripples.get(btn_id, 0.0)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        dt = FRAME_RATE_MS / 1000.0

        # Idle: slow rotation; Thinking: fast scan; others: medium
        speeds = {
            State.IDLE: 0.06,
            State.LISTENING: 0.09,
            State.THINKING: 0.22,
            State.SPEAKING: 0.11,
        }
        speed = speeds.get(self._cur_state, 0.06)
        self._angle = (self._angle + speed * dt) % 1.0
        self._phase = (self._phase + dt * 1.4) % (2 * math.pi)

        # Decay ripples
        for k in list(self._ripples.keys()):
            self._ripples[k] = max(0.0, self._ripples[k] - dt * 2.5)
            if self._ripples[k] == 0.0:
                del self._ripples[k]

        self._w.update()

    def _on_blend(self, v: object) -> None:
        self._blend = float(v)  # type: ignore[arg-type]

    def _on_hover(self, v: object) -> None:
        self._hover_boost = float(v)  # type: ignore[arg-type]

    def _on_focus(self, v: object) -> None:
        self._focus_boost = float(v)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# BORDER / GLOW PAINTER
# ─────────────────────────────────────────────────────────────────────────────

class _BorderPainter:
    """
    Stateless rendering helper. All paint calls are pure functions of
    the anim controller snapshot — no state stored here.
    """

    # Color palettes per state
    _STATE_COLORS: dict[State, list[QColor]] = {
        State.IDLE:      [Palette.PURPLE, Palette.VIOLET, Palette.ORANGE, Palette.AMBER],
        State.LISTENING: [Palette.CYAN_BRIGHT, Palette.CYAN_SOFT, Palette.CYAN_BRIGHT, Palette.CYAN_DEEP],
        State.THINKING:  [Palette.THINK_HOT, Palette.THINK_WARM, Palette.THINK_GLOW, Palette.THINK_HOT],
        State.SPEAKING:  [Palette.SPEAK_CORE, Palette.SPEAK_MID, Palette.SPEAK_OUTER, Palette.SPEAK_MID],
    }

    @staticmethod
    def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        return QColor(
            int(a.red()   + (b.red()   - a.red())   * t),
            int(a.green() + (b.green() - a.green()) * t),
            int(a.blue()  + (b.blue()  - a.blue())  * t),
            int(a.alpha() + (b.alpha() - a.alpha()) * t),
        )

    @classmethod
    def _blend_palette(
        cls,
        old: State,
        cur: State,
        blend: float,
    ) -> list[QColor]:
        old_cols = cls._STATE_COLORS[old]
        cur_cols = cls._STATE_COLORS[cur]
        return [cls._lerp_color(o, c, blend) for o, c in zip(old_cols, cur_cols)]

    @classmethod
    def _make_conical_gradient(
        cls,
        rect: QRectF,
        angle_offset: float,
        colors: list[QColor],
    ) -> QConicalGradient:
        cx, cy = rect.center().x(), rect.center().y()
        grad = QConicalGradient(cx, cy, angle_offset * 360.0)
        stops = [i / (len(colors) - 1) for i in range(len(colors))]
        for stop, col in zip(stops, colors):
            grad.setColorAt(stop, col)
        # Wrap: repeat first color at 1.0 for seamless loop
        grad.setColorAt(1.0, colors[0])
        return grad

    @classmethod
    def paint_background(cls, p: QPainter, rect: QRectF, radius: float) -> None:
        """Paint the deep dark inner background."""
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        # Base fill — more opaque so it's visible over a video background
        p.fillPath(path, QColor(0x0C, 0x0D, 0x18, 220))

        # Subtle top-left highlight (glass feel)
        hl = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + rect.height() * 0.4))
        hl.setColorAt(0.0, QColor(255, 255, 255, 22))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, hl)

        # Subtle bottom reflection
        br = QLinearGradient(rect.bottomLeft(), QPointF(rect.left(), rect.bottom() - 60))
        br.setColorAt(0.0, QColor(0x7C, 0x3A, 0xED, 18))
        br.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillPath(path, br)

    @classmethod
    def paint_glow_layers(
        cls,
        p: QPainter,
        rect: QRectF,
        radius: float,
        colors: list[QColor],
        base_alpha: float,
    ) -> None:
        """Paint 3 concentric glow halos outside the border."""
        for expand, alpha_mul in GLOW_LAYERS:
            glow_rect = rect.adjusted(-expand, -expand, expand, expand)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, radius + expand, radius + expand)

            # Radial gradient from edge inward
            rg = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.6)
            alpha = int(255 * base_alpha * alpha_mul)
            # Pick dominant color
            dom = colors[0]
            rg.setColorAt(0.0, QColor(dom.red(), dom.green(), dom.blue(), 0))
            rg.setColorAt(0.7, QColor(dom.red(), dom.green(), dom.blue(), 0))
            rg.setColorAt(1.0, QColor(dom.red(), dom.green(), dom.blue(), alpha))

            # Also blend with accent color
            acc = colors[2]
            rg2 = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.7)
            rg2.setColorAt(0.0, QColor(acc.red(), acc.green(), acc.blue(), 0))
            rg2.setColorAt(0.75, QColor(acc.red(), acc.green(), acc.blue(), 0))
            rg2.setColorAt(1.0, QColor(acc.red(), acc.green(), acc.blue(), int(alpha * 0.6)))

            p.fillPath(glow_path, rg)
            p.fillPath(glow_path, rg2)

    @classmethod
    def paint_border(
        cls,
        p: QPainter,
        rect: QRectF,
        radius: float,
        colors: list[QColor],
        angle: float,
        thickness: float,
    ) -> None:
        """Paint the animated conical gradient border."""
        grad = cls._make_conical_gradient(rect, angle, colors)

        pen = QPen()
        pen.setBrush(grad)
        pen.setWidthF(thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        inner = rect.adjusted(thickness / 2, thickness / 2, -thickness / 2, -thickness / 2)
        p.drawRoundedRect(inner, radius - thickness / 2, radius - thickness / 2)

    @classmethod
    def paint_thinking_scan(
        cls,
        p: QPainter,
        rect: QRectF,
        radius: float,
        phase: float,
        blend: float,
    ) -> None:
        """Orange scanning line that sweeps across the widget during THINKING."""
        if blend < 0.01:
            return
        scan_y = rect.top() + (math.sin(phase) * 0.5 + 0.5) * rect.height()
        scan_rect = QRectF(rect.left() + radius, scan_y - 1.5, rect.width() - radius * 2, 3)

        sg = QLinearGradient(scan_rect.topLeft(), scan_rect.topRight())
        sg.setColorAt(0.0, QColor(0, 0, 0, 0))
        sg.setColorAt(0.3, QColor(0xFF, 0x8C, 0x00, int(180 * blend)))
        sg.setColorAt(0.5, QColor(0xFF, 0xD6, 0x00, int(255 * blend)))
        sg.setColorAt(0.7, QColor(0xFF, 0x8C, 0x00, int(180 * blend)))
        sg.setColorAt(1.0, QColor(0, 0, 0, 0))

        p.fillRect(scan_rect, sg)

    @classmethod
    def paint_speaking_arcs(
        cls,
        p: QPainter,
        rect: QRectF,
        radius: float,
        phase: float,
        blend: float,
    ) -> None:
        """Concentric pulsing arcs — arc-reactor effect during SPEAKING."""
        if blend < 0.01:
            return
        cx, cy = rect.center().x(), rect.center().y()
        for i in range(3):
            offset_phase = phase + i * (2 * math.pi / 3)
            pulse = (math.sin(offset_phase) * 0.5 + 0.5)
            arc_r = 18 + i * 14 + pulse * 8
            alpha = int(120 * blend * (1.0 - i * 0.25) * pulse)
            col = QColor(0x38, 0xBD, 0xF8, alpha)
            pen = QPen(col, 1.5 + pulse)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            arc_rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
            p.drawEllipse(arc_rect)

    @classmethod
    def render(
        cls,
        p: QPainter,
        rect: QRectF,
        anim: _AnimationController,
    ) -> None:
        """Full render pipeline — call once per paintEvent."""
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        radius = float(BORDER_RADIUS)
        colors = cls._blend_palette(anim.old_state, anim.cur_state, anim.blend)

        # Intensity boosted by hover/focus
        intensity = 1.0 + anim.hover_boost * 0.45 + anim.focus_boost * 0.35

        # 1. Atmospheric glow (behind everything)
        cls.paint_glow_layers(p, rect, radius, colors, intensity)

        # 2. Dark background fill
        cls.paint_background(p, rect, radius)

        # 3. State-specific overlays (clipped inside)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        p.setClipPath(clip)

        if anim.cur_state == State.THINKING:
            cls.paint_thinking_scan(p, rect, radius, anim.phase, anim.blend)
        elif anim.cur_state == State.SPEAKING:
            cls.paint_speaking_arcs(p, rect, radius, anim.phase, anim.blend)

        p.restore()

        # 4. Animated gradient border (on top)
        cls.paint_border(p, rect, radius, colors, anim.angle, BORDER_THICK * intensity)


# ─────────────────────────────────────────────────────────────────────────────
# CHAT BUTTON
# ─────────────────────────────────────────────────────────────────────────────

class _ChatButton(QWidget):
    """
    Circular/pill button with hover glow, press scale, and ripple FX.
    Uses QPainter for all rendering — no stylesheet dependence.
    """

    clicked = pyqtSignal()

    def __init__(
        self,
        icon_text: str,
        size: int = 40,
        accent: QColor = Palette.PURPLE,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._icon_text = icon_text
        self._btn_size = size
        self._accent = accent

        self._hover_t: float = 0.0
        self._press_t: float = 0.0
        self._ripple_t: float = 0.0

        self.setFixedSize(size, size)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # Hover animation
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(200)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_anim)

        # Press animation
        self._press_anim = QVariantAnimation(self)
        self._press_anim.setDuration(120)
        self._press_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._press_anim.valueChanged.connect(self._on_press_anim)

        # Ripple decay timer
        self._ripple_timer = QTimer(self)
        self._ripple_timer.setInterval(FRAME_RATE_MS)
        self._ripple_timer.timeout.connect(self._decay_ripple)

    # ── Animations ────────────────────────────────────────────────────────────

    def _animate_hover(self, on: bool) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(1.0 if on else 0.0)
        self._hover_anim.start()

    def _animate_press(self, on: bool) -> None:
        self._press_anim.stop()
        self._press_anim.setStartValue(self._press_t)
        self._press_anim.setEndValue(1.0 if on else 0.0)
        self._press_anim.start()

    def _on_hover_anim(self, v: object) -> None:
        self._hover_t = float(v)  # type: ignore[arg-type]
        self.update()

    def _on_press_anim(self, v: object) -> None:
        self._press_t = float(v)  # type: ignore[arg-type]
        self.update()

    def _decay_ripple(self) -> None:
        self._ripple_t = max(0.0, self._ripple_t - 0.06)
        if self._ripple_t <= 0.0:
            self._ripple_timer.stop()
        self.update()

    # ── Event handlers ────────────────────────────────────────────────────────

    def enterEvent(self, e) -> None:
        self._animate_hover(True)

    def leaveEvent(self, e) -> None:
        self._animate_hover(False)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._animate_press(True)
            self._ripple_t = 1.0
            self._ripple_timer.start()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._animate_press(False)
            if self.rect().contains(e.pos()):
                self.clicked.emit()

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        sz = self._btn_size
        scale = 1.0 - self._press_t * 0.08
        margin = sz * (1.0 - scale) / 2
        btn_rect = QRectF(margin, margin, sz * scale, sz * scale)
        r = btn_rect.width() / 2

        # Glow halo
        if self._hover_t > 0.01:
            glow_r = r + 10 * self._hover_t
            rg = QRadialGradient(btn_rect.center(), glow_r)
            rg.setColorAt(0.0, QColor(
                self._accent.red(), self._accent.green(), self._accent.blue(),
                int(60 * self._hover_t)
            ))
            rg.setColorAt(1.0, QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 0))
            glow_rect = QRectF(
                btn_rect.center().x() - glow_r,
                btn_rect.center().y() - glow_r,
                glow_r * 2, glow_r * 2,
            )
            p.setBrush(rg)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(glow_rect)

        # Ripple ring
        if self._ripple_t > 0.01:
            rip_r = r + (1.0 - self._ripple_t) * r * 1.4
            rip_alpha = int(180 * self._ripple_t)
            rip_col = QColor(self._accent.red(), self._accent.green(), self._accent.blue(), rip_alpha)
            p.setPen(QPen(rip_col, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(
                btn_rect.center().x() - rip_r,
                btn_rect.center().y() - rip_r,
                rip_r * 2, rip_r * 2,
            ))

        # Circle background
        bg_alpha = int(40 + 60 * self._hover_t)
        bg_col = QColor(self._accent.red(), self._accent.green(), self._accent.blue(), bg_alpha)
        p.setBrush(bg_col)

        # Border
        border_alpha = int(80 + 120 * self._hover_t)
        p.setPen(QPen(
            QColor(self._accent.red(), self._accent.green(), self._accent.blue(), border_alpha),
            1.2,
        ))
        p.drawEllipse(btn_rect)

        # Icon text
        icon_alpha = int(180 + 75 * self._hover_t)
        p.setPen(QColor(255, 255, 255, icon_alpha))
        font = QFont("Segoe UI Symbol", int(sz * 0.38))
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)
        p.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, self._icon_text)

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# INPUT FIELD
# ─────────────────────────────────────────────────────────────────────────────

class _InputField(QTextEdit):
    """
    Custom QTextEdit with placeholder, transparent background,
    white text, and focus-change signals.
    """

    focusGained = pyqtSignal()
    focusLost   = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._placeholder = "Ask JARVIS anything..."

        self.setFrameStyle(0)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAcceptRichText(False)
        self.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: #FFFFFF;
                font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
                font-size: 15px;
                font-weight: 500;
                letter-spacing: 0.3px;
                padding: 0px;
                selection-background-color: rgba(124, 58, 237, 0.4);
            }
            QScrollBar { width: 0px; height: 0px; }
        """)

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        if self.toPlainText() == "" and not self.hasFocus():
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QColor(160, 175, 200, 180))  # bright enough to see clearly
            font = self.font()
            font.setItalic(False)
            p.setFont(font)
            p.drawText(
                self.viewport().rect().adjusted(2, 4, 0, 0),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                self._placeholder,
            )

    def focusInEvent(self, e) -> None:
        super().focusInEvent(e)
        self.focusGained.emit()
        self.viewport().update()

    def focusOutEvent(self, e) -> None:
        super().focusOutEvent(e)
        self.focusLost.emit()
        self.viewport().update()

    def keyPressEvent(self, e) -> None:
        # Enter without shift → emit submit signal up the chain
        if (
            e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and e.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            # Bubble up to parent
            parent = self.parent()
            while parent:
                if hasattr(parent, "_on_send"):
                    parent._on_send()
                    return
                parent = parent.parent()
        super().keyPressEvent(e)

    def setPlaceholder(self, text: str) -> None:
        self._placeholder = text
        self.viewport().update()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WIDGET: JarvisChatBox
# ─────────────────────────────────────────────────────────────────────────────

class JarvisChatBox(QWidget):
    """
    Production-quality JARVIS-style AI chat input widget.

    Signals:
        messageSent(str)  — emitted when user sends a message.
        micPressed()      — emitted when microphone button pressed.
        addPressed()      — emitted when add/attachment button pressed.
        toolsPressed()    — emitted when tools button pressed.

    State control:
        setListening(bool)
        setThinking(bool)
        setSpeaking(bool)
        setIdle()
    """

    messageSent  = pyqtSignal(str)
    micPressed   = pyqtSignal()
    addPressed   = pyqtSignal()
    toolsPressed = pyqtSignal()

    # Inner margin so glow doesn't clip
    _GLOW_MARGIN = 60

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._state = State.IDLE
        self._anim  = _AnimationController(self)

        self._build_ui()
        self._connect_signals()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(130)

    # ── Public API ────────────────────────────────────────────────────────────

    def setListening(self, active: bool) -> None:
        """Switch to LISTENING (cyan) state or back to IDLE."""
        self._set_state(State.LISTENING if active else State.IDLE)
        self._input.setPlaceholder("Listening..." if active else "Ask JARVIS anything...")

    def setThinking(self, active: bool) -> None:
        """Switch to THINKING (orange scan) state or back to IDLE."""
        self._set_state(State.THINKING if active else State.IDLE)
        self._input.setPlaceholder("Processing..." if active else "Ask JARVIS anything...")

    def setSpeaking(self, active: bool) -> None:
        """Switch to SPEAKING (arc-reactor) state or back to IDLE."""
        self._set_state(State.SPEAKING if active else State.IDLE)
        self._input.setPlaceholder("Speaking..." if active else "Ask JARVIS anything...")

    def setIdle(self) -> None:
        """Return to IDLE state."""
        self._set_state(State.IDLE)
        self._input.setPlaceholder("Ask JARVIS anything...")

    def getText(self) -> str:
        return self._input.toPlainText().strip()

    def clearText(self) -> None:
        self._input.clear()

    def setPlaceholder(self, text: str) -> None:
        self._input.setPlaceholder(text)

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        gm = self._GLOW_MARGIN

        # Root layout adds glow margins so glow is visible outside widget rect
        root = QVBoxLayout(self)
        root.setContentsMargins(gm, gm, gm, gm)
        root.setSpacing(0)

        # Inner container — this is the visible "card"
        self._card = QWidget(self)
        self._card.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        root.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(20, 16, 20, 14)
        card_layout.setSpacing(10)

        # ── Text input ────────────────────────────────────────────────────────
        self._input = _InputField(self._card)
        self._input.setMinimumHeight(52)
        card_layout.addWidget(self._input)

        # ── Bottom toolbar ────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)

        # Left buttons
        self._btn_add   = _ChatButton("＋", 36, Palette.PURPLE, self._card)
        self._btn_tools = _ChatButton("⚙", 36, Palette.VIOLET, self._card)
        toolbar.addWidget(self._btn_add)
        toolbar.addWidget(self._btn_tools)

        toolbar.addStretch()

        # State indicator label (subtle, right of stretch)
        self._state_label = QLabel("IDLE", self._card)
        self._state_label.setStyleSheet("""
            color: rgba(160, 185, 220, 0.85);
            font-size: 9px;
            font-family: 'Consolas', monospace;
            letter-spacing: 2px;
        """)
        toolbar.addWidget(self._state_label)

        # Right buttons
        self._btn_mic  = _ChatButton("🎤", 36, Palette.CYAN_BRIGHT, self._card)
        self._btn_send = _ChatButton("▶", 40, Palette.ORANGE, self._card)
        toolbar.addWidget(self._btn_mic)
        toolbar.addWidget(self._btn_send)

        card_layout.addLayout(toolbar)

    def _connect_signals(self) -> None:
        self._btn_add.clicked.connect(self.addPressed)
        self._btn_tools.clicked.connect(self.toolsPressed)
        self._btn_mic.clicked.connect(self.micPressed)
        self._btn_send.clicked.connect(self._on_send)
        self._input.focusGained.connect(lambda: self._anim.set_focus(True))
        self._input.focusLost.connect(lambda: self._anim.set_focus(False))

    # ── Internal logic ────────────────────────────────────────────────────────

    def _set_state(self, state: State) -> None:
        if state == self._state:
            return
        self._state = state
        self._anim.transition_to(state)
        labels = {
            State.IDLE: "IDLE",
            State.LISTENING: "LISTENING",
            State.THINKING: "THINKING",
            State.SPEAKING: "SPEAKING",
        }
        self._state_label.setText(labels[state])

    def _on_send(self) -> None:
        text = self.getText()
        if text:
            self.messageSent.emit(text)
            self.clearText()

    # ── Events ────────────────────────────────────────────────────────────────

    def enterEvent(self, e) -> None:
        self._anim.set_hover(True)

    def leaveEvent(self, e) -> None:
        self._anim.set_hover(False)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        gm = float(self._GLOW_MARGIN)
        # Card rect in widget coordinates
        card_rect = QRectF(
            gm,
            gm,
            self.width()  - gm * 2,
            self.height() - gm * 2,
        )

        _BorderPainter.render(p, card_rect, self._anim)
        p.end()

    def sizeHint(self) -> QSize:
        return QSize(700, 160)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class _DemoWindow(QWidget):
    """Standalone showcase for JarvisChatBox."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS — Chat Interface")
        self.setMinimumSize(760, 560)
        self.setStyleSheet(f"background: {Palette.BG_DEEP.name()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Title
        title = QLabel("J.A.R.V.I.S  INTERFACE  v1.0")
        title.setStyleSheet("""
            color: rgba(148, 163, 184, 0.7);
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
            letter-spacing: 4px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Message log
        self._log = QLabel("Say something, or click a state button below.")
        self._log.setStyleSheet("""
            color: rgba(148, 163, 184, 0.5);
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
            padding: 12px 20px;
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 12px;
            background: rgba(255,255,255,0.02);
        """)
        self._log.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._log.setWordWrap(True)
        self._log.setMinimumHeight(60)
        layout.addWidget(self._log)

        layout.addStretch()

        # Main chat box
        self._chatbox = JarvisChatBox()
        self._chatbox.messageSent.connect(self._on_message)
        self._chatbox.micPressed.connect(lambda: self._chatbox.setListening(True))
        layout.addWidget(self._chatbox)

        layout.addStretch()

        # State control buttons (demo row)
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)
        states = [
            ("IDLE",      "#7C3AED", self._chatbox.setIdle),
            ("LISTENING", "#06EEE8", lambda: self._chatbox.setListening(True)),
            ("THINKING",  "#F97316", lambda: self._chatbox.setThinking(True)),
            ("SPEAKING",  "#38BDF8", lambda: self._chatbox.setSpeaking(True)),
        ]
        for label, color, fn in states:
            btn = _ChatButton(label[:3], 48, QColor(color), self)
            btn.setFixedSize(100, 32)
            btn.clicked.connect(fn)
            # Use a simple label widget instead for demo
            state_btn = QLabel(label)
            state_btn.setFixedHeight(32)
            state_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            state_btn.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    border: 1px solid {color}55;
                    border-radius: 8px;
                    font-family: 'Consolas', monospace;
                    font-size: 10px;
                    letter-spacing: 2px;
                    padding: 0 14px;
                    background: {color}15;
                }}
                QLabel:hover {{
                    background: {color}30;
                    border-color: {color}AA;
                }}
            """)
            state_btn.mousePressEvent = lambda e, f=fn: f()
            state_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            ctrl_row.addWidget(state_btn)

        layout.addLayout(ctrl_row)

        hint = QLabel("Press Enter to send  •  Click mic to listen  •  Buttons cycle states")
        hint.setStyleSheet("color: rgba(100,116,139,0.4); font-size: 10px; letter-spacing: 1px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    def _on_message(self, text: str) -> None:
        self._log.setText(f"› {text}")
        # Simulate think → speak
        QTimer.singleShot(300,  lambda: self._chatbox.setThinking(True))
        QTimer.singleShot(1800, lambda: self._chatbox.setThinking(False))
        QTimer.singleShot(2000, lambda: self._chatbox.setSpeaking(True))
        QTimer.singleShot(4000, lambda: self._chatbox.setSpeaking(False))


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS Chat Interface")

    # High-DPI
    try:
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    except AttributeError:
        pass

    win = _DemoWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
