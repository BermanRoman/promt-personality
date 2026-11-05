"""Astronomical reference, input validation, HD graph and reproducibility checks."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import hd
from personality_core import ephemeris

ROOT = Path(__file__).resolve().parents[1]


class EphemerisTests(unittest.TestCase):
    def test_independent_usno_march_equinox_2024(self):
        # US Naval Observatory seasons table: 2024-03-20 03:06 UTC.
        # At the equinox apparent solar longitude is zero; 0.001 degree
        # allows ~1.5 minutes for minute-rounded reference and model error.
        jd = hd.julian_day(datetime(2024, 3, 20, 3, 6, tzinfo=timezone.utc))
        lon = hd.body_longitude("Солнце", jd)
        self.assertLess(abs((lon + 180) % 360 - 180), 0.001)

    def test_independent_jpl_horizons_moon_offline(self):
        # Independent reviewer retrieved Horizons apparent geocentric ecliptic
        # of date (observer UT, Moon 301, CENTER=500@399, QUANTITIES=31) on
        # 2026-11-05. Frozen values, not a runtime API request; see docs/ephemeris.md.
        # The 0.003 degree tolerance covers only these three reference points.
        references = ((2451545.0, 223.3237860),
                      (2460462.5, 357.9428551),
                      (2378596.5, 219.2721289))
        for jd_ut, expected in references:
            with self.subTest(jd_ut=jd_ut):
                actual = hd.body_longitude("Луна", jd_ut, backend="astronomy")
                error = (actual - expected + 180.0) % 360.0 - 180.0
                self.assertLessEqual(abs(error), 0.003)

    def test_official_engine_time_fixture(self):
        # cosinekitty/astronomy generate/test.py AstroTime fixture.
        a = ephemeris.engine()
        dt = datetime(2018, 12, 2, 18, 30, 12, 543000, tzinfo=timezone.utc)
        t = a.Time(hd.julian_day(dt) - 2451545.0)
        self.assertAlmostEqual(t.ut, 6910.270978506945, places=8)
        self.assertAlmostEqual(t.tt, 6910.271800214368, places=8)

    def test_all_longitudes_and_earth_antipode(self):
        for jd in (hd.MIN_JD, 2451545.0, hd.MAX_JD - 1):
            for body in hd.BODIES:
                lon = hd.body_longitude(body, jd)
                self.assertTrue(math.isfinite(lon))
                self.assertTrue(0 <= lon < 360)
            self.assertAlmostEqual((hd.body_longitude("Земля", jd) -
                                    hd.body_longitude("Солнце", jd)) % 360, 180)

    def test_legacy_comparison_is_only_regression(self):
        # Agreement with a weaker model is not an accuracy reference.
        exact = hd.body_longitude("Солнце", 2451545.0)
        legacy = hd.body_longitude("Солнце", 2451545.0, backend="legacy")
        self.assertLess(abs(exact - legacy), 0.1)
        self.assertGreater(abs(exact - legacy), 1e-5)
        with self.assertRaises(ValueError):
            hd.body_longitude("Солнце", 2451545, backend="unknown")
        with patch.object(ephemeris, "engine", side_effect=RuntimeError("missing")):
            with self.assertRaises(RuntimeError):
                hd.body_longitude("Солнце", 2451545)
            self.assertTrue(math.isfinite(hd.body_longitude("Солнце", 2451545, backend="legacy")))

    def test_solar_arc_and_date_range(self):
        for birth in (datetime(1800, 4, 15), datetime(1990, 1, 15, 12), datetime(2050, 12, 31)):
            jd = hd.julian_day(birth)
            design = hd.design_jd(jd)
            arc = (hd.body_longitude("Солнце", jd) - hd.body_longitude("Солнце", design)) % 360
            self.assertAlmostEqual(arc, 88, places=7)
            self.assertTrue(70 < jd - design < 100)
        with self.assertRaisesRegex(ValueError, "Design date"):
            hd.design_jd(hd.MIN_JD)
        for jd in (hd.MIN_JD - 1e-5, hd.MAX_JD, float("nan")):
            with self.assertRaises(ValueError):
                hd.design_jd(jd)

    def test_convergence_guard(self):
        birth = 2451545.0
        def step_sun(body, jd, **kwargs):
            return 100.0 if jd == birth else (0.0 if jd < birth - 85 else 20.0)
        with patch.object(hd, "body_longitude", side_effect=step_sun):
            with self.assertRaisesRegex(RuntimeError, "converge"):
                hd.design_jd(birth)


class InputTests(unittest.TestCase):
    def test_dst_gap_fold(self):
        with self.assertRaisesRegex(ValueError, "gap"):
            hd.localize(datetime(2024, 3, 10, 2, 30), "America/New_York")
        repeated = datetime(2024, 11, 3, 1, 30)
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            hd.localize(repeated, "America/New_York")
        first = hd.localize(repeated, "America/New_York", fold=0)
        second = hd.localize(repeated, "America/New_York", fold=1)
        self.assertEqual((second.astimezone(timezone.utc) - first.astimezone(timezone.utc)).total_seconds(), 3600)
        for fold in (-1, 2, True):
            with self.assertRaises(ValueError):
                hd.localize(repeated, "America/New_York", fold=fold)
        with self.assertRaises(ValueError):
            hd.localize(datetime(2024, 1, 1, tzinfo=timezone.utc), "UTC")

    def test_coordinates(self):
        for lat, lon in ((90, 0), (-90, 0), (float("nan"), 0), (0, float("inf")), (0, 181)):
            with self.assertRaises(ValueError):
                hd.compute(datetime(2000, 1, 1), "UTC", lat, lon)
        hd.validate_coordinates(89.999, -180)
        hd.validate_coordinates(-89.999, 180)

    def test_sign_rounding(self):
        self.assertEqual(hd.to_sign(29.9999), "0°00' Телец")
        self.assertEqual(hd.to_sign(359.9999), "0°00' Овен")
        self.assertEqual(hd.to_sign(0), "0°00' Овен")
        self.assertEqual(hd.to_sign(-30), "0°00' Рыбы")

    def test_gate_line_boundaries(self):
        for i, gate in enumerate(hd.GATE_WHEEL):
            start = hd.WHEEL_START + i * hd.GATE_SPAN
            self.assertEqual(hd.gate_line(start)[:2], (gate, 1))
            self.assertEqual(hd.gate_line(start - 1e-8)[:2], (hd.GATE_WHEEL[i - 1], 6))
            for line in range(1, 7):
                edge = start + (line - 1) * hd.LINE_SPAN
                self.assertEqual(hd.gate_line(edge)[:2], (gate, line))
        self.assertEqual(hd.color_tone(0), (1, 1))
        self.assertEqual(hd.color_tone(1 - 1e-12), (6, 6))


class GraphTests(unittest.TestCase):
    def test_all_main_types(self):
        cases = [({}, "Рефлектор"), ({61: [], 24: []}, "Проектор"),
                 ({5: [], 15: []}, "Генератор"), ({34: [], 20: []}, "Манифестирующий Генератор"),
                 ({21: [], 45: []}, "Манифестор")]
        for gates, expected in cases:
            self.assertEqual(hd.build_chart(gates)["type"], expected)

    def test_undefined_vs_completely_open(self):
        ch = hd.build_chart({61: []})
        self.assertIn("Голова", ch["undefined_centers"])
        self.assertNotIn("Голова", ch["completely_open_centers"])
        self.assertEqual(ch["open_centers"], ch["undefined_centers"])
        ch = hd.build_chart({61: [], 24: [], 5: [], 15: []})
        self.assertEqual(ch["definition"], "Расщеплённое")
        self.assertEqual(ch["components"], sorted(ch["components"]))

    def test_default_and_provenance(self):
        result = hd.compute(datetime(1990, 1, 15, 12), "Europe/Moscow", 55.75, 37.62)
        self.assertEqual(result["input"]["node"], "средний")
        self.assertEqual(result["provenance"]["backend"], "astronomy")
        self.assertEqual(result["provenance"]["engine_version"], "2.1.19")
        self.assertIn("не рекомендация", result["determination"]["notice"])
        self.assertIn("approximate", result["provenance"]["node_model"])
        json.dumps(result, allow_nan=False)

    def test_cli_deterministic_json_across_hash_seeds(self):
        command = [sys.executable, "hd.py", "--date", "15.01.1990", "--time", "12:00",
                   "--tz", "Europe/Moscow", "--lat", "55.75", "--lon", "37.62", "--json"]
        results = [subprocess.check_output(command, cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": seed})
                   for seed in ("1", "2", "99")]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])


if __name__ == "__main__":
    unittest.main()
