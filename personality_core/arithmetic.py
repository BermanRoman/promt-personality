"""Transparent arithmetic conventions; no diagnostic or predictive inference."""
from datetime import date
from pathlib import Path
import json
import unicodedata

CONVENTION = 'arithmetic-v1'
RU_ISO9 = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                       ['a','b','v','g','d','e','ë','ž','z','i','j','k','l','m','n','o','p','r','s','t','u','f','h','c','č','š','ŝ','ʺ','y','ʹ','è','û','â']))
HEBREW = dict(zip('אבגדהוזחטיכלמנסעפצקרשת',
                  [1,2,3,4,5,6,7,8,9,10,20,30,40,50,60,70,80,90,100,200,300,400]))
HEBREW.update({f: HEBREW[n] for f, n in zip('ךםןףץ', 'כמנפצ')})
SEPARATORS = " -'’"


def _digit_sum(number):
    return sum(map(int, str(number)))


def reduce_number(number):
    """Return master-preserving and fully reduced paths, including zero."""
    if type(number) is not int or number < 0:
        raise ValueError('number must be a nonnegative integer')
    steps = [number]
    while steps[-1] > 9 and steps[-1] not in (11, 22, 33):
        steps.append(_digit_sum(steps[-1]))
    single_steps = [number]
    while single_steps[-1] > 9:
        single_steps.append(_digit_sum(single_steps[-1]))
    return {'input': number, 'master': steps[-1], 'single': single_steps[-1],
            'steps': steps, 'single_steps': single_steps}


def gematria(name, language):
    """Count Latin A1Z26, explicit Russian ISO 9 folding, or Hebrew letters."""
    if language not in ('ru', 'en', 'he'):
        raise ValueError('language must be ru, en, or he')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('name must be a nonempty string')
    # NFC accepts canonically equivalent ё and й, but never strips unknown marks.
    normalized = unicodedata.normalize('NFC', name).lower()
    words = []
    current = []
    for char in normalized:
        if char in SEPARATORS:
            if current:
                words.append(''.join(current))
                current = []
        else:
            valid = (char in RU_ISO9 if language == 'ru' else
                     'a' <= char <= 'z' if language == 'en' else char in HEBREW)
            if not valid:
                raise ValueError('name contains a character outside the selected alphabet')
            current.append(char)
    if current:
        words.append(''.join(current))
    if not words:
        raise ValueError('name must contain letters')
    trace = []
    vowel_total = consonant_total = 0
    for word in words:
        letters = []
        for char in word:
            transliteration = RU_ISO9[char] if language == 'ru' else char
            latin = (''.join(c for c in unicodedata.normalize('NFD', transliteration)
                             if not unicodedata.combining(c)) if language != 'he' else None)
            if language == 'he':
                value, kind = HEBREW[char], 'unavailable'
            elif language == 'ru' and char in 'ьъ':
                value, kind, latin = 0, 'neutral', ''
            else:
                value = sum(ord(c) - ord('a') + 1 for c in latin)
                kind = 'vowel' if char in ('аеёиоуыэюя' if language == 'ru' else 'aeiou') else 'consonant'
                if kind == 'vowel':
                    vowel_total += value
                else:
                    consonant_total += value
            letters.append({'source': char, 'transliteration': transliteration,
                            'latin': latin, 'value': value, 'kind': kind})
        trace.append({'word': word, 'letters': letters, 'total': sum(x['value'] for x in letters)})
    total = sum(w['total'] for w in trace)
    return {'convention': CONVENTION, 'language': language,
            'normalized_name': ' '.join(words), 'words': trace,
            'total': total, 'reduction': reduce_number(total),
            'split_available': language != 'he',
            'vowels': None if language == 'he' else {'total': vowel_total, 'reduction': reduce_number(vowel_total)},
            'consonants': None if language == 'he' else {'total': consonant_total, 'reduction': reduce_number(consonant_total)}}


def _date(value, label):
    if type(value) is not date:
        raise ValueError(label + ' must be datetime.date (not datetime)')


def numerology(birth_date, as_of, gematria_result):
    """Compute convention v1 from explicit dates and a validated gematria result."""
    _date(birth_date, 'birth_date')
    _date(as_of, 'as_of')
    if as_of < birth_date:
        raise ValueError('as_of must not precede birth_date')
    try:
        valid_name = gematria(gematria_result['normalized_name'], gematria_result['language'])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('gematria_result must be a gematria() result') from error
    if gematria_result != valid_name:
        raise ValueError('gematria_result is inconsistent')
    digits = f'{birth_date.day:02d}{birth_date.month:02d}{birth_date.year:04d}'
    cells = {str(n): digits.count(str(n)) for n in range(1, 10)}
    def line(ns):
        return {'digits': ns, 'count': sum(cells[str(n)] for n in ns)}
    square = {'source_digits': digits, 'ignored_zeros': digits.count('0'), 'cells': cells,
              'rows': [line(ns) for ns in ([1,4,7], [2,5,8], [3,6,9])],
              'columns': [line(ns) for ns in ([1,2,3], [4,5,6], [7,8,9])],
              'diagonals': [line(ns) for ns in ([1,5,9], [3,5,7])]}
    path = reduce_number(sum(map(int, digits)))
    destiny = valid_name['reduction']
    keys = {'life_path': path, 'birthday': reduce_number(birth_date.day), 'destiny': destiny,
            'soul': valid_name['vowels']['reduction'] if valid_name['split_available'] else None,
            'personality': valid_name['consonants']['reduction'] if valid_name['split_available'] else None,
            'maturity': reduce_number(path['master'] + destiny['master'])}
    cycles = [reduce_number(n) for n in (birth_date.month, birth_date.day, birth_date.year)]
    m, d, y = [n['master'] for n in cycles]
    p1, p2 = reduce_number(m+d), reduce_number(d+y)
    peaks = [p1, p2, reduce_number(p1['master']+p2['master']), reduce_number(m+y)]
    boundary = 37 - path['single']
    intervals = [(0, boundary), (boundary, boundary+9), (boundary+9, boundary+18), (boundary+18, None)]
    pinnacles = [{'number': n, 'age_start_inclusive': start, 'age_end_exclusive': end}
                 for n, (start, end) in zip(peaks, intervals)]
    m, d, y = [n['single'] for n in cycles]
    c1, c2 = abs(d-m), abs(d-y)
    challenges = [c1, c2, abs(c1-c2), abs(m-y)]
    personal_year = reduce_number(_digit_sum(birth_date.day)+_digit_sum(birth_date.month)+_digit_sum(as_of.year))
    personal_month = reduce_number(personal_year['master'] + as_of.month)
    personal_day = reduce_number(personal_month['master'] + as_of.day)
    return {'convention': CONVENTION, 'birth_date': birth_date.isoformat(), 'as_of': as_of.isoformat(),
            'square': square, 'key_numbers': keys,
            'life_cycles': dict(zip(('month', 'day', 'year'), cycles)),
            'pinnacles': pinnacles, 'challenges': challenges,
            'personal_cycles': {'year': personal_year, 'month': personal_month,
                                'day': personal_day, 'year_changes': 'January 1'}}


def archetypes(answers):
    """Score the original 36-item key, preserving every tie via dense ranks."""
    if not isinstance(answers, (list, tuple)) or len(answers) != 36:
        raise ValueError('answers must contain exactly 36 integers')
    if any(type(a) is not int or not 1 <= a <= 5 for a in answers):
        raise ValueError('each answer must be an integer from 1 to 5; bool is invalid')
    data = json.loads((Path(__file__).resolve().parent.parent / 'data' / 'archetypes.json').read_text(encoding='utf-8'))
    scores = [{'name': name, 'questions': indexes,
               'score': sum(answers[i-1] for i in indexes)} for name, indexes in data['key'].items()]
    scores.sort(key=lambda row: -row['score'])
    levels = sorted({row['score'] for row in scores}, reverse=True)
    for row in scores:
        row['rank'] = levels.index(row['score']) + 1
    groups = [{'rank': i+1, 'score': value, 'names': [row['name'] for row in scores if row['score'] == value]}
              for i, value in enumerate(levels)]
    return {'convention': CONVENTION, 'scores': scores, 'rank_groups': groups,
            'highest': groups[0]['names'], 'lowest': groups[-1]['names'],
            'caution': 'Scores compare responses within one profile; a low score does not establish repression.'}
