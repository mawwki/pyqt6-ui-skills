---
name: pyqt6-macos-ui
description: Build, redesign, or restyle a desktop GUI app in PyQt6/PySide6 so it looks and feels like a polished Material Design 3 (MD3) app (frameless window, Material window buttons, navigation drawer with pill indicator, elevated cards, tonal/filled buttons with ripple, MD3 switches/sliders/checkboxes/segmented buttons, light/dark themes). Use whenever the user asks to make a desktop UI "красиво/стильно", "в стиле Material/Material Design/MD3", "современный интерфейс", "frameless window", "как в этом приложении" (referring to assets/app_template.py), or wants animations, state layers, ripple, drawer navigation, toggles, sliders, chat, drag&drop. Contains the exact build spec of the reference app app_template.py (MD3 tokens, per-widget geometry/timing/roles, interaction logic, page set) plus the must-know PyQt6-on-Windows crash pitfalls. Consult before writing any PyQt6/PySide6 UI code so the result doesn't look like a default Qt app.
---

# PyQt6 в стиле Material Design 3 — спецификация эталонного приложения

Ниже — полная спецификация, по которой можно воспроизвести `assets/app_template.py`
побайтно по поведению. Моделируй агента-дизайнера интерфейсов из студии, которая делает
MD3-десктоп-приложения: ролевая палитра (primary / on-primary / containers / surface /
outline), state layers, ripple, скругления по шкале форм, анимации ровно там, где они
объясняют, что произошло, — и не больше.

Главное правило: **«стиль MD3» в Qt — это не нативный API, а воссозданная руками эстетика**:
frameless-окно + собственный QSS + `QPropertyAnimation` для плавности. Так приложение
выглядит одинаково на Windows, Linux и macOS. Native style Qt не даёт скруглений,
полупрозрачности, state layers и анимаций.

Референс-реализация — `assets/app_template.py` (один файл). Задача агента: либо скопировать
и адаптировать его, либо пересобрать с нуля точно по этому документу.

---

## 1. Быстрый старт

```text
pip install PyQt6
python app_template.py
```

Сборка для пользователя: `pyinstaller --windowed --icon=app.ico app_template.py`.

Приложение запускается так:
```python
def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")                       # единственный стиль, уважающий QSS везде
    app.setFont(system_font(14, QFont.Weight.Normal))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

---

## 2. Структура файла app_template.py (порядок важен для читаемости)

1. Импорты: `math`, `sys`, `time`, `dataclasses`, `pathlib.Path`; QtCore (`Qt`, `QEvent`,
   `QPropertyAnimation`, `QEasingCurve`, `QRect(F)`, `QPointF`, `QParallelAnimationGroup`,
   `QVariantAnimation`, `QTimer`, `pyqtProperty`, `pyqtSignal`); QtGui (`QColor`, `QFont`,
   `QPainter`, `QPainterPath`, `QFontDatabase`, `QFontMetricsF`, `QPen`, `QPixmap`, `QIcon`,
   `QPalette`); QtSvg (`QSvgRenderer`); QtWidgets (все нужные виджеты).
2. Дизайн-токены: `Theme` (dataclass), `LIGHT`/`DARK`, константы радиусов/длительностей,
   `REPLIES`, `SVG_EYE`/`SVG_EYE_SLASH`, `PAGES`.
3. Хелперы: `system_font`, `rgba`, `accent_fg`, `shadow_color`, `lerp_color`,
   `animate_property`, `draw_checkmark`.
4. Кастомные виджеты в порядке зависимостей: `MdButton`, `MdSwitch`, `MdSlider`,
   `MdCheckBox`, `MdSegmentButton`/`MdSegmentedControl`, `DropGlyph`/`FileDropArea`,
   `WindowButton`, `SidebarToggle`, `TopAppBar`, `NavButton`/`NavigationDrawer`.
5. `build_stylesheet(theme)`.
6. `MainWindow` + `main()`.

---

## 3. Дизайн-токены (точные значения, MD3 roles)

`Theme` — frozen dataclass, все цвета — hex-строки, роли MD3:
`primary`, `on_primary`, `primary_container`, `on_primary_container`,
`secondary_container`, `on_secondary_container`, `surface`, `surface_container_low`,
`surface_container`, `surface_container_high`, `surface_container_highest`, `on_surface`,
`on_surface_variant`, `outline`, `outline_variant`, `error`, `on_error`, `error_container`,
`on_error_container`, `shadow_alpha` (int 0..255, тень всегда чёрная).

```python
LIGHT = Theme(primary="#6750A4", on_primary="#FFFFFF",
              primary_container="#EADDFF", on_primary_container="#21005D",
              secondary_container="#E8DEF8", on_secondary_container="#1D192B",
              surface="#FEF7FF", surface_container_low="#F7F2FA",
              surface_container="#F3EDF7", surface_container_high="#ECE6F0",
              surface_container_highest="#E6E0E9", on_surface="#1D1B20",
              on_surface_variant="#49454F", outline="#79747E", outline_variant="#CAC4D0",
              error="#B3261E", on_error="#FFFFFF",
              error_container="#F9DEDC", on_error_container="#410E0B", shadow_alpha=45)
DARK  = Theme(primary="#D0BCFF", on_primary="#381E72",
              primary_container="#4F378B", on_primary_container="#EADDFF",
              secondary_container="#4A4458", on_secondary_container="#E8DEF8",
              surface="#141218", surface_container_low="#1D1B20",
              surface_container="#211F26", surface_container_high="#2B2930",
              surface_container_highest="#36343B", on_surface="#E6E0E9",
              on_surface_variant="#CAC4D0", outline="#938F99", outline_variant="#49454F",
              error="#F2B8B5", on_error="#601410",
              error_container="#8C1D18", on_error_container="#F9DEDC", shadow_alpha=120)
```

Пары «роль / on-роль» обязательны: текст поверх `primary` — всегда `on_primary`, поверх
`secondary_container` — `on_secondary_container`, поверх `primary_container` —
`on_primary_container`. Никакого хардкода «white»/«black». `accent_fg(theme)` оставлен как
compat-хелпер и возвращает `theme.on_primary`.

```python
def rgba(hex_color: str, alpha_0_255: int) -> str:   # QSS ждёт альфу 0..255, не 0..1
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha_0_255})"

def shadow_color(theme: Theme) -> QColor:
    c = QColor(0, 0, 0); c.setAlpha(theme.shadow_alpha); return c
```

Константы:
- Формы: `RADIUS_WINDOW = 16`, `RADIUS_CARD = 12`, `RADIUS_MENU = 8`, `RADIUS_FIELD = 4`,
  `SIDEBAR_WIDTH = 220`. Кнопки/пилюли — radius = height/2; чипы/сегменты — full.
- `EDGE_MARGIN = 12` (совпадает с отступом root под тень), бит-маски краёв
  `EDGE_TOP, EDGE_BOTTOM, EDGE_LEFT, EDGE_RIGHT = 1, 2, 4, 8`.
- `DUR_FAST = 140` (hover), `DUR_PRESS = 90`, `DUR_RELEASE = 200`, `DUR_MED = 250`
  (страницы, drawer, тумблер, сегменты), `DUR_RIPPLE = 450`;
  `EASE = OutCubic`, `EASE_PRESS = OutQuad`.
- `PAGES = ["Обзор", "Задачи", "Ввод", "Чат", "Файлы", "Настройки"]`.
- `REPLIES` — 5 коротких ответов бота.
- `SVG_EYE` / `SVG_EYE_SLASH` — Material Symbols `visibility` / `visibility_off`
  (viewBox 0 0 24 24, `fill="currentColor"`).

Типографика: `system_font(point_size=14, weight)` — цепочка `Roboto` → `Google Sans` →
`Noto Sans` → `Segoe UI`, `setStyleStrategy(PreferAntialias)`. Размеры: заголовок страницы 24,
заголовок карточки 16/Medium, текст кнопки 14/Medium, body 14, вторичный 12, время 11.
Отступы из шкалы 4/8/12/16/24/32.

Тени: окно/панель — `blurRadius 24`, `offset (0,4)`; карточки (elevation 1) —
`blurRadius 8`, `offset (0,1)`; цвет `shadow_color(theme)`.

State layers (поверх контейнера, цветом «on-роли»): hover 0.08, press 0.12 (т.е.
`0.08*hover + 0.04*press`); у слайдера hover 0.10 / press 0.16; у чекбокса 0.06 (unchecked)
/ 0.10 (checked).

---

## 4. Каркас окна

```python
self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
self.setMinimumSize(760, 480)
self.resize(960, 600)
self.setMouseTracking(True)
QApplication.instance().installEventFilter(self)   # для ресайза за края
```

Дерево (`_build_ui`): `QMainWindow` → `root (QWidget, margins 12)` →
`panel (QFrame#Panel, drop-shadow)` → `TopAppBar (56px)` + `body (QHBoxLayout)` →
`NavigationDrawer (220px)` + `separator (1px, outline_variant)` + `QStackedWidget`.
Панель получает `build_stylesheet(theme)` — QSS наследуется вниз. Дополнительно
`_apply_palette(theme)` выставляет роли `QPalette` (Window/Base=surface, Text=on_surface,
Highlight=primary, HighlightedText=on_primary, PlaceholderText=on_surface_variant,
ToolTipBase=surface_container_high…) для нативно рисуемых частей.

**Тень и скругление живут на дочернем `QFrame#Panel`**, а не на самом окне: окно прозрачное
и даёт отступ 12px под тень. Навешивать эффект на `QMainWindow` нельзя.

### Перетаскивание и ресайз

Двигать окно — нативный механизм Qt6 (в `TopAppBar.mousePressEvent`):
```python
handle = self._window.windowHandle()
if handle is not None:
    handle.startSystemMove()
```
Двойной клик по `TopAppBar` — maximize/normal.

Менять размер за края — нативный `QWindow.startSystemResize`. В `MainWindow` установлен
**фильтр событий на `QApplication`**: на `MouseButtonPress`(Left) в зоне ≤ `EDGE_MARGIN`
вызывает `_start_system_resize(edges)` и возвращает `True`; на `MouseMove` без кнопок
обновляет курсор; на `Leave` сбрасывает курсор.

`_resize_edges_for(pos)` → бит-маска краёв (только если окно видимо и не максимизировано).
`_cursor_for_edges`: центр → Arrow; лево/право → SizeHor; верх/низ → SizeVer;
верх+лево или низ+право → SizeFDiag; иначе → SizeBDiag.

**Капкан PyQt6:** `Qt.Edge` нельзя превратить в `int` и нельзя смешивать с `int` через `|`.
Математика краёв — на своих бит-константах `EDGE_*`, флаг собирается так:
```python
flag = Qt.Edge(0)
if edges & EDGE_TOP:    flag |= Qt.Edge.TopEdge
if edges & EDGE_BOTTOM: flag |= Qt.Edge.BottomEdge
if edges & EDGE_LEFT:   flag |= Qt.Edge.LeftEdge
if edges & EDGE_RIGHT:  flag |= Qt.Edge.RightEdge
handle.startSystemResize(flag)
```

---

## 5. Кастомные виджеты (точные параметры)

### MdButton (filled / tonal, state layer + ripple)
- `QPushButton`, высота 40, pill radius 20, шрифт 14/Medium, `padding 0 24px`,
  minWidth = text + 48. `kind="filled"` → bg `primary`/fg `on_primary`;
  `kind="tonal"` → bg `secondary_container`/fg `on_secondary_container`.
- QSS: `background: transparent; color: {fg}` — фон рисуется вручную, текст через
  `super().paintEvent()`.
- `Q_PROPERTY hover/press/ripple` (float). State layer цветом fg:
  `alphaF = 0.08*hover + 0.04*press`, клип по скруглённому rect.
- Ripple: `mousePressEvent` запоминает точку (`_ripple_origin`), `pressed` запускает
  `_ripple_anim` 0→1 (`DUR_RIPPLE`); в paint — эллипс из точки радиусом
  `max_r*ripple` (max_r = расстояние до дальнего угла + 4), `alphaF = 0.18*(1-ripple)`,
  клип по pill. Ссылку на анимацию держать в атрибуте.

### MdSwitch (тумблер MD3)
- `QWidget` 52×32, сигнал `toggled(bool)` только по клику; `setChecked` молча анимирует.
- `Q_PROPERTY knobPos` (0..1) `DUR_MED`/`EASE`, плюс hover/press.
- Off: трек `surface_container_highest` + обводка 2px `outline`; ручка 16px цветом
  `outline`, центр x=16. On: трек `primary` без обводки; ручка 24px `on_primary`,
  центр x=36, внутри галочка цветом `primary` (`draw_checkmark`, pen 2px). Press: ручка 28px.
- Трек/ручка интерполируются `lerp_color` по knobPos; обводка исчезает при t→1
  (`alpha = 255*(1-t)`); state layer-круг 40px вокруг ручки.

### MdSlider
- `QWidget` высота 28, `valueChanged(int)`. Трек 4px radius 2: неактивный
  `surface_container_highest`, активный `primary`. Ручка — круг 20px `primary` + лёгкая
  тень (чёрный alpha 30, offset y+1). State layer 40px `primary`
  `alphaF = 0.10*hover + 0.06*press`.
- Значение из x: `pad = 10` (радиус ручки), `ratio = (x-pad)/(width-2*pad)`; при drag —
  без инерции, иначе `fill` анимируется `DUR_FAST`.

### MdCheckBox
- `QWidget` высота 24, шрифт 14, minWidth = 34 + text. Бокс 18×18 radius 2 at x=3.
- Unchecked: обводка 2px `on_surface_variant`. Checked: заливка `primary` + галочка
  `on_primary` (pen 2px RoundCap/RoundJoin), галочка «прорисовывается» прогрессивно
  (`check` 0..1, две сегментные линии через `drawPath`).
- State layer 36px: `on_surface` 0.06 (unchecked) / `primary` 0.10 (checked) * hover.
- `boxScale` (OutBack) сжимает бокс при press; `setChecked(checked, animate)` эмитит
  `toggled`; клик в `mouseReleaseEvent` только если курсор внутри rect.

### MdSegmentedControl / MdSegmentButton
- Контейнер высота 40, pill radius 20, обводка 1px `outline` (рисуется в paintEvent).
- Сегменты равной ширины (`addWidget(btn, 1)`), высота 38, шрифт 14/Medium;
  margins (1,1,1,1), spacing 0. Разделители 1px `outline` между НЕвыбранными соседями
  (рисуются в paintEvent, int-координаты).
- Индикатор — `QFrame#SegIndicator` (bg `secondary_container`, radius 19) позади кнопок,
  `QPropertyAnimation(geometry)` `DUR_MED`; в `showEvent` — `lower()` + геометрия без анимации.
- Выбранный сегмент: текст `on_secondary_container` + галочка слева от текста
  (`draw_checkmark`); невыбранный: `on_surface`. Цвет текста анимируется (`color` QColor
  property). State layer сегмента — pill цветом on-роли.

### DropGlyph / FileDropArea
- Glyph 38×38: стрелка вниз + лоток, цвет `lerp(on_surface_variant, primary, level)`,
  halo `primary` alpha 0.10*level.
- `FileDropArea(QFrame)`: minHeight 150, `setAcceptDrops(True)`. Фон
  `surface_container_low` radius 16; пунктир 2px `outline_variant` (dashPattern [4,3.5]);
  при hover/drag — пунктир `primary` + overlay `primary_container` alpha ≈ 60*glow+20*press.
- `dragEnterEvent(hasUrls)` / `dragLeaveEvent` / `dropEvent` (только `isLocalFile()`) →
  `dropped(list[str])`; клик → `QFileDialog.getOpenFileNames`. Вся логика сигналов неизменна.

### WindowButton (кнопки окна)
- `QPushButton` 40×40, radius 20, `Q_PROPERTY hover/press`, `set_maximized(bool)`.
- Глифы `QPen` 1.8 RoundCap/RoundJoin, **int-координаты**: minimize — горизонтальная линия;
  maximize — квадрат 12×12 (outline), при развороте — два наложенных квадрата;
  close — крестик X.
- Цвет глифа `lerp(on_surface_variant, on_surface, hover)`; close на hover — фон `error`
  (круг 40px) + глиф `on_error`. Остальные на hover — state layer `on_surface` 0.08.
- Порядок справа: minimize, maximize, close.

### SidebarToggle
- `QPushButton` 40×40, state layer `on_surface` 0.08, глиф
  `lerp(on_surface_variant, on_surface, hover)`.
- Глиф: рамка 16×16 radius 2 + разделитель; открытая панель — разделитель слева + шеврон
  `<` (panel-left-close); свёрнутая — разделитель справа (panel-left-open).
- `set_collapsed(bool)`; синхронизирует `MainWindow.toggle_sidebar`.

### TopAppBar
- `QWidget#TopAppBar` высота 56, прозрачный поверх Panel; margins (8,0,8,0), spacing 4.
- Слева `SidebarToggle`, затем title «МойПроект» 18/Medium `on_surface`, stretch, справа
  `WindowButton` minimize/maximize/close. `_max_btn` + `_sync_max_state` через eventFilter
  на `WindowStateChange`. `startSystemMove` + double-click maximize.

### NavButton / NavigationDrawer
- `NavButton(QPushButton#NavButton)` высота 48, шрифт 14, checkable; иконка 20×20 at x=16
  рисуется `QPainter` (Material Symbols outlined): dashboard (4 квадрата), tasks (круг+check),
  edit (карандаш), chat (bubble), folder, tune (3 линии + knobs). Текст через QSS
  `padding-left: 48px`.
- `nextCheckState()` переопределён — клик по уже выбранному пункту не снимает checked
  (no-op), иначе стандартный toggle QPushButton гасит выделение.
- State layer pill (radius h/2): checked — `on_secondary_container`, unchecked —
  `on_surface`, alpha 0.08*hover+0.04*press. Иконка: checked `on_secondary_container`,
  unchecked `lerp(on_surface_variant, on_surface, hover)`.
- `NavigationDrawer(QWidget)` fixedWidth 220, bg `surface_container_low`,
  margins (12,8,12,8), spacing 4; секция-лейбл «Навигация» 12/Medium `on_surface_variant`.
- Индикатор `QFrame#Indicator` (bg `secondary_container`, radius 24) анимируется по
  geometry к выбранной кнопке (`DUR_MED`); активный текст 14/Medium
  `on_secondary_container`, неактивный `on_surface_variant`. Клик по текущей — no-op;
  `showEvent` — индикатор без анимации.

---

## 6. Общий QSS (`build_stylesheet`)

- `#Panel` — bg `surface`, radius 16. `#TopAppBar` — прозрачный.
  `#NavigationDrawer` — `surface_container_low` + `border-bottom-left-radius: 16`.
- `#Indicator` — `secondary_container`, radius 24.
- `QPushButton#NavButton` — text-align left, border none, radius 24, padding-left 48,
  color `on_surface_variant`, background transparent; `:checked` — `on_secondary_container`.
- **Скроллбары**: вертикаль/горизонталь 8px margin 2px, handle radius 4
  `rgba(outline_variant,120)` (hover `outline`), min 30; стрелки и страницы прозрачные.
- `QToolTip` — `surface_container_high` / `on_surface`, рамка `outline_variant`, radius 4.
- `WA_StyledBackground = True` на любом виджете с QSS-фоном.

---

## 7. Страницы (6 штук)

Компонуется через `_page_shell(theme, title)` и `_add_card(theme, layout, title)`
(карточка `surface_container_low` radius 12 + shadow elevation 1 + заголовок 16/Medium +
margins 16 + spacing 12). В `_page_shell` контент страницы обёрнут в прозрачный frameless
`QScrollArea` (`setWidgetResizable(True)`, viewport прозрачный): страницы Ввод/Файлы выше
viewport при 960×600 и должны скроллиться, а не сжимать карточки ниже минимума; margins
(24,24,24,24) и spacing 16 относятся к внутреннему content-widget, заголовок 24,
bg transparent.

1. **Обзор** — «Система» (MdSwitch: Автозапуск ✓, Уведомления ✓, Энергосбережение ✗) и
   «Отображение» (MdSlider Яркость=70, Громкость=45). Строка слайдера — label слева,
   holder справа с `control_stretch=1` (см. капкан про stretch).

2. **Задачи** — 4 `MdCheckBox`; прогресс-бар 6px (track `surface_container_highest` r3,
   chunk `primary` r3), счётчик «Выполнено N из M», анимация через `QVariantAnimation`
   (280мс); кнопка `MdButton("Сбросить", kind="tonal")` в HBox + `addStretch(1)`.

3. **Ввод** — метка НАД полем (`_labeled_field`, 12px `on_surface_variant`):
   - Имя, E-mail — outlined `QLineEdit` 44px radius 4, рамка 1px `outline`,
     hover `on_surface_variant`, focus 2px `primary`, bg transparent, текст `on_surface`,
     placeholder через palette, selection `primary`/`on_primary`.
   - Пароль — trailing «глаз» (`eye` ↔ `eye_slash`), клик переключает EchoMode.
   - Поиск — pill radius 22 bg `surface_container_high` без рамки, leading-лупа,
     trailing-крестик только при непустом тексте (клик — очистка).
   - Многострочный — `QTextEdit` 110px radius 4 outlined + placeholder через
     `palette.setColor(PlaceholderText, …)` + счётчик символов справа.
   - Иконки: `_field_icon` (лупа/крестик рисуются) или `_svg_icon` — перед рендером
     `currentColor` заменяется на `theme.on_surface_variant` (см. капкан).

4. **Чат** — см. раздел 8.

5. **Файлы** — см. раздел 9.

6. **Настройки** — «Внешний вид» (MdSwitch «Тёмная тема» → `_on_theme_toggled`;
   метка «Размер интерфейса» сверху + `MdSegmentedControl` [Компактный/Средний/Крупный],
   default=1), «Поведение» (MdSwitch Автообновления ✓, Анимации ✓), комбобокс «Язык
   интерфейса» (44px, outlined r4; popup `QAbstractItemView` — `surface_container`,
   рамка `outline_variant`, r8, item 40px, selection `secondary_container` /
   `on_secondary_container`), MdSlider «Скорость анимаций»=50.

---

## 8. Чат (страница «Чат»)

- Контейнер — прозрачный `QScrollArea` (frameless; QSS `background: transparent` +
  `viewport().setStyleSheet(...transparent)` + внутренний QWidget прозрачный).
- Сообщения в `self._chat_messages: list[(text, mine_bool, ts_str)]` — **переживают смену
  темы**. При первом показе — 2 стартовых сообщения.
- Строка: QWidget VBox (пузырь + растяжка по стороне) + (время 11px `on_surface_variant`,
  `padding 0 4px`, по той же стороне). Пузыри `QFrame#Bubble` maxWidth 430, минимальная
  ширина считается по `fontMetrics` от текста (`horizontalAdvance(text) + 32`, кап 430) —
  без этого wordWrap-QLabel отдаёт узкий sizeHint и пузырь ломается на лишние строки;
  margins (16,10,16,10), шрифт 14, selectable:
  - свои: bg `primary_container`, текст `on_primary_container`, радиусы (tl,tr,bl,br)
    = 16,16,16,4 (хвост снизу-справа);
  - чужие: bg `surface_container_high`, текст `on_surface`, радиусы 16,16,4,16
    (хвост снизу-слева), без рамки.
- Вставка: VBox с последним `addStretch(1)`; новые строки в индекс `count()-1`.
  «Живая» вставка анимируется opacity 0→1 (200мс), эффект снимается по finished; при
  пересборке истории — без анимации.
- Ввод: `QLineEdit` 44px (`returnPressed`) + `MdButton("Отправить")` (filled). Над вводом —
  «печатает…» (12px `on_surface_variant`) справа.
- `_on_chat_send`: непустой текст → очистить поле, `(text, True, now)`, вставить пузырь,
  `_schedule_chat_reply()`, проскроллить. `_schedule_chat_reply`: флаг+лейбл «печатает»,
  ответ из `REPLIES` по `_reply_i`, задержка `700 + (i%3)*400` мс; `_append_chat_reply`:
  спрятать «печатает», `(text, False, now)`, вставить, проскроллить. Флаг/метка переживают
  пересборку. Прокрутка: `verticalScrollBar().setValue(maximum())` + `QTimer.singleShot(0)`.

---

## 9. Файлы (страница «Файлы») — drag & drop

- `FileDropArea` (см. класс) + под ней `QListWidget` 110px (`InternalMove` + `MoveAction` +
  `ExtendedSelection`), счётчик «N файл/файла/файлов» (морфология: 1 → файл, 2-4 → файла,
  ≥5 → файлов).
- Список принятых файлов в `self._dropped_files: list[str]` (имена через `Path(f).name`),
  переживает смену темы; `drop.dropped` → замыкание кладёт имена и перерисовывает список.
- Пустой `QListWidget` принятых файлов скрыт (`setVisible(n > 0)`) — вместо мёртвой зоны
  в карточке показывается подсказка «Пока нет файлов — перетащите что-нибудь в область выше».
- Стиль списка (`_list_style`): transparent bg, item padding 10px 12px radius 8,
  hover `surface_container_high`, selected `secondary_container` / `on_secondary_container`.
- Вторая карточка «Переупорядочивание» — демо-список из 5 файлов (150px, `InternalMove`)
  с подсказкой.

---

## 10. Смена темы и сворачивание панели

### Смена темы (`_on_theme_toggled`)
Только мгновенная пересборка — **никакого fade** центрального виджета (прозрачное окно
просвечивало бы десктоп):
```python
def _on_theme_toggled(self, is_dark: bool) -> None:
    self._stop_anims()
    self.theme = DARK if is_dark else LIGHT
    old_central = self.takeCentralWidget()
    if old_central is not None:
        old_central.deleteLater()
    self._build_ui()
```
Состояние, переживающее пересборку (атрибуты MainWindow): `_current_page`,
`_sidebar_collapsed`, `_chat_messages`, `_chat_typing`, `_reply_i`, `_dropped_files`.
`_stop_anims()` останавливает висящие анимации (иначе crash при deleteLater).

### Сворачивание панели (`toggle_sidebar` / `_animate_sidebar`)
`QParallelAnimationGroup` анимирует `minimumWidth`+`maximumWidth` drawer (220→0) и
разделителя (1→0), `DUR_MED`/`EASE`. Глиф `SidebarToggle` синхронизируется через
`_title_bar.sidebar_toggle.set_collapsed(...)`.

### Переход между страницами (`switch_page`)
`QStackedWidget` + `QGraphicsOpacityEffect` на обе страницы: prev 1→0, next 0→1 параллельно
(`DUR_MED`), по завершении эффекты снимаются, ссылка на группу в `_page_anim`.

---

## 11. Капканы PyQt6 на Windows — проверяй первым делом

0xC0000409 / 0xC0000005 в PyQt6 + Python 3.12 на Windows — обычно один из этих случаев:

1. **`QPen.setAlpha` не существует** — это метод `QColor`. Правильно:
   `color = QColor(...); color.setAlpha(90); pen = QPen(color)`.
2. **`QPainter.drawLine` только int-координаты** → иначе 0xC0000409. При этом
   `drawEllipse(QPointF, r, r)`, `drawRoundedRect(QRectF)`, `drawPath` со float безопасны.
3. **Альфа в QSS `rgba()` — 0..255.** Для «8%» пиши alpha ≈ 20.
4. **`Qt.Edge` не конвертируется в `int`** и не смешивается с `int` через `|` (раздел 4).
5. **`QSvgRenderer` игнорирует `fill="currentColor"`** — замени строкой до рендера:
   `svg.replace("currentColor", theme.on_surface_variant)`.
6. **QSS `:hover` мгновенный** — плавность только через `Q_PROPERTY` +
   `QPropertyAnimation` + ручной `paintEvent`.
7. **`WA_StyledBackground`** обязателен на виджете с QSS-фоном.
8. **QBoxLayout стрейч:** строка label+control — если control растягивается, то
   `addWidget(control, stretch)` и **без** `addStretch`.
9. **Держи ссылку на анимации** (`self._anim = ...`), иначе GC соберёт их до конца.
10. **`app.setStyle("Fusion")`** — иначе native-стиль местами игнорирует QSS.
11. **Никаких try/except вокруг `paintEvent`** как «защиты» — процесс умирает раньше;
    просто корректный код + smoke-тест.

---

## 12. Проверка после любых изменений (smoke-тест)

Перед сдачей прогони (временный скрипт рядом с файлом, потом удалить):
- QApplication + MainWindow, `show()`, `processEvents()` — без исключений;
- клики по кнопкам NavigationDrawer по всем 6 страницам (проверять синхронность
  `stack.currentIndex`, checked-кнопки и `_current_page`; прямой `switch_page` обходит
  навигацию) — без трейсбэков;
- `_on_theme_toggled(True)` и `(False)` — пересборка, `_current_page` сохраняется;
- повторить цикл страницы→тема 3 раза без дублирования сообщений/файлов;
- чат: `_on_chat_send()` с текстом → сообщение + очистка поля, через ~1.5с + processEvents
  приходит ответ, «печатает» гаснет, история переживает смену темы;
- файлы: `area.dropped.emit([...])` → имена в списке, переживают смену темы;
- ресайз: `_resize_edges_for` для краёв/углов/центра (центр = 0);
- задачи: чекбоксы + прогресс + tonal-«Сбросить»; sidebar collapse/expand;
- скриншоты `window.grab()` — 12 штук в `assets/_qa/`:
  `{light,dark}_{overview,tasks,input,chat,files,settings}.png`.
Процесс не должен падать нативно; при падении — чинить и перезапускать до чистого прогона.
Скрипт после чистого прогона удалить, скриншоты оставить.

Чек-лист «на глаз»: ролевые пары контрастны в обеих темах; state layers/ripple заметны;
анимации ≤ ~300мс (ripple 450); окно таскается за TopAppBar, ресайзится за края; карточки
не обрезаны (запас 12px под тень); скроллбары тонкие; drawer-pill и сегмент-индикатор
переезжают плавно.

---

## 13. Проверка соответствия эталону

- [x] Frameless + translucent + `QFrame#Panel` со скруглением 16 и тенью.
- [x] Material-кнопки окна (min/max/close), close на hover — error; порядок справа.
- [x] Перетаскивание за TopAppBar (`startSystemMove`), double-click — разворот.
- [x] Ресайз за края/углы (`startSystemResize`, EDGE_MARGIN 12) + курсоры.
- [x] Сворачивание drawer с анимацией ширины и сменой глифа SidebarToggle.
- [x] MdButton filled/tonal с state layer + ripple; MdSwitch/MdSlider/MdCheckBox/
      MdSegmentedControl анимированы (не QSS-hover).
- [x] 6 страниц с перечисленным контентом; fade-переходы.
- [x] Смена темы — мгновенная пересборка; чат и файлы сохраняются.
- [x] Чат с MD3-пузырями, временем, «печатает…», автоответом.
- [x] Drag & drop файлов + переупорядочивание списком.
- [x] Ролевая палитра MD3 (primary/on-primary/containers), текст через on-роли.
- [x] Скроллбары тонкие во всех страницах.
- [x] Ни одного из капканов раздела 11 в коде.