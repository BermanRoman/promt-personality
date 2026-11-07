"""Animated figures ("scenes") for the HTML report.

Every scene is rendered in its final state: without JavaScript, with reduced motion and in print the
reader sees the complete picture. assets/scenes.js only hides the steps until the figure scrolls
into view and replays them on request. Values come from the calculation; nothing is computed here
except screen geometry.
"""

from __future__ import annotations

import math
from html import escape


def _e(value: object) -> str:
    return escape("Нет данных" if value is None else str(value), quote=True)


def _step(k: float, j: float = 0) -> str:
    """CSS custom properties: k — step of the story, j — position inside the step."""
    return f'--k:{k:g};--j:{j:g}'


# ---------- Human Design bodygraph ----------

# Screen positions only (viewBox 0 0 300 430); the chart itself comes from hd.compute.
CENTER_SHAPES = {
    "Голова": ("tri-up", 150, 38),
    "Аджна": ("tri-down", 150, 100),
    "Горло": ("square", 150, 168),
    "G-центр": ("diamond", 150, 240),
    "Эго": ("tri-small", 210, 262),
    "Селезёнка": ("tri-right", 62, 312),
    "Сакрал": ("square", 150, 322),
    "Солнечное сплетение": ("tri-left", 238, 312),
    "Корень": ("square", 150, 414),
}
CENTER_SHORT = {
    "Голова": "Голова", "Аджна": "Аджна", "Горло": "Горло", "G-центр": "G", "Эго": "Эго",
    "Селезёнка": "Селезёнка", "Сакрал": "Сакрал", "Солнечное сплетение": "Сплетение", "Корень": "Корень",
}


def _shape(kind: str, x: float, y: float) -> str:
    s = 24
    if kind == "square":
        return f'<rect x="{x - s}" y="{y - s}" width="{2 * s}" height="{2 * s}" rx="6"/>'
    if kind == "diamond":
        return f'<polygon points="{x},{y - 30} {x + 30},{y} {x},{y + 30} {x - 30},{y}"/>'
    points = {
        "tri-up": ((x, y - 26), (x + 28, y + 22), (x - 28, y + 22)),
        "tri-down": ((x - 28, y - 22), (x + 28, y - 22), (x, y + 26)),
        "tri-right": ((x - 22, y - 28), (x + 26, y), (x - 22, y + 28)),
        "tri-left": ((x + 22, y - 28), (x - 26, y), (x + 22, y + 28)),
        "tri-small": ((x - 18, y - 16), (x + 20, y), (x - 18, y + 16)),
    }[kind]
    return '<polygon points="' + " ".join(f"{px:g},{py:g}" for px, py in points) + '"/>'


def bodygraph(chart: dict, centers_by_gate) -> str:
    """Centers and defined channels of an existing HD chart; empty string if the chart is incomplete."""
    defined = chart.get("defined_centers")
    channels = chart.get("channels")
    if not isinstance(defined, list) or not isinstance(channels, list):
        return ""
    pairs: dict[tuple[str, str], int] = {}
    lines = []
    for index, channel in enumerate(channels):
        if not (isinstance(channel, (list, tuple)) and len(channel) == 2):
            return ""
        try:
            a, b = (centers_by_gate(gate) for gate in channel)
        except (ValueError, TypeError):
            return ""
        if a not in CENTER_SHAPES or b not in CENTER_SHAPES or a == b:
            return ""
        key = tuple(sorted((a, b)))
        offset = pairs.get(key, 0)
        pairs[key] = offset + 1
        (_, x1, y1), (_, x2, y2) = CENTER_SHAPES[a], CENTER_SHAPES[b]
        # parallel channels between the same centers are shifted sideways
        length = math.hypot(x2 - x1, y2 - y1) or 1
        shift = (offset - 0) * 7
        nx, ny = -(y2 - y1) / length * shift, (x2 - x1) / length * shift
        x1, y1, x2, y2 = x1 + nx, y1 + ny, x2 + nx, y2 + ny
        lines.append(f'<line class="hd-channel s-draw" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'style="--len:{math.ceil(length)};{_step(2, index)}"><title>Канал {_e(channel[0])}–{_e(channel[1])}</title></line>')
    shapes = []
    for index, (name, (kind, x, y)) in enumerate(CENTER_SHAPES.items()):
        state = "defined" if name in defined else "open"
        shapes.append(f'<g class="hd-center {state} s-in s-pop" style="{_step(0, index)}"><title>{_e(name)}: '
                      f'{"определён" if state == "defined" else "не определён"}</title>{_shape(kind, x, y)}</g>')
        label_y = {"tri-up": y + 36, "tri-down": y + 40, "square": y + 39, "diamond": y + 45,
                   "tri-small": y - 22, "tri-right": y + 44, "tri-left": y + 44}[kind]
        shapes.append(f'<text class="hd-label s-in" x="{x}" y="{label_y}" text-anchor="middle" style="{_step(1, index)}">{_e(CENTER_SHORT[name])}</text>')
    defined_names = ", ".join(name for name in CENTER_SHAPES if name in defined) or "нет"
    channel_names = ", ".join(f"{a}–{b}" for a, b in channels) or "нет"
    return ('<figure class="graphic scene hd-graphic"><h3>Бодиграф</h3>'
            '<svg class="chart bodygraph" viewBox="0 0 300 456" role="img" aria-labelledby="hd-graph-title hd-graph-desc">'
            '<title id="hd-graph-title">Бодиграф Human Design</title>'
            f'<desc id="hd-graph-desc">Определённые центры: {_e(defined_names)}. Каналы: {_e(channel_names)}.</desc>'
            + "".join(lines) + "".join(shapes) + '</svg>'
            '<ul class="graph-legend"><li><span class="swatch defined"></span>определённые центры</li>'
            '<li><span class="swatch open"></span>неопределённые</li><li><span class="swatch channel"></span>каналы</li></ul>'
            '<figcaption>Схема по готовому расчёту: какие центры определены и какими каналами они связаны. '
            'Расположение центров условное, ворота не показаны.</figcaption></figure>')


# ---------- gematria ----------

def gematria(data: dict) -> str:
    words = data.get("words")
    reduction = data.get("reduction") or {}
    if not isinstance(words, list) or not words or "total" not in data:
        return ""
    rows = []
    totals = []
    for w, word in enumerate(words):
        letters = word.get("letters") if isinstance(word, dict) else None
        if not isinstance(letters, list) or "total" not in word:
            return ""
        chips = "".join(
            f'<span class="gem-letter {_e(letter.get("kind", ""))} s-in s-pop" style="{_step(w * 2 + 1, i)}">'
            f'<b>{_e(str(letter.get("latin", "")).upper())}</b><small>{_e(letter.get("value"))}</small></span>'
            for i, letter in enumerate(letters) if isinstance(letter, dict))
        rows.append(f'<div class="gem-word"><p class="gem-source s-in" style="{_step(w * 2)}">{_e(word.get("word", ""))}</p>'
                    f'<div class="gem-letters">{chips}</div>'
                    f'<p class="gem-sum s-in" style="{_step(w * 2 + 2)}">сумма <strong>{_e(word["total"])}</strong></p></div>')
        totals.append(_e(word["total"]))
    last = len(words) * 2 + 1
    steps = reduction.get("steps") if isinstance(reduction, dict) else None
    chain = ""
    if isinstance(steps, list) and len(steps) > 1:
        chain = " → ".join(f'<span class="s-in" style="{_step(last + 1, i)}">{_e(step)}</span>' for i, step in enumerate(steps[1:]))
        chain = f' → {chain}'
    equation = (f'<p class="gem-total s-in" style="{_step(last)}">' + " + ".join(totals)
                + f' = <strong class="big-number">{_e(data["total"])}</strong>{chain}</p>')
    return ('<figure class="graphic scene calc-graphic gem-graphic"><h3>Расчёт по буквам</h3>' + "".join(rows) + equation
            + '<figcaption>Каждая буква получает число по выбранной таблице, суммы слов складываются; '
              'сокращение показано так, как его выполнил расчёт.</figcaption></figure>')


# ---------- numerology ----------

KEY_NUMBERS = (("life_path", "Жизненный путь"), ("destiny", "Судьба"), ("soul", "Душа"),
               ("personality", "Личность"), ("birthday", "День рождения"), ("maturity", "Зрелость"))


def key_numbers(data: dict, labels: dict[str, str]) -> str:
    numbers = data.get("key_numbers")
    if not isinstance(numbers, dict):
        return ""
    cards = []
    for index, (key, fallback) in enumerate(KEY_NUMBERS):
        item = numbers.get(key)
        if not isinstance(item, dict) or "master" not in item:
            continue
        steps = item.get("steps") if isinstance(item.get("steps"), list) else [item.get("input"), item["master"]]
        chain = " → ".join(_e(step) for step in steps) if len(steps) > 1 else "без сокращения"
        cards.append(f'<li class="s-in" style="{_step(0, index)}"><span class="num-label">{_e(labels.get(key, fallback))}</span>'
                     f'<span class="num-chain">{chain}</span>'
                     f'<strong class="num-value cnt" data-to="{_e(item["master"])}">{_e(item["master"])}</strong></li>')
    if not cards:
        return ""
    return ('<figure class="graphic scene num-graphic"><h3>Ключевые числа</h3><ul class="num-cards">' + "".join(cards) + '</ul>'
            '<figcaption>Крупно — итоговое число, под ним — исходная сумма и шаги сокращения из расчёта.</figcaption></figure>')


def square(data: dict, matrix_cells: str) -> str:
    """matrix_cells — готовые ячейки квадрата со ссылками на факты (report._matrix)."""
    source = data.get("square", {}).get("source_digits") if isinstance(data.get("square"), dict) else None
    digits = ""
    if isinstance(source, str) and source.isascii() and source.isdigit():
        digits = ('<div class="sq-digits" aria-hidden="true">' + "".join(
            f'<span class="{"zero " if d == "0" else ""}s-in s-pop" style="{_step(0, i)}">{d}</span>' for i, d in enumerate(source))
            + '</div><p class="sq-note s-in" style="--k:1">Нули в квадрат не идут</p>')
    return ('<figure class="graphic scene sq-graphic"><h3>Квадрат нумерологии</h3>' + digits + matrix_cells
            + '<figcaption>Цифры даты расходятся по своим ячейкам; число в ячейке — сколько раз цифра встретилась.</figcaption></figure>')
