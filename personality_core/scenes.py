"""Animated figures ("scenes") for the HTML report.

Every scene is rendered in its final state: without JavaScript, with reduced motion and in print the
reader sees the complete picture. assets/scenes.js only hides the steps until the figure scrolls
into view; a tap on the figure plays the steps backwards and then forwards again. Values come from the calculation; nothing is computed here
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

# Screen positions only (viewBox 0 0 300 512); the chart itself comes from hd.compute.
# name: (shape, geometry, anchor of channels, label text, label x, label y, text-anchor)
CENTER_SHAPES = {
    "Голова": ("poly", "150,10 180,58 120,58", (150, 42), "Голова", 150, 76, "middle"),
    "Аджна": ("poly", "120,90 180,90 150,138", (150, 106), "Аджна", 150, 156, "middle"),
    "Горло": ("rect", (126, 170, 48, 48), (150, 194), "Горло", 150, 236, "middle"),
    # подпись «G» слева от ромба, подписи боковых треугольников — над ними: не налезают на каналы
    "G-центр": ("poly", "150,252 182,284 150,316 118,284", (150, 284), "G", 110, 289, "end"),
    "Эго": ("poly", "198,290 238,306 198,322", (211, 306), "Эго", 218, 282, "middle"),
    "Селезёнка": ("poly", "40,346 88,374 40,402", (56, 374), "Селезёнка", 10, 336, "start"),
    "Сакрал": ("rect", (126, 350, 48, 48), (150, 374), "Сакрал", 150, 416, "middle"),
    "Солнечное сплетение": ("poly", "260,346 212,374 260,402", (244, 374), "Сплетение", 290, 336, "end"),
    "Корень": ("rect", (126, 438, 48, 48), (150, 462), "Корень", 150, 504, "middle"),
}


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
        (x1, y1), (x2, y2) = CENTER_SHAPES[a][2], CENTER_SHAPES[b][2]
        # parallel channels between the same centers are shifted sideways
        length = math.hypot(x2 - x1, y2 - y1) or 1
        shift = offset * 7
        nx, ny = -(y2 - y1) / length * shift, (x2 - x1) / length * shift
        x1, y1, x2, y2 = x1 + nx, y1 + ny, x2 + nx, y2 + ny
        lines.append(f'<line class="hd-channel" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'style="--len:{math.ceil(length)};--m:{index}"><title>Канал {_e(channel[0])}–{_e(channel[1])}</title></line>')
    shapes = []
    defined_index = 0
    for index, (name, (kind, geometry, _anchor, label, lx, ly, text_anchor)) in enumerate(CENTER_SHAPES.items()):
        state = "defined" if name in defined else "open"
        order = f"--j:{index}"
        if state == "defined":
            order += f";--d:{defined_index}"
            defined_index += 1
        title = f'<title>{_e(name)}: {"определён" if state == "defined" else "не определён"}</title>'
        if kind == "rect":
            x, y, w, h = geometry
            shapes.append(f'<rect class="hd-center {state}" style="{order}" x="{x}" y="{y}" width="{w}" height="{h}" rx="6">{title}</rect>')
        else:
            shapes.append(f'<polygon class="hd-center {state}" style="{order}" points="{geometry}">{title}</polygon>')
        shapes.append(f'<text class="hd-label" style="--j:{index}" x="{lx}" y="{ly}" text-anchor="{text_anchor}">{_e(label)}</text>')
    defined_names = ", ".join(name for name in CENTER_SHAPES if name in defined) or "нет"
    channel_names = ", ".join(f"{a}–{b}" for a, b in channels) or "нет"
    return ('<figure class="graphic scene hd-graphic"><h3>Бодиграф</h3>'
            '<svg class="chart bodygraph" viewBox="0 0 300 512" role="img" aria-labelledby="hd-graph-title hd-graph-desc">'
            '<title id="hd-graph-title">Бодиграф Human Design</title>'
            f'<desc id="hd-graph-desc">Определённые центры: {_e(defined_names)}. Каналы: {_e(channel_names)}.</desc>'
            + "".join(lines) + "".join(shapes) + '</svg>'
            '<ul class="graph-legend"><li><span class="swatch defined"></span>определённые центры</li>'
            '<li><span class="swatch open"></span>неопределённые</li><li><span class="swatch channel"></span>каналы</li></ul></figure>')


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


def square(source: object, matrix_cells: str, zero_step: int = 2) -> str:
    """matrix_cells — готовые ячейки квадрата (report._matrix).

    Шаги: 0 — цифры даты, zero_step — нули гаснут, сетка и цифры по одной в свои ячейки (report._matrix)."""
    digits = ""
    if isinstance(source, str) and source.isascii() and source.isdigit():
        digits = ('<div class="sq-digits" aria-hidden="true">' + "".join(
            f'<span class="{"zero " if d == "0" else ""}s-in s-pop" style="{_step(0, i)}">{d}</span>' for i, d in enumerate(source))
            + f'</div><p class="sq-note s-in" style="--k:{zero_step}">Нули в квадрат не идут</p>')
    return ('<figure class="graphic scene sq-graphic"><h3>Квадрат нумерологии</h3>' + digits + matrix_cells
            + '<figcaption>Цифры даты расходятся по своим ячейкам; число в ячейке — сколько раз цифра встретилась.</figcaption></figure>')
