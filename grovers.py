import math
import os
import random
import sys
from datetime import datetime

from PyQt6.QtCore import QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDial,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

# ------------------------
# Assets & deck
# ------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CARD_BACK_PATH = os.path.join(SCRIPT_DIR, "cardback_resized.png")

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
DECK = [f"{rank}{suit}" for suit in SUITS for rank in RANKS]
QUEEN_CARD = "Q♥"

DEFAULT_QUBITS = 6
MAX_QUBITS = 14
MIN_QUBITS = 6
SUCCESS_THRESHOLD = 0.9
HEATMAP_MIN_QUBITS = 7
PROB_RENDER_EPSILON = 1e-4

# ------------------------
# Braun-inspired palette
# ------------------------
BG = "#f4f1ea"
PANEL = "#ece6dc"
PANEL_DARK = "#e1dbd1"
PANEL_EDGE = "#c8c1b6"
INK = "#1f1f1f"
INK_SOFT = "#3a3a38"
MUTED = "#8a857c"
HAIRLINE = "#cdc6bb"
ACCENT = "#bf3c30"
ACCENT_SOFT = "#d4a792"
CLASSICAL = "#2f7d52"
PROBE = "#1f1f1f"

FONT_SANS = "IBM Plex Sans"
FONT_MONO = "IBM Plex Mono"

TYPE_MICRO = 9
TYPE_BODY = 11
TYPE_LABEL = 10
TYPE_DISPLAY = 18
TYPE_HERO = 22


# ------------------------
# Grover helpers
# ------------------------
def custom_oracle(n, target_bin):
    qc = QuantumCircuit(n)
    for i, bit in enumerate(reversed(target_bin)):
        if bit == "0":
            qc.x(i)
    qc.h(n - 1)
    qc.mcx(list(range(n - 1)), n - 1)
    qc.h(n - 1)
    for i, bit in enumerate(reversed(target_bin)):
        if bit == "0":
            qc.x(i)
    return qc


def diffuser(n):
    qc = QuantumCircuit(n)
    qc.h(range(n))
    qc.x(range(n))
    qc.h(n - 1)
    qc.mcx(list(range(n - 1)), n - 1)
    qc.h(n - 1)
    qc.x(range(n))
    qc.h(range(n))
    return qc


def optimal_iterations(n_items: int) -> int:
    return max(1, int(round((math.pi / 4) * math.sqrt(n_items))))


# ------------------------
# Visual primitives
# ------------------------
class PanelFrame(QFrame):
    """Beige panel with a thin edge — used for every grouped section."""

    def __init__(self, object_name="Panel"):
        super().__init__()
        self.setObjectName(object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class SectionHeader(QWidget):
    """Tiny uppercase label + optional right-aligned hint."""

    def __init__(self, title: str, hint: str = ""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.title = QLabel(title.upper())
        self.title.setObjectName("SectionLabel")
        self.hint = QLabel(hint)
        self.hint.setObjectName("SectionHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.title)
        layout.addStretch(1)
        layout.addWidget(self.hint)

    def set_hint(self, text: str):
        self.hint.setText(text)


class EngineCard(QFrame):
    """Compact card showing one compute engine's status."""

    def __init__(self, name: str, subtitle: str, code: str):
        super().__init__()
        self.setObjectName("EngineCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title = QLabel(name.upper())
        title.setObjectName("EngineTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("EngineSubtitle")
        sub.setWordWrap(True)

        bar = QFrame()
        bar.setObjectName("EngineBar")
        bar.setFixedHeight(2)

        status = QLabel(f"●  ONLINE · {code}")
        status.setObjectName("EngineStatus")

        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addSpacing(6)
        layout.addWidget(bar)
        layout.addSpacing(4)
        layout.addWidget(status)


class StatTile(QFrame):
    """Right-side hero stat (Quantum √N, Classical N/2)."""

    def __init__(self, label: str):
        super().__init__()
        self.setObjectName("StatTile")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.label = QLabel(label.upper())
        self.label.setObjectName("StatLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.value = QLabel("—")
        self.value.setObjectName("StatValue")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(self.label)
        lay.addWidget(self.value)

    def set_value(self, text: str):
        self.value.setText(text)


class FlipCounter(QWidget):
    """Two-digit segmented counter used for iteration display."""

    def __init__(self):
        super().__init__()
        self.value = 0
        self.setFixedSize(74, 44)

    def set_value(self, v: int):
        self.value = max(0, min(99, int(v)))
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        text = f"{self.value:02d}"
        cell_w = self.width() // 2 - 2
        cell_h = self.height()
        for i, ch in enumerate(text):
            x = i * (cell_w + 4)
            rect = QRectF(x, 0, cell_w, cell_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(INK))
            painter.drawRoundedRect(rect, 2, 2)
            painter.setPen(QColor(BG))
            f = QFont(FONT_MONO)
            f.setPointSize(TYPE_HERO)
            f.setWeight(QFont.Weight.DemiBold)
            painter.setFont(f)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, ch)
            painter.setPen(QPen(QColor(0, 0, 0, 90), 1))
            mid = int(rect.top() + rect.height() / 2)
            painter.drawLine(int(rect.left()) + 2, mid, int(rect.right()) - 2, mid)


class QubitDial(QDial):
    """Tick-marked dial with min/max labels painted around it."""

    def __init__(self, lo: int, hi: int):
        super().__init__()
        self.setRange(lo, hi)
        self.setNotchesVisible(False)
        self.setWrapping(False)
        self.setFixedSize(150, 150)
        self.setObjectName("QubitDial")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rect = self.rect()
        cx = rect.center().x()
        cy = rect.center().y()
        r_outer = min(rect.width(), rect.height()) / 2 - 4

        ticks = self.maximum() - self.minimum() + 1
        painter.setPen(QPen(QColor(INK_SOFT), 1))
        for i in range(ticks):
            theta = math.radians(240 - (300 * i / max(1, ticks - 1)))
            x1 = cx + (r_outer - 2) * math.cos(theta)
            y1 = cy - (r_outer - 2) * math.sin(theta)
            x2 = cx + (r_outer + 6) * math.cos(theta)
            y2 = cy - (r_outer + 6) * math.sin(theta)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        f = QFont(FONT_MONO)
        f.setPointSize(TYPE_MICRO)
        painter.setFont(f)
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(0, rect.height() - 18, rect.width() / 2, 14),
                         Qt.AlignmentFlag.AlignCenter, str(self.minimum()))
        painter.drawText(QRectF(rect.width() / 2, rect.height() - 18, rect.width() / 2, 14),
                         Qt.AlignmentFlag.AlignCenter, str(self.maximum()))


class AmplitudeBar(QWidget):
    """Striped progress bar with 0 / .25 / .50 / .75 / 1.0 ticks."""

    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.threshold = 0.9
        self.setFixedHeight(34)

    def set_value(self, v: float):
        self.value = max(0.0, min(1.0, float(v)))
        self.update()

    def set_threshold(self, t: float):
        self.threshold = max(0.0, min(1.0, float(t)))
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(0, 4, 0, -14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PANEL_DARK))
        painter.drawRect(rect)

        fill_w = int(rect.width() * self.value)
        painter.save()
        painter.setClipRect(QRect(rect.left(), rect.top(), fill_w, rect.height()))
        stripe_w = 4
        for x in range(rect.left(), rect.left() + fill_w, stripe_w * 2):
            painter.setBrush(QColor(INK))
            painter.drawRect(x, rect.top(), stripe_w, rect.height())
        painter.restore()

        marker_x = rect.left() + int(rect.width() * self.threshold)
        painter.setPen(QPen(QColor(ACCENT), 2))
        painter.drawLine(marker_x, rect.top() - 2, marker_x, rect.bottom() + 2)

        f = QFont(FONT_MONO)
        f.setPointSize(TYPE_MICRO)
        painter.setFont(f)
        painter.setPen(QColor(MUTED))
        for i, label in enumerate(["0", ".25", ".50", ".75", "1.0"]):
            x = rect.left() + int(rect.width() * i / 4)
            tick_rect = QRectF(x - 14, rect.bottom() + 2, 28, 12)
            align = Qt.AlignmentFlag.AlignCenter
            if i == 0:
                tick_rect = QRectF(x, rect.bottom() + 2, 28, 12)
                align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            elif i == 4:
                tick_rect = QRectF(x - 28, rect.bottom() + 2, 28, 12)
                align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            painter.drawText(tick_rect, align, label)


class TransportButton(QPushButton):
    """Square transport control. Variants: 'ghost' (default), 'primary', 'reveal'."""

    def __init__(self, glyph: str, label: str, variant: str = "ghost"):
        super().__init__()
        self.glyph = glyph
        self.caption = label
        self.variant = variant
        self.setFixedSize(60, 70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName(f"Transport-{variant}")

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rect = self.rect()
        body = QRect(rect.left(), rect.top(), rect.width(), rect.height() - 16)

        bg = QColor(BG)
        fg = QColor(INK)
        if self.variant == "primary":
            bg = QColor(INK)
            fg = QColor(BG)
        elif self.variant == "reveal":
            bg = QColor(BG)
            fg = QColor(INK)

        if self.isDown():
            bg = bg.darker(108)

        painter.setPen(QPen(QColor(PANEL_EDGE), 1))
        painter.setBrush(bg)
        painter.drawRect(body.adjusted(0, 0, -1, -1))

        if self.variant == "reveal":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ACCENT))
            painter.drawRect(body.left() + 6, body.top() + 6, body.width() - 12, 2)

        painter.setPen(fg)
        f = QFont(FONT_SANS)
        f.setPointSize(TYPE_DISPLAY)
        f.setWeight(QFont.Weight.DemiBold)
        painter.setFont(f)
        painter.drawText(body, Qt.AlignmentFlag.AlignCenter, self.glyph)

        painter.setPen(QColor(MUTED))
        f = QFont(FONT_MONO)
        f.setPointSize(TYPE_MICRO)
        painter.setFont(f)
        cap_rect = QRect(rect.left(), body.bottom() + 2, rect.width(), 14)
        painter.drawText(cap_rect, Qt.AlignmentFlag.AlignCenter, self.caption.upper())



# ------------------------
# Card widgets
# ------------------------
class CardCell(QLabel):
    """Position-numbered tile used in both 52-card and virtual-state modes."""

    def __init__(self, index: int, label: str, suit: str = "", is_target: bool = False, size_px: int = 96):
        super().__init__()
        self.index = index
        self.label = label
        self.suit = suit
        self.is_target = is_target
        self.revealed = False
        self.show_name = False
        self.probability = 0.0
        self.classical_visited = False
        self.classical_current = False
        self._size = size_px
        self.setFixedSize(70, size_px)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_size(self, w: int, h: int):
        self.setFixedSize(max(36, w), max(60, h))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(BG))
        painter.drawRect(rect)

        if self.classical_visited:
            painter.setBrush(QColor(PANEL_DARK))
            painter.drawRect(rect)

        if self.probability > 0:
            stripe_h = max(2, int(min(1.0, self.probability * 3.5) * (rect.height() * 0.18)))
            painter.setBrush(QColor(INK))
            painter.drawRect(rect.left() + 6, rect.bottom() - stripe_h - 4,
                             rect.width() - 12, stripe_h)

        painter.setPen(QPen(QColor(PANEL_EDGE), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        painter.setPen(QColor(MUTED))
        f = QFont(FONT_MONO)
        f.setPointSize(TYPE_MICRO)
        painter.setFont(f)
        painter.drawText(QRect(rect.left() + 6, rect.top() + 4, rect.width(), 14),
                         Qt.AlignmentFlag.AlignLeft, f"{self.index + 1:02d}")

        if self.is_target and (self.revealed or self.show_name):
            painter.setPen(QColor(ACCENT))
            f = QFont(FONT_SANS)
            f.setPointSize(TYPE_BODY)
            painter.setFont(f)
            painter.drawText(QRect(rect.right() - 18, rect.top() + 2, 16, 16),
                             Qt.AlignmentFlag.AlignCenter, self.suit or "♥")

        if self.revealed and self.is_target:
            painter.setPen(QColor(ACCENT))
            f = QFont(FONT_SANS)
            f.setPointSize(min(28, max(14, rect.height() // 3)))
            f.setWeight(QFont.Weight.DemiBold)
            painter.setFont(f)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Q")
        elif self.show_name:
            painter.setPen(QColor(INK_SOFT))
            f = QFont(FONT_SANS)
            f.setPointSize(TYPE_BODY)
            painter.setFont(f)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.label)
        else:
            dot = 4
            cx = rect.center().x()
            cy = rect.center().y() - 4
            alpha = 90 if not self.classical_visited else 40
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(31, 31, 31, alpha))
            painter.drawEllipse(cx - dot // 2, cy - dot // 2, dot, dot)

        if self.classical_current:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(INK))
            painter.drawRect(rect.left() + 6, rect.bottom() - 6,
                             rect.width() - 12, 3)

        if self.is_target:
            painter.setPen(QPen(QColor(ACCENT), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)


# ------------------------
# Heatmap canvas for n >= 11
# ------------------------
class HeatmapCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.cols = 1
        self.rows = 1
        self.spacing = 1
        self.probs = {}
        self.classical_idx = None
        self.target_idx = None
        self.quantum_success = False
        self.classical_visited_count = 0

    def set_geometry(self, cols, rows, spacing=1):
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        self.spacing = max(0, spacing)
        self.update()

    def set_data(self, probs, classical_idx, target_idx, quantum_success=False, visited=0):
        self.probs = probs or {}
        self.classical_idx = classical_idx
        self.target_idx = target_idx
        self.quantum_success = quantum_success
        self.classical_visited_count = visited
        self.update()

    def _cell_rect(self, viewport_rect: QRect, r, c):
        width = viewport_rect.width()
        height = viewport_rect.height()
        cw = (width - (self.cols - 1) * self.spacing) / self.cols
        ch = (height - (self.rows - 1) * self.spacing) / self.rows
        x = viewport_rect.left() + c * (cw + self.spacing)
        y = viewport_rect.top() + r * (ch + self.spacing)
        return QRect(int(x), int(y), int(cw), int(ch))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(BG))

        if self.cols <= 0 or self.rows <= 0:
            return

        viewport = self.rect()
        total = self.cols * self.rows
        for idx in range(total):
            r = idx // self.cols
            c = idx % self.cols
            rect = self._cell_rect(viewport, r, c)
            painter.fillRect(rect, QColor(PANEL_DARK))
            if self.classical_idx is not None and idx < self.classical_visited_count:
                painter.fillRect(rect, QColor(225, 219, 209))
            p = self.probs.get(idx, 0.0)
            if p > 0:
                alpha = max(20, min(int(p * 255 * 3.5), 220))
                painter.fillRect(rect, QColor(31, 31, 31, alpha))

        if self.classical_idx is not None:
            r = self.classical_idx // self.cols
            c = self.classical_idx % self.cols
            rect = self._cell_rect(viewport, r, c)
            painter.fillRect(rect, QColor(INK))

        if self.target_idx is not None:
            r = self.target_idx // self.cols
            c = self.target_idx % self.cols
            rect = self._cell_rect(viewport, r, c)
            painter.setPen(QPen(QColor(ACCENT), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -2, -2))


class LegendSwatch(QWidget):
    def __init__(self, kind: str, label: str):
        super().__init__()
        self.kind = kind
        self.label = label
        self.setFixedHeight(20)

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(180, 20)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRect(0, 4, 12, 12)
        if self.kind == "unscanned":
            painter.setPen(QPen(QColor(PANEL_EDGE), 1))
            painter.setBrush(QColor(BG))
            painter.drawRect(rect)
        elif self.kind == "visited":
            painter.setPen(QPen(QColor(PANEL_EDGE), 1))
            painter.setBrush(QColor(PANEL_DARK))
            painter.drawRect(rect)
        elif self.kind == "probe":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(INK))
            painter.drawRect(rect)
        elif self.kind == "marked":
            painter.setPen(QPen(QColor(ACCENT), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))

        painter.setPen(QColor(MUTED))
        f = QFont(FONT_MONO)
        f.setPointSize(TYPE_MICRO)
        painter.setFont(f)
        painter.drawText(QRect(20, 0, self.width() - 20, self.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.label.upper())


# ------------------------
# Main app
# ------------------------
class GroverGame(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quantum Lab Series — Search Analyzer Q-52")
        self.setMinimumSize(1440, 920)
        self.resize(1680, 1000)

        self.session_id = f"{random.randint(0, 9999):04d}"
        self.session_started = datetime.now()

        self.num_qubits = DEFAULT_QUBITS
        self.n_items = None
        self.deck = []
        self.queen_index = None
        self.queen_bin = None
        self.oracle = None
        self.diff = None

        self.classical_attempts = 0
        self.classical_counter = 0
        self.classical_done = False
        self.grover_iterations = 0
        self.grover_done = False
        self.reveal_mode = False
        self.quantum_steps = None
        self.last_probs = {}
        self.last_classical_index = None

        self.success_threshold = SUCCESS_THRESHOLD
        self.quantum_batch = 1
        self.auto_classical = False
        self.auto_batch = 1
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_step_classical)

        self._cols = 0
        self._rows = 0
        self._grid_spacing = 6

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._refresh_clock)
        self.clock_timer.start(1000)

        self._build_ui()
        self._apply_theme()
        self._init_problem(self.num_qubits)
        QTimer.singleShot(0, self._relayout_if_needed)

    def _apply_theme(self):
        self.setStyleSheet(
            f"""
            GroverGame {{ background: {BG}; }}
            QWidget {{
                color: {INK};
                font-family: "{FONT_SANS}";
                font-size: {TYPE_BODY}px;
            }}
            QLabel {{ background: transparent; }}
            QFrame {{ background: transparent; }}
            QFrame#HeaderBar {{ background: {PANEL}; border-bottom: 1px solid {PANEL_EDGE}; }}
            QFrame#FooterBar {{ background: {PANEL}; border-top: 1px solid {PANEL_EDGE}; }}
            QFrame#Sidebar {{ background: {BG}; border-right: 1px solid {PANEL_EDGE}; }}
            QFrame#MainFrame {{ background: {BG}; }}
            QFrame#Panel {{ background: {PANEL}; border: 1px solid {PANEL_EDGE}; }}
            QFrame#EngineCard {{ background: {PANEL_DARK}; border: 1px solid {PANEL_EDGE}; }}
            QFrame#EngineBar {{ background: {INK}; border: none; }}
            QLabel#SectionLabel {{ color: {INK}; font-family: "{FONT_MONO}"; font-size: {TYPE_MICRO}px; letter-spacing: 1.5px; }}
            QLabel#SectionHint {{ color: {MUTED}; font-family: "{FONT_MONO}"; font-size: {TYPE_MICRO}px; letter-spacing: 1px; }}
            QLabel#EngineTitle {{ color: {INK}; font-family: "{FONT_MONO}"; font-size: {TYPE_LABEL}px; letter-spacing: 1.5px; }}
            QLabel#EngineSubtitle {{ color: {MUTED}; font-size: {TYPE_LABEL}px; }}
            QLabel#EngineStatus {{ color: {CLASSICAL}; font-family: "{FONT_MONO}"; font-size: {TYPE_MICRO}px; letter-spacing: 1px; }}
            QLabel#HeaderEyebrow {{ color: {MUTED}; font-family: "{FONT_MONO}"; font-size: {TYPE_MICRO}px; letter-spacing: 2px; }}
            QLabel#HeaderTitle {{ color: {INK}; font-size: {TYPE_HERO}px; font-weight: 600; }}
            QLabel#HeaderMeta {{ color: {MUTED}; font-family: "{FONT_MONO}"; font-size: {TYPE_MICRO}px; letter-spacing: 2px; }}
            QLabel#HeaderMetaValue {{ color: {INK}; font-family: "{FONT_MONO}"; font-size: {TYPE_LABEL}px; letter-spacing: 1px; }}
            QLabel#StatLabel {{ color: {MUTED}; font-family: "{FONT_MONO}"; font-size: {TYPE_MICRO}px; letter-spacing: 2px; }}
            QLabel#StatValue {{ color: {INK}; font-family: "{FONT_MONO}"; font-size: {TYPE_DISPLAY}px; font-weight: 600; }}
            QLabel#MarkedHeader {{ color: {INK}; font-size: {TYPE_DISPLAY}px; font-weight: 600; }}
            QLabel#MarkedSub {{ color: {MUTED}; font-family: "{FONT_MONO}"; font-size: {TYPE_LABEL}px; letter-spacing: 1px; }}
            QLabel#MarkedAccent {{ color: {ACCENT}; font-size: {TYPE_DISPLAY}px; font-weight: 600; }}
            QLabel#MutedMono {{ color: {MUTED}; font-family: "{FONT_MONO}"; font-size: {TYPE_MICRO}px; letter-spacing: 1.5px; }}
            QLabel#InkMono {{ color: {INK}; font-family: "{FONT_MONO}"; font-size: {TYPE_LABEL}px; letter-spacing: 1px; }}
            QLabel#FooterText {{ color: {MUTED}; font-family: "{FONT_MONO}"; font-size: {TYPE_MICRO}px; letter-spacing: 2px; }}
            QLabel#MessageLabel {{ color: {INK_SOFT}; font-size: {TYPE_LABEL}px; }}
            QScrollArea {{ border: none; background: {BG}; }}
            QSlider::groove:horizontal {{ border: none; height: 2px; background: {HAIRLINE}; }}
            QSlider::handle:horizontal {{ background: {BG}; border: 1px solid {INK}; width: 14px; height: 22px; margin: -10px 0; border-radius: 0; }}
            QSlider::handle:horizontal:hover {{ background: {PANEL_DARK}; }}
            QDial#QubitDial {{ background: {PANEL}; }}
            """
        )

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_main(), stretch=1)

        body_wrap = QWidget()
        body_wrap.setLayout(body)
        outer.addWidget(body_wrap, stretch=1)

        outer.addWidget(self._build_footer())

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("HeaderBar")
        bar.setFixedHeight(96)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 14, 28, 14)
        layout.setSpacing(28)

        left = QVBoxLayout()
        left.setSpacing(2)
        eyebrow = QLabel("QUANTUM LAB SERIES")
        eyebrow.setObjectName("HeaderEyebrow")
        ident = QLabel("Search Analyzer · Model Q-52")
        ident.setObjectName("HeaderTitle")
        left.addWidget(eyebrow)
        left.addWidget(ident)
        left_wrap = QWidget()
        left_wrap.setLayout(left)
        left_wrap.setFixedWidth(360)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color: {PANEL_EDGE};")

        center = QVBoxLayout()
        center.setSpacing(2)
        c_eye = QLabel("GROVER'S ALGORITHM — DEMONSTRATION")
        c_eye.setObjectName("HeaderEyebrow")
        c_eye.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_title = QLabel(
            f'Searching <span style="color:{ACCENT}">Queen of Hearts</span> in 52 cards'
        )
        self.header_title.setObjectName("HeaderTitle")
        self.header_title.setTextFormat(Qt.TextFormat.RichText)
        self.header_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(c_eye)
        center.addWidget(self.header_title)
        center_wrap = QWidget()
        center_wrap.setLayout(center)

        right = QHBoxLayout()
        right.setSpacing(28)
        self.session_value = QLabel(f"SESSION  {self.session_id}")
        self.session_value.setObjectName("HeaderMetaValue")
        self.date_value = QLabel(self.session_started.strftime("%d %b %Y").upper())
        self.date_value.setObjectName("HeaderMetaValue")
        self.time_value = QLabel(self.session_started.strftime("%H:%M:%S"))
        self.time_value.setObjectName("HeaderMetaValue")
        right.addWidget(self.session_value)
        right.addWidget(self.date_value)
        right.addWidget(self.time_value)
        right_wrap = QWidget()
        right_wrap.setLayout(right)

        layout.addWidget(left_wrap)
        layout.addWidget(div)
        layout.addWidget(center_wrap, stretch=1)
        layout.addWidget(right_wrap)
        return bar

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(360)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(self._build_engines_panel())
        layout.addWidget(self._build_config_panel())
        layout.addWidget(self._build_speed_panel())
        layout.addWidget(self._build_transport_panel())
        layout.addWidget(self._build_amplitude_panel())
        layout.addStretch(1)
        return side

    def _build_engines_panel(self) -> PanelFrame:
        panel = PanelFrame()
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)
        v.addWidget(SectionHeader("Compute Engines", "02 / Online"))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(EngineCard("Quantum", "6–14 qubit simulator", "6Q"))
        row.addWidget(EngineCard("Classical", "Linear scan baseline", "SEQ"))
        v.addLayout(row)
        return panel

    def _build_config_panel(self) -> PanelFrame:
        panel = PanelFrame()
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)
        v.addWidget(SectionHeader("Configuration", "N = 2ⁿ"))

        row = QHBoxLayout()
        row.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        self.qubit_dial = QubitDial(MIN_QUBITS, MAX_QUBITS)
        self.qubit_dial.setValue(self.num_qubits)
        self.qubit_dial.valueChanged.connect(self._on_qubit_dial)
        left_col.addWidget(self.qubit_dial, alignment=Qt.AlignmentFlag.AlignCenter)

        qubits_row = QHBoxLayout()
        qubits_row.setSpacing(6)
        self.qubits_value = QLabel("6")
        self.qubits_value.setStyleSheet(
            f"color: {INK}; font-family: '{FONT_MONO}'; font-size: 28px; font-weight: 600;"
        )
        qubits_label = QLabel("QUBITS")
        qubits_label.setObjectName("MutedMono")
        qubits_row.addWidget(self.qubits_value)
        qubits_row.addWidget(qubits_label, alignment=Qt.AlignmentFlag.AlignBottom)
        qubits_row.addStretch(1)
        left_col.addLayout(qubits_row)

        register_label = QLabel("REGISTER WIDTH")
        register_label.setObjectName("MutedMono")
        left_col.addWidget(register_label)
        left_col.addStretch(1)

        left_wrap = QWidget()
        left_wrap.setLayout(left_col)

        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        right_col.addStretch(1)
        self.iteration_counter = FlipCounter()
        right_col.addWidget(self.iteration_counter, alignment=Qt.AlignmentFlag.AlignRight)
        self.iter_caption = QLabel("/ 06 OPT")
        self.iter_caption.setObjectName("MutedMono")
        self.iter_caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self.iter_caption)
        right_col.addStretch(1)
        iter_label = QLabel("ITERATION")
        iter_label.setObjectName("MutedMono")
        iter_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(iter_label)

        right_wrap = QWidget()
        right_wrap.setLayout(right_col)

        row.addWidget(left_wrap)
        row.addStretch(1)
        row.addWidget(right_wrap)
        v.addLayout(row)
        return panel

    def _build_speed_panel(self) -> PanelFrame:
        panel = PanelFrame()
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)
        self.speed_header = SectionHeader("Classical Scan Speed", "BRISK · 240 ms")
        v.addWidget(self.speed_header)
        labels = QHBoxLayout()
        for txt in ["HOLD", "SLOW", "MED", "BRISK", "FAST"]:
            l = QLabel(txt)
            l.setObjectName("MutedMono")
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            labels.addWidget(l)
        v.addLayout(labels)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(5)
        self.speed_slider.setValue(4)
        self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.speed_slider.setTickInterval(1)
        self.speed_slider.valueChanged.connect(self._update_speed_label)
        v.addWidget(self.speed_slider)
        self._update_speed_label()
        return panel

    def _build_transport_panel(self) -> PanelFrame:
        panel = PanelFrame()
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)
        v.addWidget(SectionHeader("Transport", "Manual / Auto"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.restart_button = TransportButton("↺", "Restart", "ghost")
        self.restart_button.clicked.connect(self._restart_game)
        self.auto_button = TransportButton("▣", "Auto", "ghost")
        self.auto_button.clicked.connect(self._toggle_auto)
        self.next_button = TransportButton("▸", "Step", "primary")
        self.next_button.clicked.connect(self._next_turn)
        self.reveal_button = TransportButton("◉", "Reveal", "reveal")
        self.reveal_button.clicked.connect(self._toggle_reveal)
        row.addWidget(self.restart_button)
        row.addWidget(self.auto_button)
        row.addWidget(self.next_button)
        row.addWidget(self.reveal_button)
        v.addLayout(row)
        return panel

    def _build_amplitude_panel(self) -> PanelFrame:
        panel = PanelFrame()
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)
        header_row = QHBoxLayout()
        title = QLabel("AMPLITUDE · TARGET")
        title.setObjectName("SectionLabel")
        self.amplitude_value = QLabel("0%")
        self.amplitude_value.setStyleSheet(
            f"color: {INK}; font-family: '{FONT_MONO}'; font-size: {TYPE_DISPLAY}px; font-weight: 600;"
        )
        header_row.addWidget(title)
        header_row.addStretch(1)
        header_row.addWidget(self.amplitude_value)
        v.addLayout(header_row)
        self.amp_bar = AmplitudeBar()
        self.amp_bar.set_threshold(self.success_threshold)
        v.addWidget(self.amp_bar)

        threshold_row = QHBoxLayout()
        threshold_row.setSpacing(8)
        threshold_label = QLabel("STOP AT")
        threshold_label.setObjectName("MutedMono")
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(50)
        self.threshold_slider.setMaximum(99)
        self.threshold_slider.setValue(int(round(self.success_threshold * 100)))
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        self.threshold_value = QLabel(f"{int(round(self.success_threshold * 100))}%")
        self.threshold_value.setObjectName("InkMono")
        self.threshold_value.setFixedWidth(36)
        self.threshold_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        threshold_row.addWidget(threshold_label)
        threshold_row.addWidget(self.threshold_slider, stretch=1)
        threshold_row.addWidget(self.threshold_value)
        v.addLayout(threshold_row)
        return panel

    def _on_threshold_changed(self, value: int):
        self.success_threshold = value / 100.0
        self.threshold_value.setText(f"{value}%")
        self.amp_bar.set_threshold(self.success_threshold)

    def _build_main(self) -> QWidget:
        main = QFrame()
        main.setObjectName("MainFrame")
        layout = QVBoxLayout(main)
        layout.setContentsMargins(28, 22, 28, 16)
        layout.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(24)

        marked_block = QVBoxLayout()
        marked_block.setSpacing(2)
        marked_eye = QLabel("MARKED ITEM")
        marked_eye.setObjectName("MutedMono")
        marked_block.addWidget(marked_eye)

        marked_row = QHBoxLayout()
        marked_row.setSpacing(10)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {ACCENT}; font-size: {TYPE_DISPLAY}px;")
        self.marked_card = QLabel("Q♥")
        self.marked_card.setObjectName("MarkedAccent")
        self.marked_text = QLabel("— position 36 of 52")
        self.marked_text.setObjectName("MarkedHeader")
        marked_row.addWidget(dot)
        marked_row.addWidget(self.marked_card)
        marked_row.addWidget(self.marked_text)
        marked_row.addStretch(1)
        marked_wrap = QWidget()
        marked_wrap.setLayout(marked_row)
        marked_block.addWidget(marked_wrap)
        marked_widget = QWidget()
        marked_widget.setLayout(marked_block)

        self.stat_quantum = StatTile("Quantum √N")
        self.stat_classical = StatTile("Classical N/2")

        top.addWidget(marked_widget, stretch=1)
        top.addWidget(self.stat_quantum)
        top.addSpacing(24)
        top.addWidget(self.stat_classical)
        layout.addLayout(top)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {HAIRLINE}; max-height: 1px; background: {HAIRLINE};")
        line.setFixedHeight(1)
        layout.addWidget(line)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_host = QFrame()
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(self._grid_spacing)
        self.grid_host.setLayout(self.grid_layout)
        self.scroll.setWidget(self.grid_host)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.scroll, stretch=1)

        self.heatmap = HeatmapCanvas()

        self.message = QLabel("Click STEP to begin.")
        self.message.setObjectName("MessageLabel")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        bottom = QHBoxLayout()
        bottom.setSpacing(20)
        bottom.addWidget(LegendSwatch("unscanned", "Unscanned"))
        bottom.addWidget(LegendSwatch("visited", "Classical visited"))
        bottom.addWidget(LegendSwatch("probe", "Quantum probe"))
        bottom.addWidget(LegendSwatch("marked", "Marked · target"))
        bottom.addStretch(1)
        self.status_label = QLabel("SCAN 00 / 52  ·  ITER 00 / 06")
        self.status_label.setObjectName("InkMono")
        bottom.addWidget(self.status_label)
        layout.addLayout(bottom)
        return main

    def _build_footer(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("FooterBar")
        bar.setFixedHeight(36)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(20)
        left = QLabel("GROVER · Q-52 · FIRMWARE 1.04 · SIMULATION MODE")
        left.setObjectName("FooterText")
        layout.addWidget(left)
        layout.addStretch(1)
        dots = QHBoxLayout()
        dots.setSpacing(6)
        for i in range(7):
            d = QLabel("●" if i == 2 else "·")
            d.setStyleSheet(f"color: {INK if i == 2 else MUTED}; font-size: 10px;")
            dots.addWidget(d)
        dots_wrap = QWidget()
        dots_wrap.setLayout(dots)
        layout.addWidget(dots_wrap)
        layout.addStretch(1)
        right = QLabel(f"OUTPUT · LOG → /var/qlog/{self.session_id}.log")
        right.setObjectName("FooterText")
        layout.addWidget(right)
        return bar

    def _refresh_clock(self):
        now = datetime.now()
        self.time_value.setText(now.strftime("%H:%M:%S"))

    def _on_qubit_dial(self, value):
        self.qubits_value.setText(str(value))
        if value != self.num_qubits:
            self._init_problem(value)
            QTimer.singleShot(0, self._relayout_if_needed)

    def _clear_grid_layout(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

    def _init_problem(self, num_qubits: int):
        self.auto_classical = False
        self.auto_timer.stop()
        self._clear_grid_layout()

        self.num_qubits = num_qubits
        self.n_items = 52 if num_qubits == 6 else (1 << num_qubits)
        self.classical_attempts = 0
        self.classical_counter = 0
        self.classical_done = False
        self.grover_iterations = 0
        self.grover_done = False
        self.quantum_steps = None
        self.reveal_mode = False
        self.last_probs = {}
        self.last_classical_index = None

        if self.num_qubits == 6:
            self.deck = DECK[:]
            random.shuffle(self.deck)
            self.queen_index = self.deck.index(QUEEN_CARD)
            self.queen_bin = format(self.queen_index, f"0{self.num_qubits}b")
            self.header_title.setText(
                f'Searching <span style="color:{ACCENT}">Queen of Hearts</span> in 52 cards'
            )
            self.marked_card.setText("Q♥")
            self.marked_text.setText(f"— position {self.queen_index + 1} of 52")
        else:
            self.deck = None
            self.queen_index = random.randrange(self.n_items)
            self.queen_bin = format(self.queen_index, f"0{self.num_qubits}b")
            self.header_title.setText(
                f'Searching <span style="color:{ACCENT}">target state</span> in {self.n_items} cards'
            )
            self.marked_card.setText(f"|{self.queen_bin}⟩")
            self.marked_text.setText(f"— position {self.queen_index + 1} of {self.n_items}")

        self.oracle = custom_oracle(self.num_qubits, self.queen_bin)
        self.diff = diffuser(self.num_qubits)
        self.quantum_batch = 5 if self.num_qubits >= 12 else 1
        self._sv = None
        self._sv_iters = 0

        opt = optimal_iterations(self.n_items)
        self.iter_caption.setText(f"/ {opt:02d} OPT")
        self.iteration_counter.set_value(0)
        self.qubits_value.setText(str(self.num_qubits))
        self.qubit_dial.blockSignals(True)
        self.qubit_dial.setValue(self.num_qubits)
        self.qubit_dial.blockSignals(False)

        self.stat_quantum.set_value(f"≈ {math.sqrt(self.n_items):.1f}")
        self.stat_classical.set_value(f"{self.n_items / 2:.1f}")

        self.amp_bar.set_value(0.0)
        self.amplitude_value.setText("0%")
        self.message.setText("Click STEP to begin.")
        self.reveal_button.variant = "reveal"
        self.reveal_button.update()
        self._update_status()

        self.cards = []
        if self.num_qubits < HEATMAP_MIN_QUBITS:
            self.scroll.takeWidget()
            self.scroll.setWidget(self.grid_host)
            if self.num_qubits == 6:
                cols = 13
                rows = 4
            else:
                cols = int(math.sqrt(self.n_items))
                rows = math.ceil(self.n_items / cols)
            self._cols, self._rows = cols, rows

            for idx in range(self.n_items):
                if self.num_qubits == 6:
                    row = idx // 13
                    col = idx % 13
                    name = self.deck[idx]
                    is_target = (idx == self.queen_index)
                    suit = name[-1] if is_target else ""
                    card = CardCell(idx, name, suit=suit, is_target=is_target)
                else:
                    row = idx // cols
                    col = idx % cols
                    is_target = (idx == self.queen_index)
                    card = CardCell(idx, str(idx), suit="", is_target=is_target)
                self.cards.append(card)
                self.grid_layout.addWidget(card, row, col)
        else:
            self.scroll.takeWidget()
            self.scroll.setWidget(self.heatmap)
            cols = int(math.sqrt(self.n_items))
            rows = math.ceil(self.n_items / cols)
            self._cols, self._rows = cols, rows
            self.heatmap.set_geometry(cols, rows, spacing=1)
            self.cards = []

    def _relayout_if_needed(self):
        if self.num_qubits < HEATMAP_MIN_QUBITS:
            vp = self.scroll.viewport()
            vp_w = max(120, vp.width() - 8)
            vp_h = max(120, vp.height() - 8)
            spacing = self._grid_spacing
            cols, rows = self._cols, self._rows
            cell_w = (vp_w - (cols - 1) * spacing) // cols
            cell_h = (vp_h - (rows - 1) * spacing) // rows
            cell_w = max(40, cell_w)
            cell_h = max(60, min(cell_h, int(cell_w * 1.35)))
            for w in self.cards:
                w.set_size(cell_w, cell_h)
        else:
            self.heatmap.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._relayout_if_needed)

    def _toggle_reveal(self):
        self.reveal_mode = not self.reveal_mode
        if self.num_qubits < HEATMAP_MIN_QUBITS:
            for card in self.cards:
                card.show_name = self.reveal_mode
                card.update()
        self.reveal_button.caption = "Hide" if self.reveal_mode else "Reveal"
        self.reveal_button.update()

    def _toggle_auto(self):
        if self.auto_classical or self.auto_timer.isActive():
            self.auto_classical = False
            self.auto_timer.stop()
            self.next_button.setDisabled(False)
            self.auto_button.caption = "Auto"
        else:
            if self.classical_done and self.grover_done:
                return
            self.auto_classical = True
            self.next_button.setDisabled(True)
            self._configure_auto_speed()
            self.auto_timer.start()
            self.auto_button.caption = "Stop"
        self.auto_button.update()

    def _restart_game(self):
        self._init_problem(self.num_qubits)
        QTimer.singleShot(0, self._relayout_if_needed)

    def _classical_guess(self):
        if self.classical_done or self.classical_counter >= self.n_items:
            return None
        idx = self.classical_counter
        self.classical_counter += 1
        return idx

    def _apply_probs_to_view(self, probs, classical_index):
        self.last_probs = probs or {}
        self.last_classical_index = classical_index
        if self.num_qubits < HEATMAP_MIN_QUBITS:
            for card in self.cards:
                card.probability = probs.get(card.index, 0.0) if probs else 0.0
                card.classical_current = (card.index == classical_index)
                card.classical_visited = (card.index < self.classical_counter)
                card.revealed = (
                    self.num_qubits == 6
                    and card.index == self.queen_index
                    and self.grover_done
                )
                card.update()
        else:
            self.heatmap.set_data(
                probs, classical_index, self.queen_index,
                quantum_success=self.grover_done,
                visited=self.classical_counter,
            )
        target_p = (probs or {}).get(self.queen_index, 0.0)
        self.amp_bar.set_value(target_p)
        self.amplitude_value.setText(f"{int(round(target_p * 100))}%")
        self._update_status()

    def _update_status(self):
        opt = optimal_iterations(self.n_items)
        self.status_label.setText(
            f"SCAN {min(self.classical_counter, self.n_items):02d} / {self.n_items:02d}"
            f"  ·  ITER {self.grover_iterations:02d} / {opt:02d}"
        )
        self.iteration_counter.set_value(self.grover_iterations)

    def _update_speed_label(self):
        v = self.speed_slider.value()
        spec = {
            1: ("HOLD", 1000), 2: ("SLOW", 480), 3: ("MED", 320),
            4: ("BRISK", 240), 5: ("FAST", 90),
        }
        name, ms = spec.get(v, ("BRISK", 240))
        self.speed_header.set_hint(f"{name} · {ms} ms")

    def _configure_auto_speed(self):
        v = self.speed_slider.value()
        if v == 1:
            interval, batch = 1000, 1
        elif v == 2:
            interval, batch = 60, 1
        elif v == 3:
            interval, batch = 20, 4
        elif v == 4:
            interval, batch = 10, 8
        else:
            interval, batch = 2, 32
        if self.num_qubits >= 13:
            batch = max(batch, 32)
            interval = min(interval, 3)
        self.auto_batch = batch
        self.auto_timer.setInterval(interval)

    def _auto_step_classical(self):
        if not self.auto_classical:
            self.auto_timer.stop()
            return

        last_probs = self.last_probs
        last_classical_index = self.last_classical_index

        for _ in range(self.auto_batch):
            progressed = False

            if not self.grover_done:
                self.grover_iterations += 1
                last_probs = self._run_grover_exact(self.grover_iterations)
                if last_probs.get(self.queen_index, 0.0) > self.success_threshold:
                    self.grover_done = True
                    self.quantum_steps = self.grover_iterations
                progressed = True

            if not self.classical_done:
                ci = self._classical_guess()
                if ci is None:
                    self.classical_done = True
                else:
                    last_classical_index = ci
                    self.classical_attempts += 1
                    if ci == self.queen_index:
                        self.classical_done = True
                    progressed = True

            if not progressed or (self.grover_done and self.classical_done):
                break

        self._apply_probs_to_view(last_probs, last_classical_index)

        if self.grover_done and self.classical_done:
            self.auto_classical = False
            self.auto_timer.stop()
            self.next_button.setDisabled(False)
            self.auto_button.caption = "Auto"
            self.auto_button.update()
            quantum_part = (
                f"Quantum: {self.quantum_steps} iterations."
                if self.quantum_steps is not None
                else "Quantum: not found."
            )
            self.message.setText(
                f"Both engines finished. {quantum_part} "
                f"Classical: {self.classical_attempts} checks."
            )

    def _run_grover_exact(self, iterations: int):
        n = self.num_qubits
        if self._sv is None or iterations < self._sv_iters:
            init = QuantumCircuit(n)
            init.h(range(n))
            self._sv = Statevector.from_instruction(init)
            self._sv_iters = 0
        while self._sv_iters < iterations:
            self._sv = self._sv.evolve(self.oracle).evolve(self.diff)
            self._sv_iters += 1
        probs = self._sv.probabilities()
        return {i: float(p) for i, p in enumerate(probs) if p > PROB_RENDER_EPSILON}

    def _next_turn(self):
        if self.auto_classical:
            return
        classical_index = self._classical_guess()
        if classical_index is not None:
            self.classical_attempts += 1
        classical_found_now = classical_index == self.queen_index
        if classical_found_now:
            self.classical_done = True

        final_probs = self.last_probs
        if not self.grover_done:
            for _ in range(self.quantum_batch):
                self.grover_iterations += 1
                final_probs = self._run_grover_exact(self.grover_iterations)
                if final_probs.get(self.queen_index, 0.0) > self.success_threshold:
                    self.grover_done = True
                    self.quantum_steps = self.grover_iterations
                    break

        self._apply_probs_to_view(final_probs, classical_index)

        if self.grover_done and self.classical_done:
            self.message.setText(
                f"Both engines found the target. Quantum: {self.quantum_steps} iterations. "
                f"Classical: {self.classical_attempts} checks."
            )
        elif self.grover_done and not self.classical_done:
            self.message.setText(
                f"Quantum located the target in {self.quantum_steps} iterations. "
                "Classical engine continues scanning…"
            )
            self.auto_classical = True
            self.next_button.setDisabled(True)
            self.auto_button.caption = "Stop"
            self.auto_button.update()
            self._configure_auto_speed()
            self.auto_timer.start()
        elif classical_found_now and not self.grover_done:
            self.message.setText(
                f"Classical found the target on check {self.classical_attempts}. "
                "Quantum amplitudes still resolving."
            )
        else:
            if self.num_qubits == 6 and classical_index is not None:
                bit = f"checked {self.deck[classical_index]}"
            elif classical_index is not None:
                bit = f"checked index {classical_index}"
            else:
                bit = "scan complete"
            self.message.setText(
                f"Grover iter {self.grover_iterations}. Classical {bit}."
            )


def main():
    app = QApplication(sys.argv)
    QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    window = GroverGame()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()