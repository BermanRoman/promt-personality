"""Offline, escaped HTML presentation of an already computed personality report."""

from __future__ import annotations

import math
from datetime import date
from html import escape
from pathlib import Path


SECTIONS = (
    ("human_design", "Human Design"),
    ("gematria", "Гематрия"),
    ("numerology", "Нумерология"),
    ("astrology", "Астрология"),
    ("life_cycles", "Жизненные циклы"),
    ("archetypes", "Архетипы личности"),
    ("purpose", "Карта предназначения"),
    ("finance", "Финансовый потенциал"),
)
DISCLAIMER = "Это инструмент для размышления о себе, а не диагностика и не предсказание"
PLANETS = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto")
PLANET_NAMES = ("Солнце", "Луна", "Меркурий", "Венера", "Марс", "Юпитер", "Сатурн", "Уран", "Нептун", "Плутон")
SIGNS = ("Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева", "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы")
SIGN_ABBREVIATIONS = ("Овн", "Тел", "Блз", "Рак", "Лев", "Дев", "Вес", "Скр", "Стр", "Коз", "Вод", "Рыб")
SECTION_NOTES = {
    "human_design": "Ритм решений и взаимодействия",
    "gematria": "Числовой рисунок имени",
    "numerology": "Числа и жизненные циклы",
    "astrology": "Планеты в момент рождения",
    "life_cycles": "Периоды, пики и вызовы",
    "archetypes": "Мотивы и внутренние роли",
    "purpose": "Связи между результатами",
    "finance": "Гипотезы о работе и доходе",
}

# Decorative editorial artwork: no personal chart or calculated meaning.
ORBITAL_ART = ('<div class="hero-art" aria-hidden="true"><svg viewBox="0 0 400 440" focusable="false">'
               '<circle class="orbit-halo" cx="200" cy="220" r="157"/>'
               '<circle class="orbit-ring" cx="200" cy="220" r="157"/>'
               '<circle class="orbit-ring inner" cx="200" cy="220" r="129"/>'
               '<ellipse class="orbit-path" cx="200" cy="220" rx="183" ry="67" transform="rotate(-36 200 220)"/>'
               '<ellipse class="orbit-path faint" cx="200" cy="220" rx="180" ry="87" transform="rotate(42 200 220)"/>'
               '<circle class="orbit-moon" cx="200" cy="220" r="69"/>'
               '<path class="orbit-crescent" d="M 224 155 A 69 69 0 1 0 224 285 A 83 83 0 0 1 224 155"/>'
               '<circle class="orbit-dot" cx="320" cy="119" r="7"/>'
               '<circle class="orbit-dot small" cx="67" cy="303" r="4"/>'
               '<path class="orbit-star" d="M200 35v20m-10-10h20M332 334v14m-7-7h14M78 113v12m-6-6h12"/>'
               '</svg><span>Пространство для себя</span></div>')


def _text(value: object) -> str:
    """Human-readable values, never markup or an embedded raw calculation dump."""
    if value is None:
        return "Нет данных"
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(item) for item in value)
    return str(value)


def _e(value: object) -> str:
    return escape(_text(value), quote=True)


def _longitude_text(value: object) -> str:
    """Round presentation only; original fact values remain untouched."""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return _text(value)


def _fact_value(fact: dict) -> str:
    if fact["id"].startswith("astro.") and fact["id"].endswith(".longitude"):
        return _e(_longitude_text(fact.get("value")))
    return _e(fact.get("value"))


def _table(headers: tuple[str, ...], rows: list[list[str]], caption: str) -> str:
    return (f'<div class="table-wrap" role="region" aria-label="{_e(caption)}" tabindex="0">'
            f'<table><caption>{_e(caption)}</caption><thead><tr>'
            + "".join(f'<th scope="col">{_e(label)}</th>' for label in headers)
            + '</tr></thead><tbody>'
            + "".join('<tr>' + "".join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows)
            + '</tbody></table></div>')


def _sources(item: dict, anchors: dict[str, str]) -> str:
    return '<span class="sources">' + ", ".join(
        f'<a href="#{anchors[source]}" aria-label="Источник: {_e(source)}">[{index}]</a>'
        for index, source in enumerate(item.get("sources", []), 1) if source in anchors
    ) + '</span>'


def _grounded(items: list, anchors: dict[str, str], tag: str = "p", *, allow_empty: bool = False) -> str:
    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sources = item.get("sources", [])
        if not isinstance(sources, list) or (not sources and not allow_empty) or not all(
            isinstance(source, str) and source in anchors for source in sources
        ):
            continue
        citations = _sources(item, anchors) if sources else ""
        output.append(f'<{tag}>{_e(item.get("text", ""))}{citations}</{tag}>')
    return "".join(output)


def _topics(items: list, anchors: dict[str, str], *, allow_empty: bool = False) -> str:
    output = []
    for topic in items:
        if not isinstance(topic, dict):
            continue
        paragraphs = _grounded(topic.get("paragraphs", []), anchors, allow_empty=allow_empty)
        if paragraphs:
            output.append('<div class="narrative-topic"><h3>' + _e(topic.get("title", "")) + '</h3>' + paragraphs + '</div>')
    return "".join(output)


def _input_block(inputs: dict) -> str:
    rows = []
    for key, label in (("birth_date", "Дата рождения"), ("birth_time", "Время рождения"),
                       ("birth_place", "Место рождения"), ("timezone", "Часовой пояс")):
        if key in inputs:
            rows.append('<div><dt>' + label + '</dt><dd>' + _e(inputs[key]) + '</dd></div>')
    if "time_accuracy" in inputs:
        accuracy = {"exact": "Точное время", "approximate": "Приблизительное время", "unknown": "Время неизвестно"}.get(inputs["time_accuracy"], inputs["time_accuracy"])
        if inputs["time_accuracy"] == "approximate" and "time_window_minutes" in inputs:
            accuracy = _text(accuracy) + ' · окно ±' + _text(inputs["time_window_minutes"]) + ' мин.'
        rows.append('<div><dt>Точность времени</dt><dd>' + _e(accuracy) + '</dd></div>')
    if not rows and "original_text" not in inputs:
        return ""
    original = '<p class="detail-note">Ваши сведения — дословно</p><div class="original">' + _e(inputs["original_text"]) + '</div>' if "original_text" in inputs else ""
    return ('<aside class="input-card" aria-labelledby="input-heading"><p class="eyebrow">Основа вашего разбора</p>'
            '<h2 id="input-heading">Исходные данные</h2>' + original
            + ('<dl class="input-fields">' + "".join(rows) + '</dl>' if rows else "") + '</aside>')


def _cycles(module: dict, facts: dict[str, dict], anchors: dict[str, str], inputs: dict, as_of: str) -> str:
    """Draw existing age intervals and results; age is only a position marker."""
    data = module.get("data", {})
    peaks = data.get("pinnacles", [])
    challenges = data.get("challenges", [])
    if not isinstance(peaks, list) or not peaks:
        return ""
    age = None
    try:
        birth, current = date.fromisoformat(inputs["birth_date"]), date.fromisoformat(as_of)
        if current >= birth:
            age = current.year - birth.year - ((current.month, current.day) < (birth.month, birth.day))
    except (KeyError, TypeError, ValueError):
        pass
    periods = []
    for index, peak in enumerate(peaks, 1):
        if not isinstance(peak, dict):
            continue
        start, end = peak.get("age_start_inclusive"), peak.get("age_end_exclusive")
        if type(start) is not int or start < 0 or (end is not None and (type(end) is not int or end <= start)):
            continue
        number = peak.get("number", {})
        if not isinstance(number, dict) or "master" not in number:
            continue
        interval = f"От {start} лет" if end is None else f"От {start} до {end} лет"
        precise = "Без верхней границы" if end is None else f"{start} включительно · {end} не включается"
        current_period = age is not None and age >= start and (end is None or age < end)
        def sourced_value(key: str, value: object) -> str:
            rendered = _e(value)
            return f'<a href="#{anchors[key]}">{rendered}</a>' if key in facts else rendered
        challenge = ""
        if isinstance(challenges, list) and len(challenges) >= index:
            challenge = '<span>Вызов <strong>' + sourced_value(f"num.challenge.{index}", challenges[index - 1]) + '</strong></span>'
        periods.append('<li' + (' class="current-period" aria-current="step"' if current_period else '') + '>'
                       f'<span class="period-index">{index:02d}</span><div class="period-body">'
                       '<h4>' + _e(interval) + '</h4><p class="period-boundary">' + _e(precise) + '</p>'
                       '<div class="period-values"><span>Пик <strong>' + sourced_value(f"num.pinnacle.{index}", number["master"]) + '</strong></span>' + challenge + '</div>'
                       + ('<p class="period-now">Ваш период на дату расчёта</p>' if current_period else '') + '</div></li>')
    if not periods:
        return ""
    age_label = f'<p class="cycle-age">Возраст на {_e(as_of)}: {_e(age)} полных лет.</p>' if age is not None else ""
    return '<figure class="graphic cycle-graphic"><h3>Пики и вызовы по периодам</h3>' + age_label + '<ol class="cycle-timeline">' + "".join(periods) + '</ol><figcaption>Возрастные интервалы взяты из расчёта. Это условная схема периодов для размышления, а не прогноз событий.</figcaption></figure>'


def _number(fact: dict | None) -> float | None:
    value = fact.get("value") if fact else None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return None


def _key_cards(facts: dict[str, dict], anchors: dict[str, str]) -> str:
    """Select existing key facts, preserving precomputed ties rather than inventing a profile."""
    cards = []
    for key, label in (("hd.type", "Тип Human Design"), ("num.life_path", "Жизненный путь")):
        fact = facts.get(key)
        if fact and fact.get("value") is not None:
            cards.append(f'<div class="key-card"><p class="card-label">{label}</p>'
                         f'<a class="card-value" href="#{anchors[key]}">{_fact_value(fact)}</a>'
                         '<span class="card-note">Из расчёта</span></div>')
    # The arithmetic module supplies dense ranks in fact detail; do not rank again.
    leaders = [fact for fact in facts.values() if fact.get("section") == "archetypes"
               and fact["id"] in {f"arch.{i}" for i in range(1, 13)}
               and "Плотный ранг: 1;" in str(fact.get("detail", ""))]
    if leaders:
        label = "Ведущий архетип" if len(leaders) == 1 else "Ведущие архетипы"
        values = " / ".join(f'<a href="#{anchors[fact["id"]]}">{_e(fact.get("label", fact["id"]))}</a>' for fact in leaders)
        cards.append(f'<div class="key-card"><p class="card-label">{label}</p><div class="card-value">{values}</div>'
                     '<span class="card-note">По ответам на опрос</span></div>')
    return '<div class="key-cards" aria-label="Ключевые показатели">' + "".join(cards) + '</div>' if cards else ""


def _parameters(facts: dict[str, dict], anchors: dict[str, str], keys: tuple[str, ...]) -> str:
    items = []
    for key in keys:
        fact = facts.get(key)
        if fact:
            items.append(f'<div><dt>{_e(fact.get("label", key))}</dt>'
                         f'<dd><a href="#{anchors[key]}">{_fact_value(fact)}</a></dd></div>')
    return '<dl class="parameter-strip">' + "".join(items) + '</dl>' if items else ""


def _matrix(facts: dict[str, dict], anchors: dict[str, str]) -> str:
    cells = []
    for digit in (1, 4, 7, 2, 5, 8, 3, 6, 9):
        key = f"num.matrix.{digit}"
        fact = facts.get(key)
        count = _number(fact)
        if count is None or count < 0 or int(count) != count:
            return ""
        cells.append(f'<a class="matrix-cell" href="#{anchors[key]}"><strong>{_e(count)}</strong>'
                     f'<span>Цифра {digit}: количество</span></a>')
    return '<figure class="graphic"><h3>Квадрат нумерологии</h3><div class="matrix">' + "".join(cells) + '</div><figcaption>В ячейках показано количество цифр из расчёта.</figcaption></figure>'


def _bars(facts: dict[str, dict], anchors: dict[str, str]) -> str:
    values = [(f"arch.{i}", facts.get(f"arch.{i}")) for i in range(1, 13)]
    values = [(key, fact) for key, fact in values if fact and _number(fact) is not None and _number(fact) >= 0]
    if not values:
        return ""
    maximum = max(_number(fact) for _, fact in values) or 1
    bars = []
    for key, fact in values:
        score = _number(fact)
        width = score / maximum * 100
        bars.append(f'<li><div class="bar-label"><a href="#{anchors[key]}">{_e(fact.get("label", key))}</a><span>{_e(score)}</span></div>'
                    f'<div class="bar-track" aria-hidden="true"><div class="bar-fill" style="width:{width:.4f}%"></div></div></li>')
    return '<figure class="graphic"><h3>Профиль архетипов</h3><ul class="bars">' + "".join(bars) + '</ul><figcaption>Длина полосы относительно максимального балла в этом профиле; числа — исходные баллы.</figcaption></figure>'


def _astrology(facts: dict[str, dict], anchors: dict[str, str]) -> str:
    positions = []
    rows = []
    legend = []
    for planet, label in zip(PLANETS, PLANET_NAMES):
        key = f"astro.{planet}.longitude"
        longitude = _number(facts.get(key))
        if longitude is None or not 0 <= longitude < 360:
            continue
        index = len(positions) + 1
        sign = int(longitude // 30)
        positions.append((index, longitude))
        value = _e(_longitude_text(longitude)) + '°'
        rows.append([str(index), f'<a href="#{anchors[key]}">{_e(label)}</a>', _e(SIGNS[sign]), value])
        legend.append(f'<li><span class="planet-index">{index}</span><a href="#{anchors[key]}">{_e(label)}</a>'
                      f'<span class="planet-position">{_e(SIGNS[sign])}<strong>{value}</strong></span></li>')
    if not positions:
        return ""
    def polar(longitude: float, radius: float) -> tuple[float, float]:
        angle = math.radians(180 - longitude)
        return 220 + radius * math.cos(angle), 220 + radius * math.sin(angle)
    rings = '<circle class="zodiac-outer" cx="220" cy="220" r="181"/><circle cx="220" cy="220" r="140"/>'
    sectors = []
    for index, (name, abbreviation) in enumerate(zip(SIGNS, SIGN_ABBREVIATIONS)):
        longitude = index * 30
        inner_x, inner_y = polar(longitude, 140)
        outer_x, outer_y = polar(longitude, 181)
        degree_x, degree_y = polar(longitude, 202)
        sign_x, sign_y = polar(longitude + 15, 161)
        sectors.append(f'<g><title>{_e(name)}: {longitude}–{longitude + 30}°</title>'
                       f'<line x1="{inner_x:.3f}" y1="{inner_y:.3f}" x2="{outer_x:.3f}" y2="{outer_y:.3f}"/>'
                       f'<text class="degree-label" x="{degree_x:.3f}" y="{degree_y:.3f}" text-anchor="middle" dominant-baseline="central">{longitude}°</text>'
                       f'<text class="zodiac-label" x="{sign_x:.3f}" y="{sign_y:.3f}" text-anchor="middle" dominant-baseline="central">{abbreviation}</text></g>')
    markers = []
    occupied = []
    for index, longitude in positions:
        chosen = None
        # Radial lanes avoid intersecting leader lines and keep longitude unchanged.
        for radius in (125, 96, 67, 38):
            x, y = polar(longitude, radius)
            if all(math.hypot(x - old_x, y - old_y) >= 28 for old_x, old_y in occupied):
                chosen = x, y
                break
        if chosen is None:
            break
        x, y = chosen
        occupied.append(chosen)
        markers.append(f'<g><circle class="planet-marker" cx="{x:.3f}" cy="{y:.3f}" r="12"/>'
                       f'<text class="planet-number" x="{x:.3f}" y="{y:.3f}" text-anchor="middle" dominant-baseline="central">{index}</text></g>')
    if len(markers) == len(positions):
        graphic = ('<svg class="chart zodiac-chart" viewBox="0 0 440 440" role="img" aria-labelledby="astro-chart-title astro-chart-desc">'
                   '<title id="astro-chart-title">Круг эклиптических долгот</title>'
                   '<desc id="astro-chart-desc">Двенадцать знаков по 30 градусов. Нумерованные планеты читаются по легенде ниже; расстояние от центра не несёт астрологического значения. Дома и аспекты не показаны.</desc>'
                   + rings + ''.join(sectors) + ''.join(markers) + '</svg>')
        instruction = 'Шкала идёт от 0° до 360° против часовой стрелки. Номер на карте соответствует планете в легенде; радиальные дорожки разделяют близкие положения.'
    else:
        # A dense conjunction can exceed all radial lanes: keep every point legible.
        stripes = ''.join(f'<rect class="scale-band" x="{40 + i * 30}" y="40" width="30" height="{len(positions) * 34}"/>' for i in range(0, 12, 2))
        ticks = ''.join(f'<text x="{40 + degree}" y="22" text-anchor="middle">{degree}°</text>' for degree in (0, 90, 180, 270, 360))
        dots = ''.join(f'<g><text x="12" y="{60 + (index - 1) * 34}" text-anchor="middle">{index}</text><line x1="40" x2="400" y1="{55 + (index - 1) * 34}" y2="{55 + (index - 1) * 34}"/><circle class="planet" cx="{40 + longitude:.3f}" cy="{55 + (index - 1) * 34}" r="5"/></g>' for index, longitude in positions)
        graphic = ('<svg class="chart longitude-scale" viewBox="0 0 440 ' + str(55 + len(positions) * 34) + '" role="img" aria-label="Долготы планет от нуля до 360 градусов, номера соответствуют легенде">' + stripes + ticks + dots + '</svg>')
        instruction = 'Близкие положения показаны на отдельных строках шкалы 0–360°, чтобы подписи оставались читаемыми. Одна полоса соответствует 30°; номера читаются по легенде.'
    return ('<figure class="graphic astrology-graphic"><h3>Планеты в зодиакальном круге</h3>' + graphic
            + '<p class="chart-instruction">' + instruction + '</p><ol class="planet-legend">' + ''.join(legend) + '</ol>'
            + '<figcaption>Схема долгот без домов и аспектов. В легенде указаны знаки и общая долгота от начала Овна; это отображение готовых расчётных положений.</figcaption>'
            + '<details class="chart-details"><summary>Таблица положений планет</summary>'
            + _table(("№", "Планета", "Знак", "Общая долгота"), rows, "Положения планет в градусах") + '</details></figure>')


def _gematria(module: dict) -> str:
    words = module.get("data", {}).get("words", [])
    if not isinstance(words, list):
        return ""
    tables = []
    for word in words:
        if not isinstance(word, dict) or not isinstance(word.get("letters"), list):
            continue
        rows = [[_e(letter.get(key)) for key in ("source", "transliteration", "latin", "value", "kind")]
                for letter in word["letters"] if isinstance(letter, dict)]
        tables.append(_table(("Буква", "Транслитерация", "Латиница", "Значение", "Тип"), rows, _text(word.get("word", "Слово"))))
        if "total" in word:
            tables.append(f'<p>Итого для слова: {_e(word["total"])}</p>')
    return '<details class="calculation-details"><summary>Буквенный расчёт</summary>' + "".join(tables) + '</details>' if tables else ""


def render_report(calculation: dict, narrative: dict | None = None) -> str:
    """Render trusted calculation structure and escaped text without network or JS.

    Calculation/narrative validation and their identity binding belong to the caller.
    Unknown source references are suppressed defensively; fact IDs never become HTML IDs.
    """
    css = (Path(__file__).resolve().parent.parent / "assets" / "report.css").read_text(encoding="utf-8")
    facts = [fact for fact in calculation.get("facts", []) if isinstance(fact, dict) and isinstance(fact.get("id"), str)]
    anchors = {fact["id"]: f"fact-{index}" for index, fact in enumerate(facts, 1)}
    inputs = calculation.get("input", {})
    name = inputs.get("name") or "Индивидуальный отчёт"
    indexed = {fact["id"]: fact for fact in facts}
    header = ('<div class="masthead"><span class="wordmark">Личная карта<span class="wordmark-dot" aria-hidden="true"> · </span></span>'
              '<span class="edition">Индивидуальный разбор</span></div>'
              '<header class="hero"><div class="hero-copy"><p class="eyebrow">Искусство узнавать себя</p>'
              f'<h1>{_e(name)}</h1><p class="hero-lead">Личный разбор</p>'
              '<p class="hero-description">Личный разбор, чтобы заметить свои привычки, исследовать мотивы и найти вопросы, которые стоит задать себе.</p>')
    if narrative is None:
        header += '<p class="status draft-status">Расчётный черновик — интерпретация не подготовлена</p>'
    else:
        header += '<p class="hero-footnote">Символические системы для размышления о себе</p>'
    header += '</div>' + ORBITAL_ART + '</header>' + _input_block(inputs) + _key_cards(indexed, anchors)
    toc = ('<nav class="contents" aria-label="Оглавление"><div class="contents-heading"><p class="eyebrow">Маршрут чтения</p>'
           '<h2>Грани вашего<br>портрета</h2><p>Читайте по порядку или начните с того, что откликается сейчас.</p></div><ol>'
           + "".join(f'<li><a href="#{key}"><span class="toc-number" aria-hidden="true">{number:02d}</span>'
                     f'<span><span class="toc-title">{_e(title)}</span><span class="toc-note">{_e(SECTION_NOTES[key])}</span></span>'
                     '<span class="toc-arrow" aria-hidden="true">↗</span></a></li>' for number, (key, title) in enumerate(SECTIONS, 1))
           + '<li class="toc-summary"><a href="#summary"><span class="toc-number" aria-hidden="true">✧</span><span><span class="toc-title">Общий разбор</span><span class="toc-note">Как результаты складываются вместе</span></span><span class="toc-arrow" aria-hidden="true">↗</span></a></li></ol></nav>')
    warnings = calculation.get("warnings", [])
    notices = '<aside class="notice caveats" aria-label="Ограничения расчёта"><h2>О точности этого разбора</h2><ul>' + "".join(f'<li>{_e(warning)}</li>' for warning in warnings) + '</ul></aside>' if warnings else ""
    summary_text = _grounded(narrative.get("summary", []), anchors) if narrative else ""
    summary_topics = _topics(narrative.get("summary_topics", []), anchors) if narrative else ""
    summary = ('<section id="summary" class="report-section summary-section" aria-labelledby="heading-summary">'
               '<p class="eyebrow">Собирая целый портрет</p><h2 id="heading-summary">Общий разбор</h2>'
               + (summary_text + summary_topics if summary_text or summary_topics else '<p class="muted">Общий разбор не подготовлен.</p>') + '</section>')
    sections = []
    modules = calculation.get("modules", {})
    for number, (key, title) in enumerate(SECTIONS, 1):
        module = modules.get("numerology" if key == "life_cycles" else key, {})
        body = (f'<section class="report-section" id="{key}" aria-labelledby="heading-{key}">'
                f'<div class="section-heading"><span class="section-number" aria-hidden="true">{number:02d}</span>'
                f'<div><p class="section-kicker">{_e(SECTION_NOTES[key])}</p><h2 id="heading-{key}">{_e(title)}</h2></div></div>')
        available = module.get("status") == "computed"
        synthesis = key in {"purpose", "finance"}
        if synthesis:
            body += '<p class="muted">Синтез предыдущих разделов.</p>'
        elif not available:
            body += '<p class="status">Расчёт недоступен: ' + _e(module.get("reason") or "Для этого раздела нет расчётных данных.") + '</p>'
        section_narrative = narrative.get("sections", {}).get(key, {}) if narrative else {}
        if section_narrative.get("intro"):
            body += '<p class="section-intro">' + _e(section_narrative["intro"]) + '</p>'
        section_facts = [fact for fact in facts if fact.get("section") == key]
        # Only this section's facts feed its graphics.
        local_facts = {fact["id"]: fact for fact in section_facts}
        calculation_details = ""
        if available:
            if key == "human_design":
                body += _parameters(local_facts, anchors, ("hd.type", "hd.authority", "hd.profile"))
            elif key == "numerology":
                body += _matrix(local_facts, anchors)
            elif key == "archetypes":
                body += _bars(local_facts, anchors)
            elif key == "astrology":
                body += _astrology(local_facts, anchors)
            elif key == "gematria":
                body += _parameters(local_facts, anchors, ("gem.total", "gem.vowels", "gem.consonants"))
                calculation_details = _gematria(module)
            elif key == "life_cycles":
                body += _cycles(module, local_facts, anchors, inputs, calculation.get("as_of"))
        topics = _topics(section_narrative.get("topics", []), anchors, allow_empty=not available and not synthesis)
        body += topics
        interpretations = _grounded(
            section_narrative.get("interpretation", []), anchors,
            allow_empty=not available and key not in {"purpose", "finance"},
        )
        actions = _grounded(section_narrative.get("actions", []), anchors, "li")
        if interpretations:
            body += '<div class="interpretation"><h3>Как это можно прочитать</h3>' + interpretations + '</div>'
        elif not topics:
            body += '<p class="muted">Интерпретация не подготовлена.</p>'
        if actions:
            body += '<div class="practice"><p class="eyebrow">От размышления к опыту</p><h3>Что можно попробовать</h3><ul class="actions">' + actions + '</ul></div>'
        if section_facts:
            rows = [[f'<span id="{anchors[fact["id"]]}">{_e(fact.get("label", fact["id"]))}</span>', _fact_value(fact), _e(fact.get("detail", ""))] for fact in section_facts]
            body += '<details class="fact-details"><summary>Расчётные факты и источники<span class="detail-count">' + str(len(section_facts)) + '</span></summary>' + _table(("Параметр", "Значение", "Пояснение"), rows, title + ": расчётные данные") + '</details>'
        elif available and not synthesis:
            body += '<p class="muted">Расчётные факты для этого раздела не представлены.</p>'
        body += calculation_details
        sections.append(body + '</section>')
    technical = ('<details class="technical-details"><summary>Технические сведения об отчёте</summary><dl>'
                 f'<dt>Дата расчёта</dt><dd>{_e(calculation.get("as_of", "Не указана"))}</dd>'
                 f'<dt>Идентификатор расчёта</dt><dd>{_e(calculation.get("calculation_id", "Не указан"))}</dd>'
                 f'<dt>Версия структуры данных</dt><dd>{_e(calculation.get("schema_version", "Не указана"))}</dd>'
                 '</dl></details>')
    return ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow,noarchive">'
            f'<title>Анализ личности — {_e(name)}</title><style>{css}</style></head><body>'
            '<a class="skip" href="#report">К отчёту</a><main id="report">' + header + toc + notices + "".join(sections) + summary + technical
            + f'<footer><p>{DISCLAIMER}</p></footer></main></body></html>')
