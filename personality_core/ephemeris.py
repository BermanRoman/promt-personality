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
