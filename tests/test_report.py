"""Safety and contract checks for the standalone HTML report."""

import math
import re
import unittest
from html.parser import HTMLParser

from personality_core.report import ASSETS, DISCLAIMER, MOTION_BOOT, SECTIONS, THEME_BOOT, render_report


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def calculation():
    return {
        "schema_version": 2,
        "calculation_id": "test-calculation",
        "input": {"name": "Тестовый профиль", "original_text": "Исходная строка\nс переносом", "answers": [5] * 36},
        "as_of": "2026-11-05",
        "modules": {key: {"status": "computed", "data": {}} for key, _ in SECTIONS},
        "facts": [{"id": "hd.type", "section": "human_design", "label": "Тип", "value": "Генератор"}],
        "warnings": [],
        "provenance": {},
    }


class ReportTests(unittest.TestCase):
    def test_all_sections_and_draft(self):
        report = render_report(calculation())
        doc = Document(report)
        ids = [attrs["id"] for _, attrs in doc.elements if "id" in attrs]
        for key, _ in SECTIONS:
            self.assertIn(key, ids)
        self.assertEqual(9, sum(tag == "section" for tag, _ in doc.elements))
        self.assertIn("Расчётный черновик", report)
        self.assertEqual(8, report.count("Интерпретация не подготовлена."))
        self.assertNotIn("Что можно попробовать", report)
        self.assertIn("Исходная строка\nс переносом", report)
        self.assertNotIn("[5, 5, 5", report)
        self.assertIn(f'<footer class="site-foot"><p class="pa-foot">{DISCLAIMER}</p></footer></div></main>', report)
        self.assertTrue(report.endswith('</script></body></html>'))

    def test_absent_and_unavailable_sections_explain_why(self):
        calc = calculation()
        calc["modules"] = {"astrology": {"status": "unavailable", "data": {}, "reason": "Нет точного времени"}}
        report = render_report(calc)
        self.assertIn("Нет точного времени", report)
        self.assertEqual(6, report.count("Расчёт недоступен:"))
        self.assertEqual(2, report.count("Синтез предыдущих разделов."))

    def test_full_narrative_synthesis_does_not_require_calculation_modules(self):
        calc = calculation()
        del calc["modules"]["purpose"]
        del calc["modules"]["finance"]
        narrative = {"calculation_id": calc["calculation_id"], "summary": [], "sections": {
            key: {"intro": f"Введение: {title}",
                  "interpretation": [{"text": f"Интерпретация: {title}", "sources": ["hd.type"]}],
                  "actions": [{"text": f"Действие: {title}", "sources": ["hd.type"]}]}
            for key, title in SECTIONS
        }}
        report = render_report(calc, narrative)
        self.assertNotIn("Расчёт недоступен", report)
        self.assertNotIn("Интерпретация не подготовлена", report)
        self.assertEqual(2, report.count("Синтез предыдущих разделов."))
        self.assertIn("Интерпретация: Карта предназначения", report)
        self.assertIn("Действие: Финансовый потенциал", report)

    def test_longitudes_round_for_display_without_mutating_facts(self):
        calc = calculation()
        precise = 135.123456789012345
        calc["facts"] += [
            {"id": "astro.sun.longitude", "section": "astrology", "label": "Солнце", "value": precise},
            {"id": "astro.moon.longitude", "section": "astrology", "label": "Луна", "value": 100},
            {"id": "astro.mars.longitude", "section": "astrology", "label": "Марс", "value": 0},
        ]
        report = render_report(calc)
        self.assertIn("135.123°", report)
        self.assertIn("100°", report)
        self.assertIn("0°", report)
        self.assertNotIn(str(precise), report)
        self.assertNotIn("100.0°", report)
        self.assertEqual(precise, calc["facts"][-3]["value"])
        self.assertIsInstance(calc["facts"][-2]["value"], int)

    def test_xss_is_text_everywhere(self):
        malicious = '\"><script>alert(1)</script><img src=x onerror=alert(1)>'
        calc = calculation()
        calc["input"]["name"] = malicious
        calc["input"]["original_text"] = malicious
        calc["as_of"] = malicious
        calc["calculation_id"] = malicious
        calc["facts"][0].update(id=malicious, label=malicious, value={malicious: malicious}, detail=malicious)
        calc["warnings"] = [malicious]
        calc["modules"]["finance"] = {"status": "unavailable", "reason": malicious}
        calc["modules"]["gematria"]["data"] = {"words": [{"word": malicious, "letters": [{key: malicious for key in ("source", "transliteration", "latin", "value", "kind")}], "total": malicious}]}
        topic = {"title": malicious, "paragraphs": [{"text": malicious, "sources": [malicious]}]}
        narrative = {"sections": {"human_design": {"intro": malicious, "topics": [topic], "interpretation": [{"text": malicious, "sources": [malicious]}], "actions": [{"text": malicious, "sources": [malicious]}]}}, "summary": [{"text": malicious, "sources": [malicious]}], "summary_topics": [topic]}
        report = render_report(calc, narrative)
        doc = Document(report)
        self.assertNotIn(malicious, report)
        self.assertNotIn("<script>alert", report)
        self.assertIn("&lt;script&gt;", report)
        # Only our own scripts: theme and motion boots in <head> and assets/scenes.js before </body>.
        scripts = [part.split("</script>", 1)[0] for part in report.split("<script>")[1:]]
        self.assertEqual([THEME_BOOT, MOTION_BOOT, (ASSETS / "scenes.js").read_text(encoding="utf-8")], scripts)
        self.assertFalse(any(tag in {"img", "iframe", "object"} for tag, _ in doc.elements))
        self.assertFalse(any(key.startswith("on") for _, attrs in doc.elements for key in attrs))

    def test_no_network_resources_or_javascript(self):
        report = render_report(calculation())
        doc = Document(report)
        for _, attrs in doc.elements:
            for key in ("src", "href", "action", "poster"):
                if key in attrs:
                    self.assertTrue(attrs[key].startswith("#"), attrs[key])
        self.assertNotRegex(report, r"(?i)@import|url\s*\(|https?://|javascript:")
        self.assertIn('content="noindex,nofollow,noarchive"', report)

    def test_unavailable_analysis_can_explain_missing_data_without_citations(self):
        calc = calculation()
        calc["modules"]["astrology"] = {"status": "unavailable", "data": {}, "reason": "Нет времени рождения"}
        calc["modules"]["purpose"] = {"status": "unavailable", "data": {}, "reason": "Недостаточно данных"}
        calc["modules"]["finance"] = {"status": "unavailable", "data": {}, "reason": "Недостаточно данных"}
        narrative = {"sections": {
            "astrology": {
                "interpretation": [{"text": "Без времени рождения нельзя определить дома.", "sources": []}],
                "actions": [{"text": "Неподтверждённая рекомендация", "sources": []}],
            },
            "human_design": {"interpretation": [{"text": "Неподтверждённая интерпретация", "sources": []}]},
            "purpose": {"interpretation": [{"text": "Неподтверждённое предназначение", "sources": []}]},
            "finance": {"interpretation": [{"text": "Неподтверждённые финансы", "sources": []}]},
        }}
        report = render_report(calc, narrative)
        self.assertIn("Без времени рождения нельзя определить дома.", report)
        for text in ("Неподтверждённая рекомендация", "Неподтверждённая интерпретация", "Неподтверждённое предназначение", "Неподтверждённые финансы"):
            self.assertNotIn(text, report)

    def test_citations_are_internal_and_resolve(self):
        calc = calculation()
        calc["facts"][0]["id"] = 'https://evil.invalid/" autofocus'
        source = calc["facts"][0]["id"]
        narrative = {"summary": [{"text": "Проверяемый вывод", "sources": [source]}], "sections": {"human_design": {"interpretation": [{"text": "Есть источник", "sources": [source]}, {"text": "Нет источника", "sources": ["unknown"]}], "actions": [{"text": "Неподтверждённое действие", "sources": []}]}}}
        report = render_report(calc, narrative)
        doc = Document(report)
        ids = [attrs["id"] for _, attrs in doc.elements if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for _, attrs in doc.elements:
            if "href" in attrs:
                self.assertIn(attrs["href"][1:], ids)
        self.assertIn("Есть источник", report)
        self.assertNotIn('href="#fact-', report)
        self.assertNotIn("Нет источника", report)
        self.assertNotIn("Неподтверждённое действие", report)

    def test_visualizations_use_facts(self):
        calc = calculation()
        calc["facts"] += [{"id": f"num.matrix.{digit}", "section": "numerology", "label": f"Цифра {digit}", "value": digit % 3} for digit in range(1, 10)]
        calc["facts"] += [{"id": f"arch.{i}", "section": "archetypes", "label": f"Архетип {i}", "value": i} for i in range(1, 13)]
        calc["facts"] += [{"id": "astro.sun.longitude", "section": "astrology", "label": "Солнце", "value": 135.5}]
        report = render_report(calc)
        self.assertEqual(9, report.count('class="matrix-cell'))
        self.assertEqual(12, report.count('class="bar-fill'))
        self.assertIn("135.5°", report)
        self.assertIn('<svg class="chart wheel-chart"', report)
        self.assertNotIn("аспект", report.split("</style>", 1)[1].lower().replace("аспекты не", ""))
        self.assertNotIn('class="graphic scene hd-graphic"', report)

    def test_missing_invalid_or_cross_section_graphics_not_fabricated(self):
        calc = calculation()
        calc["facts"] += [{"id": "astro.sun.longitude", "section": "astrology", "label": "Солнце", "value": float("nan")}, {"id": "arch.1", "section": "finance", "label": "Не архетип", "value": 100}]
        report = render_report(calc)
        self.assertNotIn('<svg class="chart wheel-chart"', report)
        self.assertNotIn('class="matrix-cell', report)
        self.assertNotIn('class="bar-fill', report)

    def test_gematria_preserves_letter_details_without_recalculation(self):
        calc = calculation()
        calc["modules"]["gematria"]["data"] = {"words": [{"word": "Анна", "letters": [{"source": "А", "transliteration": "A", "latin": "A", "value": 1, "kind": "vowel"}], "total": 987}]}
        report = render_report(calc)
        self.assertIn("Итого для слова: 987", report)
        self.assertIn("Транслитерация", report)
        self.assertIn("vowel", report)

    def test_responsive_print_and_keyboard_access(self):
        report = render_report(calculation())
        self.assertIn("@media print", report)
        self.assertIn("@media (max-width: 480px)", report)
        self.assertIn("overflow-x: auto", report)
        self.assertIn("focus-visible", report)
        self.assertIn("--fs-m: 1.1875rem", report)
        self.assertIn("--paper: #faf7f2", report)
        self.assertIn("--accent: #493447", report)
        self.assertIn("--rose: #bc8f9b", report)
        self.assertIn("prefers-reduced-motion: reduce", report)
        self.assertIn('html[data-theme="dark"]', report)
        self.assertIn('<html lang="ru" data-theme="dark">', report)
        self.assertIn('id="pa-theme" role="switch"', report)
        self.assertIn('aria-label="Тёмная тема"', report)
        self.assertNotIn("Светлая тема", report)  # подпись переключателя постоянна, меняется только aria-checked
        self.assertIn("setAttribute('aria-checked'", report + (ASSETS / "scenes.js").read_text(encoding="utf-8"))
        self.assertNotIn("setAttribute('aria-label'", (ASSETS / "scenes.js").read_text(encoding="utf-8"))
        self.assertIn("r.classList.remove('gj')", report)  # запасной таймер скрывает переключатель без scenes.js
        self.assertIn('details::details-content { content-visibility: visible', report)
        self.assertNotIn('aria-label="Оглавление"', report)
        self.assertNotIn('fact-details', report)
        self.assertNotIn('technical-details', report)
        self.assertNotIn('"answers"', report)

    def test_header_is_orbit_caption_and_word_without_name_and_contents(self):
        calc = calculation()
        narrative = {"sections": {"human_design": {
            "intro": "Вводный текст",
            "interpretation": [{"text": "Чтение результата", "sources": ["hd.type"]}],
            "actions": [{"text": "Проверить на опыте", "sources": ["hd.type"]}],
        }}}
        report = render_report(calc, narrative, banner="Пример")
        header = report.split('<header class="note-head">', 1)[1].split('</header>', 1)[0]
        self.assertNotIn("Тестовый профиль", header)
        self.assertNotIn(calc["calculation_id"], header)
        self.assertIn('class="pa-art" aria-hidden="true"', header)
        self.assertIn('d="M 224 155 A 69 69 0 1 0 224 285 A 83 83 0 0 1 224 155"', header)
        self.assertEqual(2, header.count('<ellipse'))
        self.assertEqual(2, header.count('<g class="a-dot a-dot'))
        self.assertEqual(3, header.count('class="a-star"'))
        self.assertIn('<p class="pa-eyebrow">Матрица программного комплекса</p><h1>Судьба</h1>', header)
        self.assertIn("<title>Анализ личности — Тестовый профиль</title>", report)
        self.assertIn('<p class="example-banner">Пример</p>', report)
        body = report.split("</style>", 1)[1]
        for gone in ("masthead", "Личная карта", "Индивидуальный разбор", 'class="contents"', "Грани вашего", 'class="hero'):
            self.assertNotIn(gone, body)
        self.assertLess(report.index('<header class="note-head">'), report.index('<aside class="input-card"'))
        self.assertNotIn("Расчётные факты и источники", report)
        self.assertNotIn("Технические сведения", report)
        section = report.split('id="human_design"', 1)[1].split('</section>', 1)[0].replace("&nbsp;", " ")
        self.assertLess(section.index("Вводный текст"), section.index('class="parameter-strip"'))
        self.assertLess(section.index("Чтение результата"), section.index("Проверить на опыте"))

    def test_section_heading_kicker_then_outlined_number_and_title(self):
        report = render_report(calculation())
        section = report.split('id="human_design"', 1)[1].split('</section>', 1)[0]
        self.assertIn('<div class="section-heading"><p class="section-kicker">Ритм решений и взаимодействия</p>'
                      '<h2 id="heading-human_design"><span class="section-number" aria-hidden="true">01</span> Human Design</h2></div>', section)
        self.assertIn('<span class="section-number" aria-hidden="true">09</span> Общий разбор', report)

    def test_questions_cards_parentheses_and_closing_dot(self):
        calc = calculation()
        narrative = {"sections": {"human_design": {
            "interpretation": [{"text": "Он говорит «да» (но не всегда).", "sources": ["hd.type"]}, {"text": "Конец предложения (примечание).", "sources": ["hd.type"]}],
            "actions": [{"text": "Две недели отмечайте решения", "sources": ["hd.type"]}, {"text": "Назовите срок", "sources": ["hd.type"]}],
        }}}
        report = render_report(calc, narrative)
        self.assertIn('<aside class="pa-read"><h3>Как это можно прочитать?</h3>', report)
        self.assertIn('<p class="pa-try-k">От размышления к опыту</p><h3>Что можно попробовать?</h3><ol class="pa-try-list"><li>', report)
        self.assertIn('<span class="paren">(но&nbsp;не&nbsp;всегда)</span></p>', report)
        self.assertIn('<span class="paren">(примечание)</span></p>', report)
        self.assertNotIn(')</span>.</p>', report)
        # внутри абзаца точка после » остаётся: снимается только в конце текста
        merged = render_report(calc, {"sections": {"human_design": {"interpretation": [{"text": "Слово «да». Потом нет.", "sources": ["hd.type"]}]}}})
        self.assertIn("«да». Потом", merged)
        closing = render_report(calc, {"sections": {"human_design": {"interpretation": [{"text": "Он сказал «да».", "sources": ["hd.type"]}]}}})
        self.assertIn("«да»</p>", closing)

    def test_no_footnote_links_and_no_fact_anchors(self):
        calc = calculation()
        narrative = {"summary": [{"text": "Вывод", "sources": ["hd.type"]}], "sections": {"human_design": {"interpretation": [{"text": "Есть источник", "sources": ["hd.type"]}]}}}
        report = render_report(calc, narrative)
        self.assertIn("Есть источник", report)
        self.assertNotIn('class="sources"', report)
        self.assertNotIn("[1]", report)
        self.assertNotIn('id="fact-', report)
        self.assertNotIn('href="#fact-', report)
        self.assertNotIn("Источник:", report)

    def test_input_card_has_caps_labels_over_values_and_quiet_notes(self):
        calc = calculation()
        calc["input"].update(birth_date="1990-01-15", birth_time="12:00", timezone="Europe/Moscow", time_accuracy="approximate", time_window_minutes=15)
        calc["modules"]["human_design"]["data"] = {"input": {"utc_offset": 3}}
        inputs = render_report(calc).split('<aside class="input-card"', 1)[1].split('</aside>', 1)[0]
        self.assertIn('Основа вашего разбора', inputs)
        self.assertIn('<div><dt>Дата рождения</dt><dd>15.01.1990</dd></div>', inputs)
        self.assertIn('<dd>Europe/Moscow<small>UTC+3 на момент рождения</small></dd>', inputs)
        self.assertIn('<dd>Приблизительное время<small>окно ±15 мин.</small></dd>', inputs)

    def test_key_cards_only_use_existing_facts_and_keep_ties(self):
        calc = calculation()
        calc["facts"] += [
            {"id": "num.life_path", "section": "numerology", "label": "Жизненный путь", "value": 7},
            {"id": "arch.1", "section": "archetypes", "label": "Искатель", "value": 15, "detail": "Плотный ранг: 1; сумма трёх ответов."},
            {"id": "arch.2", "section": "archetypes", "label": "Творец", "value": 15, "detail": "Плотный ранг: 1; сумма трёх ответов."},
            {"id": "arch.3", "section": "archetypes", "label": "Герой", "value": 14, "detail": "Плотный ранг: 2; сумма трёх ответов."},
        ]
        report = render_report(calc)
        cards = report.split('aria-label="Ключевые показатели">', 1)[1].split('<section class="report-section"', 1)[0]
        self.assertEqual(3, cards.count('class="key-card"'))
        self.assertIn("Ведущие архетипы", cards)
        self.assertIn("Искатель", cards)
        self.assertIn("Творец", cards)
        self.assertNotIn("Герой", cards)
        calc["facts"] = []
        self.assertNotIn('aria-label="Ключевые показатели"', render_report(calc))

    def test_open_input_and_final_summary_reading_order(self):
        calc = calculation()
        calc["input"].update(birth_date="1990-01-15", birth_time="12:00", birth_place="Москва", timezone="Europe/Moscow", time_accuracy="approximate", time_window_minutes=15)
        narrative = {"summary": [{"text": "Итоговые связи", "sources": ["hd.type"]}], "summary_topics": [
            {"title": "Общая картина", "paragraphs": [{"text": "Подробный синтез", "sources": ["hd.type"]}]}
        ]}
        report = render_report(calc, narrative)
        self.assertLess(report.index('</header>'), report.index('<aside class="input-card"'))
        self.assertLess(report.index('<aside class="input-card"'), report.index('aria-label="Ключевые показатели"'))
        inputs = report.split('<aside class="input-card"', 1)[1].split('</aside>', 1)[0]
        self.assertNotIn('<details', inputs)
        self.assertIn("Исходная строка\nс переносом", inputs)
        self.assertIn("Europe/Moscow", inputs)
        self.assertIn("окно ±15 мин.", inputs)
        self.assertNotIn("Тестовый профиль", inputs)
        self.assertNotIn("На первый взгляд", report)
        self.assertLess(report.index('id="finance"'), report.index('id="summary"'))
        self.assertLess(report.index('id="summary"'), report.index('class="site-foot"'))
        self.assertLess(report.index("Итоговые связи"), report.index("Общая картина"))
        self.assertIn("Подробный синтез", report)

    def test_topics_obey_source_rules_and_render_in_all_sections(self):
        calc = calculation()
        narrative = {"sections": {key: {"topics": [{"title": f"Тема {key}", "paragraphs": [
            {"text": f"Абзац {key}", "sources": ["hd.type"]},
            {"text": "НЕВЕРНЫЙ_ИСТОЧНИК", "sources": ["missing"]},
        ]}]} for key, _ in SECTIONS}, "summary_topics": [{"title": "НЕВЕРНЫЙ_ИТОГ", "paragraphs": [{"text": "БЕЗ_ОСНОВАНИЯ", "sources": []}]}]}
        report = render_report(calc, narrative)
        for key, _ in SECTIONS:
            self.assertIn(f"Тема {key}", report)
            self.assertIn(f"Абзац {key}", report)
        self.assertNotIn("НЕВЕРНЫЙ_ИСТОЧНИК", report)
        self.assertNotIn("НЕВЕРНЫЙ_ИТОГ", report)
        self.assertNotIn("БЕЗ_ОСНОВАНИЯ", report)
        calc["modules"]["numerology"]["status"] = "unavailable"
        narrative["sections"]["life_cycles"] = {"topics": [{"title": "Данные недоступны", "paragraphs": [{"text": "Объяснение отсутствия", "sources": []}]}]}
        self.assertIn("Объяснение отсутствия", render_report(calc, narrative))

    def test_cycles_use_existing_numbers_and_exact_intervals(self):
        calc = calculation()
        calc["input"]["birth_date"] = "1990-11-06"
        calc["modules"].pop("life_cycles", None)
        peaks = [
            {"number": {"master": 11}, "age_start_inclusive": 0, "age_end_exclusive": 36},
            {"number": {"master": 7}, "age_start_inclusive": 36, "age_end_exclusive": 45},
            {"number": {"master": 5}, "age_start_inclusive": 45, "age_end_exclusive": 54},
            {"number": {"master": 9}, "age_start_inclusive": 54, "age_end_exclusive": None},
        ]
        calc["modules"]["numerology"]["data"] = {"pinnacles": peaks, "challenges": [1, 2, 3, 4]}
        calc["facts"] += [
            {"id": f"num.pinnacle.{i}", "section": "life_cycles", "label": f"Пик {i}", "value": peak["number"]["master"]}
            for i, peak in enumerate(peaks, 1)
        ]
        report = render_report(calc)
        cycles = report.split('id="life_cycles"', 1)[1].split('</section>', 1)[0]
        self.assertNotIn("Расчёт недоступен", cycles)
        self.assertIn("35 полных лет", cycles)
        self.assertIn("0 включительно · 36 не включается", cycles)
        self.assertIn("От 54 лет", cycles)
        self.assertIn("Без верхней границы", cycles)
        self.assertRegex(cycles, r'aria-current="step" style="[^"]*"><span class="period-index">01')
        self.assertIn('<strong>11</strong>', cycles)
        self.assertEqual(1, cycles.count('aria-current="step"'))
        calc["as_of"] = "2026-11-06"
        report = render_report(calc)
        self.assertRegex(report, r'aria-current="step" style="[^"]*"><span class="period-index">02')
        self.assertEqual(11, peaks[0]["number"]["master"])

    def test_gematria_table_scrolls_by_keyboard_and_no_zodiac_glyphs(self):
        calc = calculation()
        calc["modules"]["gematria"]["data"] = {"words": [{"word": "Анна", "letters": [{"source": "А", "transliteration": "A", "latin": "A", "value": 1, "kind": "vowel"}], "total": 987}]}
        report = render_report(calc)
        self.assertIn('class="table-wrap" role="region"', report)
        self.assertIn('tabindex="0"', report)
        self.assertFalse(any(0x2648 <= ord(character) <= 0x2653 for character in report))

    def test_astrology_wheel_has_signs_planet_marks_and_no_lists_under_it(self):
        calc = calculation()
        planets = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto")
        calc["facts"] += [{"id": f"astro.{planet}.longitude", "section": "astrology", "label": planet, "value": i * 30 + 2.12345} for i, planet in enumerate(planets)]
        report = render_report(calc)
        self.assertIn('class="chart wheel-chart"', report)
        self.assertEqual(12, report.count('<text class="w-sign"'))
        for label in ("Овн", "Тел", "Блз", "Рак", "Лев", "Дев", "Вес", "Скр", "Стр", "Коз", "Вод", "Рыб"):
            self.assertIn(f'>{label}</text>', report)
        self.assertEqual(10, report.count('<circle class="w-pl"'))
        for mark in ("Су", "Лу", "Ме", "Ве", "Ма", "Юп", "Са", "Ур", "Не", "Пл"):
            self.assertIn(f'>{mark}</text>', report)
        self.assertNotIn("planet-legend", report)
        self.assertNotIn("Таблица положений планет", report)
        self.assertNotIn("chart-instruction", report)
        figure = report.split('<figure class="graphic scene astrology-graphic">', 1)[1].split('</figure>', 1)[0]
        self.assertNotIn("<figcaption>", figure)
        self.assertNotIn("<ol", figure)
        self.assertNotIn("аспект", figure.lower())  # фактов аспектов нет: круг их не рисует
        self.assertNotIn("w-asp", figure)
        # доступное описание круга хранит положения без списка на странице
        self.assertIn("2.123°", report)
        # плотная группа раздвигается по дуге, долготы не меняются: 10 кружков, расстояние между центрами не меньше диаметра
        for fact in calc["facts"][1:]:
            fact["value"] = 10
        dense = render_report(calc)
        centers = [(float(x), float(y)) for x, y in re.findall(r'<circle class="w-pl" cx="([\d.]+)" cy="([\d.]+)" r="19"/>', dense)]
        self.assertEqual(10, len(centers))
        for i, a in enumerate(centers):
            for b in centers[i + 1:]:
                self.assertGreaterEqual(math.hypot(a[0] - b[0], a[1] - b[1]), 38)

    def test_wheel_turns_so_ascendant_is_on_the_left_and_draws_axes(self):
        calc = calculation()
        calc["facts"] += [{"id": "astro.sun.longitude", "section": "astrology", "label": "Солнце", "value": 100.0},
                          {"id": "astro.ascendant.longitude", "section": "astrology", "label": "Асц", "value": 157.664},
                          {"id": "astro.midheaven.longitude", "section": "astrology", "label": "MC", "value": 57.45}]
        report = render_report(calc)
        self.assertEqual(2, report.count('class="w-axis s-draw"'))
        self.assertIn(">Асц≈</text>", report)
        self.assertIn(">MC≈</text>", report)
        axis = re.search(r'<line class="w-axis s-draw" x1="([\d.]+)" y1="([\d.]+)"', report)
        self.assertLess(float(axis.group(1)), 100)  # конец оси Асцендента — слева от центра
        self.assertIn("приближённо", report)

    def _aspect_calc(self, *aspects):
        calc = calculation()
        calc["facts"] += [{"id": "astro.sun.longitude", "section": "astrology", "label": "Солнце", "value": 177.074},
                          {"id": "astro.saturn.longitude", "section": "astrology", "label": "Сатурн", "value": 18.293},
                          {"id": "astro.neptune.longitude", "section": "astrology", "label": "Нептун", "value": 297.27},
                          {"id": "astro.mars.longitude", "section": "astrology", "label": "Марс", "value": 233.836}]
        for first, second, kind, deviation in aspects:
            calc["facts"].append({"id": f"astro.aspect.{first}.{second}", "section": "astrology", "label": "аспект",
                                  "value": {"planets": [first, second], "kind": kind, "deviation": deviation}})
        return calc

    def test_aspect_lines_legend_and_description(self):
        report = render_report(self._aspect_calc(("sun", "neptune", "trine", 0.196), ("sun", "mars", "sextile", 3.238),
                                                 ("sun", "saturn", "square", 5.0)))
        figure = report.split('<figure class="graphic scene astrology-graphic">', 1)[1].split('</figure>', 1)[0]
        self.assertEqual(2, figure.count('class="w-asp w-asp--h s-draw"'))
        self.assertEqual(1, figure.count('class="w-asp w-asp--t s-draw"'))
        self.assertIn("гармоничные аспекты: трин 120°, секстиль 60°", figure)
        self.assertIn("напряжённые: квадрат 90°, оппозиция 180°", figure)
        self.assertIn("Аспекты: Солнце — Нептун, трин; Солнце — Марс, секстиль; Солнце — Сатурн, квадрат.", figure)
        self.assertIn("Солнце — Нептун: трин 120° (отклонение 0.196°)", figure)
        # линия идёт между точками планет на внутреннем круге (радиус 118), а не из центра
        line = re.search(r'<line class="w-asp w-asp--h s-draw" x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"', figure)
        for x, y in ((line.group(1), line.group(2)), (line.group(3), line.group(4))):
            self.assertAlmostEqual(118, math.hypot(float(x) - 300, float(y) - 300), delta=0.2)

    def test_aspects_skip_unknown_planets_and_escape_text(self):
        calc = self._aspect_calc(("sun", "pluto", "trine", 1))  # Плутона нет на круге
        calc["facts"].append({"id": "astro.aspect.sun.saturn", "section": "astrology", "label": "<b>x</b>",
                              "value": {"planets": ["sun", "saturn"], "kind": "<script>alert(1)</script>"}})
        calc["facts"].append({"id": "astro.aspect.sun.mars", "section": "astrology", "label": "x",
                              "value": {"planets": ["sun", "mars"], "kind": "square", "deviation": "<img onerror=x>"}})
        report = render_report(calc)
        figure = report.split('<figure class="graphic scene astrology-graphic">', 1)[1].split('</figure>', 1)[0]
        self.assertEqual(1, figure.count('class="w-asp'))  # только корректный квадрат Солнце — Марс
        self.assertNotIn("<script>alert", report)
        self.assertNotIn("<img onerror", report)
        self.assertNotIn("<b>x</b>", figure)

    def test_bodygraph_draws_existing_chart_only(self):
        calc = calculation()
        calc["modules"]["human_design"]["data"] = {"chart": {"channels": [[3, 60], [10, 57]], "defined_centers": ["Сакрал", "Корень", "G-центр", "Селезёнка"]}}
        report = render_report(calc)
        self.assertIn('class="graphic scene hd-graphic"', report)
        self.assertEqual(2, report.count('class="hd-channel"'))
        self.assertEqual(4, report.count('class="hd-center defined'))
        self.assertEqual(5, report.count('class="hd-center open'))
        self.assertEqual(9, report.count('class="hd-label"'))
        self.assertIn("Канал 3–60", report)
        figure = report.split('hd-graphic', 1)[1].split('</figure>', 1)[0]
        for label in ("Голова", "Аджна", "Горло", "Эго", "Селезёнка", "Сакрал", "Сплетение", "Корень"):
            self.assertIn(f'>{label}</text>', figure)
        # «G» стоит слева от ромба, подписи боковых треугольников — над ними
        self.assertIn('x="110" y="289" text-anchor="end">G</text>', figure)
        self.assertIn('y="336" text-anchor="start">Селезёнка</text>', figure)
        for text in ("определённые центры", "неопределённые", "каналы"):
            self.assertIn(text, figure)
        self.assertNotIn("<figcaption>", figure)
        calc["modules"]["human_design"]["data"]["chart"]["channels"] = [[3, 999]]
        self.assertNotIn('class="graphic scene hd-graphic"', render_report(calc))

    def test_hidden_channel_leaves_no_round_cap(self):
        css = (ASSETS / "report.css").read_text(encoding="utf-8")
        self.assertIn("stroke-dasharray: calc(var(--len) * 1px) calc(var(--len) * 1px + 12px)", css)
        self.assertIn("stroke-dashoffset: calc(var(--len) * 1px + 6px)", css)

    def test_square_steps_date_zeros_grid_then_digits_one_by_one(self):
        calc = calculation()
        calc["modules"]["numerology"]["data"] = {"square": {"source_digits": "15011990"}}
        counts = {1: 3, 5: 1, 9: 2}
        calc["facts"] += [{"id": f"num.matrix.{d}", "section": "numerology", "label": f"Цифра {d}", "value": counts.get(d, 0)} for d in range(1, 10)]
        report = render_report(calc)
        figure = report.split('sq-graphic', 1)[1].split('</figure>', 1)[0]
        self.assertEqual(6, figure.count('<span class="s-in s-pop" style="--k:0;'))
        self.assertEqual(2, figure.count('class="zero s-in s-pop"'))
        self.assertIn('class="sq-note s-in" style="--k:2"', figure)
        self.assertEqual(9, figure.count('style="--k:3;--j:'))
        self.assertIn("Цифра 1: 3", figure)
        self.assertIn("Цифра 2: 0", figure)
        # шесть ненулевых цифр даты ложатся по очереди на шагах 4–9; пустые ячейки — прочерк после последней
        steps = sorted(int(k) for k in re.findall(r'<span class="s-in s-pop" style="--k:(\d+)">[1-9]</span>', figure))
        self.assertEqual([4, 5, 6, 7, 8, 9], steps)
        self.assertEqual(6, figure.count('style="--k:10;--j:'))
        self.assertEqual(6, figure.count('>—</span>'))

    def test_scenes_script_has_reverse_replay_hidden_button_and_intro(self):
        js = (ASSETS / "scenes.js").read_text(encoding="utf-8")
        css = (ASSETS / "report.css").read_text(encoding="utf-8")
        self.assertIn("gs-back", js)
        self.assertIn("sessionStorage", js)
        self.assertIn("startViewTransition", js)
        self.assertIn(".replay { position: absolute; width: 1px; height: 1px;", css)
        self.assertIn(".gm .scene.gs-back:not(.hd-graphic)", css)
        self.assertIn("html.gm.pa-back .pa-art", css)

    def test_scenes_have_final_frame_without_javascript(self):
        calc = calculation()
        calc["facts"] += [{"id": f"arch.{i}", "section": "archetypes", "label": f"Архетип {i}", "value": i} for i in range(1, 13)]
        report = render_report(calc)
        # Hidden start frames exist only under .gm (set by script) and before .in.
        css = (ASSETS / "report.css").read_text(encoding="utf-8")
        for rule in css.split("}"):
            if "opacity: 0" in rule or "scaleX(0)" in rule or "stroke-dashoffset: var(--len)" in rule.split("{")[-1]:
                selector = rule.split("{")[0]
                if ".s-" in selector or ".has .cell-fill" in selector:
                    self.assertIn(".gm .scene:not(.in)", selector)
        self.assertIn('class="graphic scene"', report)

    def test_external_assets_are_versioned_links(self):
        report = render_report(calculation(), assets="external")
        self.assertRegex(report, r'<link rel="stylesheet" href="assets/report\.css\?v=[0-9a-f]{10}">')
        self.assertRegex(report, r'<script src="assets/scenes\.js\?v=[0-9a-f]{10}" defer></script>')
        self.assertNotIn("<style>", report)
        with self.assertRaises(ValueError):
            render_report(calculation(), assets="cdn")

    def test_site_archive_contains_page_assets_and_manifest(self):
        import json
        import tempfile
        import zipfile
        from pathlib import Path
        from personality_core.package import write_site
        with tempfile.TemporaryDirectory() as tmp:
            folder, archive = write_site(Path(tmp) / "page", calculation())
            names = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
            self.assertEqual([".htaccess", "assets/report.css", "assets/scenes.js", "index.html", "manifest.json"], names)
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("test-calculation", manifest["calculation_id"])
            self.assertEqual(set(names) - {"manifest.json"}, set(manifest["files"]))
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(sorted("page/" + n for n in names), sorted(z.namelist()))
            first = archive.read_bytes()
            write_site(Path(tmp) / "page", calculation())
            self.assertEqual(first, archive.read_bytes())
            with self.assertRaises(ValueError):
                write_site(Path(tmp), calculation(), protected_paths=(str(Path(tmp) / "calc.json"),))



class SiteSafetyTests(unittest.TestCase):
    def test_refuses_to_overwrite_foreign_folder(self):
        import tempfile
        from pathlib import Path
        from personality_core.package import write_site
        with tempfile.TemporaryDirectory() as tmp:
            foreign = Path(tmp) / "docs"
            foreign.mkdir()
            (foreign / "thesis.txt").write_text("важно", encoding="utf-8")
            with self.assertRaises(ValueError):
                write_site(foreign, calculation())
            self.assertEqual("важно", (foreign / "thesis.txt").read_text(encoding="utf-8"))
            page, _ = write_site(Path(tmp) / "page", calculation())
            write_site(page, calculation())  # own previous release is replaced

    def test_unstable_bodygraph_is_not_drawn(self):
        calc = calculation()
        calc["modules"]["human_design"]["data"] = {
            "chart": {"channels": [[3, 60]], "defined_centers": ["Сакрал", "Корень"]},
            "time_window": {"varied": ["human_design.channels"]},
        }
        report = render_report(calc)
        self.assertNotIn('class="graphic scene hd-graphic"', report)
        self.assertIn("Бодиграф не показан", report)

    def test_reader_text_gets_site_typography(self):
        calc = calculation()
        narrative = {"sections": {"human_design": {"interpretation": [{"text": "Я и он — в доме, а не <b>", "sources": ["hd.type"]}]}}}
        report = render_report(calc, narrative)
        self.assertIn("Я&nbsp;и&nbsp;он&nbsp;— в&nbsp;доме, а&nbsp;не&nbsp;&lt;b&gt;", report)


if __name__ == "__main__":
    unittest.main()


class AspectViewMatchesCalculation(unittest.TestCase):
    """Виды и углы аспектов отчёта совпадают с расчётом: смена ASPECT_KINDS без отчёта ловится тестом."""

    def test_same_kinds_names_and_angles(self):
        from personality_core import ephemeris, report
        calc = {kind: (name, exact, "h" if group == "harmonious" else "t") for kind, name, exact, _orb, group in ephemeris.ASPECT_KINDS}
        self.assertEqual(calc, report.ASPECT_VIEW)
