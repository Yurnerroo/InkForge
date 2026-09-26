[English](README.md) | **Українська**

# InkForge

Автоматизація верстки щотижневої газети в Adobe InDesign — від перевірки контенту до готового друк-PDF у кілька кліків.

> Статус: **Рівень 1 (Content Checker) готовий**. Рівень 2 (планувальник верстки) — Python-частина (`inkforge-plan`) готова й покрита тестами; ExtendScript-виконавець для InDesign реалізує геометричне групування статей, relink фото, чергування шрифту заголовка (де підтверджено) і спеціальний випадок для 1 сторінки МІФ (головна стаття + прогноз магнітних бур) — усе для 3 профільованих газет, але ще не перевірено на реальному документі (див. [extendscript/README.md](extendscript/README.md)). Рівень 3 (One-Click Launcher, FastAPI) тепер покриває весь ланцюжок: перевірка → план → верстка в InDesign → експорт друк-PDF, кожен крок — окрема підтверджувана кнопка; обидва COM-кроки (верстка й експорт) ще не перевірені наживо.

## Для кого

Інструмент для людини, яка вже впевнено верстає в Adobe InDesign та Photoshop, але хоче автоматизувати рутинну частину: розкладання підготовлених текстів і фото по вже готових файлах-основах (попередніх випусках), з можливістю ручного доопрацювання після автоматичної верстки.

## Документація

- [docs/requirements.md](docs/requirements.md) — повний перелік зібраних вимог (контент, типографіка, друк, виняткові сторінки).
- [docs/architecture.md](docs/architecture.md) — 4 рівні автоматизації, технологічний стек, знахідки з аналізу реальних IDML-зразків, відкриті питання.
- [docs/content-structure.md](docs/content-structure.md) — конвенція папок/файлів для тижневого випуску.

## Технологічний стек

- **Python** — підготовка та перевірка контенту (`src/inkforge/content_checker`), планування верстки (`src/inkforge/layout_engine`), one-click launcher (Рівень 3).
- **Adobe InDesign ExtendScript/UXP** — власна автоверстка та експорт друк-PDF (Рівень 2), бо це найнадійніше відтворює справжню газетну верстку (CMYK, обріз, PDF/X-1a).

## Структура репозиторію

```
docs/                     вимоги, архітектура, конвенції контенту
profiles/                 по одному YAML-профілю на газету (схема — profiles/schema.md)
src/inkforge/
  content_checker/        Рівень 1: сканування випуску, побудова manifest.json
  layout_engine/          Рівень 2 (Python-частина): manifest.json + профіль -> layout_plan.json
  launcher/               Рівень 3: FastAPI-застосунок, що керує Рівнями 1-2 і InDesign
extendscript/              Рівень 2 (InDesign-частина): виконавець layout_plan.json (частковий)
tests/                    pytest-тести для Python-частини
```

## Рівень 1: Content Checker

Перевіряє папку тижневого випуску (структура — [docs/content-structure.md](docs/content-structure.md)):
зіставляє тексти й фото за іменем файлу, рахує обсяг тексту, читає метадані фото
(розміри, DPI, кольоровий режим), формує звіт про проблеми та `manifest.json` для Рівня 2.

```bash
pip install -e ".[dev]"
inkforge-check path/to/2026-W40_gazeta-x --newspaper "Ти і Я"
```

Це виведе звіт у консоль і запише `manifest.json` у папку випуску
(шлях можна змінити прапорцем `--manifest-out`, або пропустити запис `--no-manifest`).

## Рівень 2: планувальник верстки

Python-частина читає `manifest.json` (з Рівня 1) і профіль газети
(`profiles/<id>.yaml`, схема — [profiles/schema.md](profiles/schema.md)), і
будує `layout_plan.json`: які сторінки автоматизувати, який колірний режим і
пропорційний розподіл простору між статтями. ExtendScript-виконавець для
самого InDesign, що споживає цей план, — ще чорновий (див.
[extendscript/README.md](extendscript/README.md)).

```bash
inkforge-plan path/to/2026-W40_gazeta-x/manifest.json --profile ty_i_ya
```

## Рівень 3: One-Click Launcher

Локальний веб-застосунок на FastAPI, що об'єднує Рівні 1-2 і (за наявності
Windows+InDesign) сам керує InDesign через COM — одна сторінка з кнопками
"Перевірити контент" → "Побудувати план" → "Зверстати в InDesign" →
(ручне доправлення) → "Експорт друк-PDF". Деталі —
[docs/architecture.md](docs/architecture.md), розділ "Рівень 3".

```bash
pip install -e ".[launcher]"
inkforge-launcher
```

Відкриє `http://127.0.0.1:8765` у браузері. Кроки "Перевірити контент" і
"Побудувати план" не залежать від InDesign і повністю покриті тестами; кроки
"Зверстати в InDesign" і "Експорт друк-PDF" (COM-автоматизація) ще не
перевірені на реальному InDesign-встановленні.

Запуск тестів:

```bash
pytest
```