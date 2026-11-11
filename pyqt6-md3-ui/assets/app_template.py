"""
Готовый каркас приложения на PyQt6 в стиле Material Design 3 (MD3).

Запуск:
    pip install PyQt6
    python app_template.py

Что внутри:
    - frameless-окно с Material-кнопками окна (minimize/maximize/close),
      перетаскиванием за TopAppBar и изменением размера за края
    - NavigationDrawer с анимированным pill-индикатором выбранного пункта
    - QStackedWidget с плавным fade-переходом между страницами
    - elevated-карточки с мягкой тенью (QGraphicsDropShadowEffect)
    - MdButton с анимированным state layer и ripple из точки нажатия
    - MdSwitch / MdSlider / MdCheckBox / MdSegmentedControl в стиле MD3
    - переключатель темы (свет/тёмная): переключение пересобирает интерфейс
      на новом наборе MD3-токенов, сохраняя состояние страниц

Это стартовая точка, а не готовое приложение: страницы, текст и логика —
демо-контент, который нужно заменить на реальный контент конкретного проекта.
"""

from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import (
    Qt,
    QEvent,
    QPropertyAnimation,
    QEasingCurve,
    QRect,
    QRectF,
    QPointF,
    QParallelAnimationGroup,
    QVariantAnimation,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QFontDatabase,
    QFontMetricsF,
    QPen,
    QPixmap,
    QIcon,
    QPalette,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QStackedWidget,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QSizePolicy,
    QComboBox,
    QProgressBar,
    QLineEdit,
    QTextEdit,
    QListWidget,
    QScrollArea,
    QAbstractItemView,
    QFileDialog,
)


# ---------------------------------------------------------------------------
# Дизайн-токены (Material Design 3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Theme:
    primary: str
    on_primary: str
    primary_container: str
    on_primary_container: str
    secondary_container: str
    on_secondary_container: str
    surface: str
    surface_container_low: str
    surface_container: str
    surface_container_high: str
    surface_container_highest: str
    on_surface: str
    on_surface_variant: str
    outline: str
    outline_variant: str
    error: str
    on_error: str
    error_container: str
    on_error_container: str
    shadow_alpha: int      # 0..255, тень всегда чёрная, меняется только альфа


LIGHT = Theme(
    primary="#6750A4",
    on_primary="#FFFFFF",
    primary_container="#EADDFF",
    on_primary_container="#21005D",
    secondary_container="#E8DEF8",
    on_secondary_container="#1D192B",
    surface="#FEF7FF",
    surface_container_low="#F7F2FA",
    surface_container="#F3EDF7",
    surface_container_high="#ECE6F0",
    surface_container_highest="#E6E0E9",
    on_surface="#1D1B20",
    on_surface_variant="#49454F",
    outline="#79747E",
    outline_variant="#CAC4D0",
    error="#B3261E",
    on_error="#FFFFFF",
    error_container="#F9DEDC",
    on_error_container="#410E0B",
    shadow_alpha=45,
)

DARK = Theme(
    primary="#D0BCFF",
    on_primary="#381E72",
    primary_container="#4F378B",
    on_primary_container="#EADDFF",
    secondary_container="#4A4458",
    on_secondary_container="#E8DEF8",
    surface="#141218",
    surface_container_low="#1D1B20",
    surface_container="#211F26",
    surface_container_high="#2B2930",
    surface_container_highest="#36343B",
    on_surface="#E6E0E9",
    on_surface_variant="#CAC4D0",
    outline="#938F99",
    outline_variant="#49454F",
    error="#F2B8B5",
    on_error="#601410",
    error_container="#8C1D18",
    on_error_container="#F9DEDC",
    shadow_alpha=120,
)

RADIUS_WINDOW = 16
RADIUS_CARD = 12
RADIUS_MENU = 8
RADIUS_FIELD = 4
SIDEBAR_WIDTH = 220
EDGE_MARGIN = 12  # px, зона захвата края окна (совпадает с отступом под тень)
EDGE_TOP, EDGE_BOTTOM, EDGE_LEFT, EDGE_RIGHT = 1, 2, 4, 8

DUR_FAST = 140       # hover
DUR_PRESS = 90       # нажатие: входим быстро, чтобы отклик ощущался мгновенным
DUR_RELEASE = 200    # отпускание: мягкий возврат
DUR_MED = 250        # переход страницы, индикатор сайдбара, тумблер
DUR_RIPPLE = 450     # ripple кнопки
EASE = QEasingCurve.Type.OutCubic
EASE_PRESS = QEasingCurve.Type.OutQuad

REPLIES = (
    "Понял, уже смотрю.",
    "Хорошо, сделаю.",
    "Принято!",
    "Записал в план.",
    "Отлично, спасибо!",
)

# Material Symbols "visibility" / "visibility_off" (currentColor заменяется перед рендером).
SVG_EYE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">'
    '<path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5'
    'c-1.73-4.39-6-7.5-11-7.5Zm0 12.5a5 5 0 1 1 0-10 5 5 0 0 1 0 10Zm0-8a3 3 0 1 0 0 6 '
    '3 3 0 0 0 0-6Z"/>'
    '</svg>'
)

SVG_EYE_SLASH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">'
    '<path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 '
    '2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 '
    '7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 '
    '7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 '
    '9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 '
    '1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78 '
    '3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/>'
    '</svg>'
)

PAGES = ["Обзор", "Задачи", "Ввод", "Чат", "Файлы", "Настройки"]


def system_font(point_size: int = 14, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """MD3-типографика: Roboto / Google Sans / Noto Sans с разумным фоллбэком."""
    families = QFontDatabase.families()
    for candidate in (
        "Roboto",
        "Google Sans",
        "Noto Sans",
        "Segoe UI",
    ):
        if candidate in families:
            font = QFont(candidate, point_size)
            font.setWeight(weight)
            font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            return font
    font = QFont()
    font.setPointSize(point_size)
    font.setWeight(weight)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def rgba(hex_color: str, alpha_0_255: int) -> str:
    """hex-цвет + альфа (0..255) -> строка rgba(...) для QSS (Qt ждёт альфу 0..255, не 0..1)."""
    color = QColor(hex_color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha_0_255})"


def accent_fg(theme: Theme) -> str:
    """Совместимость: контрастный текст на primary-подложке = роль on_primary."""
    return theme.on_primary


def shadow_color(theme: Theme) -> QColor:
    color = QColor(0, 0, 0)
    color.setAlpha(theme.shadow_alpha)
    return color


def lerp_color(start: QColor, end: QColor, t: float) -> QColor:
    """Линейная интерполяция RGB между двумя цветами (t зажимается в 0..1)."""
    t = max(0.0, min(1.0, t))
    return QColor(
        round(start.red() + (end.red() - start.red()) * t),
        round(start.green() + (end.green() - start.green()) * t),
        round(start.blue() + (end.blue() - start.blue()) * t),
    )


def animate_property(anim: QPropertyAnimation, current: float, target: float,
                     duration: int, easing: QEasingCurve.Type) -> None:
    """Перезапускает уже созданную анимацию с текущего значения (press/release/hover)."""
    anim.stop()
    anim.setDuration(duration)
    anim.setEasingCurve(easing)
    anim.setStartValue(current)
    anim.setEndValue(target)
    anim.start()


def draw_checkmark(painter: QPainter, cx: float, cy: float, scale: float,
                   color, width: float = 2.0) -> None:
    """Галочка MD3. drawLine — только int-координаты (округляем)."""
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    x1, y1 = round(cx - 4.0 * scale), round(cy)
    x2, y2 = round(cx - 1.0 * scale), round(cy + 3.0 * scale)
    x3, y3 = round(cx + 5.0 * scale), round(cy - 3.0 * scale)
    painter.drawLine(x1, y1, x2, y2)
    painter.drawLine(x2, y2, x3, y3)


# ---------------------------------------------------------------------------
# MdButton: filled / tonal, state layer + ripple
# ---------------------------------------------------------------------------

class MdButton(QPushButton):
    """MD3-кнопка: pill-форма, анимированный state layer и ripple из точки нажатия."""

    def __init__(self, text: str, theme: Theme, kind: str = "filled", parent=None):
        super().__init__(text, parent)
        self._theme = theme
        self._kind = kind
        self._hover = 0.0
        self._press = 0.0
        self._ripple = 1.0
        self._ripple_origin = QPointF()
        if kind == "tonal":
            self._bg = theme.secondary_container
            self._fg = theme.on_secondary_container
        else:
            self._bg = theme.primary
            self._fg = theme.on_primary
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(system_font(14, QFont.Weight.Medium))
        self.setFixedHeight(40)
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance(text) + 48)
        self.setStyleSheet(
            f"QPushButton {{ border: none; background: transparent; "
            f"color: {self._fg}; padding: 0 24px; border-radius: 20px; }}"
        )
        self._hover_anim = QPropertyAnimation(self, b"hover", self)
        self._hover_anim.setDuration(DUR_FAST)
        self._hover_anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)
        self._ripple_anim = QPropertyAnimation(self, b"ripple", self)
        self._ripple_anim.setDuration(DUR_RIPPLE)
        self._ripple_anim.setEasingCurve(EASE)
        self.pressed.connect(self._on_pressed)
        self.released.connect(self._on_released)

    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    hover = pyqtProperty(float, fget=get_hover, fset=set_hover)

    def get_press(self) -> float:
        return self._press

    def set_press(self, value: float) -> None:
        self._press = value
        self.update()

    press = pyqtProperty(float, fget=get_press, fset=set_press)

    def get_ripple(self) -> float:
        return self._ripple

    def set_ripple(self, value: float) -> None:
        self._ripple = value
        self.update()

    ripple = pyqtProperty(float, fget=get_ripple, fset=set_ripple)

    def _on_pressed(self) -> None:
        animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)
        self._ripple_anim.stop()
        self._ripple_anim.setStartValue(0.0)
        self._ripple_anim.setEndValue(1.0)
        self._ripple_anim.start()

    def _on_released(self) -> None:
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._ripple_origin = event.position()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        animate_property(self._hover_anim, self._hover, 1.0, DUR_FAST, EASE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate_property(self._hover_anim, self._hover, 0.0, DUR_FAST, EASE)
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2

        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._bg))
        painter.drawRoundedRect(rect, radius, radius)

        # State layer: hover 0.08, press 0.12 (от on_primary / on_secondary_container).
        layer = QColor(self._fg)
        layer.setAlphaF(min(1.0, 0.08 * self._hover + 0.04 * self._press))
        if layer.alphaF() > 0.004:
            painter.setBrush(layer)
            painter.drawRoundedRect(rect, radius, radius)

        # Ripple из точки нажатия, расширяется до покрытия всей кнопки.
        if 0.0 <= self._ripple < 1.0:
            origin = self._ripple_origin
            if origin.isNull():
                origin = rect.center()
            ox, oy = origin.x(), origin.y()
            w, h = rect.width(), rect.height()
            max_r = max(math.hypot(ox - x, oy - y)
                        for x, y in ((0, 0), (w, 0), (0, h), (w, h))) + 4.0
            ripple_color = QColor(self._fg)
            ripple_color.setAlphaF(0.18 * (1.0 - self._ripple))
            painter.setBrush(ripple_color)
            r = max_r * self._ripple
            painter.drawEllipse(origin, r, r)
        painter.end()
        super().paintEvent(event)


# ---------------------------------------------------------------------------
# MdSwitch: 52x32, трек + ручка с галочкой
# ---------------------------------------------------------------------------

class MdSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, theme: Theme, checked: bool = False, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._checked = checked
        self._knob_pos = 1.0 if checked else 0.0
        self._hover = 0.0
        self._press = 0.0
        self.setFixedSize(52, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"knobPos", self)
        self._anim.setDuration(DUR_MED)
        self._anim.setEasingCurve(EASE)
        self._hover_anim = QPropertyAnimation(self, b"hover", self)
        self._hover_anim.setDuration(DUR_FAST)
        self._hover_anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)

    def get_knob_pos(self) -> float:
        return self._knob_pos

    def set_knob_pos(self, value: float) -> None:
        self._knob_pos = value
        self.update()

    knobPos = pyqtProperty(float, fget=get_knob_pos, fset=set_knob_pos)

    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    hover = pyqtProperty(float, fget=get_hover, fset=set_hover)

    def get_press(self) -> float:
        return self._press

    def set_press(self, value: float) -> None:
        self._press = value
        self.update()

    press = pyqtProperty(float, fget=get_press, fset=set_press)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if checked == self._checked:
            return
        self._checked = checked
        self._anim.stop()
        self._anim.setStartValue(self._knob_pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def enterEvent(self, event):
        animate_property(self._hover_anim, self._hover, 1.0, DUR_FAST, EASE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate_property(self._hover_anim, self._hover, 0.0, DUR_FAST, EASE)
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self._theme
        w, h = self.width(), self.height()
        t = max(0.0, min(1.0, self._knob_pos))

        track_rect = QRectF(0, 0, w, h)
        track_color = lerp_color(
            QColor(theme.surface_container_highest), QColor(theme.primary), t
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, h / 2, h / 2)

        # Во включённом состоянии обводка исчезает.
        if t < 0.99:
            border = QColor(theme.outline)
            border.setAlpha(round(255 * (1.0 - t)))
            pen = QPen(border)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(track_rect.adjusted(1, 1, -1, -1), h / 2 - 1, h / 2 - 1)

        cx = 16.0 + 20.0 * t
        cy = h / 2.0
        base_d = 16.0 + 8.0 * t
        d = base_d + (28.0 - base_d) * self._press

        # State layer вокруг ручки.
        state = lerp_color(QColor(theme.on_surface), QColor(theme.primary), t)
        state.setAlphaF(min(1.0, 0.08 * self._hover + 0.04 * self._press))
        if state.alphaF() > 0.004:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(state)
            painter.drawEllipse(QPointF(cx, cy), 20.0, 20.0)

        knob_color = lerp_color(QColor(theme.outline), QColor(theme.on_primary), t)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(knob_color)
        painter.drawEllipse(QPointF(cx, cy), d / 2, d / 2)

        # Галочка внутри включённой ручки.
        if t > 0.5:
            check = QColor(theme.primary)
            check.setAlphaF((t - 0.5) * 2.0)
            draw_checkmark(painter, cx, cy, (d / 24.0) * 0.9, check, width=2.0)
        painter.end()


# ---------------------------------------------------------------------------
# MdSlider: трек 4px + ручка 20px + state layer 40px
# ---------------------------------------------------------------------------

class MdSlider(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, theme: Theme, value: int = 50, minimum: int = 0,
                 maximum: int = 100, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._min = minimum
        self._max = maximum
        self._value = max(minimum, min(maximum, value))
        self._hover = 0.0
        self._pressed = False
        self._press = 0.0
        self._fill = (self._value - self._min) / max(1, self._max - self._min)
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hover_anim = QPropertyAnimation(self, b"hover", self)
        self._hover_anim.setDuration(DUR_FAST)
        self._hover_anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)
        self._fill_anim = QPropertyAnimation(self, b"fill", self)
        self._fill_anim.setDuration(DUR_FAST)
        self._fill_anim.setEasingCurve(EASE)

    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    hover = pyqtProperty(float, fget=get_hover, fset=set_hover)

    def get_press(self) -> float:
        return self._press

    def set_press(self, value: float) -> None:
        self._press = value
        self.update()

    press = pyqtProperty(float, fget=get_press, fset=set_press)

    def get_fill(self) -> float:
        return self._fill

    def set_fill(self, value: float) -> None:
        self._fill = max(0.0, min(1.0, value))
        self.update()

    fill = pyqtProperty(float, fget=get_fill, fset=set_fill)

    def _knob_radius(self) -> float:
        return 10.0

    def value(self) -> int:
        return self._value

    def setValue(self, v: int) -> None:
        v = max(self._min, min(self._max, v))
        if v != self._value:
            self._value = v
            self.valueChanged.emit(v)
            target = (self._value - self._min) / max(1, self._max - self._min)
            if self._pressed:
                self.set_fill(target)
            else:
                animate_property(self._fill_anim, self._fill, target, DUR_FAST, EASE)

    def _value_from_x(self, x: float) -> int:
        pad = self._knob_radius()
        track_w = self.width() - 2 * pad
        if track_w <= 0:
            return self._min
        ratio = min(1.0, max(0.0, (x - pad) / track_w))
        return round(self._min + ratio * (self._max - self._min))

    def enterEvent(self, event):
        animate_property(self._hover_anim, self._hover, 1.0, DUR_FAST, EASE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate_property(self._hover_anim, self._hover, 0.0, DUR_FAST, EASE)
        if not self._pressed:
            animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)
            self.setValue(self._value_from_x(event.position().x()))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pressed:
            self.setValue(self._value_from_x(event.position().x()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
            self.setValue(self._value)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self._theme
        h = self.height()
        pad = self._knob_radius()
        track_h = 4.0
        cy = h / 2
        track_x0, track_x1 = pad, self.width() - pad
        ratio = max(0.0, min(1.0, self._fill))
        fill_end = track_x0 + ratio * (track_x1 - track_x0)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.surface_container_highest))
        painter.drawRoundedRect(
            QRectF(track_x0, cy - track_h / 2, track_x1 - track_x0, track_h), 2, 2
        )
        if ratio > 0:
            painter.setBrush(QColor(theme.primary))
            painter.drawRoundedRect(
                QRectF(track_x0, cy - track_h / 2, fill_end - track_x0, track_h), 2, 2
            )

        knob_x = min(max(fill_end, track_x0), track_x1)

        # State layer 40px: hover 0.10, press 0.16.
        state = QColor(theme.primary)
        state.setAlphaF(min(1.0, 0.10 * self._hover + 0.06 * self._press))
        if state.alphaF() > 0.004:
            painter.setBrush(state)
            painter.drawEllipse(QPointF(knob_x, cy), 20.0, 20.0)

        shadow = QColor(0, 0, 0)
        shadow.setAlpha(30)
        painter.setBrush(shadow)
        painter.drawEllipse(QPointF(knob_x, cy + 1), 10.0, 10.0)

        painter.setBrush(QColor(theme.primary))
        painter.drawEllipse(QPointF(knob_x, cy), 10.0, 10.0)
        painter.end()


# ---------------------------------------------------------------------------
# MdCheckBox: бокс 18x18 r2, анимированная галочка
# ---------------------------------------------------------------------------

class MdCheckBox(QWidget):
    """MD3-чекбокс: галочка «прорисовывается» по мере включения, state layer 36px."""

    toggled = pyqtSignal(bool)

    def __init__(self, text: str, theme: Theme, checked: bool = False, parent=None):
        super().__init__(parent)
        self._text = text
        self._theme = theme
        self._checked = checked
        self._check = 1.0 if checked else 0.0
        self._hover = 0.0
        self._press = 0.0
        self._box_scale = 1.0
        self.setFont(system_font(14))
        self.setFixedHeight(24)
        self.setMinimumWidth(34 + self.fontMetrics().horizontalAdvance(text))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._check_anim = QPropertyAnimation(self, b"check", self)
        self._hover_anim = QPropertyAnimation(self, b"hover", self)
        self._hover_anim.setDuration(DUR_FAST)
        self._hover_anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)
        self._scale_anim = QPropertyAnimation(self, b"boxScale", self)
        self._scale_anim.setDuration(DUR_MED)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutBack)

    def get_check(self) -> float:
        return self._check

    def set_check(self, value: float) -> None:
        self._check = value
        self.update()

    check = pyqtProperty(float, fget=get_check, fset=set_check)

    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    hover = pyqtProperty(float, fget=get_hover, fset=set_hover)

    def get_press(self) -> float:
        return self._press

    def set_press(self, value: float) -> None:
        self._press = value
        self.update()

    press = pyqtProperty(float, fget=get_press, fset=set_press)

    def get_box_scale(self) -> float:
        return self._box_scale

    def set_box_scale(self, value: float) -> None:
        self._box_scale = value
        self.update()

    boxScale = pyqtProperty(float, fget=get_box_scale, fset=set_box_scale)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = True) -> None:
        if checked == self._checked:
            return
        self._checked = checked
        if animate:
            duration = DUR_RELEASE if checked else DUR_FAST
            animate_property(self._check_anim, self._check,
                             1.0 if checked else 0.0, duration, EASE)
        else:
            self.set_check(1.0 if checked else 0.0)
        self.toggled.emit(checked)

    def enterEvent(self, event):
        animate_property(self._hover_anim, self._hover, 1.0, DUR_FAST, EASE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate_property(self._hover_anim, self._hover, 0.0, DUR_FAST, EASE)
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        animate_property(self._scale_anim, self._box_scale, 1.0, DUR_MED,
                         QEasingCurve.Type.OutBack)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)
            animate_property(self._scale_anim, self._box_scale, 0.86, DUR_PRESS, EASE_PRESS)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.rect().contains(event.position().toPoint()):
                self.setChecked(not self._checked)
            animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
            animate_property(self._scale_anim, self._box_scale, 1.0, DUR_RELEASE,
                             QEasingCurve.Type.OutBack)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self._theme

        box = QRectF(3.0, (self.height() - 18) / 2.0, 18.0, 18.0)
        center = box.center()

        # State layer 36px вокруг бокса.
        state = QColor(theme.primary if self._checked else theme.on_surface)
        state.setAlphaF(min(1.0, (0.10 if self._checked else 0.06) * self._hover
                            + 0.04 * self._press))
        if state.alphaF() > 0.004:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(state)
            painter.drawEllipse(center, 18.0, 18.0)

        painter.save()
        painter.translate(center)
        painter.scale(self._box_scale, self._box_scale)
        painter.translate(-center)

        if self._check > 0.01:
            fill = QColor(theme.primary)
            fill.setAlphaF(self._check)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(box, 2, 2)

        border = QColor(theme.on_surface_variant)
        border.setAlpha(round(255 * (1.0 - self._check)))
        if border.alpha() > 0:
            pen = QPen(border)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box.adjusted(1, 1, -1, -1), 1.5, 1.5)

        if self._check > 0.01:
            left, top = box.left(), box.top()
            p1 = QPointF(left + 4, top + 9)
            p2 = QPointF(left + 7.5, top + 12.5)
            p3 = QPointF(left + 14, top + 5.5)
            path = QPainterPath(p1)
            if self._check <= 0.45:
                q = self._check / 0.45
                path.lineTo(p1 + (p2 - p1) * q)
            else:
                path.lineTo(p2)
                q = (self._check - 0.45) / 0.55
                path.lineTo(p2 + (p3 - p2) * q)
            mark = QPen(QColor(theme.on_primary))
            mark.setWidthF(2.0)
            mark.setCapStyle(Qt.PenCapStyle.RoundCap)
            mark.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(mark)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        painter.restore()

        painter.setPen(QColor(theme.on_surface))
        painter.setFont(self.font())
        painter.drawText(
            QRectF(32, 0, max(0, self.width() - 32), self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text,
        )
        painter.end()


# ---------------------------------------------------------------------------
# MdSegmentedControl: контейнер-pill + переезжающий индикатор
# ---------------------------------------------------------------------------

class MdSegmentButton(QPushButton):
    """Сегмент: state layer, галочка слева от текста выбранного, анимированный цвет."""

    def __init__(self, text: str, theme: Theme, parent=None):
        super().__init__(text, parent)
        self._theme = theme
        self._hover = 0.0
        self._press = 0.0
        self._color = QColor(theme.on_surface)
        self.setCheckable(True)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(system_font(14, QFont.Weight.Medium))
        self.setFixedHeight(38)
        self.setStyleSheet(
            "QPushButton { border: none; background: transparent; color: transparent; }"
        )
        self._hover_anim = QPropertyAnimation(self, b"hover", self)
        self._hover_anim.setDuration(DUR_FAST)
        self._hover_anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)
        self._color_anim = QPropertyAnimation(self, b"color", self)
        self._color_anim.setDuration(DUR_FAST)
        self._color_anim.setEasingCurve(EASE)

    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    hover = pyqtProperty(float, fget=get_hover, fset=set_hover)

    def get_press(self) -> float:
        return self._press

    def set_press(self, value: float) -> None:
        self._press = value
        self.update()

    press = pyqtProperty(float, fget=get_press, fset=set_press)

    def get_color(self) -> QColor:
        return self._color

    def set_color(self, value: QColor) -> None:
        self._color = QColor(value)
        self.update()

    color = pyqtProperty(QColor, fget=get_color, fset=set_color)

    def set_text_color(self, hex_color: str, animate: bool = True) -> None:
        target = QColor(hex_color)
        if not animate:
            self.set_color(target)
            return
        if target == self._color:
            return
        self._color_anim.stop()
        self._color_anim.setStartValue(self._color)
        self._color_anim.setEndValue(target)
        self._color_anim.start()

    def enterEvent(self, event):
        animate_property(self._hover_anim, self._hover, 1.0, DUR_FAST, EASE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate_property(self._hover_anim, self._hover, 0.0, DUR_FAST, EASE)
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        h = rect.height()

        if self._hover > 0.01 or self._press > 0.01:
            overlay = QColor(self._theme.on_secondary_container if self.isChecked()
                             else self._theme.on_surface)
            overlay.setAlphaF(min(1.0, 0.08 * self._hover + 0.04 * self._press))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(overlay)
            painter.drawRoundedRect(rect, h / 2, h / 2)

        fm = QFontMetricsF(self.font())
        tw = fm.horizontalAdvance(self.text())
        checked = self.isChecked()
        total = tw + (20.0 if checked else 0.0)
        x0 = (rect.width() - total) / 2
        if checked:
            draw_checkmark(painter, x0 + 7, h / 2, 0.85, self._color, width=2.0)
        text_x = x0 + (20.0 if checked else 0.0)
        painter.setPen(self._color)
        painter.setFont(self.font())
        painter.drawText(
            QRectF(text_x, 0, max(0.0, rect.width() - text_x), h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )
        painter.end()


class MdSegmentedControl(QWidget):
    def __init__(self, theme: Theme, options: list[str], default: int = 0, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._buttons: list[QPushButton] = []
        self._current = default
        self.setFixedHeight(40)

        self._indicator = QFrame(self)
        self._indicator.setObjectName("SegIndicator")
        self._indicator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._anim = QPropertyAnimation(self._indicator, b"geometry", self)
        self._anim.setDuration(DUR_MED)
        self._anim.setEasingCurve(EASE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        fm = QFontMetricsF(system_font(14, QFont.Weight.Medium))
        seg_w = max(int(fm.horizontalAdvance(opt)) + 44 for opt in options)
        for i, opt in enumerate(options):
            btn = MdSegmentButton(opt, theme)
            btn.setMinimumWidth(seg_w)
            btn.setChecked(i == default)
            btn.clicked.connect(lambda _checked, b=btn: self._select(self._buttons.index(b), True))
            layout.addWidget(btn, 1)
            self._buttons.append(btn)

        self.setStyleSheet(
            f"QFrame#SegIndicator {{ background-color: {theme.secondary_container}; "
            f"border-radius: 19px; }}"
        )
        self._apply_colors()

    def _current_geometry(self) -> QRect:
        return self._buttons[self._current].geometry()

    def _apply_colors(self) -> None:
        for i, btn in enumerate(self._buttons):
            color = (self._theme.on_secondary_container if i == self._current
                     else self._theme.on_surface)
            btn.set_text_color(color, animate=self.isVisible())

    def _select(self, idx: int, animate: bool) -> None:
        self._current = idx
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == idx)
        self._apply_colors()
        self._anim.stop()
        if animate:
            self._anim.setStartValue(self._indicator.geometry())
            self._anim.setEndValue(self._current_geometry())
            self._anim.start()
        else:
            self._indicator.setGeometry(self._current_geometry())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._indicator.lower()
        self._indicator.setGeometry(self._current_geometry())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        h = self.height()

        border = QPen(QColor(self._theme.outline))
        border.setWidthF(1.0)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), h / 2, h / 2)

        # Разделители между невыбранными сегментами.
        div = QPen(QColor(self._theme.outline))
        div.setWidthF(1.0)
        painter.setPen(div)
        for i in range(1, len(self._buttons)):
            if i == self._current or i - 1 == self._current:
                continue
            x = self._buttons[i].geometry().left()
            painter.drawLine(x, 12, x, h - 12)
        painter.end()

    def currentIndex(self) -> int:
        return self._current


# ---------------------------------------------------------------------------
# Зона drag & drop: пунктирная рамка, подсветка при перетаскивании
# ---------------------------------------------------------------------------

class DropGlyph(QWidget):
    """Иконка загрузки: мягко растёт и окрашивается в primary при наведении/перетаскивании."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._level = 0.0
        self.setFixedSize(38, 38)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._anim = QPropertyAnimation(self, b"level", self)
        self._anim.setDuration(DUR_FAST)
        self._anim.setEasingCurve(EASE)

    def get_level(self) -> float:
        return self._level

    def set_level(self, value: float) -> None:
        self._level = value
        self.update()

    level = pyqtProperty(float, fget=get_level, fset=set_level)

    def set_target(self, target: float) -> None:
        animate_property(self._anim, self._level, target, DUR_FAST, EASE)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        level = max(0.0, min(1.0, self._level))
        cx, cy = self.width() / 2, self.height() / 2

        halo = QColor(self._theme.primary)
        halo.setAlphaF(0.10 * level)
        if halo.alphaF() > 0.004:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(QPointF(cx, cy), 16.0 + 2.0 * level, 16.0 + 2.0 * level)

        color = lerp_color(
            QColor(self._theme.on_surface_variant), QColor(self._theme.primary), level
        )
        pen = QPen(color)
        pen.setWidthF(1.9)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        s = 1.0 + 0.08 * level

        def px(dx: float) -> int:
            return round(cx + dx * s)

        def py(dy: float) -> int:
            return round(cy + dy * s)

        painter.drawLine(px(0), py(-9), px(0), py(2))
        painter.drawLine(px(-4), py(-2), px(0), py(2))
        painter.drawLine(px(0), py(2), px(4), py(-2))
        painter.drawLine(px(-8), py(5), px(-8), py(9))
        painter.drawLine(px(-8), py(9), px(8), py(9))
        painter.drawLine(px(8), py(9), px(8), py(5))
        painter.end()


class FileDropArea(QFrame):
    dropped = pyqtSignal(list)

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._hovered = False
        self._dragging = False
        self._glow = 0.0
        self._press = 0.0
        self.setObjectName("DropZone")
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QFrame#DropZone { background: transparent; border: none; }")

        self._glyph = DropGlyph(theme, self)
        self._glow_anim = QPropertyAnimation(self, b"glow", self)
        self._glow_anim.setDuration(DUR_FAST)
        self._glow_anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)
        layout.addWidget(self._glyph, 0, Qt.AlignmentFlag.AlignHCenter)

        caption = QLabel("Перетащите файлы сюда")
        caption.setObjectName("DropCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setFont(system_font(16, QFont.Weight.Medium))
        caption.setStyleSheet(
            f"color: {theme.on_surface}; border: none; background: transparent;"
        )
        hint = QLabel("или нажмите, чтобы выбрать")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setFont(system_font(12))
        hint.setStyleSheet(
            f"color: {theme.on_surface_variant}; border: none; background: transparent;"
        )
        for label in (caption, hint):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(caption)
        layout.addWidget(hint)

    def get_glow(self) -> float:
        return self._glow

    def set_glow(self, value: float) -> None:
        self._glow = value
        self.update()

    glow = pyqtProperty(float, fget=get_glow, fset=set_glow)

    def get_press(self) -> float:
        return self._press

    def set_press(self, value: float) -> None:
        self._press = value
        self.update()

    press = pyqtProperty(float, fget=get_press, fset=set_press)

    def _target_glow(self) -> float:
        return 1.0 if (self._hovered or self._dragging) else 0.0

    def _apply_glow(self) -> None:
        target = self._target_glow()
        animate_property(self._glow_anim, self._glow, target, DUR_FAST, EASE)
        self._glyph.set_target(target)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_glow()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_glow()
        super().leaveEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._dragging = True
            self._apply_glow()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._dragging = False
        self._apply_glow()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._dragging = False
        self._apply_glow()
        files = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if files:
            self.dropped.emit(files)
            event.acceptProposedAction()
        else:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
            paths, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы")
            if paths:
                self.dropped.emit(paths)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self._theme
        g = max(0.0, min(1.0, self._glow))
        p = max(0.0, min(1.0, self._press))
        inset = 1.2 + 1.6 * p
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.surface_container_low))
        painter.drawRoundedRect(rect, 16, 16)

        if g > 0.01 or p > 0.01:
            overlay = QColor(theme.primary_container)
            overlay.setAlpha(round(60 * g + 20 * p))
            painter.setBrush(overlay)
            painter.drawRoundedRect(rect, 16, 16)

        border = lerp_color(QColor(theme.outline_variant), QColor(theme.primary), g)
        pen = QPen(border)
        pen.setWidthF(2.0)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([4.0, 3.5])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 15, 15)
        painter.end()


# ---------------------------------------------------------------------------
# Кнопки окна и переключатель панели навигации
# ---------------------------------------------------------------------------

class WindowButton(QPushButton):
    """Material-кнопка окна 40x40: minimize / maximize / close."""

    def __init__(self, theme: Theme, symbol: str, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._symbol = symbol  # "minimize" | "maximize" | "close"
        self._hover = 0.0
        self._press = 0.0
        self._maximized = False
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(DUR_FAST)
        self._anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)

    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    hover = pyqtProperty(float, fget=get_hover, fset=set_hover)

    def get_press(self) -> float:
        return self._press

    def set_press(self, value: float) -> None:
        self._press = value
        self.update()

    press = pyqtProperty(float, fget=get_press, fset=set_press)

    def set_maximized(self, maximized: bool) -> None:
        if self._maximized != maximized:
            self._maximized = maximized
            self.update()

    def enterEvent(self, event):
        animate_property(self._anim, self._hover, 1.0, DUR_FAST, EASE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate_property(self._anim, self._hover, 0.0, DUR_FAST, EASE)
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self._theme
        cx, cy = self.width() // 2, self.height() // 2
        h, p = self._hover, self._press

        painter.setPen(Qt.PenStyle.NoPen)
        if self._symbol == "close":
            bg = QColor(theme.error)
            bg.setAlphaF(min(1.0, h + 0.12 * p))
            if bg.alphaF() > 0.004:
                painter.setBrush(bg)
                painter.drawEllipse(QPointF(cx, cy), 20.0, 20.0)
            glyph = lerp_color(QColor(theme.on_surface_variant), QColor(theme.on_error), h)
        else:
            layer = QColor(theme.on_surface)
            layer.setAlphaF(min(1.0, 0.08 * h + 0.04 * p))
            if layer.alphaF() > 0.004:
                painter.setBrush(layer)
                painter.drawEllipse(QPointF(cx, cy), 20.0, 20.0)
            glyph = lerp_color(QColor(theme.on_surface_variant), QColor(theme.on_surface), h)

        pen = QPen(glyph)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._symbol == "close":
            painter.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
            painter.drawLine(cx + 5, cy - 5, cx - 5, cy + 5)
        elif self._symbol == "minimize":
            painter.drawLine(cx - 6, cy + 2, cx + 6, cy + 2)
        elif self._symbol == "maximize":
            if self._maximized:
                painter.drawRoundedRect(QRectF(cx - 6, cy - 3, 11, 11), 1.5, 1.5)
                painter.drawLine(cx - 2, cy - 6, cx + 6, cy - 6)
                painter.drawLine(cx + 6, cy - 6, cx + 6, cy + 2)
            else:
                painter.drawRoundedRect(QRectF(cx - 6, cy - 6, 12, 12), 1.5, 1.5)
        painter.end()
        super().paintEvent(event)


class SidebarToggle(QPushButton):
    """Material icon button: panel-left-close / panel-left-open."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._hover = 0.0
        self._press = 0.0
        self._collapsed = False
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(DUR_FAST)
        self._anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)

    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    hover = pyqtProperty(float, fget=get_hover, fset=set_hover)

    def get_press(self) -> float:
        return self._press

    def set_press(self, value: float) -> None:
        self._press = value
        self.update()

    press = pyqtProperty(float, fget=get_press, fset=set_press)

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed != collapsed:
            self._collapsed = collapsed
            self.update()

    def enterEvent(self, event):
        animate_property(self._anim, self._hover, 1.0, DUR_FAST, EASE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate_property(self._anim, self._hover, 0.0, DUR_FAST, EASE)
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self._theme
        cx, cy = self.width() // 2, self.height() // 2

        layer = QColor(theme.on_surface)
        layer.setAlphaF(min(1.0, 0.08 * self._hover + 0.04 * self._press))
        if layer.alphaF() > 0.004:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(layer)
            painter.drawEllipse(QPointF(cx, cy), 20.0, 20.0)

        glyph = lerp_color(QColor(theme.on_surface_variant), QColor(theme.on_surface),
                           self._hover)
        pen = QPen(glyph)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(QRectF(cx - 8, cy - 8, 16, 16), 2, 2)
        if self._collapsed:
            painter.drawLine(cx + 2, cy - 6, cx + 2, cy + 6)
        else:
            painter.drawLine(cx - 2, cy - 6, cx - 2, cy + 6)
            painter.drawLine(cx + 5, cy - 2, cx + 1, cy)
            painter.drawLine(cx + 1, cy, cx + 5, cy + 2)
        painter.end()


class TopAppBar(QWidget):
    def __init__(self, theme: Theme, window: QMainWindow, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("TopAppBar")
        self.setFixedHeight(56)
        self._window = window

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        nav_btn = SidebarToggle(theme)
        nav_btn.setToolTip("Свернуть/развернуть панель навигации")
        nav_btn.set_collapsed(getattr(self._window, "_sidebar_collapsed", False))
        nav_btn.clicked.connect(self._window.toggle_sidebar)
        self.sidebar_toggle = nav_btn

        title = QLabel("МойПроект")
        title.setFont(system_font(18, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {theme.on_surface};")

        layout.addWidget(nav_btn)
        layout.addWidget(title)
        layout.addStretch(1)

        min_btn = WindowButton(theme, "minimize")
        max_btn = WindowButton(theme, "maximize")
        close_btn = WindowButton(theme, "close")
        min_btn.setToolTip("Свернуть")
        max_btn.setToolTip("Развернуть/восстановить")
        close_btn.setToolTip("Закрыть")
        self._max_btn = max_btn
        min_btn.clicked.connect(self._window.showMinimized)
        max_btn.clicked.connect(self._toggle_maximize)
        close_btn.clicked.connect(self._window.close)

        layout.addWidget(min_btn)
        layout.addWidget(max_btn)
        layout.addWidget(close_btn)

        self._window.installEventFilter(self)
        self._sync_max_state()

    def _sync_max_state(self) -> None:
        self._max_btn.set_maximized(self._window.isMaximized())

    def eventFilter(self, obj, event):
        if obj is self._window and event.type() == QEvent.Type.WindowStateChange:
            self._sync_max_state()
        return super().eventFilter(obj, event)

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self._sync_max_state()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._toggle_maximize()
        super().mouseDoubleClickEvent(event)


# ---------------------------------------------------------------------------
# NavigationDrawer с анимированным pill-индикатором
# ---------------------------------------------------------------------------

class NavButton(QPushButton):
    """Пункт навигации MD3: иконка + текст, state layer поверх индикатора."""

    def __init__(self, text: str, theme: Theme, icon: str, parent=None):
        super().__init__(text, parent)
        self._theme = theme
        self._icon = icon
        self._hover = 0.0
        self._press = 0.0
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setFlat(True)
        self.setFont(system_font(14))
        self.setFixedHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover_anim = QPropertyAnimation(self, b"hover", self)
        self._hover_anim.setDuration(DUR_FAST)
        self._hover_anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)

    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    hover = pyqtProperty(float, fget=get_hover, fset=set_hover)

    def get_press(self) -> float:
        return self._press

    def set_press(self, value: float) -> None:
        self._press = value
        self.update()

    press = pyqtProperty(float, fget=get_press, fset=set_press)

    def enterEvent(self, event):
        animate_property(self._hover_anim, self._hover, 1.0, DUR_FAST, EASE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate_property(self._hover_anim, self._hover, 0.0, DUR_FAST, EASE)
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().mouseReleaseEvent(event)

    def nextCheckState(self) -> None:
        # Клик по уже выбранному пункту — no-op: выделение не снимается
        # (стандартный toggle QPushButton иначе гасит checked-состояние).
        if not self.isChecked():
            self.setChecked(True)

    def _draw_icon(self, painter: QPainter, color: QColor) -> None:
        theme = self._theme
        pen = QPen(color)
        pen.setWidthF(1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        x0 = 16.0
        y0 = (self.height() - 20) / 2.0

        def X(dx: float) -> int:
            return round(x0 + dx)

        def Y(dy: float) -> int:
            return round(y0 + dy)

        kind = self._icon
        if kind == "dashboard":
            for dx, dy in ((1, 1), (11, 1), (1, 11), (11, 11)):
                painter.drawRoundedRect(QRectF(x0 + dx, y0 + dy, 8, 8), 1.5, 1.5)
        elif kind == "tasks":
            painter.drawEllipse(QRectF(x0 + 1, y0 + 1, 18, 18))
            painter.drawLine(X(6), Y(10), X(9), Y(13))
            painter.drawLine(X(9), Y(13), X(14), Y(7))
        elif kind == "edit":
            path = QPainterPath(QPointF(x0 + 3, y0 + 17))
            path.lineTo(x0 + 3, y0 + 14)
            path.lineTo(x0 + 13, y0 + 4)
            path.lineTo(x0 + 16, y0 + 7)
            path.lineTo(x0 + 6, y0 + 17)
            path.closeSubpath()
            painter.drawPath(path)
        elif kind == "chat":
            painter.drawRoundedRect(QRectF(x0 + 2, y0 + 3, 16, 12), 3, 3)
            tail = QPainterPath(QPointF(x0 + 6, y0 + 15))
            tail.lineTo(x0 + 6, y0 + 19)
            tail.lineTo(x0 + 10, y0 + 15)
            painter.drawPath(tail)
        elif kind == "folder":
            path = QPainterPath(QPointF(x0 + 2, y0 + 6))
            path.lineTo(x0 + 8, y0 + 6)
            path.lineTo(x0 + 10, y0 + 8)
            path.lineTo(x0 + 18, y0 + 8)
            path.lineTo(x0 + 18, y0 + 16)
            path.lineTo(x0 + 2, y0 + 16)
            path.closeSubpath()
            painter.drawPath(path)
        elif kind == "tune":
            for dy in (5, 10, 15):
                painter.drawLine(X(2), Y(dy), X(18), Y(dy))
            knob = QColor(theme.secondary_container if self.isChecked()
                          else theme.surface_container_low)
            painter.setBrush(knob)
            for dx, dy in ((13, 5), (7, 10), (15, 15)):
                painter.drawEllipse(QPointF(x0 + dx, y0 + dy), 2.6, 2.6)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self._theme
        rect = QRectF(self.rect())
        radius = rect.height() / 2

        if self.isChecked():
            if self._hover > 0.01 or self._press > 0.01:
                overlay = QColor(theme.on_secondary_container)
                overlay.setAlphaF(min(1.0, 0.08 * self._hover + 0.04 * self._press))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(overlay)
                painter.drawRoundedRect(rect, radius, radius)
            icon_color = QColor(theme.on_secondary_container)
        else:
            if self._hover > 0.01 or self._press > 0.01:
                overlay = QColor(theme.on_surface)
                overlay.setAlphaF(min(1.0, 0.08 * self._hover + 0.04 * self._press))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(overlay)
                painter.drawRoundedRect(rect, radius, radius)
            icon_color = lerp_color(QColor(theme.on_surface_variant),
                                    QColor(theme.on_surface), self._hover)
        self._draw_icon(painter, icon_color)
        painter.end()
        super().paintEvent(event)


class NavigationDrawer(QWidget):
    def __init__(self, theme: Theme, pages: list[str], on_select, current: int = 0, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("NavigationDrawer")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.on_select = on_select
        self._current = current
        self._buttons: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        section = QLabel("Навигация")
        section.setFont(system_font(12, QFont.Weight.Medium))
        section.setStyleSheet(
            f"color: {theme.on_surface_variant}; padding: 8px 16px; background: transparent;"
        )
        layout.addWidget(section)

        self.indicator = QFrame(self)
        self.indicator.setObjectName("Indicator")
        self.indicator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        icons = ("dashboard", "tasks", "edit", "chat", "folder", "tune")
        for i, name in enumerate(pages):
            btn = NavButton(name, theme, icons[i % len(icons)])
            btn.setChecked(i == current)
            if i == current:
                btn.setFont(system_font(14, QFont.Weight.Medium))
            btn.clicked.connect(lambda _checked, idx=i: self._handle_click(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch(1)
        self.indicator.lower()

        self._anim = QPropertyAnimation(self.indicator, b"geometry", self)
        self._anim.setDuration(DUR_MED)
        self._anim.setEasingCurve(EASE)

    def _handle_click(self, idx: int) -> None:
        if idx == self._current:
            return
        self._current = idx
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == idx)
            btn.setFont(system_font(14, QFont.Weight.Medium if i == idx else QFont.Weight.Normal))
        self._move_indicator(animate=True)
        self.on_select(idx)

    def _move_indicator(self, animate: bool) -> None:
        target = self._buttons[self._current].geometry()
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self.indicator.geometry())
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self.indicator.setGeometry(target)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._move_indicator(animate=False)


# ---------------------------------------------------------------------------
# Общий QSS-шаблон
# ---------------------------------------------------------------------------

def build_stylesheet(theme: Theme) -> str:
    return f"""
        #Panel {{
            background-color: {theme.surface};
            border-radius: {RADIUS_WINDOW}px;
        }}
        #TopAppBar {{
            background-color: transparent;
        }}
        #NavigationDrawer {{
            background-color: {theme.surface_container_low};
            border-bottom-left-radius: {RADIUS_WINDOW}px;
        }}
        #Indicator {{
            background-color: {theme.secondary_container};
            border-radius: 24px;
        }}
        QPushButton#NavButton {{
            text-align: left;
            border: none;
            border-radius: 24px;
            padding-left: 48px;
            color: {theme.on_surface_variant};
            background: transparent;
        }}
        QPushButton#NavButton:checked {{
            color: {theme.on_secondary_container};
        }}
        QScrollBar:vertical {{
            width: 8px; margin: 2px; background: transparent;
        }}
        QScrollBar::handle:vertical {{
            background: {rgba(theme.outline_variant, 120)};
            border-radius: 4px; min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {theme.outline};
        }}
        QScrollBar:horizontal {{
            height: 8px; margin: 2px; background: transparent;
        }}
        QScrollBar::handle:horizontal {{
            background: {rgba(theme.outline_variant, 120)};
            border-radius: 4px; min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {theme.outline};
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0; height: 0; background: transparent;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: transparent;
        }}
        QToolTip {{
            background-color: {theme.surface_container_high};
            color: {theme.on_surface};
            border: 1px solid {theme.outline_variant};
            border-radius: 4px; padding: 4px 8px;
        }}
    """


# ---------------------------------------------------------------------------
# Главное окно
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.theme = LIGHT
        self._current_page = 0
        self._page_anim = None
        self._seg_anim = None
        self._progress_anim = None
        self._theme_anim = None
        self._sidebar_anim = None
        self._sidebar_collapsed = False
        self._sidebar = None
        self._sidebar_sep = None
        self._title_bar = None
        self._chat_messages: list[tuple[str, bool, str]] | None = None
        self._chat_msgs_layout = None
        self._chat_scroll = None
        self._chat_input_edit = None
        self._chat_typing = False
        self._chat_typing_label = None
        self._reply_i = 0
        self._dropped_files: list[str] = []

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(760, 480)
        self.resize(960, 600)

        self.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)

        self._build_ui()

    def _apply_palette(self, theme: Theme) -> None:
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(theme.surface))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(theme.on_surface))
        pal.setColor(QPalette.ColorRole.Base, QColor(theme.surface))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.surface_container))
        pal.setColor(QPalette.ColorRole.Text, QColor(theme.on_surface))
        pal.setColor(QPalette.ColorRole.Button, QColor(theme.surface_container))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(theme.on_surface))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(theme.primary))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.on_primary))
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.on_surface_variant))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.surface_container_high))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.on_surface))
        self.setPalette(pal)

    def _build_ui(self) -> None:
        theme = self.theme

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)

        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel_shadow = QGraphicsDropShadowEffect(panel)
        panel_shadow.setBlurRadius(24)
        panel_shadow.setOffset(0, 4)
        panel_shadow.setColor(shadow_color(theme))
        panel.setGraphicsEffect(panel_shadow)
        root_layout.addWidget(panel)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        title_bar = TopAppBar(theme, self)
        self._title_bar = title_bar
        panel_layout.addWidget(title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        panel_layout.addWidget(body)

        sidebar = NavigationDrawer(theme, PAGES, on_select=self.switch_page,
                                   current=self._current_page)
        self._sidebar = sidebar
        body_layout.addWidget(sidebar)
        separator = self._build_separator(theme)
        self._sidebar_sep = separator
        body_layout.addWidget(separator)

        if self._sidebar_collapsed:
            sidebar.setFixedWidth(0)
            separator.setFixedWidth(0)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        for name in PAGES:
            self.stack.addWidget(self._build_page(theme, name))
        self.stack.setCurrentIndex(self._current_page)
        body_layout.addWidget(self.stack, 1)

        panel.setStyleSheet(build_stylesheet(theme))
        self._apply_palette(theme)

    def _build_separator(self, theme: Theme) -> QFrame:
        line = QFrame()
        line.setFixedWidth(1)
        line.setStyleSheet(f"background-color: {theme.outline_variant};")
        return line

    def toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._animate_sidebar(self._sidebar_collapsed)
        title_bar = getattr(self, "_title_bar", None)
        if title_bar is not None and title_bar.sidebar_toggle is not None:
            title_bar.sidebar_toggle.set_collapsed(self._sidebar_collapsed)

    def _animate_sidebar(self, collapsed: bool) -> None:
        if self._sidebar_anim is not None:
            self._sidebar_anim.stop()
        widgets = [self._sidebar, self._sidebar_sep]
        widths = [SIDEBAR_WIDTH, 1]
        group = QParallelAnimationGroup(self)
        for widget, expanded_width in zip(widgets, widths):
            if widget is None:
                continue
            start = widget.width()
            target = 0 if collapsed else expanded_width
            for prop in (b"minimumWidth", b"maximumWidth"):
                anim = QPropertyAnimation(widget, prop, self)
                anim.setDuration(DUR_MED)
                anim.setEasingCurve(EASE)
                anim.setStartValue(start)
                anim.setEndValue(target)
                group.addAnimation(anim)
        group.finished.connect(self._on_sidebar_anim_finished)
        group.start()
        self._sidebar_anim = group

    def _on_sidebar_anim_finished(self) -> None:
        self._sidebar_anim = None

    def _build_page(self, theme: Theme, name: str) -> QWidget:
        builders = {
            "Задачи": self._build_tasks_page,
            "Ввод": self._build_inputs_page,
            "Чат": self._build_chat_page,
            "Файлы": self._build_files_page,
            "Настройки": self._build_settings_page,
        }
        builder = builders.get(name, self._build_overview_page)
        return builder(theme)

    def _page_shell(self, theme: Theme, name: str):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Контент страницы скроллится, если не влезает в viewport: иначе
        # QBoxLayout сжимает карточки ниже минимума и поля/списки наползают
        # друг на друга, а тень карточки обрезает вылезающих детей.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setStyleSheet("background: transparent;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(name)
        title.setFont(system_font(24))
        title.setStyleSheet(f"color: {theme.on_surface};")
        layout.addWidget(title)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return page, layout

    def _add_card(self, theme: Theme, layout, card_title: str):
        card = QFrame()
        card.setObjectName("Card")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(
            f"#Card {{ background-color: {theme.surface_container_low}; "
            f"border-radius: {RADIUS_CARD}px; }}"
        )
        card_shadow = QGraphicsDropShadowEffect(card)
        card_shadow.setBlurRadius(8)
        card_shadow.setOffset(0, 1)
        card_shadow.setColor(shadow_color(theme))
        card.setGraphicsEffect(card_shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        head = QLabel(card_title)
        head.setFont(system_font(16, QFont.Weight.Medium))
        head.setStyleSheet(f"color: {theme.on_surface};")
        card_layout.addWidget(head)

        layout.addWidget(card)
        return card, card_layout

    def _settings_row(self, theme: Theme, card_layout, label_text: str, control,
                      control_stretch: int = 0) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        lab = QLabel(label_text)
        lab.setFont(system_font(14))
        lab.setStyleSheet(f"color: {theme.on_surface};")
        row.addWidget(lab)
        if control_stretch:
            row.addWidget(control, control_stretch)
        else:
            row.addStretch(1)
            row.addWidget(control)
        card_layout.addLayout(row)

    def _make_slider(self, theme: Theme, value: int, minimum: int = 0, maximum: int = 100):
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        holder.setFixedHeight(28)
        holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        slider = MdSlider(theme, value, minimum, maximum)
        slider.setMinimumWidth(140)

        value_label = QLabel(str(value))
        value_label.setFixedWidth(34)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_label.setFont(system_font(12))
        value_label.setStyleSheet(f"color: {theme.on_surface_variant};")

        slider.valueChanged.connect(lambda v, lab=value_label: lab.setText(str(v)))

        row.addWidget(slider, 1)
        row.addWidget(value_label)
        return slider, holder

    def _toggle_row(self, theme: Theme, card_layout, label_text: str, checked: bool = False,
                    on_toggled=None) -> MdSwitch:
        toggle = MdSwitch(theme, checked=checked)
        if on_toggled is not None:
            toggle.toggled.connect(on_toggled)
        self._settings_row(theme, card_layout, label_text, toggle)
        return toggle

    def _make_line_edit(self, theme: Theme, placeholder: str = "",
                        password: bool = False, pill: bool = False) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFont(system_font(14))
        edit.setFixedHeight(44)
        edit.setCursor(Qt.CursorShape.IBeamCursor)
        if password:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        if pill:
            edit.setStyleSheet(
                f"QLineEdit {{ background-color: {theme.surface_container_high}; "
                f"border: none; border-radius: 22px; padding: 4px 16px; "
                f"color: {theme.on_surface}; "
                f"selection-background-color: {theme.primary}; "
                f"selection-color: {theme.on_primary}; }}"
                f"QLineEdit:hover {{ background-color: {theme.surface_container_highest}; }}"
                f"QLineEdit:focus {{ background-color: {theme.surface_container_highest}; }}"
            )
        else:
            edit.setStyleSheet(
                f"QLineEdit {{ background: transparent; border: 1px solid {theme.outline}; "
                f"border-radius: {RADIUS_FIELD}px; padding: 4px 12px; "
                f"color: {theme.on_surface}; "
                f"selection-background-color: {theme.primary}; "
                f"selection-color: {theme.on_primary}; }}"
                f"QLineEdit:hover {{ border-color: {theme.on_surface_variant}; }}"
                f"QLineEdit:focus {{ border: 2px solid {theme.primary}; }}"
            )
        pal = edit.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.on_surface_variant))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(theme.primary))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.on_primary))
        edit.setPalette(pal)
        return edit

    def _field_icon(self, theme: Theme, kind: str, size: int = 18) -> QIcon:
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon = None
        pen = QPen(QColor(theme.on_surface_variant))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if kind == "search":
            painter.setPen(pen)
            painter.drawEllipse(QRectF(size * 0.22, size * 0.22, size * 0.44, size * 0.44))
            painter.drawLine(int(size * 0.62), int(size * 0.62),
                             int(size * 0.85), int(size * 0.85))
        elif kind == "clear":
            painter.setPen(pen)
            painter.drawLine(int(size * 0.30), int(size * 0.30),
                             int(size * 0.70), int(size * 0.70))
            painter.drawLine(int(size * 0.70), int(size * 0.30),
                             int(size * 0.30), int(size * 0.70))
        elif kind == "eye":
            icon = self._svg_icon(SVG_EYE, size)
        elif kind == "eye_slash":
            icon = self._svg_icon(SVG_EYE_SLASH, size)
        painter.end()
        return icon if icon is not None else QIcon(pm)

    def _svg_icon(self, svg: str, size: int) -> QIcon:
        # QSvgRenderer игнорирует currentColor — подставляем роль строкой до рендера.
        source = svg.replace("currentColor", self.theme.on_surface_variant)
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(source.encode("utf-8"))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return QIcon(pm)

    def _build_search_field(self, theme: Theme) -> QLineEdit:
        edit = self._make_line_edit(theme, "Поиск по проекту…", pill=True)
        edit.addAction(self._field_icon(theme, "search"),
                       QLineEdit.ActionPosition.LeadingPosition)
        clear_action = edit.addAction(self._field_icon(theme, "clear"),
                                      QLineEdit.ActionPosition.TrailingPosition)
        clear_action.setVisible(False)
        clear_action.triggered.connect(edit.clear)
        edit.textChanged.connect(
            lambda _t: clear_action.setVisible(bool(edit.text().strip()))
        )
        return edit

    def _build_password_field(self, theme: Theme) -> QLineEdit:
        edit = self._make_line_edit(theme, "Введите пароль", password=True)
        eye = self._field_icon(theme, "eye")
        eye_slash = self._field_icon(theme, "eye_slash")
        action = edit.addAction(eye, QLineEdit.ActionPosition.TrailingPosition)

        def toggle_visibility() -> None:
            show = edit.echoMode() == QLineEdit.EchoMode.Password
            edit.setEchoMode(QLineEdit.EchoMode.Normal if show
                             else QLineEdit.EchoMode.Password)
            action.setIcon(eye_slash if show else eye)

        action.triggered.connect(toggle_visibility)
        return edit

    def _labeled_field(self, theme: Theme, label_text: str, edit: QLineEdit) -> QWidget:
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        lab = QLabel(label_text)
        lab.setFont(system_font(12))
        lab.setStyleSheet(f"color: {theme.on_surface_variant};")
        col.addWidget(lab)
        col.addWidget(edit)
        return holder

    def _build_inputs_page(self, theme: Theme) -> QWidget:
        page, layout = self._page_shell(theme, "Ввод")

        _, card_layout = self._add_card(theme, layout, "Текстовые поля")
        card_layout.addWidget(self._labeled_field(
            theme, "Имя", self._make_line_edit(theme, "Например, Анастасия")))
        card_layout.addWidget(self._labeled_field(
            theme, "E-mail", self._make_line_edit(theme, "you@example.com")))
        card_layout.addWidget(self._labeled_field(
            theme, "Пароль", self._build_password_field(theme)))
        card_layout.addWidget(self._labeled_field(
            theme, "Поиск", self._build_search_field(theme)))

        _, card_layout = self._add_card(theme, layout, "Многострочный ввод")
        area = QTextEdit()
        area.setPlaceholderText("Введите комментарий…")
        area.setFont(system_font(14))
        area.setFixedHeight(110)
        area.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: 1px solid {theme.outline}; "
            f"border-radius: {RADIUS_FIELD}px; padding: 8px; color: {theme.on_surface}; "
            f"selection-background-color: {theme.primary}; "
            f"selection-color: {theme.on_primary}; }}"
            f"QTextEdit:hover {{ border-color: {theme.on_surface_variant}; }}"
            f"QTextEdit:focus {{ border: 2px solid {theme.primary}; }}"
        )
        pal = area.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.on_surface_variant))
        area.setPalette(pal)
        card_layout.addWidget(area)

        char_label = QLabel("0 символов")
        char_label.setFont(system_font(12))
        char_label.setStyleSheet(f"color: {theme.on_surface_variant};")
        char_row = QHBoxLayout()
        char_row.addStretch(1)
        char_row.addWidget(char_label)
        card_layout.addLayout(char_row)
        area.textChanged.connect(
            lambda: char_label.setText(f"{len(area.toPlainText())} символов")
        )

        layout.addStretch(1)
        return page

    def _build_chat_page(self, theme: Theme) -> QWidget:
        page, layout = self._page_shell(theme, "Чат")

        container = QScrollArea()
        container.setWidgetResizable(True)
        container.setFrameShape(QFrame.Shape.NoFrame)
        container.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        container.viewport().setStyleSheet("background: transparent;")

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        msgs = QVBoxLayout(body)
        msgs.setContentsMargins(8, 8, 8, 8)
        msgs.setSpacing(10)
        msgs.addStretch(1)
        container.setWidget(body)
        layout.addWidget(container, 1)

        self._chat_msgs_layout = msgs
        self._chat_scroll = container

        if self._chat_messages is None:
            now = time.strftime("%H:%M")
            self._chat_messages = [
                ("Привет! Добро пожаловать в чат.", False, now),
                ("Попробуй отправить сообщение — я отвечу.", False, now),
            ]
        for msg in self._chat_messages:
            text, mine, ts = msg if len(msg) == 3 else (msg[0], msg[1], "")
            self._insert_chat_bubble(theme, text, mine, ts)

        typing_label = QLabel("печатает…")
        typing_label.setFont(system_font(12))
        typing_label.setStyleSheet(
            f"color: {theme.on_surface_variant}; background: transparent;"
        )
        typing_label.setVisible(self._chat_typing)
        self._chat_typing_label = typing_label
        typing_row = QHBoxLayout()
        typing_row.addStretch(1)
        typing_row.addWidget(typing_label)
        layout.addLayout(typing_row)

        input_row = QHBoxLayout()
        input_row.setSpacing(12)
        edit = self._make_line_edit(theme, "Напишите сообщение…")
        edit.returnPressed.connect(self._on_chat_send)
        send = MdButton("Отправить", theme)
        send.clicked.connect(self._on_chat_send)
        self._chat_input_edit = edit
        input_row.addWidget(edit, 1)
        input_row.addWidget(send)
        layout.addLayout(input_row)

        QTimer.singleShot(0, self._chat_scroll_to_bottom)
        return page

    def _make_message_widget(self, theme: Theme, text: str, mine: bool,
                             ts: str) -> QWidget:
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        box = QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)

        bubble = self._make_chat_bubble(theme, text, mine)
        brow = QHBoxLayout()
        brow.setSpacing(0)
        if mine:
            brow.addStretch(1)
            brow.addWidget(bubble)
        else:
            brow.addWidget(bubble)
            brow.addStretch(1)
        box.addLayout(brow)

        if ts:
            trow = QHBoxLayout()
            trow.setSpacing(0)
            stamp = QLabel(ts)
            stamp.setFont(system_font(11))
            stamp.setStyleSheet(
                f"color: {theme.on_surface_variant}; background: transparent; padding: 0 4px;"
            )
            if mine:
                trow.addStretch(1)
                trow.addWidget(stamp)
            else:
                trow.addWidget(stamp)
                trow.addStretch(1)
            box.addLayout(trow)
        return holder

    def _insert_chat_bubble(self, theme: Theme, text: str, mine: bool,
                            ts: str = "") -> None:
        lay = getattr(self, "_chat_msgs_layout", None)
        if lay is None:
            return
        widget = self._make_message_widget(theme, text, mine, ts)
        lay.insertWidget(lay.count() - 1, widget)

        # Анимируем только «живую» вставку. При пересборке страницы история
        # восстанавливается без вспышек, а эффект не вкладывается в fade страницы.
        scroll = getattr(self, "_chat_scroll", None)
        if scroll is None or not scroll.isVisible():
            return

        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(EASE)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        widget._entrance_anim = anim
        anim.start()

    def _make_chat_bubble(self, theme: Theme, text: str, mine: bool) -> QFrame:
        bubble = QFrame()
        bubble.setObjectName("Bubble")
        bubble.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bubble.setMaximumWidth(430)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setFont(system_font(14))
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # Без минимальной ширины wordWrap-QLabel отдаёт layout'у узкий sizeHint,
        # и пузырь ломается на лишние строки. Ширина по контенту, максимум 430.
        fm = QFontMetricsF(label.font())
        bubble.setMinimumWidth(int(min(430.0, fm.horizontalAdvance(text) + 32.0)))

        lay = QHBoxLayout(bubble)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.addWidget(label)

        if mine:
            tl, tr, bl, br = 16, 16, 16, 4
            bg = theme.primary_container
            fg = theme.on_primary_container
        else:
            tl, tr, bl, br = 16, 16, 4, 16
            bg = theme.surface_container_high
            fg = theme.on_surface
        bubble.setStyleSheet(
            f"QFrame#Bubble {{ background-color: {bg}; border: none; "
            f"border-top-left-radius: {tl}px; border-top-right-radius: {tr}px; "
            f"border-bottom-left-radius: {bl}px; border-bottom-right-radius: {br}px; }}"
            f"QFrame#Bubble QLabel {{ color: {fg}; border: none; "
            f"background: transparent; }}"
        )
        return bubble

    def _chat_scroll_to_bottom(self) -> None:
        scroll = getattr(self, "_chat_scroll", None)
        if scroll is None:
            return
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _on_chat_send(self) -> None:
        edit = getattr(self, "_chat_input_edit", None)
        if edit is None:
            return
        text = edit.text().strip()
        if not text:
            return
        edit.clear()
        now = time.strftime("%H:%M")
        self._chat_messages.append((text, True, now))
        self._insert_chat_bubble(self.theme, text, True, now)
        self._schedule_chat_reply()
        self._chat_scroll_to_bottom()

    def _schedule_chat_reply(self) -> None:
        self._chat_typing = True
        label = getattr(self, "_chat_typing_label", None)
        if label is not None:
            label.setVisible(True)
        reply = REPLIES[self._reply_i % len(REPLIES)]
        self._reply_i += 1
        delay = 700 + (self._reply_i % 3) * 400
        QTimer.singleShot(delay, lambda: self._append_chat_reply(reply))

    def _append_chat_reply(self, text: str) -> None:
        self._chat_typing = False
        label = getattr(self, "_chat_typing_label", None)
        if label is not None:
            label.setVisible(False)
        now = time.strftime("%H:%M")
        self._chat_messages.append((text, False, now))
        self._insert_chat_bubble(self.theme, text, False, now)
        self._chat_scroll_to_bottom()

    def _list_style(self, theme: Theme) -> str:
        return (
            f"QListWidget {{ background: transparent; border: none; color: {theme.on_surface}; "
            f"outline: none; }}"
            f"QListWidget::item {{ padding: 10px 12px; border-radius: 8px; }}"
            f"QListWidget::item:hover {{ background-color: {theme.surface_container_high}; }}"
            f"QListWidget::item:selected {{ background-color: {theme.secondary_container}; "
            f"color: {theme.on_secondary_container}; }}"
        )

    def _build_files_page(self, theme: Theme) -> QWidget:
        page, layout = self._page_shell(theme, "Файлы")

        _, card_layout = self._add_card(theme, layout, "Загрузка")
        drop = FileDropArea(theme)
        card_layout.addWidget(drop)

        drop_list = QListWidget()
        drop_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        drop_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        drop_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        drop_list.setFixedHeight(110)
        drop_list.setStyleSheet(self._list_style(theme))
        card_layout.addWidget(drop_list)

        count_label = QLabel()
        count_label.setFont(system_font(12))
        count_label.setStyleSheet(f"color: {theme.on_surface_variant};")
        card_layout.addWidget(count_label)

        self._refresh_files_list(drop_list, count_label, theme)
        drop.dropped.connect(
            lambda files, lw=drop_list, cl=count_label:
            self._on_files_dropped(files, lw, cl, theme)
        )

        _, card_layout = self._add_card(theme, layout, "Переупорядочивание")
        hint = QLabel("Перетаскивайте строки списка, чтобы изменить порядок.")
        hint.setFont(system_font(12))
        hint.setStyleSheet(f"color: {theme.on_surface_variant};")
        card_layout.addWidget(hint)

        drag_list = QListWidget()
        drag_list.addItems([
            "Отчёт_Q3.pdf", "Макет_дома.png", "Демо-ролик.mp4",
            "Смета.xlsx", "Логотип.svg",
        ])
        drag_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        drag_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        drag_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        drag_list.setFixedHeight(150)
        drag_list.setStyleSheet(self._list_style(theme))
        card_layout.addWidget(drag_list)

        layout.addStretch(1)
        return page

    def _on_files_dropped(self, files, list_widget, count_label, theme: Theme) -> None:
        for path in files:
            name = Path(path).name
            if name not in self._dropped_files:
                self._dropped_files.append(name)
        self._refresh_files_list(list_widget, count_label, theme)

    def _refresh_files_list(self, list_widget, count_label, theme: Theme) -> None:
        list_widget.clear()
        list_widget.addItems(self._dropped_files)
        n = len(self._dropped_files)
        # Пустой прозрачный список оставлял бы мёртвую зону в карточке.
        list_widget.setVisible(n > 0)
        if n == 0:
            count_label.setText("Пока нет файлов — перетащите что-нибудь в область выше")
        else:
            word = "файл" if n == 1 else ("файла" if n < 5 else "файлов")
            count_label.setText(f"{n} {word}")

    def _build_overview_page(self, theme: Theme) -> QWidget:
        page, layout = self._page_shell(theme, "Обзор")

        _, card_layout = self._add_card(theme, layout, "Система")
        self._toggle_row(theme, card_layout, "Автозапуск", checked=True)
        self._toggle_row(theme, card_layout, "Уведомления", checked=True)
        self._toggle_row(theme, card_layout, "Энергосбережение")

        _, card_layout = self._add_card(theme, layout, "Отображение")
        brightness_slider, holder = self._make_slider(theme, 70)
        self._settings_row(theme, card_layout, "Яркость", holder, control_stretch=1)
        volume_slider, holder = self._make_slider(theme, 45)
        self._settings_row(theme, card_layout, "Громкость", holder, control_stretch=1)

        layout.addStretch(1)
        return page

    def _build_tasks_page(self, theme: Theme) -> QWidget:
        page, layout = self._page_shell(theme, "Задачи")

        cards = ("Подготовить макет", "Проверить код", "Запустить тесты", "Собрать отчёт")

        def make_progress() -> QProgressBar:
            pb = QProgressBar()
            pb.setRange(0, 100)
            pb.setValue(0)
            pb.setTextVisible(False)
            pb.setFixedHeight(6)
            pb.setStyleSheet(
                f"QProgressBar {{ background-color: {theme.surface_container_highest}; "
                f"border: none; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background-color: {theme.primary}; border-radius: 3px; }}"
            )
            return pb

        _, card_layout = self._add_card(theme, layout, "Активные задачи")
        checkboxes = []
        for text in cards:
            cb = MdCheckBox(text, theme)
            card_layout.addWidget(cb)
            checkboxes.append(cb)

        _, card_layout = self._add_card(theme, layout, "Прогресс")
        progress = make_progress()
        card_layout.addWidget(progress)
        counter = QLabel(f"Выполнено 0 из {len(checkboxes)}")
        counter.setFont(system_font(12))
        counter.setStyleSheet(f"color: {theme.on_surface_variant};")
        card_layout.addWidget(counter)

        def refresh_progress() -> None:
            done = sum(1 for cb in checkboxes if cb.isChecked())
            target = int(done * 100 / len(checkboxes))
            counter.setText(f"Выполнено {done} из {len(checkboxes)}")
            anim = QVariantAnimation(self)
            anim.setStartValue(progress.value())
            anim.setEndValue(target)
            anim.setDuration(280)
            anim.setEasingCurve(EASE)
            anim.valueChanged.connect(lambda v: progress.setValue(int(v)))
            anim.finished.connect(lambda: progress.setValue(target))
            anim.start()
            self._progress_anim = anim

        for cb in checkboxes:
            cb.toggled.connect(refresh_progress)

        reset_btn = MdButton("Сбросить", theme, kind="tonal")
        reset_btn.clicked.connect(lambda: [cb.setChecked(False) for cb in checkboxes])
        reset_row = QHBoxLayout()
        reset_row.addWidget(reset_btn)
        reset_row.addStretch(1)
        card_layout.addLayout(reset_row)

        layout.addStretch(1)
        return page

    def _build_settings_page(self, theme: Theme) -> QWidget:
        page, layout = self._page_shell(theme, "Настройки")

        _, card_layout = self._add_card(theme, layout, "Внешний вид")
        self._toggle_row(theme, card_layout, "Тёмная тема", checked=(theme is DARK),
                         on_toggled=self._on_theme_toggled)

        seg_lab = QLabel("Размер интерфейса")
        seg_lab.setFont(system_font(14))
        seg_lab.setStyleSheet(f"color: {theme.on_surface};")
        card_layout.addWidget(seg_lab)
        seg_row = QHBoxLayout()
        seg_row.addWidget(self._build_segmented(theme, ["Компактный", "Средний", "Крупный"],
                                                default=1))
        seg_row.addStretch(1)
        card_layout.addLayout(seg_row)

        _, card_layout = self._add_card(theme, layout, "Поведение")
        self._toggle_row(theme, card_layout, "Автообновления", checked=True)
        self._toggle_row(theme, card_layout, "Анимации", checked=True)

        combo = QComboBox()
        combo.addItems(["Русский", "English", "Deutsch"])
        combo.setFixedHeight(44)
        combo.setMinimumWidth(180)
        combo.setFont(system_font(14))
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setStyleSheet(
            f"QComboBox {{ background: transparent; border: 1px solid {theme.outline}; "
            f"border-radius: {RADIUS_FIELD}px; padding: 2px 12px; color: {theme.on_surface}; }}"
            f"QComboBox:hover {{ border-color: {theme.on_surface_variant}; }}"
            f"QComboBox:focus {{ border: 2px solid {theme.primary}; }}"
            f"QComboBox::drop-down {{ border: none; width: 28px; }}"
            f"QComboBox::down-arrow {{ image: none; width: 0; height: 0; "
            f"border-left: 4px solid transparent; border-right: 4px solid transparent; "
            f"border-top: 5px solid {theme.on_surface_variant}; margin-right: 10px; }}"
            f"QComboBox QAbstractItemView {{ background-color: {theme.surface_container}; "
            f"color: {theme.on_surface}; border: 1px solid {theme.outline_variant}; "
            f"border-radius: {RADIUS_MENU}px; "
            f"selection-background-color: {theme.secondary_container}; "
            f"selection-color: {theme.on_secondary_container}; outline: none; }}"
            f"QComboBox QAbstractItemView::item {{ padding: 10px 12px; min-height: 20px; }}"
        )
        self._settings_row(theme, card_layout, "Язык интерфейса", combo)

        speed_slider, holder = self._make_slider(theme, 50)
        self._settings_row(theme, card_layout, "Скорость анимаций", holder, control_stretch=1)

        layout.addStretch(1)
        return page

    def _build_segmented(self, theme: Theme, options: list[str],
                         default: int = 0) -> MdSegmentedControl:
        return MdSegmentedControl(theme, options, default)

    def switch_page(self, idx: int) -> None:
        self._current_page = idx
        prev = self.stack.currentWidget()
        next_widget = self.stack.widget(idx)
        if next_widget is None or next_widget is prev:
            return

        if self._page_anim is not None:
            self._page_anim.stop()
            self._page_anim = None
        self._clear_page_effects(prev, next_widget)

        prev_effect = QGraphicsOpacityEffect(prev)
        prev_effect.setOpacity(1.0)
        prev.setGraphicsEffect(prev_effect)

        next_effect = QGraphicsOpacityEffect(next_widget)
        next_effect.setOpacity(0.0)
        next_widget.setGraphicsEffect(next_effect)

        self.stack.setCurrentIndex(idx)

        group = QParallelAnimationGroup(self)
        fade_out = QPropertyAnimation(prev_effect, b"opacity", self)
        fade_out.setDuration(DUR_MED)
        fade_out.setEasingCurve(EASE)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_in = QPropertyAnimation(next_effect, b"opacity", self)
        fade_in.setDuration(DUR_MED)
        fade_in.setEasingCurve(EASE)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        group.addAnimation(fade_out)
        group.addAnimation(fade_in)
        group.finished.connect(
            lambda: self._clear_page_effects(prev, next_widget)
        )
        group.start()
        self._page_anim = group  # держим ссылку, чтобы Python не убрал объект до конца анимации

    def _clear_page_effects(self, prev, next_widget) -> None:
        prev.setGraphicsEffect(None)
        next_widget.setGraphicsEffect(None)

    def _stop_anims(self) -> None:
        for attr in ("_page_anim", "_seg_anim", "_progress_anim", "_theme_anim", "_sidebar_anim"):
            anim = getattr(self, attr, None)
            if anim is not None:
                anim.stop()
                setattr(self, attr, None)

    def eventFilter(self, obj, event) -> bool:
        if self.isVisible() and not self.isMaximized():
            if (event.type() == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton):
                edges = self._resize_edges_for(event.globalPosition().toPoint())
                if edges and self._start_system_resize(edges):
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                if not (event.buttons() & Qt.MouseButton.LeftButton):
                    edges = self._resize_edges_for(event.globalPosition().toPoint())
                    self.setCursor(self._cursor_for_edges(edges))
            elif event.type() == QEvent.Type.Leave:
                self.unsetCursor()
        return super().eventFilter(obj, event)

    def _start_system_resize(self, edges: int) -> bool:
        handle = self.windowHandle()
        if handle is None:
            return False
        flag = Qt.Edge(0)
        if edges & EDGE_TOP:
            flag |= Qt.Edge.TopEdge
        if edges & EDGE_BOTTOM:
            flag |= Qt.Edge.BottomEdge
        if edges & EDGE_LEFT:
            flag |= Qt.Edge.LeftEdge
        if edges & EDGE_RIGHT:
            flag |= Qt.Edge.RightEdge
        try:
            handle.startSystemResize(flag)
            return True
        except Exception:
            return False

    def _resize_edges_for(self, pos) -> int:
        if not self.isVisible() or self.isMaximized() or self.isFullScreen():
            return 0
        rect = self.geometry()
        x, y = pos.x() - rect.x(), pos.y() - rect.y()
        edges = 0
        if x <= EDGE_MARGIN:
            edges |= EDGE_LEFT
        elif x >= rect.width() - EDGE_MARGIN - 1:
            edges |= EDGE_RIGHT
        if y <= EDGE_MARGIN:
            edges |= EDGE_TOP
        elif y >= rect.height() - EDGE_MARGIN - 1:
            edges |= EDGE_BOTTOM
        return edges

    def _cursor_for_edges(self, edges: int) -> Qt.CursorShape:
        if not edges:
            return Qt.CursorShape.ArrowCursor
        if (edges & (EDGE_TOP | EDGE_BOTTOM)) and (edges & (EDGE_LEFT | EDGE_RIGHT)):
            diag = bool((edges & EDGE_TOP and edges & EDGE_LEFT)
                        or (edges & EDGE_BOTTOM and edges & EDGE_RIGHT))
            return (Qt.CursorShape.SizeFDiagCursor if diag
                    else Qt.CursorShape.SizeBDiagCursor)
        if edges & (EDGE_TOP | EDGE_BOTTOM):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.SizeHorCursor

    def _on_theme_toggled(self, is_dark: bool) -> None:
        self._stop_anims()
        self.theme = DARK if is_dark else LIGHT
        old_central = self.takeCentralWidget()
        if old_central is not None:
            old_central.deleteLater()
        self._build_ui()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(system_font(14, QFont.Weight.Normal))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()