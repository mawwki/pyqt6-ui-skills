# PyQt6 UI Skills

Три скилла для ИИ-агентов и три эталонных десктоп-приложения на PyQt6/PySide6:
**macOS**, **Material Design 3** и **glassmorphism**. Каждый скилл — это `SKILL.md`
с полной спецификацией интерфейса и `assets/app_template.py` — готовый каркас
приложения в один файл, который можно скопировать и адаптировать или пересобрать
с нуля по спецификации.

Все скины — frameless-окна с собственным QSS и анимациями на `QPropertyAnimation`,
светлая и тёмная темы, одинаковый вид на Windows, Linux и macOS.

## Скины

### macOS — `pyqt6-macos-ui`

Сдержанная палитра, один акцентный цвет, traffic lights, сайдбар, карточки с мягкими
тенями, анимированные микро-взаимодействия.

| Light | Dark |
| --- | --- |
| <img src="pyqt6-macos-ui/assets/screenshots/overview_light.png" width="460"> | <img src="pyqt6-macos-ui/assets/screenshots/overview_dark.png" width="460"> |

### Material Design 3 — `pyqt6-md3-ui`

Ролевая палитра MD3 (primary / containers / surface / outline), state layers, ripple,
navigation drawer с pill-индикатором, tonal/filled кнопки, MD3 switches/sliders/checkboxes.

#### Обзор

| Light | Dark |
| --- | --- |
| <img src="pyqt6-md3-ui/assets/_qa/light_overview.png" width="460"> | <img src="pyqt6-md3-ui/assets/_qa/dark_overview.png" width="460"> |

#### Задачи

| Light | Dark |
| --- | --- |
| <img src="pyqt6-md3-ui/assets/_qa/light_tasks.png" width="460"> | <img src="pyqt6-md3-ui/assets/_qa/dark_tasks.png" width="460"> |

#### Ввод

| Light | Dark |
| --- | --- |
| <img src="pyqt6-md3-ui/assets/_qa/light_input.png" width="460"> | <img src="pyqt6-md3-ui/assets/_qa/dark_input.png" width="460"> |

#### Чат

| Light | Dark |
| --- | --- |
| <img src="pyqt6-md3-ui/assets/_qa/light_chat.png" width="460"> | <img src="pyqt6-md3-ui/assets/_qa/dark_chat.png" width="460"> |

#### Файлы

| Light | Dark |
| --- | --- |
| <img src="pyqt6-md3-ui/assets/_qa/light_files.png" width="460"> | <img src="pyqt6-md3-ui/assets/_qa/dark_files.png" width="460"> |

#### Настройки

| Light | Dark |
| --- | --- |
| <img src="pyqt6-md3-ui/assets/_qa/light_settings.png" width="460"> | <img src="pyqt6-md3-ui/assets/_qa/dark_settings.png" width="460"> |

### Glassmorphism — `pyqt6-gm-ui`

«Молочное» стекло карточек поверх градиентного фона с настоящим backdrop-blur,
вложенное стекло для строк и полей ввода, тёплый акцент.

#### Задачи

| Light | Dark |
| --- | --- |
| <img src="pyqt6-gm-ui/assets/screenshots/tasks_light.png" width="460"> | <img src="pyqt6-gm-ui/assets/screenshots/tasks_dark.png" width="460"> |

#### Ввод

| Light | Dark |
| --- | --- |
| <img src="pyqt6-gm-ui/assets/screenshots/inputs_light.png" width="460"> | <img src="pyqt6-gm-ui/assets/screenshots/inputs_dark.png" width="460"> |

#### Чат

| Light | Dark |
| --- | --- |
| <img src="pyqt6-gm-ui/assets/screenshots/chat_light.png" width="460"> | <img src="pyqt6-gm-ui/assets/screenshots/chat_dark.png" width="460"> |

#### Файлы

| Light | Dark |
| --- | --- |
| <img src="pyqt6-gm-ui/assets/screenshots/files_light.png" width="460"> | <img src="pyqt6-gm-ui/assets/screenshots/files_dark.png" width="460"> |

#### Настройки

| Light | Dark |
| --- | --- |
| <img src="pyqt6-gm-ui/assets/screenshots/settings_light.png" width="460"> | <img src="pyqt6-gm-ui/assets/screenshots/settings_dark.png" width="460"> |

## Состав репозитория

```
pyqt6-macos-ui/   SKILL.md + assets/app_template.py + скриншоты
pyqt6-md3-ui/     SKILL.md + assets/app_template.py + скриншоты
pyqt6-gm-ui/      SKILL.md + assets/app_template.py + скриншоты
```

## Быстрый старт

```bash
pip install PyQt6
python pyqt6-macos-ui/assets/app_template.py   # или любой другой скилл
```

Сборка: `pyinstaller --windowed --icon=app.ico app_template.py`.

## Как использовать скилл

Скопируйте папку скилла в директорию скиллов вашего агента (например,
`~/.qoder/skills/` или `.claude/skills/` в проекте). Агент читает `SKILL.md`
перед написанием любого PyQt6/PySide6-кода и собирает интерфейс по спецификации:
дизайн-токены, геометрия и тайминги виджетов, логика взаимодействий, набор страниц
и подводные камни PyQt6 на Windows.
