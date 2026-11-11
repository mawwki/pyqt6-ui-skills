---
name: pyqt6-macos-ui
description: Build, redesign, or restyle a desktop GUI app in PyQt6/PySide6 so it looks and feels like a polished macOS app (frameless window, traffic lights, sidebar, cards with soft shadows, animated micro-interactions, light/dark themes). Use whenever the user asks to make a desktop UI "красиво/стильно", "в стиле macOS/Mac", "современный интерфейс", "frameless window", "как в macOS", "сделай как в этом приложении" (referring to assets/app_template.py), or wants animations, blur/vibrancy, sidebar navigation, toggles, sliders, chat, drag&drop. Contains the exact build spec of the reference app app_template.py (tokens, per-widget geometry/timing/colors, interaction logic, page set) plus the must-know PyQt6-on-Windows crash pitfalls. Consult before writing any PyQt6/PySide6 UI code so the result doesn't look like a default Qt app.
---

# PyQt6 в стиле macOS — спецификация эталонного приложения

Ниже — полная спецификация, по которой можно воспроизвести `assets/app_template.py`
побайтно по поведению. Моделируй агента-дизайнера интерфейсов из студии, которая делает
macOS-style десктоп-приложения: сдержанная палитра, один акцентный цвет, мягкий свет,
анимации ровно там, где они объясняют, что произошло, — и не больше.

Главное правило: **«стиль macOS» в Qt — это не нативный API, а воссозданная руками эстетика**:
frameless-окно + собственный QSS + `QPropertyAnimation` для плавности. Так приложение
выглядит одинаково на Windows, Linux и macOS. Native style Qt не даёт скруглений,
полупрозрачности и анимаций.

Референс-реализация — `assets/app_template.py` (один файл). Задача агента: либо скопировать
и адаптировать его, либо пересобрать с нуля точно по этому документу.

---

## 1. Быстрый старт

```text
pip install PyQt6
python app_template.py
```

Сборка для пользователя: `pyinstaller --windowed --icon=app.icns app_template.py`.

Приложение запускается так:
```python
def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")                       # единственный стиль, уважающий QSS везде
    app.setFont(system_font(10, QFont.Weight.Normal))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

---

## 2. Структура файла app_template.py (порядок важен для читаемости)

1. Импорты: `sys`, `time`, `dataclasses`, `pathlib.Path`; QtCore (`Qt`, `QEvent`,
   `QPropertyAnimation`, `QEasingCurve`, `QRect( F)`, `QPointF`, `QParallelAnimationGroup`,
   `QVariantAnimation`, `QTimer`, `pyqtProperty`, `pyqtSignal`); QtGui (`QColor`, `QFont`,
   `QPainter`, `QFontDatabase`, `QPen`, `QPixmap`, `QIcon`, `QPalette`); QtSvg (`QSvgRenderer`);
   QtWidgets (все нужные виджеты).
2. Дизайн-токены: `Theme` (dataclass), `LIGHT`/`DARK`, константы радиусов/длительностей,
   `REPLIES`, `SVG_EYE`/`SVG_EYE_SLASH`, `PAGES`.
3. Хелперы: `system_font`, `rgba`, `accent_fg`, `shadow_color`.
4. Кастомные виджеты в порядке зависимостей: `HoverButton`, `ToggleSwitch`, `MacSlider`,
   `SegmentedControl`, `FileDropArea`, `TrafficLight`, `SidebarToggle`, `TitleBar`, `Sidebar`.
5. `build_stylesheet(theme)`.
6. `MainWindow` + `main()`.

---

## 3. Дизайн-токены (точные значения)

`Theme` — frozen dataclass с полями: `bg`, `surface`, `sidebar`, `text`, `text_secondary`,
`accent`, `separator_rgb` (строка `#000000`/`#FFFFFF` — база для `rgba()`), `separator_alpha`
(0..255), `shadow_alpha` (0..255).

```python
LIGHT = Theme(bg="#F5F5F7", surface="#FFFFFF", sidebar="#ECECEF", text="#1D1D1F",
              text_secondary="#6E6E73", accent="#1D1D1F",
              separator_rgb="#000000", separator_alpha=20, shadow_alpha=55)
DARK  = Theme(bg="#1E1E1E", surface="#2A2A2C", sidebar="#242426", text="#F5F5F7",
              text_secondary="#98989D", accent="#CFCFD4",
              separator_rgb="#FFFFFF", separator_alpha=20, shadow_alpha=150)
```

Важно: **акцент в этом приложении не синий**. Он «инвертированный» — чёрный
`#1D1D1F` в светлой теме и светлый `#CFCFD4` в тёмной (это даёт тот же контраст, что
System Blue, но в чёрно-белой гамме). Любой код, который кладёт текст поверх акцента,
обязан использовать `accent_fg(theme)`, а не хардкод.

```python
def accent_fg(theme: Theme) -> str:
    color = QColor(theme.accent)
    luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255
    return "#1D1D1F" if luminance > 0.6 else "#FFFFFF"

def rgba(hex_color: str, alpha_0_255: int) -> str:
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha_0_255})"
```

Константы:
- `RADIUS_WINDOW = 14`, `RADIUS_CARD = 12`, `RADIUS_CONTROL = 8`, `SIDEBAR_WIDTH = 196`.
- `EDGE_MARGIN = 6`, бит-маски краёв `EDGE_TOP, EDGE_BOTTOM, EDGE_LEFT, EDGE_RIGHT = 1, 2, 4, 8`.
- `DUR_FAST = 140` (hover/press), `DUR_MED = 250` (страницы, сайдбар, тумблер, сегменты),
  `EASE = QEasingCurve.Type.OutCubic`.
- `PAGES = ["Обзор", "Задачи", "Ввод", "Чат", "Файлы", "Настройки"]`.
- `REPLIES` — 5 коротких ответов бота.
- `SVG_EYE` (Heroicons, viewBox 0 0 24 24, `fill="currentColor"`) и `SVG_EYE_SLASH`
  (Bootstrap, viewBox 0 0 16 16) — многострочные строки.

Шрифт: цепочка фоллбэков в `system_font()` — `Inter` → `Segoe UI Variable Text` →
`.AppleSystemUIFont` → `SF Pro Text` → `Helvetica Neue` → `Manrope` → `Segoe UI`;
плюс `setStyleStrategy(QFont.StyleStrategy.PreferAntialias)`.

Отступы из шкалы 4/8/12/16/20/24/32. Тени мягкие: карточки — `blurRadius 24`,
`offset (0,5)`, цвет `shadow_color(theme)` (чёрный с `shadow_alpha`).

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

Дерево (`_build_ui`): `QMainWindow` → `root (QWidget)` → `panel (QFrame, objectName "Panel")` →
`TitleBar (40px)` + `body (QHBoxLayout)` → `Sidebar (196px)` + `separator (1px)` + `QStackedWidget`.
Панель получила `build_stylesheet(theme)` — QSS наследуется вниз.

**Тень и скругление живут на дочернем `QFrame#Panel`**, а не на самом окне: окно прозрачное
и даёт отступ под тень. Это принципиально — навешивать эффект на `QMainWindow` нельзя.

### Перетаскивание и ресайз

Двигать окно — нативный механизм Qt6, никакой ручной математики смещения:
```python
def mousePressEvent(self, event):   # в TitleBar
    if event.button() == Qt.MouseButton.LeftButton:
        handle = self._window.windowHandle()
        if handle is not None:
            handle.startSystemMove()
```

Менять размер за края — тоже нативный `QWindow.startSystemResize`. В `MainWindow`
установлен **фильтр событий на `QApplication`**, который:
- на `MouseButtonPress` (Left) в зоне ≤ `EDGE_MARGIN` от края окна вызывает
  `_start_system_resize(edges)` и возвращает `True` (событие съедается);
- на `MouseMove` без кнопок обновляет курсор окна;
- на `Leave` сбрасывает курсор.

`_resize_edges_for(pos)` переводит глобальную позицию в бит-маску краёв; работает только
если окно видимо и не максимизировано. `_cursor_for_edges(edges)`: центр → `Arrow`; лево/право
→ `SizeHor`; верх/низ → `SizeVer`; верх+лево или низ+право → `SizeFDiag`; иначе → `SizeBDiag`.

**Капкан PyQt6:** `Qt.Edge` нельзя превратить в `int` и нельзя смешивать с `int` оператором `|`
(TypeError). Поэтому вся математика краёв — на своих бит-константах `EDGE_*`, а флаг для
`startSystemResize` собирается так:

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

### HoverButton (кнопка с плавным hover/press)
- `QPushButton`, `setFlat(True)`, высота 34, шрифт 13/Medium, `padding 0 18px`,
  radius `RADIUS_CONTROL`.
- Текст в QSS: `color: {accent_fg(theme)}` (не жёстко «white»!).
- Подложка — не QSS `:hover` (мгновенный), а `Q_PROPERTY alpha` (float, 0..1): в `paintEvent`
  красятся акцентный `QColor` с `setAlphaF(alpha)` + скруглённый прямоугольник, потом
  `super().paintEvent()` рисует текст. События: enter → 0.85, leave → 1.0,
  press → 0.7, release → 0.85/1.0. Анимация `DUR_FAST`, `EASE`.

### ToggleSwitch (тумблер macOS)
- `QWidget` 42×24, сигнал `toggled(bool)`, обработчик только по левой кнопке.
- `Q_PROPERTY knobPos` (float 0..1) анимируется `DUR_MED`/`EASE`.
- Отрисовка: трек скруглённый (radius = h/2), цвет интерполируется между `#B9B9BE` (выкл)
  и `accent` (вкл); ручка — кругл. `QColor(self._theme.bg)`, диаметр `h-4`,
  позиция `x_min = 2`, `x_max = width - knob_d - 2`.
- **Капкан:** ручка красится `theme.bg`, а не белым — в тёмной теме белая ручка сливается
  с белым выключенным треком.
- Программный `setChecked` только анимирует, сигнал НЕ эмитит (эмитятся в `mousePressEvent`).

### MacSlider (слайдер macOS)
- `QWidget` высота 28, `Q_PROPERTY knobScale` (1.0 → 1.12 hover, 0.94 press), `DUR_FAST`.
- Значение из x: `ratio = (x - pad) / (width - 2*pad)`, `pad = 9.5`.
- Отрисовка: трек высота 6 (фон `separator` с alpha 26, заполнение — `accent`), кружок
  9.5px: glow (`accent`, alpha 22 hover / 34 press, радиус +4), тень (чёрный alpha 26),
  сам кружок `theme.bg` с ободком `separator` alpha 90 (255 при pressed), `penWidth 1.2`.

### SegmentedControl (сегменты «Компактный/Средний/Крупный»)
- `QWidget` высота 30; кнопки высота 26, шрифт 12, `padding 0 16px`, box `spacing 4`, margins 4.
- «Пилюля» — `QFrame#SegIndicator` (bg `accent`, radius 7) позади кнопок в той же раскладке,
  перемещается `QPropertyAnimation(geometry)` `DUR_MED`/`EASE`.
- Цвет текста: у выбранной `accent_fg(theme)`, у остальных `text_secondary`.
- В `showEvent` пилюлю опустить вниз (`lower()`) и выставить на геометрию выбранной кнопки.

### TrafficLight (светофор)
- `QPushButton` 22×22, `Q_PROPERTY hover` (0..1) анимация `DUR_MED`.
- **Без рамок-цветов жёлтого/зелёного**: close — красный `#FF5F57` (alpha 200 + 35·hover),
  minimize/zoom — нейтральный `rgba(text_secondary, 60 + 40·hover)`.
- Глифы рисуются `QPen` с `RoundCap`, шириной 2, **только целочисленные координаты** (см. капканы):
  - close — крестик из двух линий;
  - minimize — шеврон вниз: `(cx-5,cy-3)-(cx,cy+3)-(cx+5,cy-3)`;
  - maximize (не развёрнуто) — шеврон вверх: `(cx-5,cy+3)-(cx,cy-3)-(cx+5,cy+3)`;
  - maximize в развёрнутом состоянии (`_maximized`) — 8 линий четырёх уголков-скобок.
- Цвет глифа: для close — белый alpha 205+30·hover; для остальных — интерполяция
  `text_secondary → text` по hover.

### SidebarToggle (кнопка сворачивания панели)
- `QPushButton` 22×22, `hover` 0..1, hover-bg `rgba(separator,26)`, глиф интерполирует
  `text_secondary → text`.
- Глиф открытой панели (Lucide `panel-left-close`): рамка `drawRoundedRect(QRectF(cx-7, cy-7, 14, 14), 2, 2)`,
  вертикальный разделитель на `cx-2`, шеврон `<` из `(cx+4, cy-2)→(cx, cy)→(cx+4, cy+2)`.
- Глиф свёрнутой (Lucide `panel-right`): рамка + разделитель на `cx+2`, шеврона нет.
- `set_collapsed(bool)` переключает глиф; состояние синхронизирует `MainWindow.toggle_sidebar`.

### Sidebar (навигация)
- `QWidget` `setFixedWidth(SIDEBAR_WIDTH)`, margins `10,16,10,16`, spacing 2.
- Бренд «МойПроект» (13/Bold, `padding: 0 8px 14px 8px`).
- Названия страниц — `QPushButton#NavButton` высоты 30, шрифт 13, `checkable`,
  неактивная — `text_secondary`, активная — `text`. Индикатор — `QFrame` радиус 8,
  bg `rgba(accent,40)`, анимируется по `geometry` к выбранной кнопке (`DUR_MED`).
- Неактивный клик по текущей странице — no-op. В `showEvent` индикатор ставится без анимации.

---

## 6. Общий QSS (`build_stylesheet`)

- `#Panel` — bg темы, radius окна. `#TitleBar` — прозрачный. `#Sidebar` — bg сайдбара.
- `#Indicator` — rgba(accent, 40), radius 8.
- `QPushButton#NavButton` — слева выравнивание, radius 8, padding-left 10; `:checked` — `text`;
  `:hover` — rgba(separator,26).
- `QPushButton#ToolButton` — вторичный цвет, radius 6, hover подсветка.
- **Скроллбары** (добавляются глобально, чтобы чат и списки не были «толстыми»):
  вертикаль/горизонталь 8px, handle radius 3 `rgba(separator,60)` (hover 120), min 30,
  стрелки и страницы — прозрачные.
- Выставлять `setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)` на любой виджет
  с QSS-фонами.

---

## 7. Страницы (6 штук)

Компонуется через `_page_shell(theme, title)` (margins 28/24/28/24, spacing 16, заголовок
22/Bold) и `_add_card(theme, layout, title)` (карточка + заголовок 14/DemiBold + shadow).

1. **Обзор** — карточка «Система» (тумблеры: Автозапуск ✓, Уведомления ✓, Энергосбережение ✗)
   и «Отображение» (слайдеры Яркость=70, Громкость=45). Строка слайдера — label слева,
   control справа с `control_stretch=1` (см. капкан про stretch).

2. **Задачи** — 4 `QCheckBox` с индикатором 18×18 (border`rgba(separator,120)`, hover →
   `accent`, checked → bg `accent`); прогресс-бар (12px, chunk `accent`), счётчик
   «Выполнено N из M», анимация `QProgressBar` через `QVariantAnimation` (280мс);
   кнопка `HoverButton("Сбросить")`.

3. **Ввод** — поля:
   - Имя, E-mail — обычный `QLineEdit` (34px, radius 8, hover рамка `rgba(sep,140)`,
     focus → рамка `accent` + tint `rgba(accent,8)`, placeholder `text_secondary`,
     selection `accent`+`accent_fg`).
   - Пароль — `_build_password_field`: trailing-действие «глаз» — иконка меняется
     `eye` ↔ `eye_slash`, клик переключает `EchoMode.Password` ↔ `Normal`.
   - Поиск — `_build_search_field`: pill-radius 17, leading-иконка увеличения, trailing-иконка
     крестика, видимая только при непустом тексте (клик — очистка).
   - Многострочный — `QTextEdit` (radius 10, placeholder через
     `palette.setColor(QPalette.ColorRole.PlaceholderText, ...)` — QSS-селектор
     `QTextEdit[placeholderText]` ненадёжен) + счётчик символов справа.
   - Иконки полей рисуются в `_field_icon` (18px: лупа = круг+f-ручка; крестик = кружок
     `rgba(text_secondary,110)` + «✕» цветом `theme.bg`) либо рендерятся из SVG (`_svg_icon`):
     перед рендером в SVG заменяется `currentColor` на `theme.text_secondary` (см. капкан).

4. **Чат** — см. раздел 8.

5. **Файлы** — см. раздел 9.

6. **Настройки** — карточка «Внешний вид» (тумблер «Тёмная тема» → `_on_theme_toggled`,
   сегмент «Размер интерфейса»), «Поведение» (тумблеры Автообновления ✓, Анимации ✓),
   комбобокс «Язык интерфейса» (QSS: поле `surface`+рамка, `QAbstractItemView` —
   `selection-background-color: accent; selection-color: accent_fg`), слайдер
   «Скорость анимаций»=50.

---

## 8. Чат (страница «Чат»)

- Контейнер — прозрачный `QScrollArea` (frameless; чтобы не было белого фона: QSS
  `background: transparent` + `viewport().setStyleSheet(...transparent)` + внутренний
  `QWidget` прозрачный).
- Сообщения хранятся в `self._chat_messages: list[(text, mine_bool, ts_str)]` — **переживают
  смену темы** (пересборка страницы заново отрисовывает их). При первом показе — 2 стартовых
  сообщения.
- Строка сообщения: QWidget с VBox: (пузырь + растяжка по стороне) + (время 11px
  `text_secondary`, `padding 0 4px`, по той же стороне). Пузыри `QFrame#Bubble` maxWidth 430:
  - свои: bg `accent`, текст `accent_fg`, радиусы `16, 4, 16, 4` (tl,tr,bl,br);
  - чужие: bg `surface` + рамка `rgba(separator,70)`, текст `text`, радиусы `16, 16, 4, 16`.
- Вставка: `QQVBoxLayout(msgs)` с последним `addStretch(1)`; новые строки вставляются
  в индекс `count()-1` (перед растяжкой) — порядок правильный, растяжка внизу.
- Ввод: `QLineEdit` 36px (с `returnPressed`) + `HoverButton("Отправить")`. Над вводом —
  строка «печатает…» (12px, `text_secondary`), справа.
- Отправка `_on_chat_send`: непустой текст → очистить поле, `(text, True, now)` в историю,
  вставить пузырь, `_schedule_chat_reply()`, проскроллить вниз.
- Ответ бота `_schedule_chat_reply`: выставить флаг «печатает» + показать лейбл, выбрать
  ответ из `REPLIES` по счётчику `_reply_i`, отложить `700 + (i%3)*400` мс через
  `QTimer.singleShot`; `_append_chat_reply` —спрятать «печатает», `(text, False, now)`,
  вставить, проскроллить. Метка и флаг переживают пересборку темы.
- Прокрутка вниз: `verticalScrollBar().setValue(bar.maximum())` через `QTimer.singleShot(0)`
  после сборки.

---

## 9. Файлы (страница «Файлы») — drag & drop

- `FileDropArea(QFrame)` (см. класс): minHeight 150, `setAcceptDrops(True)`, пунктирная рамка
  `2px dashed rgba(separator,90)`, radius 14, фон `rgba(separator,10)`; при перетаскивании
  (`dragEnterEvent` с `hasUrls()`) — рамка `accent` alpha 200 и фон `rgba(separator,26)`;
  `dropEvent` извлекает `u.toLocalFile()` (только `isLocalFile()`) и эмитит `dropped(list[str])`;
  клик (`mouseReleaseEvent`) — `QFileDialog.getOpenFileNames`.
- Загрузка-зона: внутренний текст «Перетащите файлы сюда / или нажмите, чтобы выбрать».
- Под ней `QListWidget` (110px, `InternalMove` + `MoveAction` — файлы можно переупорядочивать),
  счётчик «N файл/файла/файлов» (русская морфология: 1 → файл, 2-4 → файла, ≥5 → файлов).
- Список принятых файлов живёт в `self._dropped_files: list[str]` (имена через `Path(f).name`),
  переживает смену темы; `drop.dropped` коннектится к замыканию, которое кладёт новые имена
  в список и перерисовывает `QListWidget`.
- Вторая карточка «Переупорядочивание» — демо-список из 5 файлов (`QListWidget` 150px,
  `InternalMove`) с подсказкой.

---

## 10. Смена темы и сворачивание панели

### Смена темы (`_on_theme_toggled`)

Окно умеет только мгновенную пересборку — **никакого fade прозрачности** центрального виджета:
фокус на `WA_TranslucentBackground` просвечивает десктоп во время opacity-анимации.

```python
def _on_theme_toggled(self, is_dark: bool) -> None:
    self._stop_anims()
    self.theme = DARK if is_dark else LIGHT
    old_central = self.takeCentralWidget()
    if old_central is not None:
        old_central.deleteLater()
    self._build_ui()
```

Состояние, которое переживает пересборку (держать атрибутами `MainWindow`): `_current_page`,
`_sidebar_collapsed`, `_chat_messages`, `_chat_typing`, `_reply_i`, `_dropped_files`.
`_stop_anims()` останавливает все висящие QPropertyAnimation (иначе Python может собрать
их объекты во время deleteLater → crash).

### Сворачивание панели (`toggle_sidebar` / `_animate_sidebar`)

`QParallelAnimationGroup` анимирует `minimumWidth` и `maximumWidth` сайдбара (196 → 0) и
разделителя (1 → 0) одновременно, `DUR_MED`/`EASE`. Иконка `SidebarToggle` синхронизируется
через `_title_bar.sidebar_toggle.set_collapsed(...)`.

### Переход между страницами (`switch_page`)

`QStackedWidget` + `QGraphicsOpacityEffect` на обе страницы: prev 1→0, next 0→1 параллельно
(`QParallelAnimationGroup`, `DUR_MED`), по завершении эффекты снимаются
(`setGraphicsEffect(None)`) и ссылку на группу держим в `_page_anim`.

---

## 11. Капканы PyQt6 на Windows — проверяй первым делом

0xC0000409 / 0xC0000005 (fast-fail access violation) в PyQt6 + Python 3.12 на Windows — это
обычно один из этих случаев. Смотри сюда сразу, как только падает нативный код:

1. **`QPen.setAlpha` не существует.** Это метод `QColor`, а не `QPen`. `pen.setAlpha(90)` →
   AttributeError внутри `paintEvent`, вызванного из Qt, → аварийный выход `0xC0000409`.
   Правильно:
   ```python
   color = QColor(...)
   color.setAlpha(90)
   pen = QPen(color)
   ```
2. **`QPainter.drawLine` с нецелочисленными координатами** → `0xC0000409`. Всегда передавай
   `int` (или `QPoint`): `painter.drawLine(int(a), int(b), int(c), int(d))`. При этом
   `drawEllipse(QPointF(...), r, r)`, `drawRoundedRect(QRectF(...))`, `drawRect` со float
   безопасны.
3. **Формат альфы в QSS.** Qt QSS-`rgba()` ожидает альфу **0..255**. Для «8%» пиши alpha ≈ 20.
4. **`Qt.Edge` не конвертируется в `int`** и не смешивается с `int` через `|` (см. раздел 4).
5. **`QSvgRenderer` игнорирует `fill="currentColor"`** — рисует чёрным. До рендера замени
   `currentColor` на нужный hex строкой: `svg.replace("currentColor", color)`.
6. **QSS `:hover` мгновенный** — плавность только через `Q_PROPERTY` + `QPropertyAnimation` +
   ручной `paintEvent`.
7. **`WA_StyledBackground`** обязателен на виджете, которому задаёшь QSS-фон.
8. **QBoxLayout стрейч:** свободное место сначала уходит ненулевым stretch-факторам, потом
   Expanding-виджетам. `addStretch(1)` в строке со слайдером съедал всю ширину у holder
   слайдера. Правило строки label+control: если control должен растянуться — `addWidget(control,
   stretch)` и **без** `addStretch`.
9. **Держи ссылку на анимации** (`self._anim = ...`), иначе QPropertyAnimation собирается
   сборщиком до конца анимации.
10. **`app.setStyle("Fusion")`** — иначе native-стиль местами игнорирует QSS.
11. **Не передавай необработанные AttributeError «наружу» из paint — окно падает жёстко.**
    Любой новый рисующий код прогоняй через smoke-тест (ниже), не полагайся на try/except
    вокруг `paintEvent`, он не поможет — процесс умирает раньше.

---

## 12. Проверка после любых изменений (smoke-тест)

Перед сдачей прогони (агент может написать такой же):

- приложение строится и показывает окно без исключений;
- поочерёдно `switch_page` по всем 6 страницам — без трейсбэков;
- переключение темы в обе стороны (`_on_theme_toggled(True/False)`) пересобирает окно,
  `_current_page` сохраняется;
- чат: `_on_chat_send()` добавляет сообщение, поле очищается, через `time.sleep(1.5+)` +
  `processEvents()` приходит ответ, история переживает смену темы;
- файлы: эмуляция drop через
  `area.dropped.emit([r'C:\tmp\a.pdf', r'C:\tmp\b.png'])` добавляет имена в список,
  список переживает смену темы;
- ресайз: `_resize_edges_for` корректно возвращает биты для краёв и углов, центр — 0;
- иконки-глаза: `.pixmap(18,18).toImage()` содержит непрозрачные пиксели
  (>20 шт. — рендер не пустой) в обеих темах.

Чек-лист «на глаз»: один акцентный цвет; контраст текста на акценте через `accent_fg`
проверен в обеих темах; все UI-анимации ≤ ~300мс; окно таскается за тулбар, ресайзится
за края, сворачивается/разворачивается; карточки не обрезаны (запас под тень); скроллбары
тонкие.

---

## 13. Проверка соответствия эталону

Если агент пересобирает приложение с нуля, сверяй по этому списку (это и есть «всё, как в
приложении»):

- [x] Frameless + translucent + Panel QFrame со скруглением и тенью.
- [x] Светофор: красный close, нейтральные min/zoom, глиф-корнбрекеты при развороте.
- [x] Перетаскивание за тулбар (`startSystemMove`) и двойной клик — разворот.
- [x] Ресайз за все края и углы (`startSystemResize`, EDGE_MARGIN 6) + курсоры.
- [x] Сворачивание сайдбара с анимацией ширины и сменой глифа `SidebarToggle`.
- [x] Анимированный hover/press у кнопок (не QSS), анимированный тумблер, слайдер, сегменты.
- [x] 6 страниц с перечисленным контентом; fade-переход между ними.
- [x] Смена темы — мгновенная пересборка; история чата и принятые файлы сохраняются.
- [x] Чат с пузырями, временем, «печатает…», автоответом бота.
- [x] Drag & drop файлов в область + переупорядочивание списком.
- [x] Акцент чёрный/светлый (не синий), текст на акценте — через `accent_fg`.
- [x] Скроллбары тонкие, во всех страницах.
- [x] Ни одного из капканов раздела 11 в коде.