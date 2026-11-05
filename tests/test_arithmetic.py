import json
from datetime import date, datetime
from pathlib import Path
import hashlib
import unittest

from personality_core.arithmetic import archetypes, gematria, numerology, reduce_number


class ArithmeticTests(unittest.TestCase):
    def test_reduction(self):
        self.assertEqual(reduce_number(29), {'input': 29, 'master': 11, 'single': 2, 'steps': [29,11], 'single_steps': [29,11,2]})
        for number in (11,22,33):
            self.assertEqual(reduce_number(number)['master'], number)
        self.assertEqual(reduce_number(0)['single'], 0)
        for bad in (-1, True, 1.5, '1'):
            with self.assertRaises(ValueError): reduce_number(bad)

    def test_latin_trace_and_separator_normalization(self):
        result = gematria("  AB-CD’EF ' G  ", 'en')
        self.assertEqual(result['normalized_name'], 'ab cd ef g')
        self.assertEqual([w['total'] for w in result['words']], [3,7,11,7])
        self.assertEqual(result['total'], 28)
        self.assertEqual(result['vowels']['total'], 6)
        self.assertEqual(result['consonants']['total'], 22)
        self.assertEqual(gematria('Y', 'en')['consonants']['total'],25)

    def test_russian_table_all_letters(self):
        alphabet = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
        result = gematria(alphabet.upper(), 'ru')
        letters = result['words'][0]['letters']
        self.assertEqual([x['value'] for x in letters], [1,2,22,7,4,5,5,26,26,9,10,11,12,13,14,15,16,18,19,20,21,6,8,3,3,19,19,0,25,0,5,21,1])
        self.assertEqual(result['total'], result['vowels']['total']+result['consonants']['total'])
        self.assertEqual(gematria('е\u0308 и\u0306', 'ru')['normalized_name'], 'ё й')
        self.assertEqual(gematria('ъь','ru')['total'],0)

    def test_hebrew_final_forms_no_inferred_vowels(self):
        result = gematria('אבךםןףץת', 'he')
        self.assertEqual(result['total'], 1+2+20+40+50+80+90+400)
        self.assertFalse(result['split_available'])
        self.assertIsNone(result['vowels'])
        self.assertIsNone(result['consonants'])

    def test_name_rejection(self):
        for name, language in [('AБ','en'),('AБ','ru'),('אבA','he'),('A1','en'),('É','en'),('A\tB','en'),('א\u05b7','he'),(' - ', 'en'),('', 'ru'),('A', 'fr'),(None,'en')]:
            with self.subTest(name=name,language=language), self.assertRaises(ValueError):
                gematria(name,language)

    def test_square_numbers_cycles(self):
        result = numerology(date(2000,11,22), date(2025,3,4), gematria('ABC','en'))
        self.assertEqual(result['square']['source_digits'],'22112000')
        self.assertEqual(result['square']['cells'], {'1':2,'2':3,'3':0,'4':0,'5':0,'6':0,'7':0,'8':0,'9':0})
        self.assertEqual(result['square']['ignored_zeros'],3)
        self.assertEqual([l['count'] for l in result['square']['rows']],[2,3,0])
        self.assertEqual([l['count'] for l in result['square']['columns']],[5,0,0])
        self.assertEqual([l['count'] for l in result['square']['diagonals']],[2,0])
        keys=result['key_numbers']
        self.assertEqual(keys['life_path']['master'],8)
        self.assertEqual(keys['birthday']['master'],22)
        self.assertEqual(keys['destiny']['master'],6)
        self.assertEqual(keys['soul']['master'],1)
        self.assertEqual(keys['personality']['master'],5)
        self.assertEqual(keys['maturity']['master'],5)
        self.assertEqual([p['number']['master'] for p in result['pinnacles']], [33,6,3,4])
        self.assertEqual([(p['age_start_inclusive'],p['age_end_exclusive']) for p in result['pinnacles']], [(0,29),(29,38),(38,47),(47,None)])
        self.assertEqual(result['challenges'],[2,2,0,0])
        self.assertEqual([result['personal_cycles'][k]['master'] for k in ('year','month','day')],[6,9,4])
        json.dumps(result)

    def test_january_change_and_hebrew_unavailable(self):
        g=gematria('א','he')
        a=numerology(date(2000,1,1),date(2024,12,31),g)
        b=numerology(date(2000,1,1),date(2025,1,1),g)
        self.assertEqual(a['personal_cycles']['year']['input'],10)
        self.assertEqual(b['personal_cycles']['year']['input'],11)
        self.assertIsNone(a['key_numbers']['soul'])
        self.assertIsNone(a['key_numbers']['personality'])

    def test_date_and_result_validation(self):
        g=gematria('A','en')
        for birth,as_of in [('2000-01-01',date(2020,1,1)),(datetime(2000,1,1),date(2020,1,1)),(date(2000,1,1),date(1999,1,1))]:
            with self.assertRaises(ValueError): numerology(birth,as_of,g)
        for invalid in ({},None,dict(g,total=999)):
            with self.assertRaises(ValueError): numerology(date(2000,1,1),date(2020,1,1),invalid)

    def test_original_questionnaire_and_key_preserved(self):
        root=Path(__file__).resolve().parents[1]
        data=json.loads((root/'data/archetypes.json').read_text())
        payload={'questions':data['questions'],'key':data['key']}
        # Fingerprint of questions/key extracted unchanged from the original prompt.
        self.assertEqual(hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
                         '2f498996c84e95abf994aa9984e38da2cedd12b85053739d345430662e456f82')
        self.assertEqual(len(data['questions']),36)
        self.assertEqual(sorted(i for group in data['key'].values() for i in group),list(range(1,37)))

    def test_archetype_ties_dense_ranks_and_validation(self):
        result=archetypes([3]*36)
        self.assertEqual(len(result['highest']),12)
        self.assertEqual(result['highest'],result['lowest'])
        self.assertTrue(all(row['rank']==1 and row['score']==9 for row in result['scores']))
        answers=[1]*36
        answers[0]=5
        answers[1]=3
        result=archetypes(answers)
        self.assertEqual([(g['rank'],g['score']) for g in result['rank_groups']],[(1,7),(2,5),(3,3)])
        self.assertEqual(result['highest'],['Простодушный'])
        json.dumps(result)
        for bad in ([1]*35,[1]*37,[True]*36,[1.0]*36,[0]*36,[6]*36,'1'*36):
            with self.assertRaises(ValueError): archetypes(bad)


if __name__ == '__main__':
    unittest.main()
