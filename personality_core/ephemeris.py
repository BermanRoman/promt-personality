"""Pinned Astronomy Engine adapter; UTC input, apparent ecliptic of date output."""
from importlib.metadata import version
from functools import lru_cache

ENGINE_VERSION = "2.1.19"
BODY_NAMES = {
    "Солнце": "Sun", "Луна": "Moon", "Меркурий": "Mercury", "Венера": "Venus",
    "Марс": "Mars", "Юпитер": "Jupiter", "Сатурн": "Saturn", "Уран": "Uranus",
    "Нептун": "Neptune", "Плутон": "Pluto",
}


@lru_cache(maxsize=1)
def engine():
    try:
        import astronomy
        installed = version("astronomy-engine")
    except ImportError as exc:
        raise RuntimeError("Install dependencies with .venv/bin/python -m pip install -r requirements.txt") from exc
    if installed != ENGINE_VERSION:
        raise RuntimeError(f"Expected astronomy-engine=={ENGINE_VERSION}, found {installed}")
    return astronomy


def longitude(name, jd_utc):
    astronomy = engine()
    time = astronomy.Time(jd_utc - 2451545.0)
    body = getattr(astronomy.Body, BODY_NAMES[name])
    if body == astronomy.Body.Moon:
        # GeoVector special-cases Moon with geometric GeoMoon, so use the general
        # heliocentric light-time solver (which also supports the Moon) instead.
        vector = astronomy.BackdatePosition(time, astronomy.Body.Earth, body, True)
        vector.t = time  # Rotate at observation time, not light departure time.
    else:
        vector = astronomy.GeoVector(body, time, True)
    return astronomy.Ecliptic(vector).elon % 360.0


# Условность расчёта aspects-v1: виды, орбы и группы выбраны автором, это не астрономический факт.
# Соединения в список не входят; считаются только пары планет по готовым эклиптическим долготам.
ASPECTS_CONVENTION = "aspects-v1"
ASPECT_KINDS = (
    ("trine", "трин", 120, 7, "harmonious"),
    ("sextile", "секстиль", 60, 5, "harmonious"),
    ("square", "квадрат", 90, 7, "tense"),
    ("opposition", "оппозиция", 180, 8, "tense"),
)


def aspects(longitudes):
    """Aspects between planets from ecliptic longitudes: dict {planet_key: degrees}, order = dict order.

    A pair gets at most one aspect (the first matching kind; orbs of the kinds never overlap).
    Missing, non-finite or out-of-range longitudes are skipped, so no longitude means no aspects.
    """
    import math
    valid = [(key, value) for key, value in longitudes.items()
             if isinstance(value, (int, float)) and not isinstance(value, bool)
             and math.isfinite(value) and 0 <= value < 360]
    result = []
    for index, (first, a) in enumerate(valid):
        for second, b in valid[index + 1:]:
            distance = abs(a - b) % 360
            distance = min(distance, 360 - distance)
            for kind, name, exact, orb, group in ASPECT_KINDS:
                deviation = abs(distance - exact)
                if deviation <= orb:
                    result.append({"planets": [first, second], "kind": kind, "name": name, "group": group,
                                   "angle": round(distance, 3), "exact": exact,
                                   "deviation": round(deviation, 3), "orb": orb})
                    break
    return result
