"""
Готовый каркас macOS-style приложения на PyQt6.

Запуск:
    pip install PyQt6
    python app_template.py

Что внутри:
    - frameless-окно со "светофором" (close/minimize/zoom) и перетаскиванием за тулбар
    - сайдбар с анимированным индикатором выбранного пункта
    - QStackedWidget с плавным fade-переходом между страницами
    - карточки с мягкой тенью (QGraphicsDropShadowEffect)
    - кнопка с анимированным (а не мгновенным QSS) hover/press
    - переключатель темы (свет/тёмная) с анимированной ручкой,
      переключение темы пересобирает интерфейс на новом наборе токенов

Это стартовая точка, а не готовое приложение: страницы, текст и логика —
заглушки, которые нужно заменить на реальный контент конкретного проекта.
"""

from __future__ import annotations

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
# Дизайн-токены
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Theme:
    bg: str
    surface: str
    sidebar: str
    text: str
    text_secondary: str
    accent: str
    separator_rgb: str   # базовый hex-цвет для разделителей ("#000000" / "#FFFFFF")
    separator_alpha: int  # 0..255
    shadow_alpha: int      # 0..255, тень всегда чёрная, меняется только альфа


LIGHT = Theme(
    bg="#F5F5F7",
    surface="#FFFFFF",
    sidebar="#ECECEF",
    text="#1D1D1F",
    text_secondary="#6E6E73",
    accent="#1D1D1F",
    separator_rgb="#000000",
    separator_alpha=20,
    shadow_alpha=55,
)

DARK = Theme(
    bg="#1E1E1E",
    surface="#2A2A2C",
    sidebar="#242426",
    text="#F5F5F7",
    text_secondary="#98989D",
    accent="#CFCFD4",
    separator_rgb="#FFFFFF",
    separator_alpha=20,
    shadow_alpha=150,
)

RADIUS_WINDOW = 14
RADIUS_CARD = 12
SIDEBAR_WIDTH = 196
RADIUS_CONTROL = 8
EDGE_MARGIN = 6   # px, зона захвата края окна для изменения размера
EDGE_TOP, EDGE_BOTTOM, EDGE_LEFT, EDGE_RIGHT = 1, 2, 4, 8

DUR_FAST = 140       # hover
DUR_PRESS = 90       # нажатие: входим быстро, чтобы отклик ощущался мгновенным
DUR_RELEASE = 200    # отпускание: мягкий возврат
DUR_MED = 250        # переход страницы, индикатор сайдбара, тумблер
EASE = QEasingCurve.Type.OutCubic
EASE_PRESS = QEasingCurve.Type.OutQuad

REPLIES = (
    "Понял, уже смотрю.",
    "Хорошо, сделаю.",
    "Принято!",
    "Записал в план.",
    "Отлично, спасибо!",
)

SVG_EYE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">'
    '<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"/>'
    '<path fill-rule="evenodd" d="M1.323 11.447C2.811 6.976 7.028 3.75 12.001 3.75'
    'c4.97 0 9.185 3.223 10.675 7.69.12.362.12.752 0 1.113-1.487 4.471-5.705 7.697-10.677 7.697'
    '-4.97 0-9.186-3.223-10.675-7.69a1.762 1.762 0 0 1 0-1.113ZM17.25 12a5.25 5.25 0 1 1-10.5 0 '
    '5.25 5.25 0 0 1 10.5 0Z" clip-rule="evenodd"/>'
    '</svg>'
)

SVG_EYE_SLASH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor">'
    '<path d="m10.79 12.912-1.614-1.615a3.5 3.5 0 0 1-4.474-4.474l-2.06-2.06'
    'C.938 6.278 0 8 0 8s3 5.5 8 5.5a7 7 0 0 0 2.79-.588M5.21 3.088A7 7 0 0 1 8 2.5'
    'c5 0 8 5.5 8 5.5s-.939 1.721-2.641 3.238l-2.062-2.062a3.5 3.5 0 0 0-4.474-4.474z"/>'
    '<path d="M5.525 7.646a2.5 2.5 0 0 0 2.829 2.829zm4.95.708-2.829-2.83a2.5 2.5 0 0 1 '
    '2.829 2.829zm3.171 6-12-12 .708-.708 12 12z"/>'
    '</svg>'
)

PAGES = ["Обзор", "Задачи", "Ввод", "Чат", "Файлы", "Настройки"]


def system_font(point_size: int = 13, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Подбираем шрифт, максимально близкий к San Francisco, с разумным фоллбэком."""
    families = QFontDatabase.families()
    for candidate in (
        "Inter",
        "Segoe UI Variable Text",
        ".AppleSystemUIFont",
        "SF Pro Text",
        "Helvetica Neue",
        "Manrope",
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
    """Контрастный цвет текста на акцентной подложке (тёмный акцент -> белый, светлый -> чёрный)."""
    color = QColor(theme.accent)
    luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255
    return "#1D1D1F" if luminance > 0.6 else "#FFFFFF"


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


# ---------------------------------------------------------------------------
# Кнопка с анимированным (не мгновенным) hover/press
# ---------------------------------------------------------------------------

class HoverButton(QPushButton):
    """QSS :hover переключается мгновенно — здесь подложка живёт на Q_PROPERTY.

    Реакция на касание: подложка мягко светлеет, при нажатии «продавливается»
    (inset + затемнение) и на отпускании возвращается с плавным выходом.
    """

    def __init__(self, text: str, theme: Theme, parent=None):
        super().__init__(text, parent)
        self._theme = theme
        self._hover = 0.0   # 0..1
        self._press = 0.0   # 0..1
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(system_font(13, QFont.Weight.Medium))
        self.setFixedHeight(34)
        self.setStyleSheet(
            f"QPushButton {{ border: none; background: transparent; "
            f"color: {accent_fg(self._theme)}; padding: 0 18px; border-radius: {RADIUS_CONTROL}px; }}"
        )
        self._hover_anim = QPropertyAnimation(self, b"hover", self)
        self._hover_anim.setDuration(DUR_FAST)
        self._hover_anim.setEasingCurve(EASE)
        self._press_anim = QPropertyAnimation(self, b"press", self)
        self._press_anim.setDuration(DUR_PRESS)
        self._press_anim.setEasingCurve(EASE_PRESS)
        # Сигналы вместо переопределения mouse-событий: так анимируется и нажатие с клавиатуры.
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

    def _on_pressed(self) -> None:
        animate_property(self._press_anim, self._press, 1.0, DUR_PRESS, EASE_PRESS)

    def _on_released(self) -> None:
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)

    def enterEvent(self, event):
        animate_property(self._hover_anim, self._hover, 1.0, DUR_FAST, EASE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate_property(self._hover_anim, self._hover, 0.0, DUR_FAST, EASE)
        # Курсор ушёл — снимаем «вдавленность», даже если кнопка ещё зажата.
        animate_property(self._press_anim, self._press, 0.0, DUR_RELEASE, EASE)
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Нажатие сжимает подложку на ~1px по кругу и делает её темнее.
        inset = 1.2 * self._press
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        alpha = 1.0 - 0.14 * self._hover - 0.16 * self._press
        color = QColor(self._theme.accent)
        color.setAlphaF(max(0.0, min(1.0, alpha)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(rect, RADIUS_CONTROL, RADIUS_CONTROL)

        # Тонкий ореол появляется на hover — кнопка «подсвечивается» под курсором.
        if self._hover > 0.01:
            ring = QColor(self._theme.accent)
            ring.setAlphaF(0.10 * self._hover)
            pen = QPen(ring)
            pen.setWidthF(1.2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                rect.adjusted(-1, -1, 1, 1), RADIUS_CONTROL + 1, RADIUS_CONTROL + 1
            )
        painter.end()
        super().paintEvent(event)


# ---------------------------------------------------------------------------
# Тумблер (toggle switch) в духе macOS System Settings
# ---------------------------------------------------------------------------

class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, theme: Theme, checked: bool = False, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._checked = checked
        self._knob_pos = 1.0 if checked else 0.0
        self._hover = 0.0
        self._press = 0.0
        self.setFixedSize(42, 24)
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

        track_rect = QRectF(self.rect().adjusted(0, 0, -1, -1))
        off = QColor("#B9B9BE")
        on = QColor(self._theme.accent)
        t = self._knob_pos
        track_color = lerp_color(off, on, t)
        # Hover/press чуть «двигают» цвет трека к цвету текста — отклик на касание.
        if self._hover > 0.01 or self._press > 0.01:
            track_color = lerp_color(
                track_color, QColor(self._theme.text), 0.05 * self._hover + 0.04 * self._press
            )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        radius = track_rect.height() / 2
        painter.drawRoundedRect(track_rect, radius, radius)

        # При нажатии ручка вытягивается в «пилюлю», как в системных переключателях.
        knob_d = track_rect.height() - 4
        knob_w = knob_d + 4.0 * self._press
        x_min, x_max = 2.0, track_rect.width() - knob_w - 2.0
        knob_x = x_min + (x_max - x_min) * t
        knob_rect = QRectF(knob_x, 2.0, knob_w, knob_d)

        glow = QColor(self._theme.accent)
        glow.setAlphaF(0.0 + 0.09 * self._hover + 0.08 * self._press)
        if glow.alphaF() > 0.005:
            painter.setBrush(glow)
            painter.drawEllipse(
                QPointF(knob_rect.center().x(), knob_rect.center().y()),
                knob_w / 2 + 3.0, knob_d / 2 + 3.0,
            )

        painter.setBrush(QColor(self._theme.bg))
        painter.drawEllipse(knob_rect)
        painter.end()


# ---------------------------------------------------------------------------
# Слайдер в стиле macOS (кастомная отрисовка, анимированный кружок)
# ---------------------------------------------------------------------------

class MacSlider(QWidget):
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
        return 9.5

    def value(self) -> int:
        return self._value

    def setValue(self, v: int) -> None:
        v = max(self._min, min(self._max, v))
        if v != self._value:
            self._value = v
            self.valueChanged.emit(v)
            target = (self._value - self._min) / max(1, self._max - self._min)
            if self._pressed:
                # При перетаскивании подчиняемся пальцу без инерции.
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
        h = self.height()
        pad = self._knob_radius()
        # Трек слегка утолщается под курсором и сжимается при нажатии.
        track_h = 6.0 + 1.2 * self._hover + 0.6 * self._press
        cy = h / 2
        track_x0, track_x1 = pad, self.width() - pad
        ratio = max(0.0, min(1.0, self._fill))
        fill_end = track_x0 + ratio * (track_x1 - track_x0)

        painter.setPen(Qt.PenStyle.NoPen)
        track_bg = QColor(self._theme.separator_rgb)
        track_bg.setAlpha(26)
        painter.setBrush(track_bg)
        painter.drawRoundedRect(
            QRectF(track_x0, cy - track_h / 2, track_x1 - track_x0, track_h),
            track_h / 2, track_h / 2,
        )

        if ratio > 0:
            painter.setBrush(QColor(self._theme.accent))
            painter.drawRoundedRect(
                QRectF(track_x0, cy - track_h / 2, fill_end - track_x0, track_h),
                track_h / 2, track_h / 2,
            )

        knob_x = min(max(fill_end, track_x0), track_x1)
        r = self._knob_radius() * (1.0 + 0.12 * self._hover - 0.18 * self._press)

        glow = QColor(self._theme.accent)
        glow.setAlpha(round(min(40, 22 * self._hover + 18 * self._press)))
        if glow.alpha() > 0:
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(knob_x, cy), r + 4, r + 4)

        shadow = QColor(0, 0, 0)
        shadow.setAlpha(26)
        painter.setBrush(shadow)
        painter.drawEllipse(QPointF(knob_x, cy + 1), r, r)

        painter.setBrush(QColor(self._theme.bg))
        stroke = QColor(self._theme.separator_rgb)
        stroke.setAlpha(round(90 + 165 * self._press))
        pen = QPen(stroke)
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(knob_x, cy), r - 0.5, r - 0.5)
        painter.end()


# ---------------------------------------------------------------------------
# Кастомный чекбокс: анимированная галочка и тактильный отклик
# ---------------------------------------------------------------------------

class MacCheckBox(QWidget):
    """Чекбокс с собственной отрисовкой: галочка «прорисовывается» по мере включения."""

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
        self.setFont(system_font(13))
        self.setFixedHeight(24)
        self.setMinimumWidth(27 + self.fontMetrics().horizontalAdvance(text))
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

        box = QRectF(1.0, (self.height() - 18) / 2.0, 18.0, 18.0)
        center = box.center()

        painter.save()
        painter.translate(center)
        painter.scale(self._box_scale, self._box_scale)
        painter.translate(-center)

        if self._check > 0.01:
            fill = QColor(self._theme.accent)
            fill.setAlphaF(self._check)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(box, 5, 5)
        elif self._hover > 0.01:
            tint = QColor(self._theme.separator_rgb)
            tint.setAlphaF(0.05 * self._hover)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tint)
            painter.drawRoundedRect(box, 5, 5)

        base = QColor(self._theme.separator_rgb)
        border = lerp_color(base, QColor(self._theme.accent), self._check)
        border.setAlpha(round(120 + 135 * max(self._hover, self._check)))
        pen = QPen(border)
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), 4.5, 4.5)

        if self._check > 0.01:
            left, top = box.left(), box.top()
            p1 = QPointF(left + 4.6, top + 9.2)
            p2 = QPointF(left + 7.7, top + 12.2)
            p3 = QPointF(left + 13.4, top + 5.6)
            path = QPainterPath(p1)
            if self._check <= 0.45:
                q = self._check / 0.45
                path.lineTo(p1 + (p2 - p1) * q)
            else:
                path.lineTo(p2)
                q = (self._check - 0.45) / 0.55
                path.lineTo(p2 + (p3 - p2) * q)
            mark = QPen(QColor(accent_fg(self._theme)))
            mark.setWidthF(2.0)
            mark.setCapStyle(Qt.PenCapStyle.RoundCap)
            mark.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(mark)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        painter.restore()

        painter.setPen(QColor(self._theme.text))
        painter.setFont(self.font())
        painter.drawText(
            QRectF(27, 0, max(0, self.width() - 27), self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text,
        )
        painter.end()


# ---------------------------------------------------------------------------
# Сегментный контрол с переезжающей «пилюлей»
# ---------------------------------------------------------------------------

class SegmentButton(QPushButton):
    """Сегмент с собственной отрисовкой: плавный hover/press и анимированный цвет текста."""

    def __init__(self, text: str, theme: Theme, parent=None):
        super().__init__(text, parent)
        self._theme = theme
        self._hover = 0.0
        self._press = 0.0
        self._color = QColor(theme.text_secondary)
        self.setCheckable(True)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(system_font(12))
        self.setFixedHeight(26)
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance(text) + 32)
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
        rect = QRectF(self.rect()).adjusted(0, 0, 0, 0)

        if self.isChecked():
            # Выбранный сегмент лежит на акцентной «пилюле» — краской только отклик на нажатие.
            if self._press > 0.01:
                overlay = QColor(accent_fg(self._theme))
                overlay.setAlphaF(0.20 * self._press)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(overlay)
                painter.drawRoundedRect(rect, 7, 7)
        elif self._hover > 0.01 or self._press > 0.01:
            overlay = QColor(self._theme.separator_rgb)
            overlay.setAlphaF(0.10 * self._hover + 0.12 * self._press)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(overlay)
            painter.drawRoundedRect(rect, 7, 7)

        painter.setPen(self._color)
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


class SegmentedControl(QWidget):
    def __init__(self, theme: Theme, options: list[str], default: int = 0, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._buttons: list[QPushButton] = []
        self._current = default
        self.setFixedHeight(30)

        self._indicator = QFrame(self)
        self._indicator.setObjectName("SegIndicator")
        self._indicator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._anim = QPropertyAnimation(self._indicator, b"geometry", self)
        self._anim.setDuration(DUR_MED)
        self._anim.setEasingCurve(EASE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)
        for i, opt in enumerate(options):
            btn = SegmentButton(opt, theme)
            btn.setChecked(i == default)
            btn.clicked.connect(lambda _checked, b=btn: self._select(self._buttons.index(b), True))
            layout.addWidget(btn)
            self._buttons.append(btn)

        self.setStyleSheet(
            f"QFrame#SegIndicator {{ background-color: {theme.accent}; border-radius: 7px; }}"
        )
        self._apply_colors()

    def _current_geometry(self) -> QRect:
        return self._buttons[self._current].geometry()

    def _apply_colors(self) -> None:
        for i, btn in enumerate(self._buttons):
            color = accent_fg(self._theme) if i == self._current else self._theme.text_secondary
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

    def currentIndex(self) -> int:
        return self._current


# ---------------------------------------------------------------------------
# Зона drag & drop: пунктирная рамка, подсветка при перетаскивании
# ---------------------------------------------------------------------------

class DropGlyph(QWidget):
    """Иконка загрузки: мягко растёт и окрашивается в акцент, когда на зону навели/тащат файл."""

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

        halo = QColor(self._theme.accent)
        halo.setAlphaF(0.10 * level)
        if halo.alphaF() > 0.004:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(QPointF(cx, cy), 16.0 + 2.0 * level, 16.0 + 2.0 * level)

        color = lerp_color(
            QColor(self._theme.text_secondary), QColor(self._theme.accent), level
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

        # Стрелка вниз + лоток.
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
        caption.setFont(system_font(15, QFont.Weight.DemiBold))
        caption.setStyleSheet(
            f"color: {theme.text_secondary}; border: none; background: transparent;"
        )
        hint = QLabel("или нажмите, чтобы выбрать")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setFont(system_font(12))
        hint.setStyleSheet(
            f"color: {theme.text_secondary}; border: none; background: transparent;"
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
        g = max(0.0, min(1.0, self._glow))
        p = max(0.0, min(1.0, self._press))
        inset = 1.2 + 1.6 * p
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)

        bg = QColor(self._theme.separator_rgb)
        bg.setAlpha(round(10 + 16 * g + 8 * p))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 14, 14)

        border = lerp_color(
            QColor(self._theme.separator_rgb), QColor(self._theme.accent), g
        )
        border.setAlpha(round(90 + 110 * g))
        pen = QPen(border)
        pen.setWidthF(2.0)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([4.0, 3.5])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 13, 13)
        painter.end()


# ---------------------------------------------------------------------------
# Заголовок окна: светофор + перетаскивание + переключатель темы
# ---------------------------------------------------------------------------

class TrafficLight(QPushButton):
    def __init__(self, theme: Theme, symbol: str, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._symbol = symbol  # "minimize" | "maximize" | "close"
        self._hover = 0.0
        self._press = 0.0
        self._maximized = False
        self.setFixedSize(22, 22)
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

    def _animate_hover(self, target: float) -> None:
        animate_property(self._anim, self._hover, target, DUR_FAST, EASE)

    def set_maximized(self, maximized: bool) -> None:
        if self._maximized != maximized:
            self._maximized = maximized
            self.update()

    def _glyph_color(self) -> QColor:
        h = self._hover
        if self._symbol == "close":
            color = QColor("#FFFFFF")
            color.setAlpha(round(205 + 30 * h))
            return color
        base = QColor(self._theme.text_secondary)
        bright = QColor(self._theme.text)
        return lerp_color(base, bright, h)

    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
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
        rect = self.rect()
        p = self._press

        # Кружок на hover обзаводится тонким ореолом, при нажатии сжимается.
        if self._hover > 0.01:
            ring = (QColor("#FF5F57") if self._symbol == "close"
                    else QColor(self._theme.text_secondary))
            ring.setAlpha(round(55 * self._hover))
            ring_pen = QPen(ring)
            ring_pen.setWidthF(1.5)
            painter.setPen(ring_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(rect).adjusted(-1.5, -1.5, 1.5, 1.5))

        inset = 1.0 + 1.4 * p
        circle_rect = QRectF(rect).adjusted(inset, inset, -inset, -inset)
        if self._symbol == "close":
            bg = QColor("#FF5F57")
            bg.setAlpha(round(200 + 35 * self._hover))
        else:
            bg = QColor(self._theme.text_secondary)
            bg.setAlpha(round(60 + 40 * self._hover))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawEllipse(circle_rect)

        pen = QPen(self._glyph_color())
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        cx = rect.center().x() + 1
        cy = rect.center().y() + 1
        s = 1.0 - 0.14 * p

        def d(value: int) -> int:
            return round(value * s)

        if self._symbol == "close":
            painter.drawLine(cx - d(4), cy - d(4), cx + d(4), cy + d(4))
            painter.drawLine(cx + d(4), cy - d(4), cx - d(4), cy + d(4))
        elif self._symbol == "minimize":
            painter.drawLine(cx - d(5), cy - d(3), cx, cy + d(3))
            painter.drawLine(cx, cy + d(3), cx + d(5), cy - d(3))
        elif self._symbol == "maximize":
            if self._maximized:
                painter.drawLine(cx - d(5), cy - d(5), cx - d(5), cy - d(2))
                painter.drawLine(cx - d(5), cy - d(5), cx - d(2), cy - d(5))
                painter.drawLine(cx + d(5), cy - d(5), cx + d(5), cy - d(2))
                painter.drawLine(cx + d(5), cy - d(5), cx + d(2), cy - d(5))
                painter.drawLine(cx - d(5), cy + d(5), cx - d(5), cy + d(2))
                painter.drawLine(cx - d(5), cy + d(5), cx - d(2), cy + d(5))
                painter.drawLine(cx + d(5), cy + d(5), cx + d(5), cy + d(2))
                painter.drawLine(cx + d(5), cy + d(5), cx + d(2), cy + d(5))
            else:
                painter.drawLine(cx - d(5), cy + d(3), cx, cy - d(3))
                painter.drawLine(cx, cy - d(3), cx + d(5), cy + d(3))

        painter.end()
        super().paintEvent(event)


class SidebarToggle(QPushButton):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._hover = 0.0
        self._press = 0.0
        self._collapsed = False
        self.setFixedSize(22, 22)
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

    def _animate_hover(self, target: float) -> None:
        animate_property(self._anim, self._hover, target, DUR_FAST, EASE)

    def _glyph_color(self) -> QColor:
        return lerp_color(
            QColor(self._theme.text_secondary), QColor(self._theme.text), self._hover
        )

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed != collapsed:
            self._collapsed = collapsed
            self.update()

    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
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

        bg = QColor(self._theme.separator_rgb)
        bg.setAlpha(round(26 * self._hover + 18 * self._press))
        if bg.alpha() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(QRectF(self.rect()), 6, 6)

        rect = self.rect()
        cx = rect.center().x() + 1
        cy = rect.center().y() + 1
        s = 1.0 - 0.12 * self._press

        def d(value: int) -> int:
            return round(value * s)

        pen = QPen(self._glyph_color())
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(
            QRectF(cx - d(7), cy - d(7), d(14), d(14)), 2, 2
        )
        if self._collapsed:
            painter.drawLine(cx + d(2), cy - d(5), cx + d(2), cy + d(5))
        else:
            painter.drawLine(cx - d(2), cy - d(5), cx - d(2), cy + d(5))
            painter.drawLine(cx + d(4), cy - d(2), cx, cy)
            painter.drawLine(cx, cy, cx + d(4), cy + d(2))

        painter.end()


class TitleBar(QWidget):
    def __init__(self, theme: Theme, window: QMainWindow, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)
        self._window = window

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        nav_btn = SidebarToggle(theme)
        nav_btn.setToolTip("Свернуть/развернуть панель навигации")
        nav_btn.set_collapsed(getattr(self._window, "_sidebar_collapsed", False))
        nav_btn.clicked.connect(self._window.toggle_sidebar)
        self.sidebar_toggle = nav_btn

        title = QLabel("Моё приложение")
        title.setFont(system_font(13, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {theme.text_secondary};")

        layout.addWidget(nav_btn)
        layout.addWidget(title)

        layout.addStretch(1)

        min_btn = TrafficLight(theme, "minimize")
        zoom_btn = TrafficLight(theme, "maximize")
        close_btn = TrafficLight(theme, "close")
        self._zoom_btn = zoom_btn
        min_btn.clicked.connect(self._window.showMinimized)
        zoom_btn.clicked.connect(self._toggle_maximize)
        close_btn.clicked.connect(self._window.close)

        layout.addWidget(min_btn)
        layout.addWidget(zoom_btn)
        layout.addWidget(close_btn)

        self._window.installEventFilter(self)
        self._sync_zoom_state()

    def _sync_zoom_state(self) -> None:
        self._zoom_btn.set_maximized(self._window.isMaximized())

    def eventFilter(self, obj, event):
        if obj is self._window and event.type() == QEvent.Type.WindowStateChange:
            self._sync_zoom_state()
        return super().eventFilter(obj, event)

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self._sync_zoom_state()

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
# Сайдбар с анимированным индикатором выбора
# ---------------------------------------------------------------------------

class NavButton(QPushButton):
    """Пункт навигации: подсветка под курсором и отклик на нажатие рисуются вручную."""

    def __init__(self, text: str, theme: Theme, parent=None):
        super().__init__(text, parent)
        self._theme = theme
        self._hover = 0.0
        self._press = 0.0
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setFlat(True)
        self.setFont(system_font(13))
        self.setFixedHeight(30)
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            # Активная строка сидит на индикаторе — не перекрываем его hover-заливкой.
            if self._press > 0.01:
                overlay = QColor(accent_fg(self._theme))
                overlay.setAlphaF(0.12 * self._press)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(overlay)
                painter.drawRoundedRect(QRectF(self.rect()), 8, 8)
        elif self._hover > 0.01 or self._press > 0.01:
            bg = QColor(self._theme.separator_rgb)
            bg.setAlphaF(0.10 * self._hover + 0.12 * self._press)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(QRectF(self.rect()), 8, 8)
        painter.end()
        super().paintEvent(event)


class Sidebar(QWidget):
    def __init__(self, theme: Theme, pages: list[str], on_select, current: int = 0, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.on_select = on_select
        self._current = current
        self._buttons: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 16, 10, 16)
        layout.setSpacing(2)

        brand = QLabel("МойПроект")
        brand.setFont(system_font(13, QFont.Weight.Bold))
        brand.setStyleSheet(f"color: {theme.text}; padding: 0 8px 14px 8px;")
        layout.addWidget(brand)

        self.indicator = QFrame(self)
        self.indicator.setObjectName("Indicator")

        for i, name in enumerate(pages):
            btn = NavButton(name, theme)
            btn.setChecked(i == current)
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
    indicator_bg = rgba(theme.accent, 40)
    hover_bg = rgba(theme.separator_rgb, 26)
    return f"""
        #Panel {{
            background-color: {theme.bg};
            border-radius: {RADIUS_WINDOW}px;
        }}
        #TitleBar {{
            background-color: transparent;
        }}
        #Sidebar {{
            background-color: {theme.sidebar};
            border-bottom-left-radius: {RADIUS_WINDOW}px;
        }}
        #Indicator {{
            background-color: {indicator_bg};
            border-radius: 8px;
        }}
        QPushButton#NavButton {{
            text-align: left;
            border: none;
            border-radius: 8px;
            padding-left: 10px;
            color: {theme.text_secondary};
            background: transparent;
        }}
        QPushButton#NavButton:checked {{
            color: {theme.text};
        }}
        QPushButton#ToolButton {{
            color: {theme.text_secondary};
            background: transparent;
            border: none;
            border-radius: 6px;
        }}
        QPushButton#ToolButton:hover {{
            color: {theme.text};
            background-color: {hover_bg};
        }}
        QScrollBar {{ background: transparent; }}
        QScrollBar:vertical {{ width: 8px; margin: 2px; }}
        QScrollBar::handle:vertical {{
            background: {rgba(theme.separator_rgb, 60)};
            border-radius: 3px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {rgba(theme.separator_rgb, 120)};
        }}
        QScrollBar:horizontal {{ height: 8px; margin: 2px; }}
        QScrollBar::handle:horizontal {{
            background: {rgba(theme.separator_rgb, 60)};
            border-radius: 3px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {rgba(theme.separator_rgb, 120)};
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0; height: 0; background: transparent;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: transparent;
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

    def _build_ui(self) -> None:
        theme = self.theme

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)

        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root_layout.addWidget(panel)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        title_bar = TitleBar(theme, self)
        self._title_bar = title_bar
        panel_layout.addWidget(title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        panel_layout.addWidget(body)

        sidebar = Sidebar(theme, PAGES, on_select=self.switch_page, current=self._current_page)
        self._sidebar = sidebar
        body_layout.addWidget(sidebar)
        separator = self._build_separator(theme)
        self._sidebar_sep = separator
        body_layout.addWidget(separator)

        if self._sidebar_collapsed:
            sidebar.setFixedWidth(0)
            separator.setFixedWidth(0)

        self.stack = QStackedWidget()
        for name in PAGES:
            self.stack.addWidget(self._build_page(theme, name))
        self.stack.setCurrentIndex(self._current_page)
        body_layout.addWidget(self.stack, 1)

        panel.setStyleSheet(build_stylesheet(theme))

    def _build_separator(self, theme: Theme) -> QFrame:
        line = QFrame()
        line.setFixedWidth(1)
        line.setStyleSheet(f"background-color: {rgba(theme.separator_rgb, theme.separator_alpha)};")
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
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel(name)
        title.setFont(system_font(22, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.text};")
        layout.addWidget(title)
        return page, layout

    def _add_card(self, theme: Theme, layout, card_title: str):
        card = QFrame()
        card.setObjectName("Card")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(
            f"#Card {{ background-color: {theme.surface}; border-radius: {RADIUS_CARD}px; }}"
        )
        card_shadow = QGraphicsDropShadowEffect(card)
        card_shadow.setBlurRadius(24)
        card_shadow.setOffset(0, 5)
        card_shadow.setColor(shadow_color(theme))
        card.setGraphicsEffect(card_shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(14)

        head = QLabel(card_title)
        head.setFont(system_font(14, QFont.Weight.DemiBold))
        head.setStyleSheet(f"color: {theme.text};")
        card_layout.addWidget(head)

        layout.addWidget(card)
        return card, card_layout

    def _settings_row(self, theme: Theme, card_layout, label_text: str, control,
                      control_stretch: int = 0) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        lab = QLabel(label_text)
        lab.setFont(system_font(13))
        lab.setStyleSheet(f"color: {theme.text};")
        row.addWidget(lab)
        if control_stretch:
            row.addWidget(control, control_stretch)
        else:
            row.addStretch(1)
            row.addWidget(control)
        card_layout.addLayout(row)

    def _make_slider(self, theme: Theme, value: int, minimum: int = 0, maximum: int = 100):
        holder = QWidget()
        holder.setFixedHeight(28)
        holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        slider = MacSlider(theme, value, minimum, maximum)
        slider.setMinimumWidth(140)

        value_label = QLabel(str(value))
        value_label.setFixedWidth(34)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_label.setFont(system_font(12))
        value_label.setStyleSheet(f"color: {theme.text_secondary};")

        slider.valueChanged.connect(lambda v, lab=value_label: lab.setText(str(v)))

        row.addWidget(slider, 1)
        row.addWidget(value_label)
        return slider, holder

    def _toggle_row(self, theme: Theme, card_layout, label_text: str, checked: bool = False,
                    on_toggled=None) -> ToggleSwitch:
        toggle = ToggleSwitch(theme, checked=checked)
        if on_toggled is not None:
            toggle.toggled.connect(on_toggled)
        self._settings_row(theme, card_layout, label_text, toggle)
        return toggle

    def _make_line_edit(self, theme: Theme, placeholder: str = "",
                        password: bool = False, pill: bool = False) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFont(system_font(13))
        edit.setFixedHeight(34)
        edit.setCursor(Qt.CursorShape.IBeamCursor)
        if password:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        radius = 17 if pill else RADIUS_CONTROL
        edit.setStyleSheet(
            f"QLineEdit {{ background-color: {theme.surface}; border: 1px solid "
            f"{rgba(theme.separator_rgb, 70)}; border-radius: {radius}px; "
            f"padding: 4px 12px; color: {theme.text}; "
            f"selection-background-color: {theme.accent}; "
            f"selection-color: {accent_fg(theme)}; }}"
            f"QLineEdit:hover {{ border-color: {rgba(theme.separator_rgb, 140)}; }}"
            f"QLineEdit:focus {{ border: 1px solid {theme.accent}; "
            f"background-color: {rgba(theme.accent, 8)}; }}"
            f"QLineEdit::placeholder {{ color: {theme.text_secondary}; }}"
        )
        return edit

    def _field_icon(self, theme: Theme, kind: str, size: int = 18) -> QIcon:
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon = None
        pen = QPen(QColor(theme.text_secondary))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if kind == "search":
            painter.setPen(pen)
            painter.drawEllipse(QRectF(size * 0.22, size * 0.22, size * 0.44, size * 0.44))
            painter.drawLine(int(size * 0.62), int(size * 0.62),
                             int(size * 0.85), int(size * 0.85))
        elif kind == "clear":
            painter.setPen(Qt.PenStyle.NoPen)
            disc = QColor(theme.text_secondary)
            disc.setAlpha(110)
            painter.setBrush(disc)
            painter.drawEllipse(QRectF(size * 0.15, size * 0.15, size * 0.7, size * 0.7))
            xpen = QPen(QColor(theme.bg))
            xpen.setWidthF(1.5)
            xpen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(xpen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(int(size * 0.34), int(size * 0.34),
                             int(size * 0.66), int(size * 0.66))
            painter.drawLine(int(size * 0.66), int(size * 0.34),
                             int(size * 0.34), int(size * 0.66))
        elif kind == "eye":
            icon = self._svg_icon(SVG_EYE, size)
        elif kind == "eye_slash":
            icon = self._svg_icon(SVG_EYE_SLASH, size)
        painter.end()
        return icon if icon is not None else QIcon(pm)

    def _svg_icon(self, svg: str, size: int) -> QIcon:
        source = svg.replace("currentColor", self.theme.text_secondary)
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

    def _build_inputs_page(self, theme: Theme) -> QWidget:
        page, layout = self._page_shell(theme, "Ввод")

        _, card_layout = self._add_card(theme, layout, "Текстовые поля")
        self._settings_row(theme, card_layout, "Имя",
                           self._make_line_edit(theme, "Например, Анастасия"),
                           control_stretch=1)
        self._settings_row(theme, card_layout, "E-mail",
                           self._make_line_edit(theme, "you@example.com"),
                           control_stretch=1)
        self._settings_row(theme, card_layout, "Пароль",
                           self._build_password_field(theme),
                           control_stretch=1)
        self._settings_row(theme, card_layout, "Поиск",
                           self._build_search_field(theme),
                           control_stretch=1)

        _, card_layout = self._add_card(theme, layout, "Многострочный ввод")
        area = QTextEdit()
        area.setPlaceholderText("Введите комментарий…")
        area.setFont(system_font(13))
        area.setFixedHeight(110)
        area.setStyleSheet(
            f"QTextEdit {{ background-color: {theme.surface}; border: 1px solid "
            f"{rgba(theme.separator_rgb, 70)}; border-radius: 10px; padding: 8px; "
            f"color: {theme.text}; selection-background-color: {theme.accent}; "
            f"selection-color: {accent_fg(theme)}; }}"
        )
        pal = area.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.text_secondary))
        area.setPalette(pal)
        card_layout.addWidget(area)

        char_label = QLabel("0 символов")
        char_label.setFont(system_font(12))
        char_label.setStyleSheet(f"color: {theme.text_secondary};")
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
            f"color: {theme.text_secondary}; background: transparent;"
        )
        typing_label.setVisible(self._chat_typing)
        self._chat_typing_label = typing_label
        typing_row = QHBoxLayout()
        typing_row.addStretch(1)
        typing_row.addWidget(typing_label)
        layout.addLayout(typing_row)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        edit = self._make_line_edit(theme, "Напишите сообщение…")
        edit.setFixedHeight(36)
        edit.returnPressed.connect(self._on_chat_send)
        send = HoverButton("Отправить", theme)
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
                f"color: {theme.text_secondary}; background: transparent; padding: 0 4px;"
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
        label.setFont(system_font(13))
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        lay = QHBoxLayout(bubble)
        lay.setContentsMargins(14, 9, 14, 9)
        lay.addWidget(label)

        if mine:
            tl, tr, bl, br = 16, 4, 16, 4
            bg = theme.accent
            fg = accent_fg(theme)
            border = ""
        else:
            tl, tr, bl, br = 16, 16, 4, 16
            bg = theme.surface
            fg = theme.text
            border = f"border: 1px solid {rgba(theme.separator_rgb, 70)}; "
        bubble.setStyleSheet(
            f"QFrame#Bubble {{ background-color: {bg}; {border}"
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
            f"QListWidget {{ background: transparent; border: none; color: {theme.text}; "
            f"outline: none; }}"
            f"QListWidget::item {{ padding: 7px 10px; border-radius: 7px; }}"
            f"QListWidget::item:hover {{ background-color: {rgba(theme.separator_rgb, 16)}; }}"
            f"QListWidget::item:selected {{ background-color: {rgba(theme.accent, 45)}; }}"
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
        count_label.setStyleSheet(f"color: {theme.text_secondary};")
        card_layout.addWidget(count_label)

        self._refresh_files_list(drop_list, count_label, theme)
        drop.dropped.connect(
            lambda files, lw=drop_list, cl=count_label:
            self._on_files_dropped(files, lw, cl, theme)
        )

        _, card_layout = self._add_card(theme, layout, "Переупорядочивание")
        hint = QLabel("Перетаскивайте строки списка, чтобы изменить порядок.")
        hint.setFont(system_font(12))
        hint.setStyleSheet(f"color: {theme.text_secondary};")
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
            pb.setFixedHeight(12)
            pb.setStyleSheet(
                f"QProgressBar {{ background-color: {rgba(theme.separator_rgb, 26)}; border: none; "
                f"border-radius: 6px; }}"
                f"QProgressBar::chunk {{ background-color: {theme.accent}; border-radius: 6px; }}"
            )
            return pb

        _, card_layout = self._add_card(theme, layout, "Активные задачи")
        checkboxes = []
        for text in cards:
            cb = MacCheckBox(text, theme)
            card_layout.addWidget(cb)
            checkboxes.append(cb)

        _, card_layout = self._add_card(theme, layout, "Прогресс")
        progress = make_progress()
        card_layout.addWidget(progress)
        counter = QLabel(f"Выполнено 0 из {len(checkboxes)}")
        counter.setFont(system_font(12))
        counter.setStyleSheet(f"color: {theme.text_secondary};")
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

        reset_btn = HoverButton("Сбросить", theme)
        reset_btn.clicked.connect(lambda: [cb.setChecked(False) for cb in checkboxes])
        card_layout.addWidget(reset_btn)

        layout.addStretch(1)
        return page

    def _build_settings_page(self, theme: Theme) -> QWidget:
        page, layout = self._page_shell(theme, "Настройки")

        _, card_layout = self._add_card(theme, layout, "Внешний вид")
        self._toggle_row(theme, card_layout, "Тёмная тема", checked=(theme is DARK),
                         on_toggled=self._on_theme_toggled)

        seg_row = QHBoxLayout()
        seg_row.setSpacing(12)
        seg_lab = QLabel("Размер интерфейса")
        seg_lab.setFont(system_font(13))
        seg_lab.setStyleSheet(f"color: {theme.text};")
        seg_row.addWidget(seg_lab)
        seg_row.addStretch(1)
        seg_row.addWidget(self._build_segmented(theme, ["Компактный", "Средний", "Крупный"], default=1))
        card_layout.addLayout(seg_row)

        _, card_layout = self._add_card(theme, layout, "Поведение")
        self._toggle_row(theme, card_layout, "Автообновления", checked=True)
        self._toggle_row(theme, card_layout, "Анимации", checked=True)

        combo = QComboBox()
        combo.addItems(["Русский", "English", "Deutsch"])
        combo.setFixedHeight(30)
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setStyleSheet(
            f"QComboBox {{ background-color: {theme.surface}; border: 1px solid "
            f"{rgba(theme.separator_rgb, 70)}; border-radius: 8px; padding: 2px 12px; "
            f"color: {theme.text}; }}"
            f"QComboBox::drop-down {{ border: none; width: 24px; }}"
            f"QComboBox::down-arrow {{ image: none; width: 0; height: 0; "
            f"border-left: 4px solid transparent; border-right: 4px solid transparent; "
            f"border-top: 5px solid {theme.text_secondary}; margin-right: 8px; }}"
            f"QComboBox QAbstractItemView {{ background-color: {theme.surface}; "
            f"color: {theme.text}; selection-background-color: {theme.accent}; "
            f"selection-color: {accent_fg(theme)}; border-radius: 8px; outline: none; }}"
        )
        self._settings_row(theme, card_layout, "Язык интерфейса", combo)

        speed_slider, holder = self._make_slider(theme, 50)
        self._settings_row(theme, card_layout, "Скорость анимаций", holder, control_stretch=1)

        layout.addStretch(1)
        return page

    def _build_segmented(self, theme: Theme, options: list[str], default: int = 0) -> SegmentedControl:
        return SegmentedControl(theme, options, default)

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
    app.setFont(system_font(10, QFont.Weight.Normal))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
