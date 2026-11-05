#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Калькулятор Human Design + астрологических позиций.

Считает всё сам: эфемериды планет, колесо ворот, каналы, центры,
тип, авторитет, профиль, крест инкарнации, определение.

Зависимости: Python 3.9+, astronomy-engine==2.1.19 (requirements.txt).
Запуск:
    python3 hd.py --date 15.01.1990 --time 12:00 --tz Europe/Moscow --lat 55.75 --lon 37.62
    python3 hd.py ... --json
"""

import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from personality_core.ephemeris import ENGINE_VERSION, longitude as engine_longitude

D2R = math.pi / 180.0
R2D = 180.0 / math.pi


def norm360(x):
    return x % 360.0


# ---------------------------------------------------------------------------
# Время
# ---------------------------------------------------------------------------

def julian_day(dt_utc):
    """Юлианская дата из datetime в UTC."""
    y, m = dt_utc.year, dt_utc.month
    d = (dt_utc.day
         + (dt_utc.hour + dt_utc.minute / 60.0 + (dt_utc.second + dt_utc.microsecond / 1e6) / 3600.0) / 24.0)
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return (math.floor(365.25 * (y + 4716))
            + math.floor(30.6001 * (m + 1))
            + d + b - 1524.5)


def jd_to_datetime(jd):
    """Обратное преобразование: JD -> datetime UTC."""
    z = math.floor(jd + 0.5)
    f = (jd + 0.5) - z
    if z < 2299161:
        a = z
    else:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day = b - d - math.floor(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    day_int = int(day)
    frac = day - day_int
    return (datetime(year, month, day_int, tzinfo=timezone.utc)
            + timedelta(days=frac))


def centuries(jd):
    return (jd - 2451545.0) / 36525.0


# ---------------------------------------------------------------------------
# Нутация и наклон эклиптики
# ---------------------------------------------------------------------------

def nutation_longitude(jd):
    """Главный член нутации по долготе, в градусах."""
    t = centuries(jd)
    omega = 125.04452 - 1934.136261 * t
    l_sun = 280.4665 + 36000.7698 * t
    l_moon = 218.3165 + 481267.8813 * t
    dpsi = (-17.20 * math.sin(omega * D2R)
            - 1.32 * math.sin(2 * l_sun * D2R)
            - 0.23 * math.sin(2 * l_moon * D2R)
            + 0.21 * math.sin(2 * omega * D2R))
    return dpsi / 3600.0


def obliquity(jd):
    """Средний наклон эклиптики, в градусах."""
    t = centuries(jd)
    return (23.439291111
            - 0.0130041667 * t
            - 1.638889e-7 * t ** 2
            + 5.036111e-7 * t ** 3)


# ---------------------------------------------------------------------------
# Солнце (Meeus, гл. 25). Точность ~0.01 градуса.
# ---------------------------------------------------------------------------

def sun_longitude(jd):
    """Видимая геоцентрическая эклиптическая долгота Солнца, градусы."""
    t = centuries(jd)
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t ** 2
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t ** 2
    m_rad = norm360(m) * D2R
    c = ((1.914602 - 0.004817 * t - 0.000014 * t ** 2) * math.sin(m_rad)
         + (0.019993 - 0.000101 * t) * math.sin(2 * m_rad)
         + 0.000289 * math.sin(3 * m_rad))
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    apparent = true_long - 0.00569 - 0.00478 * math.sin(omega * D2R)
    return norm360(apparent)


# ---------------------------------------------------------------------------
# Луна (усечённая ELP-2000/82, главные члены). Точность ~2 угловых минуты.
# ---------------------------------------------------------------------------

_MOON_TERMS = [
    # (D, M, M', F, коэффициент в градусах)
    (0, 0, 1, 0, 6.288774),
    (2, 0, -1, 0, 1.274027),
    (2, 0, 0, 0, 0.658314),
    (0, 0, 2, 0, 0.213618),
    (0, 1, 0, 0, -0.185116),
    (0, 0, 0, 2, -0.114332),
    (2, 0, -2, 0, 0.058793),
    (2, -1, -1, 0, 0.057066),
    (2, 0, 1, 0, 0.053322),
    (2, -1, 0, 0, 0.045758),
    (0, 1, -1, 0, -0.040923),
    (1, 0, 0, 0, -0.034720),
    (0, 1, 1, 0, -0.030383),
    (2, 0, 0, -2, 0.015327),
    (0, 0, 1, 2, -0.012528),
    (0, 0, 1, -2, 0.010980),
    (4, 0, -1, 0, 0.010675),
    (0, 0, 3, 0, 0.010034),
    (4, 0, -2, 0, 0.008548),
    (2, 1, -1, 0, -0.007888),
    (2, 1, 0, 0, -0.006766),
    (1, 0, -1, 0, -0.005163),
    (1, 1, 0, 0, 0.004987),
    (2, -1, 1, 0, 0.004036),
    (2, 0, 2, 0, 0.003994),
    (4, 0, 0, 0, 0.003861),
    (2, 0, -3, 0, 0.003665),
    (0, 1, -2, 0, -0.002689),
    (2, 0, -1, 2, -0.002602),
    (2, -1, -2, 0, 0.002390),
    (1, 0, 1, 0, -0.002348),
    (2, -2, 0, 0, 0.002236),
    (0, 1, 2, 0, -0.002120),
    (0, 2, 0, 0, -0.002069),
    (2, -2, -1, 0, 0.002048),
]


def moon_longitude(jd):
    """Видимая геоцентрическая эклиптическая долгота Луны, градусы."""
    t = centuries(jd)
    l_prime = (218.3164477 + 481267.88123421 * t
               - 0.0015786 * t ** 2 + t ** 3 / 538841.0)
    d = (297.8501921 + 445267.1114034 * t
         - 0.0018819 * t ** 2 + t ** 3 / 545868.0)
    m = 357.5291092 + 35999.0502909 * t - 0.0001536 * t ** 2
    m_prime = (134.9633964 + 477198.8675055 * t
               + 0.0087414 * t ** 2 + t ** 3 / 69699.0)
    f = (93.2720950 + 483202.0175233 * t
         - 0.0036539 * t ** 2 - t ** 3 / 3526000.0)
    e = 1.0 - 0.002516 * t - 0.0000074 * t ** 2

    total = 0.0
    for cd, cm, cmp_, cf, coeff in _MOON_TERMS:
        arg = (cd * d + cm * m + cmp_ * m_prime + cf * f) * D2R
        term = coeff
        if abs(cm) == 1:
            term *= e
        elif abs(cm) == 2:
            term *= e * e
        total += term * math.sin(arg)

    lon = l_prime + total + nutation_longitude(jd)
    return norm360(lon)


def node_longitude(jd, true_node=False):
    """Mean polynomial node, or explicitly approximate truncated true node."""
    t = centuries(jd)
    omega_mean = (125.0445479 - 1934.1362891 * t
                  + 0.0020754 * t ** 2 + t ** 3 / 467441.0)
    if not true_node:
        return norm360(omega_mean)

    d = 297.8501921 + 445267.1114034 * t - 0.0018819 * t ** 2
    m = 357.5291092 + 35999.0502909 * t
    m_prime = 134.9633964 + 477198.8675055 * t + 0.0087414 * t ** 2
    f = 93.2720950 + 483202.0175233 * t - 0.0036539 * t ** 2

    corr = (-1.4979 * math.sin(2 * (d - f) * D2R)
            - 0.1500 * math.sin(m * D2R)
            - 0.1226 * math.sin(2 * d * D2R)
            + 0.1176 * math.sin(2 * f * D2R)
            - 0.0801 * math.sin(2 * (m_prime - f) * D2R))
    return norm360(omega_mean + corr)


# ---------------------------------------------------------------------------
# Планеты: кеплеровы элементы JPL (интервал 1800-2050)
# ---------------------------------------------------------------------------
# a (а.е.), e, I (град), L (град), долгота перигелия, долгота узла
# и их изменение за столетие.

_PLANET_ELEMENTS = {
    "Меркурий": (
        (0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593),
        (0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081),
    ),
    "Венера": (
        (0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255),
        (0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418),
    ),
    "Земля": (
        (1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0),
        (0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0),
    ),
    "Марс": (
        (1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891),
        (0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343),
    ),
    "Юпитер": (
        (5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909),
        (-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106),
    ),
    "Сатурн": (
        (9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448),
        (-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794),
    ),
    "Уран": (
        (19.18916464, 0.04725744, 0.77263783, 313.23810451, 170.95427630, 74.01692503),
        (-0.00196176, -0.00004397, -0.00242939, 428.48202785, 0.40805281, 0.04240589),
    ),
    "Нептун": (
        (30.06992276, 0.00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574),
        (0.00026291, 0.00005105, 0.00035372, 218.45945325, -0.32241464, -0.00508664),
    ),
    "Плутон": (
        (39.48211675, 0.24882730, 17.14001206, 238.92903833, 224.06891629, 110.30393684),
        (-0.00031596, 0.00005170, 0.00004818, 145.20780515, -0.04062942, -0.01183482),
    ),
}


def _kepler_xyz(name, t):
    """Гелиоцентрические координаты в эклиптике J2000, а.е."""
    base, rate = _PLANET_ELEMENTS[name]
    a = base[0] + rate[0] * t
    e = base[1] + rate[1] * t
    inc = base[2] + rate[2] * t
    l = base[3] + rate[3] * t
    peri = base[4] + rate[4] * t
    node = base[5] + rate[5] * t

    arg_peri = peri - node
    m = l - peri
    m = ((m + 180.0) % 360.0) - 180.0

    # Уравнение Кеплера
    e_deg = R2D * e
    ecc_anom = m + e_deg * math.sin(m * D2R)
    for _ in range(60):
        dm = m - (ecc_anom - e_deg * math.sin(ecc_anom * D2R))
        de = dm / (1.0 - e * math.cos(ecc_anom * D2R))
        ecc_anom += de
        if abs(de) < 1e-10:
            break

    x_orb = a * (math.cos(ecc_anom * D2R) - e)
    y_orb = a * math.sqrt(max(0.0, 1.0 - e * e)) * math.sin(ecc_anom * D2R)

    cw, sw = math.cos(arg_peri * D2R), math.sin(arg_peri * D2R)
    co, so = math.cos(node * D2R), math.sin(node * D2R)
    ci, si = math.cos(inc * D2R), math.sin(inc * D2R)

    x = (cw * co - sw * so * ci) * x_orb + (-sw * co - cw * so * ci) * y_orb
    y = (cw * so + sw * co * ci) * x_orb + (-sw * so + cw * co * ci) * y_orb
    z = (sw * si) * x_orb + (cw * si) * y_orb
    return x, y, z


def planet_longitude(name, jd):
    """Legacy approximate longitude; no light-time or aberration correction."""
    t = centuries(jd)
    px, py, pz = _kepler_xyz(name, t)
    ex, ey, ez = _kepler_xyz("Земля", t)
    gx, gy, gz = px - ex, py - ey, pz - ez
    lon_j2000 = norm360(math.atan2(gy, gx) * R2D)
    # Прецессия из J2000 в эклиптику даты
    precession = 1.396971 * t + 0.0003086 * t ** 2
    return norm360(lon_j2000 + precession + nutation_longitude(jd))


def body_longitude(name, jd, true_node=False, backend="astronomy"):
    validate_jd(jd)
    if backend not in ("astronomy", "legacy"):
        raise ValueError("backend must be astronomy or legacy")
    if name == "Земля":
        return norm360(body_longitude("Солнце", jd, true_node, backend) + 180.0)
    if name not in ("Северный узел", "Южный узел") and backend == "astronomy":
        return engine_longitude(name, jd)
    if name == "Солнце":
        return sun_longitude(jd)
    if name == "Земля":
        return norm360(sun_longitude(jd) + 180.0)
    if name == "Луна":
        return moon_longitude(jd)
    if name == "Северный узел":
        return node_longitude(jd, true_node)
    if name == "Южный узел":
        return norm360(node_longitude(jd, true_node) + 180.0)
    return planet_longitude(name, jd)


BODIES = ["Солнце", "Земля", "Северный узел", "Южный узел", "Луна",
          "Меркурий", "Венера", "Марс", "Юпитер", "Сатурн",
          "Уран", "Нептун", "Плутон"]


# ---------------------------------------------------------------------------
# Колесо ворот
# ---------------------------------------------------------------------------
# Ворота 41 начинаются в 2 градуса Водолея = 302 градуса эклиптики.
# Далее по колесу каждые 5.625 градуса.

GATE_WHEEL = [41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17,
              21, 51, 42, 3, 27, 24, 2, 23, 8, 20, 16, 35,
              45, 12, 15, 52, 39, 53, 62, 56, 31, 33, 7, 4,
              29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50,
              28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10, 58,
              38, 54, 61, 60]

WHEEL_START = 302.0
GATE_SPAN = 360.0 / 64.0        # 5.625
LINE_SPAN = GATE_SPAN / 6.0     # 0.9375


def gate_line(longitude):
    """Долгота -> (ворота, линия, позиция внутри линии 0..1)."""
    offset = norm360(longitude - WHEEL_START)
    idx = int(offset // GATE_SPAN)
    gate = GATE_WHEEL[idx]
    within = offset - idx * GATE_SPAN
    line = int(within // LINE_SPAN) + 1
    frac = (within - (line - 1) * LINE_SPAN) / LINE_SPAN
    return gate, line, frac


# Четверти: отсчёт от ворот 13, по 16 ворот на четверть.
_I13 = GATE_WHEEL.index(13)
QUARTERS = {
    "Инициации": [GATE_WHEEL[(_I13 + k) % 64] for k in range(0, 16)],
    "Цивилизации": [GATE_WHEEL[(_I13 + k) % 64] for k in range(16, 32)],
    "Дуальности": [GATE_WHEEL[(_I13 + k) % 64] for k in range(32, 48)],
    "Мутации": [GATE_WHEEL[(_I13 + k) % 64] for k in range(48, 64)],
}

DETERMINATION = {1: "Аппетит", 2: "Вкус", 3: "Жажда",
                 4: "Прикосновение", 5: "Звук", 6: "Свет"}


def quarter_of(gate):
    for name, gates in QUARTERS.items():
        if gate in gates:
            return name
    return None


def color_tone(frac):
    """Позиция внутри линии -> (цвет 1-6, тон 1-6)."""
    color = int(frac * 6) + 1
    rest = frac * 6 - int(frac * 6)
    tone = int(rest * 6) + 1
    return min(color, 6), min(tone, 6)


# ---------------------------------------------------------------------------
# Схема бодиграфа
# ---------------------------------------------------------------------------

CENTERS = {
    "Голова": [61, 63, 64],
    "Аджна": [4, 11, 17, 24, 43, 47],
    "Горло": [8, 12, 16, 20, 23, 31, 33, 35, 45, 56, 62],
    "G-центр": [1, 2, 7, 10, 13, 15, 25, 46],
    "Эго": [21, 26, 40, 51],
    "Сакрал": [3, 5, 9, 14, 27, 29, 34, 42, 59],
    "Солнечное сплетение": [6, 22, 30, 36, 37, 49, 55],
    "Селезёнка": [18, 28, 32, 44, 48, 50, 57],
    "Корень": [19, 38, 39, 41, 52, 53, 54, 58, 60],
}

CHANNELS = [
    (1, 8), (2, 14), (3, 60), (4, 63), (5, 15), (6, 59), (7, 31),
    (9, 52), (10, 20), (10, 34), (10, 57), (11, 56), (12, 22),
    (13, 33), (16, 48), (17, 62), (18, 58), (19, 49), (20, 34),
    (20, 57), (21, 45), (23, 43), (24, 61), (25, 51), (26, 44),
    (27, 50), (28, 38), (29, 46), (30, 41), (32, 54), (34, 57),
    (35, 36), (37, 40), (39, 55), (42, 53), (47, 64),
]

MOTORS = {"Сакрал", "Солнечное сплетение", "Эго", "Корень"}


def center_of_gate(gate):
    for center, gates in CENTERS.items():
        if gate in gates:
            return center
    raise ValueError(f"Ворота {gate} не найдены ни в одном центре")


def build_chart(activations):
    """activations: dict gate -> список активаций. Возвращает механику карты."""
    active_gates = set(activations.keys())

    defined_channels = [(a, b) for a, b in CHANNELS
                        if a in active_gates and b in active_gates]

    defined_centers = set()
    for a, b in defined_channels:
        defined_centers.add(center_of_gate(a))
        defined_centers.add(center_of_gate(b))

    # Граф определённых центров
    adjacency = {c: set() for c in defined_centers}
    for a, b in defined_channels:
        ca, cb = center_of_gate(a), center_of_gate(b)
        if ca != cb:
            adjacency[ca].add(cb)
            adjacency[cb].add(ca)

    # Связные компоненты -> определение
    components = []
    unseen = set(defined_centers)
    while unseen:
        stack = [unseen.pop()]
        comp = {stack[0]}
        while stack:
            node = stack.pop()
            for nb in adjacency[node]:
                if nb not in comp:
                    comp.add(nb)
                    unseen.discard(nb)
                    stack.append(nb)
        components.append(comp)

    def motor_to_throat():
        if "Горло" not in defined_centers:
            return False
        for comp in components:
            if "Горло" in comp and (comp & MOTORS):
                return True
        return False

    sacral = "Сакрал" in defined_centers
    connected = motor_to_throat()

    if not defined_centers:
        type_ = "Рефлектор"
    elif sacral:
        type_ = "Манифестирующий Генератор" if connected else "Генератор"
    else:
        type_ = "Манифестор" if connected else "Проектор"

    strategy = {
        "Генератор": "Ждать отклика",
        "Манифестирующий Генератор": "Ждать отклика, затем информировать",
        "Манифестор": "Информировать до действия",
        "Проектор": "Ждать приглашения",
        "Рефлектор": "Ждать полный лунный цикл (28 дней)",
    }[type_]

    if "Солнечное сплетение" in defined_centers:
        authority = "Эмоциональный"
    elif sacral:
        authority = "Сакральный"
    elif "Селезёнка" in defined_centers:
        authority = "Селезёночный"
    elif "Эго" in defined_centers:
        authority = "Эго"
    elif "G-центр" in defined_centers:
        authority = "Само-проецируемый"
    elif defined_centers:
        authority = "Ментальный (внешний авторитет)"
    else:
        authority = "Лунный"

    definition = {0: "Нет определения", 1: "Единичное", 2: "Расщеплённое",
                  3: "Тройное расщепление",
                  4: "Четверное расщепление"}.get(len(components), "Множественное")

    return {
        "channels": defined_channels,
        "defined_centers": sorted(defined_centers),
        "undefined_centers": sorted(set(CENTERS) - defined_centers),
        "completely_open_centers": sorted(c for c in CENTERS
                                           if not active_gates.intersection(CENTERS[c])),
        "open_centers": sorted(set(CENTERS) - defined_centers),  # Deprecated alias.
        "type": type_,
        "strategy": strategy,
        "authority": authority,
        "definition": definition,
        "components": sorted(sorted(c) for c in components),
    }


RIGHT_ANGLE = {"1/3", "1/4", "2/4", "2/5", "3/5", "3/6", "4/6"}
JUXTAPOSITION = {"4/1"}
LEFT_ANGLE = {"5/1", "5/2", "6/2", "6/3"}


def cross_angle(profile):
    if profile in RIGHT_ANGLE:
        return "Правоугольный крест"
    if profile in JUXTAPOSITION:
        return "Крест juxtaposition"
    if profile in LEFT_ANGLE:
        return "Левоугольный крест"
    return "Неопределённый угол"


# ---------------------------------------------------------------------------
# Астрология: асцендент и середина неба
# ---------------------------------------------------------------------------

def sidereal_time(jd, longitude_east):
    """Местное звёздное время в градусах."""
    t = centuries(jd)
    gst = (280.46061837 + 360.98564736629 * (jd - 2451545.0)
           + 0.000387933 * t ** 2 - t ** 3 / 38710000.0)
    return norm360(gst + longitude_east)


def ascendant_mc(jd, lat, lon):
    validate_coordinates(lat, lon)
    theta = sidereal_time(jd, lon) * D2R
    eps = obliquity(jd) * D2R
    phi = lat * D2R
    mc = math.atan2(math.sin(theta), math.cos(theta) * math.cos(eps))
    asc = math.atan2(math.cos(theta),
                     -(math.sin(theta) * math.cos(eps)
                       + math.tan(phi) * math.sin(eps)))
    return norm360(asc * R2D), norm360(mc * R2D)


SIGNS = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
         "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]


def to_sign(longitude):
    # Round globally before choosing the sign, carrying 30 degrees and 360.
    minutes = int(round(norm360(longitude) * 60.0)) % (360 * 60)
    idx, within = divmod(minutes, 30 * 60)
    d, m = divmod(within, 60)
    return f"{d}°{m:02d}' {SIGNS[idx]}"


# ---------------------------------------------------------------------------
# Дата дизайна: 88 градусов солнечной дуги до рождения
# ---------------------------------------------------------------------------

MIN_JD = julian_day(datetime(1800, 1, 1, tzinfo=timezone.utc))
MAX_JD = julian_day(datetime(2051, 1, 1, tzinfo=timezone.utc))


def validate_jd(jd):
    if not math.isfinite(jd) or not MIN_JD <= jd < MAX_JD:
        raise ValueError("Birth and design dates must both be within 1800–2050 UTC")


def design_jd(birth_jd, backend="astronomy"):
    """Solve 88 degrees of solar arc by bracketed bisection, not 88 days."""
    validate_jd(birth_jd)
    birth_sun = body_longitude("Солнце", birth_jd, backend=backend)

    def residual(jd):
        return norm360(birth_sun - body_longitude("Солнце", jd, backend=backend)) - 88.0

    lo, hi = max(MIN_JD, birth_jd - 100.0), max(MIN_JD, birth_jd - 70.0)
    if not residual(lo) >= 0.0 >= residual(hi):
        raise ValueError("Design date is outside 1800–2050 or solar arc is not bracketed")
    for _ in range(64):
        mid = (lo + hi) / 2.0
        error = residual(mid)
        if abs(error) < 1e-8:
            return mid
        if error > 0:
            lo = mid
        else:
            hi = mid
    raise RuntimeError("88-degree solar arc solver did not converge")


def localize(dt_local, tz_name, fold=None):
    """Reject missing/ambiguous wall times; fold is explicit only for repeats."""
    if dt_local.tzinfo is not None:
        raise ValueError("dt_local must be a naive local datetime; pass timezone separately")
    if fold is not None and (type(fold) is not int or fold not in (0, 1)):
        raise ValueError("fold must be 0 or 1")
    tz = ZoneInfo(tz_name)
    candidates = {}
    for value in (0, 1):
        aware = dt_local.replace(tzinfo=tz, fold=value)
        back = aware.astimezone(timezone.utc).astimezone(tz)
        if back.replace(tzinfo=None) == dt_local and back.fold == value:
            candidates[value] = aware
    if not candidates:
        raise ValueError("Nonexistent local time (DST gap)")
    if len(candidates) == 2 and fold is None:
        raise ValueError("Ambiguous local time; explicitly provide fold=0 or fold=1")
    if fold is not None and fold not in candidates:
        raise ValueError("fold is not valid for this local time")
    return candidates[fold if fold is not None else min(candidates)]


def validate_coordinates(lat, lon):
    if not math.isfinite(lat) or not -90 < lat < 90:
        raise ValueError("latitude must be finite and strictly between -90 and 90 for ASC")
    if not math.isfinite(lon) or not -180 <= lon <= 180:
        raise ValueError("longitude must be finite and within [-180, 180]")


# ---------------------------------------------------------------------------
# Сборка
# ---------------------------------------------------------------------------

def compute(dt_local, tz_name, lat, lon, true_node=False, fold=None, backend="astronomy"):
    validate_coordinates(lat, lon)
    dt_aware = localize(dt_local, tz_name, fold)
    dt_utc = dt_aware.astimezone(timezone.utc)
    offset_hours = dt_aware.utcoffset().total_seconds() / 3600.0

    p_jd = julian_day(dt_utc)
    d_jd = design_jd(p_jd, backend)

    activations = {}
    personality = {}
    design = {}

    for body in BODIES:
        lon_p = body_longitude(body, p_jd, true_node, backend)
        g, l, frac = gate_line(lon_p)
        personality[body] = {"longitude": lon_p, "gate": g, "line": l,
                             "sign": to_sign(lon_p),
                             "line_edge": min(frac, 1 - frac) < 0.05}
        activations.setdefault(g, []).append(("Личность", body, l))

    for body in BODIES:
        lon_d = body_longitude(body, d_jd, true_node, backend)
        g, l, frac = gate_line(lon_d)
        design[body] = {"longitude": lon_d, "gate": g, "line": l,
                        "sign": to_sign(lon_d),
                        "line_edge": min(frac, 1 - frac) < 0.05}
        activations.setdefault(g, []).append(("Дизайн", body, l))

    chart = build_chart(activations)

    # Четверть по Солнцу личности, питание по цвету Солнца дизайна
    quarter = quarter_of(personality["Солнце"]["gate"])
    _, _, d_sun_frac = gate_line(design["Солнце"]["longitude"])
    color, tone = color_tone(d_sun_frac)

    profile = f"{personality['Солнце']['line']}/{design['Солнце']['line']}"
    cross = {
        "angle": cross_angle(profile),
        "gates": (personality["Солнце"]["gate"], personality["Земля"]["gate"],
                  design["Солнце"]["gate"], design["Земля"]["gate"]),
    }

    asc, mc = ascendant_mc(p_jd, lat, lon)

    return {
        "input": {
            "local_time": dt_local.strftime("%d.%m.%Y %H:%M"),
            "timezone": tz_name,
            "utc_offset": offset_hours,
            "utc_time": dt_utc.strftime("%d.%m.%Y %H:%M"),
            "lat": lat, "lon": lon,
            "node": "истинный" if true_node else "средний",
            "fold": dt_aware.fold,
            "local_iso": dt_aware.isoformat(),
            "utc_iso": dt_utc.isoformat(),
        },
        "provenance": {
            "backend": backend,
            "engine_version": ENGINE_VERSION if backend == "astronomy" else None,
            "coordinate_frame": "geocentric true ecliptic/equinox of date",
            "planet_positions": "apparent: light-time and aberration" if backend == "astronomy" else "approximate legacy; no light-time/aberration",
            "time_scale": "UTC approximates UT1; TT from engine Delta-T model" if backend == "astronomy" else "UTC used as dynamical time (approximate)",
            "node_model": "truncated true node (approximate)" if true_node else "mean node polynomial (approximate)",
            "asc_mc_model": "legacy mean sidereal time and obliquity (approximate)",
            "date_range_utc": "1800-01-01 inclusive to 2051-01-01 exclusive; birth and design",
            "solar_arc_degrees": 88.0,
            "design_utc_iso": jd_to_datetime(d_jd).isoformat(),
            "limitations": "HD/astrology are symbolic systems without established scientific validity; boundary assignments and color/tone are sensitive to time and model precision",
            "deprecated_fields": {"chart.open_centers": "alias of undefined_centers; use completely_open_centers for centers without active gates"},
        },
        "design_date_utc": jd_to_datetime(d_jd).strftime("%d.%m.%Y %H:%M"),
        "personality": personality,
        "design": design,
        "profile": profile,
        "cross": cross,
        "chart": chart,
        "quarter": quarter,
        "determination": {"color": color, "tone": tone,
                          "name": DETERMINATION[color],
                          "notice": "Символическая классификация HD; не рекомендация по питанию или здоровью"},
        "astro": {"Асцендент": to_sign(asc), "Середина неба": to_sign(mc),
                  "asc_deg": asc, "mc_deg": mc},
    }


def render(res):
    out = []
    inp = res["input"]
    out.append("=" * 62)
    out.append("HUMAN DESIGN")
    out.append("=" * 62)
    out.append(f"Рождение (местное):  {inp['local_time']} {inp['timezone']} "
               f"(UTC{inp['utc_offset']:+g})")
    out.append(f"Рождение (UTC):      {inp['utc_time']}")
    out.append(f"Координаты:          {inp['lat']}, {inp['lon']}")
    out.append(f"Дата дизайна (UTC):  {res['design_date_utc']}")
    out.append("")

    ch = res["chart"]
    out.append(f"ТИП:        {ch['type']}")
    out.append(f"СТРАТЕГИЯ:  {ch['strategy']}")
    out.append(f"АВТОРИТЕТ:  {ch['authority']}")
    out.append(f"ПРОФИЛЬ:    {res['profile']}")
    out.append(f"ОПРЕДЕЛЕНИЕ: {ch['definition']}")
    out.append(f"КРЕСТ:      {res['cross']['angle']}, ворота "
               f"{res['cross']['gates']}")
    out.append(f"ЧЕТВЕРТЬ:   {res['quarter']}")
    det = res["determination"]
    out.append(f"ОПРЕДЕЛЕНИЕ HD: {det['name']} (цвет {det['color']}, тон {det['tone']})")
    out.append(det["notice"])
    out.append(f"ЭФЕМЕРИДЫ: {res['provenance']['backend']}; {res['provenance']['node_model']}")
    out.append(f"УЗЕЛ:       {inp['node']}")
    out.append("")

    out.append("-" * 62)
    out.append(f"{'ТЕЛО':<16}{'ЛИЧНОСТЬ':<24}{'ДИЗАЙН':<24}")
    out.append("-" * 62)
    for body in BODIES:
        p = res["personality"][body]
        d = res["design"][body]
        pm = "!" if p["line_edge"] else " "
        dm = "!" if d["line_edge"] else " "
        out.append(f"{body:<16}"
                   f"{p['gate']}.{p['line']}{pm} {p['sign']:<17}"
                   f"{d['gate']}.{d['line']}{dm} {d['sign']:<17}")
    out.append("")
    out.append("! = позиция ближе 5% к границе линии, возможен сдвиг")
    out.append("")

    out.append(f"ОПРЕДЕЛЁННЫЕ ЦЕНТРЫ ({len(ch['defined_centers'])}): "
               + ", ".join(ch["defined_centers"]))
    out.append(f"НЕОПРЕДЕЛЁННЫЕ ЦЕНТРЫ ({len(ch['undefined_centers'])}): "
               + ", ".join(ch["undefined_centers"]))
    out.append("ПОЛНОСТЬЮ ОТКРЫТЫЕ ЦЕНТРЫ: " + ", ".join(ch["completely_open_centers"]))
    out.append("")
    out.append(f"КАНАЛЫ ({len(ch['channels'])}): "
               + ", ".join(f"{a}-{b}" for a, b in ch["channels"]))
    out.append("")
    out.append("-" * 62)
    out.append("АСТРОЛОГИЯ")
    out.append("-" * 62)
    out.append(f"Асцендент:     {res['astro']['Асцендент']}")
    out.append(f"Середина неба: {res['astro']['Середина неба']}")
    for body in ["Солнце", "Луна", "Меркурий", "Венера", "Марс",
                 "Юпитер", "Сатурн", "Уран", "Нептун", "Плутон"]:
        out.append(f"{body:<15}{res['personality'][body]['sign']}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="ДД.ММ.ГГГГ")
    ap.add_argument("--time", required=True, help="ЧЧ:ММ (местное)")
    ap.add_argument("--tz", required=True, help="Europe/Moscow")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--node", choices=["true", "mean"], default="mean",
                    help="истинный или средний лунный узел")
    ap.add_argument("--fold", type=int, choices=[0, 1], help="повтор местного времени: 0 первый, 1 второй")
    ap.add_argument("--backend", choices=["astronomy", "legacy"], default="astronomy")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    try:
        dt = datetime.strptime(f"{a.date} {a.time}", "%d.%m.%Y %H:%M")
        res = compute(dt, a.tz, a.lat, a.lon, true_node=(a.node == "true"),
                      fold=a.fold, backend=a.backend)
    except (ValueError, KeyError, RuntimeError) as exc:
        ap.error(str(exc))
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(render(res))


if __name__ == "__main__":
    main()
