"""Offline, escaped HTML presentation of an already computed personality report."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import date
from html import escape
from pathlib import Path

from . import scenes

ASSETS = Path(__file__).resolve().parent.parent / "assets"
# Тема ставится на <html> до первой отрисовки (по умолчанию тёмная, выбор читателя хранится в localStorage).
THEME_BOOT = ("(function(r){var t='dark';try{t=localStorage.getItem('pa-theme')||'dark'}catch(e){}"
              "r.setAttribute('data-theme',t==='light'?'light':'dark');"
              # Начальное aria-checked переключателя соответствует выбранной теме (кнопка появляется позже скрипта в <head>).
              "document.addEventListener('DOMContentLoaded',function(){var b=document.getElementById('pa-theme');"
              "if(b)b.setAttribute('aria-checked',String(t!=='light'))})})(document.documentElement);")
# Класс gj показывает переключатель темы (CSS: html:not(.gj) .pa-theme скрыт); если scenes.js не загрузился, таймер снимает gj и переключатель исчезает.
# Добавляет класс движения до первой отрисовки и флаг вступительной анимации (один раз за визит);
# если scenes.js не загрузился, через 3 секунды классы снимаются и всё остаётся в финальном кадре.
MOTION_BOOT = ("(function(r){r.classList.add('gj');if(!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)"
               "&&'IntersectionObserver' in window){r.classList.add('gm');try{if(!sessionStorage.getItem('pa-intro')&&!location.hash)"
               "r.classList.add('pa-intro')}catch(e){}setTimeout(function(){if(!window.__personalityScenes)"
               "r.classList.remove('gm','pa-intro')},3000)}setTimeout(function(){if(!window.__personalityScenes)r.classList.remove('gj')},3000)})(document.documentElement);")


_SUN = ('<svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">'
        '<circle cx="12" cy="12" r="4.2" fill="currentColor" stroke="none"/>'
        '<path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/></svg>')
_MOON = '<svg class="moon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.5 14.6A8.5 8.5 0 0 1 9.4 3.5a8.5 8.5 0 1 0 11.1 11.1z"/></svg>'
# Переключатель темы справа вверху: капсула, бегунок с месяцем (тёмная) или солнцем (светлая); логика — assets/scenes.js.
THEME_TOGGLE = ('<button type="button" class="pa-theme" id="pa-theme" role="switch" aria-checked="true" aria-label="Тёмная тема">'
                f'<span class="pa-theme-ico moon">{_MOON}</span><span class="pa-theme-ico sun">{_SUN}</span>'
                f'<span class="pa-knob">{_MOON}{_SUN}</span></button>')


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

# Decorative editorial artwork: no personal chart or calculated meaning. Moon-lens, ring, two orbits, two dots, three stars.
ORBIT_ART = ('<div class="pa-art" aria-hidden="true"><svg viewBox="0 0 400 440" focusable="false">'
                          '<g class="a-halo"><circle class="a-halo-fill" cx="200" cy="220" r="157"/><circle class="a-ring" cx="200" cy="220" r="129"/></g>'
             '<g class="a-moon"><g class="a-litg"><circle class="a-lit" cx="200" cy="220" r="69"/></g>'
             '<g class="a-clip"><path class="a-shadow" d="M 224 155 A 69 69 0 1 0 224 285 A 83 83 0 0 1 224 155"/></g>'
             '<circle class="a-edge" cx="200" cy="220" r="69"/></g>'
             '<g class="a-orbits"><g class="a-spin a-spin1"><ellipse class="a-orbit" cx="200" cy="220" rx="183" ry="67" transform="rotate(-36 200 220)" pathLength="1"/></g>'
             '<g class="a-spin a-spin2"><ellipse class="a-orbit a-faint" cx="200" cy="220" rx="180" ry="87" transform="rotate(42 200 220)" pathLength="1"/></g></g>'
             '<g class="a-dots"><g class="a-dot a-dot1"><circle cx="357" cy="220" r="7"/></g><g class="a-dot a-dot2"><circle cx="43" cy="220" r="4.5"/></g></g>'
             '<g class="a-stars"><g class="a-st a-st1"><path class="a-star" d="M200 35v20m-10-10h20"/></g>'
             '<g class="a-st a-st2"><path class="a-star" d="M332 334v14m-7-7h14"/></g>'
             '<g class="a-st a-st3"><path class="a-star" d="M78 113v12m-6-6h12"/></g></g>'
             '</svg></div>')

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


GLUE = re.compile(r"(?<![^\s(«])([а-яёА-ЯЁ]{1,2}) (?=\S)")
PAREN = re.compile(r"\([^()]*\)")
CLOSING_DOT = re.compile(r"([»)])\.(?=\s*$)")


def _t(value: object) -> str:
    """Escaped reader text with typography of the site: short prepositions and conjunctions
    do not hang at the end of a line, a dash does not start a new line, text in (parentheses)
    is a quiet grey italic, and the full stop after a closing » or ) at the end is not set."""
    text = CLOSING_DOT.sub(r"\1", _e(value))
    text = GLUE.sub(lambda m: m.group(1) + "&nbsp;", text)
    text = text.replace(" — ", "&nbsp;— ")
    return PAREN.sub(lambda m: f'<span class="paren">{m.group(0)}</span>', text)


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


def _grounded(items: list, anchors: dict[str, str], tag: str = "p", *, allow_empty: bool = False) -> str:
    """Text items whose sources exist in the calculation. The sources are checked, not shown:
    the reader text has no footnote links."""
    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sources = item.get("sources", [])
        if not isinstance(sources, list) or (not sources and not allow_empty) or not all(
            isinstance(source, str) and source in anchors for source in sources
        ):
            continue
        output.append(f'<{tag}>{_t(item.get("text", ""))}</{tag}>')
    return "".join(output)


def _topics(items: list, anchors: dict[str, str], *, allow_empty: bool = False) -> str:
    output = []
    for topic in items:
        if not isinstance(topic, dict):
            continue
        paragraphs = _grounded(topic.get("paragraphs", []), anchors, allow_empty=allow_empty)
        if paragraphs:
            output.append('<div class="narrative-topic"><h3>' + _t(topic.get("title", "")) + '</h3>' + paragraphs + '</div>')
    return "".join(output)


def _input_block(inputs: dict, offset: object = None) -> str:
    """Rows «caps label over the value», explanation as a quiet line under the value."""
    def row(label: str, value: object, note: object = None) -> str:
        small = f'<small>{_e(note)}</small>' if note else ""
        return f'<div><dt>{label}</dt><dd>{_e(value)}{small}</dd></div>'
    rows = []
    for key, label in (("birth_date", "Дата рождения"), ("birth_time", "Время рождения"),
                       ("birth_place", "Место рождения"), ("timezone", "Часовой пояс")):
        if key in inputs:
            value, note = inputs[key], None
            if key == "birth_date":
                try:
                    value = date.fromisoformat(value).strftime("%d.%m.%Y")
                except (TypeError, ValueError):
                    pass
            elif key == "timezone" and isinstance(offset, (int, float)) and not isinstance(offset, bool):
                note = f"UTC{offset:+g}".replace("-", "−") + " на момент рождения"
            rows.append(row(label, value, note))
    if "time_accuracy" in inputs:
        accuracy = {"exact": "Точное время", "approximate": "Приблизительное время", "unknown": "Время неизвестно"}.get(inputs["time_accuracy"], inputs["time_accuracy"])
        note = None
        if inputs["time_accuracy"] == "approximate" and "time_window_minutes" in inputs:
            note = "окно ±" + _text(inputs["time_window_minutes"]) + " мин."
        rows.append(row("Точность времени", accuracy, note))
    if not rows and "original_text" not in inputs:
        return ""
    original = '<p class="detail-note">Ваши сведения — дословно</p><div class="original">' + _e(inputs["original_text"]) + '</div>' if "original_text" in inputs else ""
    return ('<aside class="input-card" aria-labelledby="input-heading"><p class="eyebrow">Основа вашего разбора</p>'
            '<h2 id="input-heading">Исходные данные</h2>'
            '<p class="input-lead">Разбор складывается из трёх источников: дата, время и место рождения — для Human Design, '
            'астрологии, нумерологии и циклов; имя — для гематрии и чисел имени; ответы на 36 утверждений опроса — для архетипов.</p>'
            + original
            + ('<dl class="input-fields">' + "".join(rows) + '</dl>' if rows else "") + '</aside>')


def _cycles(module: dict, facts: dict[str, dict], inputs: dict, as_of: str) -> str:
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
        challenge = ""
        if isinstance(challenges, list) and len(challenges) >= index:
            challenge = '<span>Вызов <strong>' + _e(challenges[index - 1]) + '</strong></span>'
        periods.append('<li class="s-in' + (' current-period" aria-current="step"' if current_period else '"') + f' style="--k:0;--j:{index - 1}">'
                       f'<span class="period-index">{index:02d}</span><div class="period-body">'
                       '<h4>' + _e(interval) + '</h4><p class="period-boundary">' + _e(precise) + '</p>'
                       '<div class="period-values"><span>Пик <strong>' + _e(number["master"]) + '</strong></span>' + challenge + '</div>'
                       + ('<p class="period-now">Ваш период на дату расчёта</p>' if current_period else '') + '</div></li>')
    if not periods:
        return ""
    age_label = f'<p class="cycle-age">Возраст на {_e(as_of)}: {_e(age)} полных лет.</p>' if age is not None else ""
    return '<figure class="graphic scene cycle-graphic"><h3>Пики и вызовы по периодам</h3>' + age_label + '<ol class="cycle-timeline">' + "".join(periods) + '</ol><figcaption>Возрастные интервалы взяты из расчёта. Это условная схема периодов для размышления, а не прогноз событий.</figcaption></figure>'


def _number(fact: dict | None) -> float | None:
    value = fact.get("value") if fact else None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return None


def _key_cards(facts: dict[str, dict]) -> str:
    """Select existing key facts, preserving precomputed ties rather than inventing a profile."""
    cards = []
    for key, label in (("hd.type", "Тип Human Design"), ("num.life_path", "Жизненный путь")):
        fact = facts.get(key)
        if fact and fact.get("value") is not None:
            cards.append(f'<div class="key-card"><p class="card-label">{label}</p>'
                         f'<span class="card-value">{_fact_value(fact)}</span>'
                         '<span class="card-note">Из расчёта</span></div>')
    # The arithmetic module supplies dense ranks in fact detail; do not rank again.
    leaders = [fact for fact in facts.values() if fact.get("section") == "archetypes"
               and fact["id"] in {f"arch.{i}" for i in range(1, 13)}
               and "Плотный ранг: 1;" in str(fact.get("detail", ""))]
    if leaders:
        label = "Ведущий архетип" if len(leaders) == 1 else "Ведущие архетипы"
        values = " / ".join(f'<span>{_e(fact.get("label", fact["id"]))}</span>' for fact in leaders)
        cards.append(f'<div class="key-card"><p class="card-label">{label}</p><div class="card-value">{values}</div>'
                     '<span class="card-note">По ответам на опрос</span></div>')
    return '<div class="key-cards" aria-label="Ключевые показатели">' + "".join(cards) + '</div>' if cards else ""


def _parameters(facts: dict[str, dict], keys: tuple[str, ...]) -> str:
    items = []
    for key in keys:
        fact = facts.get(key)
        if fact:
            items.append(f'<div><dt>{_e(fact.get("label", key))}</dt>'
                         f'<dd>{_fact_value(fact)}</dd></div>')
    return '<dl class="parameter-strip">' + "".join(items) + '</dl>' if items else ""


def _matrix(facts: dict[str, dict], module: dict | None = None) -> str:
    """Square 3x3: «Цифра N: сколько раз», empty cells get a dash.

    Steps of the story: 0 — digits of the date, 2 — zeros fade, 3 — grid, from 4 — the non-zero digits
    one by one fly into their cells, at the end — dashes of the empty cells."""
    source = (module or {}).get("data", {}).get("square", {}).get("source_digits") if isinstance((module or {}).get("data", {}).get("square"), dict) else None
    if not (isinstance(source, str) and source.isascii() and source.isdigit()):
        source = ""
    nonzero = [i for i, c in enumerate(source) if c != "0"]
    end_step = 4 + len(nonzero)

    def hits(digit: int) -> list[int]:
        return [4 + nonzero.index(i) for i, c in enumerate(source) if c == str(digit)]

    cells = []
    for order, digit in enumerate((1, 4, 7, 2, 5, 8, 3, 6, 9)):
        key = f"num.matrix.{digit}"
        fact = facts.get(key)
        count = _number(fact)
        if count is None or count < 0 or int(count) != count:
            return ""
        count = int(count)
        steps = hits(digit)
        if count == 0:
            marks = f'<span class="s-in" style="--k:{end_step};--j:{order}">—</span>'
        elif 0 < count <= 6 and len(steps) == count:
            marks = "".join(f'<span class="s-in s-pop" style="--k:{k}">{digit}</span>' for k in steps)
        else:
            text = str(digit) * count if count <= 6 else f"{digit}×{count}"
            marks = f'<span class="s-in s-pop" style="--k:{steps[0] if steps else 4}">{text}</span>'
        first = steps[0] if len(steps) == count and steps else 4
        cells.append(f'<div class="matrix-cell s-in{" has" if count else ""}" style="--k:3;--j:{order}">'
                     f'<span class="cell-fill s-in" style="--k:{first};--j:0" aria-hidden="true"></span>'
                     f'<strong>{marks}</strong>'
                     f'<span class="cell-label">Цифра {digit}: {_e(count)}</span></div>')
    return scenes.square(source, '<div class="matrix">' + "".join(cells) + '</div>')


def _bars(facts: dict[str, dict]) -> str:
    values = [(f"arch.{i}", facts.get(f"arch.{i}")) for i in range(1, 13)]
    values = [(key, fact) for key, fact in values if fact and _number(fact) is not None and _number(fact) >= 0]
    if not values:
        return ""
    maximum = max(_number(fact) for _, fact in values) or 1
    bars = []
    for order, (key, fact) in enumerate(values):
        score = _number(fact)
        width = score / maximum * 100
        lead = " lead" if score == maximum else ""
        bars.append(f'<li class="s-in{lead}" style="--k:0;--j:{order}"><div class="bar-label"><span class="bar-name">{_e(fact.get("label", key))}</span><span>{_e(score)}</span></div>'
                    f'<div class="bar-track" aria-hidden="true"><div class="bar-fill s-grow" style="width:{width:.4f}%;--k:1;--j:{order}"></div></div></li>')
    return '<figure class="graphic scene"><h3>Профиль архетипов</h3><ul class="bars">' + "".join(bars) + '</ul><figcaption>Длина полосы относительно максимального балла в этом профиле; числа — исходные баллы.</figcaption></figure>'


# Short planet marks inside the circles of the natal wheel.
PLANET_SHORT = ("Су", "Лу", "Ме", "Ве", "Ма", "Юп", "Са", "Ур", "Не", "Пл")


# Виды аспектов отчёта (совпадают с personality_core.ephemeris.ASPECT_KINDS); группа берётся отсюда, а не из данных.
ASPECT_VIEW = {"trine": ("трин", 120, "h"), "sextile": ("секстиль", 60, "h"),
               "square": ("квадрат", 90, "t"), "opposition": ("оппозиция", 180, "t")}


def _aspects(facts: dict[str, dict], placed: dict[str, float]) -> list[tuple]:
    """Aspects from facts `astro.aspect.*` between planets that are on the wheel; anything malformed is skipped."""
    found = []
    for identifier, fact in facts.items():
        value = fact.get("value") if identifier.startswith("astro.aspect.") else None
        if not isinstance(value, dict) or value.get("kind") not in ASPECT_VIEW:
            continue
        pair = value.get("planets")
        if (not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]
                or not all(isinstance(key, str) and key in placed for key in pair)):
            continue
        deviation = _number({"value": value.get("deviation")})
        found.append((pair[0], pair[1], value["kind"], deviation))
    return found


def _astrology(facts: dict[str, dict]) -> str:
    """Natal wheel: signs around the ring, planets on their degrees, axes of Ascendant and MC.

    Sized for a 375 px phone (viewBox 600): sign labels are smaller than their ring, planet circles sit on
    their own track and neighbours closer than GAP degrees are spread along the arc, so nothing crosses.
    The wheel is turned so that the Ascendant (if the calculation has it) is on the left; longitudes grow
    counter-clockwise. Aspect lines (if the calculation has `astro.aspect.*` facts) connect the planet points on the
    inner circle; houses and lists under the circle are not drawn."""
    planets = []
    keys = {}
    for planet, label, short in zip(PLANETS, PLANET_NAMES, PLANET_SHORT):
        longitude = _number(facts.get(f"astro.{planet}.longitude"))
        if longitude is not None and 0 <= longitude < 360:
            planets.append((label, short, longitude))
            keys[planet] = (label, longitude)
    if not planets:
        return ""
    axes_data = []
    for key, short, name in (("astro.ascendant.longitude", "Асц", "Асцендент"), ("astro.midheaven.longitude", "MC", "Середина неба")):
        axis = _number(facts.get(key))
        if axis is not None and 0 <= axis < 360:
            axes_data.append((short, name, axis))
    ascendant = next((axis for short, _, axis in axes_data if short == "Асц"), 0)
    c, r_out, r_in, r_lab, r_planet, r_circle, r_inner, r_axis = 300, 250, 212, 231, 182, 19, 118, 272

    def pt(longitude: float, radius: float) -> tuple[float, float]:
        angle = math.radians(180 + longitude - ascendant)
        return round(c + radius * math.cos(angle), 1), round(c - radius * math.sin(angle), 1)

    def line(p: tuple, q: tuple, cls: str, k: float = 0, j: float = 0) -> str:
        length = math.ceil(math.hypot(q[0] - p[0], q[1] - p[1])) or 1
        return f'<line class="{cls}" x1="{p[0]}" y1="{p[1]}" x2="{q[0]}" y2="{q[1]}" style="--len:{length};--k:{k:g};--j:{j:g}"/>'

    parts = [f'<circle class="w-ring s-in" cx="{c}" cy="{c}" r="{r_out}" style="--k:0"/>'
             f'<circle class="w-ring s-in" cx="{c}" cy="{c}" r="{r_in}" style="--k:0"/>'
             f'<circle class="w-in s-in" cx="{c}" cy="{c}" r="{r_inner}" style="--k:0"/>']
    for index, (name, abbreviation) in enumerate(zip(SIGNS, SIGN_ABBREVIATIONS)):
        x, y = pt(index * 30 + 15, r_lab)
        parts.append(f'<g class="s-in" style="--k:1;--j:{index}"><title>{_e(name)}: {index * 30}–{index * 30 + 30}°</title>'
                     + line(pt(index * 30, r_in), pt(index * 30, r_out), "w-tick")
                     + f'<text class="w-sign" x="{x}" y="{y}" dy="0.36em" text-anchor="middle">{abbreviation}</text></g>')
    for step, (short, name, axis) in enumerate(axes_data):
        parts.append(line(pt(axis, r_in), pt(axis + 180, r_in), "w-axis s-draw", 4, step * 4))
        x, y = pt(axis, r_axis)
        parts.append(f'<text class="w-ax s-in" x="{x}" y="{y}" dy="0.36em" text-anchor="middle" style="--k:6"><title>{_e(name)} (приближённо)</title>{short}≈</text>')
    aspect_list = _aspects(facts, {key: value[1] for key, value in keys.items()})
    for step, (first, second, kind, deviation) in enumerate(aspect_list):
        name, exact, group = ASPECT_VIEW[kind]
        note = f" (отклонение {_longitude_text(deviation)}°)" if deviation is not None else ""
        parts.append(line(pt(keys[first][1], r_inner), pt(keys[second][1], r_inner),
                          f"w-asp w-asp--{group} s-draw", 12, step)
                     .replace("/>", f"><title>{_e(keys[first][0])} — {_e(keys[second][0])}: {name} {exact}°{_e(note)}</title></line>"))
    order = sorted(range(len(planets)), key=lambda i: planets[i][2])
    placed = {i: planets[i][2] for i in order}
    gap = 13.5
    for _ in range(300):
        moved = False
        for position, i in enumerate(order):
            j = order[(position + 1) % len(order)]
            if i == j:
                continue
            # sorted order is kept: only the last→first pair crosses 0°/360°
            distance = placed[j] - placed[i] + (360 if position == len(order) - 1 else 0)
            if distance < gap:
                push = (gap - distance) / 2
                placed[i] -= push
                placed[j] += push
                moved = True
        if not moved:
            break
    for step, i in enumerate(order):
        label, short, longitude = planets[i]
        dx, dy = pt(longitude, r_inner)
        tx, ty = pt(placed[i], r_planet)
        ex, ey = pt(placed[i], r_planet - r_circle)
        (o1x, o1y), (o2x, o2y) = pt(longitude, r_in), pt(longitude, r_in - 9)
        parts.append(f'<g class="s-in s-pop" style="--k:8;--j:{step}"><title>{_e(label)}: {_e(SIGNS[int(longitude // 30)])}, {_e(_longitude_text(longitude))}°</title>'
                     f'<line class="w-tick" x1="{o1x}" y1="{o1y}" x2="{o2x}" y2="{o2y}"/>'
                     f'<line class="w-lead" x1="{dx}" y1="{dy}" x2="{ex}" y2="{ey}"/><circle class="w-dot" cx="{dx}" cy="{dy}" r="4"/>'
                     f'<circle class="w-pl" cx="{tx}" cy="{ty}" r="{r_circle}"/>'
                     f'<text class="w-pt" x="{tx}" y="{ty}" dy="0.36em" text-anchor="middle">{short}</text></g>')
    description = "; ".join(f"{label} — {SIGNS[int(longitude // 30)]}, {_longitude_text(longitude)}°" for label, _, longitude in planets)
    axes_text = " Оси: " + "; ".join(f"{name} {_longitude_text(axis)}° (приближённо)" for _, name, axis in axes_data) + "." if axes_data else ""
    aspects_text = ""
    if aspect_list:
        aspects_text = " Аспекты: " + "; ".join(
            f"{keys[a][0]} — {keys[b][0]}, {ASPECT_VIEW[kind][0]}" for a, b, kind, _ in aspect_list) + "."
    graphic = ('<svg class="chart wheel-chart" viewBox="0 0 600 600" role="img" aria-labelledby="astro-chart-title astro-chart-desc">'
               '<title id="astro-chart-title">Круг эклиптических долгот</title>'
               f'<desc id="astro-chart-desc">Двенадцать знаков по 30 градусов, планеты на своих градусах. {_e(description)}.{_e(axes_text)}{_e(aspects_text)}</desc>'
               + "".join(parts) + '</svg>')
    legend = ""
    if aspect_list:
        legend = ('<ul class="graph-legend aspect-legend">'
                  '<li><span class="swatch asp-h"></span>гармоничные аспекты: трин 120°, секстиль 60°</li>'
                  '<li><span class="swatch asp-t"></span>напряжённые: квадрат 90°, оппозиция 180°</li></ul>')
    return '<figure class="graphic scene astrology-graphic"><h3>Планеты в зодиакальном круге</h3>' + graphic + legend + '</figure>'


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


def _centers_by_gate():
    """Gate → center lookup from the calculation core; None if hd.py is not importable."""
    try:
        import hd
    except ImportError:
        return None
    return hd.center_of_gate


def render_report(calculation: dict, narrative: dict | None = None, *, assets: str = "inline", banner: str | None = None) -> str:
    """Render trusted calculation structure and escaped text without network requests.

    assets="inline" embeds report.css and scenes.js into one offline file; assets="external" links
    assets/report.css and assets/scenes.js for the site archive (see package.write_site).

    Calculation/narrative validation and their identity binding belong to the caller.
    Unknown source references are suppressed defensively; fact IDs never become HTML IDs.
    """
    if assets not in {"inline", "external"}:
        raise ValueError("assets must be inline or external")
    facts = [fact for fact in calculation.get("facts", []) if isinstance(fact, dict) and isinstance(fact.get("id"), str)]
    known = {fact["id"] for fact in facts}
    inputs = calculation.get("input", {})
    name = inputs.get("name") or "Индивидуальный отчёт"
    indexed = {fact["id"]: fact for fact in facts}
    banner_html = f'<p class="example-banner">{_e(banner)}</p>' if banner else ""
    # Шапка: орбита-иллюстрация, подпись капсом и крупное слово; имени, оглавления и издательской плашки нет.
    header = (banner_html + '<header class="note-head">' + ORBIT_ART
              + '<p class="pa-eyebrow">Матрица программного комплекса</p><h1>Судьба</h1>')
    if narrative is None:
        header += '<p class="status draft-status">Расчётный черновик — интерпретация не подготовлена</p>'
    header += '</header>'
    offset = ((calculation.get("modules", {}).get("human_design", {}).get("data") or {}).get("input") or {}).get("utc_offset")
    opening = _input_block(inputs, offset) + _key_cards(indexed)
    warnings = calculation.get("warnings", [])
    notices = ('<aside class="notice caveats" aria-label="Ограничения расчёта"><h2>О точности этого разбора</h2>'
               '<p>Числа и положения планет посчитала программа. Несколько показателей зависят от точности времени '
               'рождения или считаются приближённо; в главах они отмечены там, где это меняет вывод.</p>'
               '<details><summary>Технические оговорки расчёта</summary><ul>'
               + "".join(f'<li>{_e(warning)}</li>' for warning in warnings) + '</ul></details></aside>') if warnings else ""

    def heading(number: int, kicker: str, title: str, anchor: str) -> str:
        """Section head: kicker in caps, below in one line the outlined number and the title, all centered."""
        return (f'<div class="section-heading"><p class="section-kicker">{_e(kicker)}</p>'
                f'<h2 id="heading-{anchor}"><span class="section-number" aria-hidden="true">{number:02d}</span> {_e(title)}</h2></div>')

    summary_text = _grounded(narrative.get("summary", []), known) if narrative else ""
    summary_topics = _topics(narrative.get("summary_topics", []), known) if narrative else ""
    summary = ('<section id="summary" class="report-section summary-section" aria-labelledby="heading-summary">'
               + heading(len(SECTIONS) + 1, "Собирая целый портрет", "Общий разбор", "summary")
               + (summary_text + summary_topics if summary_text or summary_topics else '<p class="muted">Общий разбор не подготовлен.</p>') + '</section>')
    sections = []
    modules = calculation.get("modules", {})
    for number, (key, title) in enumerate(SECTIONS, 1):
        module = modules.get("numerology" if key == "life_cycles" else key, {})
        body = (f'<section class="report-section" id="{key}" aria-labelledby="heading-{key}">'
                + heading(number, SECTION_NOTES[key], title, key))
        available = module.get("status") == "computed"
        synthesis = key in {"purpose", "finance"}
        if synthesis:
            body += '<p class="muted">Синтез предыдущих разделов.</p>'
        elif not available:
            body += '<p class="status">Расчёт недоступен: ' + _e(module.get("reason") or "Для этого раздела нет расчётных данных.") + '</p>'
        section_narrative = narrative.get("sections", {}).get(key, {}) if narrative else {}
        if section_narrative.get("intro"):
            body += '<p class="section-intro">' + _t(section_narrative["intro"]) + '</p>'
        # Only this section's facts feed its graphics.
        local_facts = {fact["id"]: fact for fact in facts if fact.get("section") == key}
        calculation_details = ""
        if available:
            if key == "human_design":
                body += _parameters(local_facts, ("hd.type", "hd.authority", "hd.profile"))
                lookup = _centers_by_gate()
                data = module.get("data", {})
                chart = data.get("chart", {})
                window = data.get("time_window") if isinstance(data.get("time_window"), dict) else {}
                varied = window.get("varied") if isinstance(window.get("varied"), list) else []
                if any(item in varied for item in ("human_design.channels", "human_design.defined_centers")):
                    body += ('<p class="status">Бодиграф не показан: в пределах окна приблизительного времени '
                             'меняются каналы или определённые центры.</p>')
                elif lookup and isinstance(chart, dict):
                    body += scenes.bodygraph(chart, lookup)
            elif key == "numerology":
                labels = {k: local_facts[f"num.{k}"].get("label", k) for k, _ in scenes.KEY_NUMBERS if f"num.{k}" in local_facts}
                body += scenes.key_numbers(module.get("data", {}), labels) + _matrix(local_facts, module)
            elif key == "archetypes":
                body += _bars(local_facts)
            elif key == "astrology":
                body += _astrology(local_facts)
            elif key == "gematria":
                body += _parameters(local_facts, ("gem.total", "gem.vowels", "gem.consonants"))
                body += scenes.gematria(module.get("data", {}))
                calculation_details = _gematria(module)
            elif key == "life_cycles":
                body += _cycles(module, local_facts, inputs, calculation.get("as_of"))
        topics = _topics(section_narrative.get("topics", []), known, allow_empty=not available and not synthesis)
        body += topics
        interpretations = _grounded(
            section_narrative.get("interpretation", []), known,
            allow_empty=not available and key not in {"purpose", "finance"},
        )
        actions = _grounded(section_narrative.get("actions", []), known, "li")
        if interpretations:
            body += '<aside class="pa-read"><h3>Как это можно прочитать?</h3>' + interpretations + '</aside>'
        elif not topics:
            body += '<p class="muted">Интерпретация не подготовлена.</p>'
        if actions:
            body += '<section class="pa-try"><p class="pa-try-k">От размышления к опыту</p><h3>Что можно попробовать?</h3><ol class="pa-try-list">' + actions + '</ol></section>'
        body += calculation_details
        sections.append(body + '</section>')
    if assets == "inline":
        css = (ASSETS / "report.css").read_text(encoding="utf-8")
        js = (ASSETS / "scenes.js").read_text(encoding="utf-8")
        head_assets = f'<style>{css}</style>'
        tail_assets = f'<script>{js}</script>'
    else:
        # Версия по содержимому: после обновления браузер и хостинг не отдадут старый файл из кэша.
        def version(name: str) -> str:
            return hashlib.sha256((ASSETS / name).read_bytes()).hexdigest()[:10]
        head_assets = f'<link rel="stylesheet" href="assets/report.css?v={version("report.css")}">'
        tail_assets = f'<script src="assets/scenes.js?v={version("scenes.js")}" defer></script>'
    return ('<!doctype html><html lang="ru" data-theme="dark"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow,noarchive">'
            '<meta name="color-scheme" content="dark light">'
            f'<title>Анализ личности — {_e(name)}</title><script>{THEME_BOOT}</script><script>{MOTION_BOOT}</script>{head_assets}</head><body>'
            + THEME_TOGGLE + '<a class="skip" href="#report">К отчёту</a><main id="report">' + header
            + '<div id="text">' + opening + notices + "".join(sections) + summary
            + f'<footer class="site-foot"><p class="pa-foot">{DISCLAIMER}</p></footer></div></main>{tail_assets}</body></html>')
