import contextlib
from copy import deepcopy
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personality import main
from personality_core.pipeline import (PLANETS, SECTIONS, calculate, calculation_id, load_json,
                                       summary, validate_calculation, validate_input,
                                       validate_narrative, write_atomic)

ROOT=Path(__file__).resolve().parents[1]


def fake_compute(moment, tz, lat, lon, true_node=False, fold=None, backend='astronomy'):
    # Synthetic stand-in exercises orchestration, not astronomical accuracy.
    point={'longitude':123.5,'gate':1,'line':2,'sign':'Синтетический знак','line_edge':False}
    return {'input':{'local_iso':moment.isoformat(),'utc_iso':moment.isoformat()},
            'personality':{label:dict(point) for label in list(PLANETS.values())+['Земля']},
            'design':{label:dict(point) for label in list(PLANETS.values())+['Земля']},
            'chart':{'type':'Синтетический тип','authority':'Синтетический авторитет','strategy':'Ожидать',
                     'definition':'Единичное','channels':[], 'defined_centers':[],
                     'undefined_centers':[], 'completely_open_centers':[]},
            'profile':'1/3','quarter':'Синтетическая четверть','cross':{'gates':[1,2,3,4]},
            'determination':{'name':'Синтетическое значение'},
            'astro':{'asc_deg':10.5,'mc_deg':20.5,'Асцендент':'Синтетический знак','Середина неба':'Синтетический знак'},
            'provenance':{'backend':backend,'engine_version':'synthetic-test','design_utc_iso':(moment-timedelta(days=88)).isoformat()+'+00:00'}}


def narrative_for(calc):
    source=calc['facts'][0]['id']
    sections={}
    for key in SECTIONS:
        unavailable=key in calc['modules'] and calc['modules'][key]['status']=='unavailable'
        sections[key]={'intro':'Описание раздела.',
                       'interpretation':[{'text':'Нет данных.' if unavailable else 'Объяснение факта.',
                                          'sources':[] if unavailable else [source]}],
                       'topics':[{'title':'Тема раздела','paragraphs':[{'text':'Объяснение темы.',
                                  'sources':[] if unavailable else [source]}]}],
                       'actions':[] if unavailable else [{'text':'Обсудить наблюдение.','sources':[source]}]}
    return {'calculation_id':calc['calculation_id'],'sections':sections,
            'summary':[{'text':'Сводка наблюдений.','sources':[source]}],
            'summary_topics':[{'title':'Общий итог','paragraphs':[{'text':'Сводка темы.','sources':[source]}]}]}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.input=load_json(ROOT/'examples/input.json')

    def partial(self):
        value=deepcopy(self.input)
        value.update(birth_time=None,time_accuracy='unknown',answers=None)
        return value

    @patch('hd.compute',side_effect=fake_compute)
    def test_determinism_and_stable_facts(self,compute):
        a=calculate(self.input)
        b=calculate(self.input)
        self.assertEqual(a,b)
        self.assertEqual(a['schema_version'],2)
        self.assertEqual(a['calculation_id'],calculation_id(a))
        facts={f['id']:f for f in a['facts']}
        self.assertEqual(facts['num.matrix.1']['value'],3)
        self.assertEqual(facts['arch.1']['label'],'Простодушный')
        self.assertEqual(facts['astro.sun.longitude']['value'],123.5)
        self.assertEqual(facts['hd.profile']['value'],'1/3')
        self.assertNotIn('life_cycles',a['modules'])
        for identifier,fact in facts.items():
            if identifier.startswith(('num.cycle.','num.pinnacle.','num.challenge.','num.personal.')):
                self.assertEqual(fact['section'],'life_cycles')
        for layer in ('personality','design'):
            for body in ('sun','earth'):
                self.assertEqual(facts['hd.'+layer+'.'+body]['value'],{'gate':1,'line':2})
        self.assertEqual(facts['hd.design_date']['value'],a['modules']['human_design']['data']['provenance']['design_utc_iso'])
        validate_narrative(a,narrative_for(a))
        self.assertEqual(compute.call_count,2)
        original_name=self.input['name']
        self.input['name']='Другое имя'
        self.assertEqual(a['input']['name'],original_name)
        self.assertNotIn('modules',summary(a))
        self.assertNotIn('input',summary(a))

    @patch('hd.compute',side_effect=AssertionError('must not calculate a guessed time'))
    def test_unknown_time_and_unanswered_partial(self,compute):
        result=calculate(self.partial())
        for key in ('human_design','astrology','archetypes'):
            self.assertEqual(result['modules'][key]['status'],'unavailable')
            self.assertTrue(result['modules'][key]['reason'])
        self.assertFalse(any(f['section'] in ('human_design','astrology','archetypes') for f in result['facts']))
        self.assertEqual(compute.call_count,0)
        validate_narrative(result,narrative_for(result))

    @patch('hd.compute',side_effect=fake_compute)
    def test_approximate_samples_include_endpoints_center_and_variation(self,compute):
        value=deepcopy(self.input)
        value.update(time_accuracy='approximate',time_window_minutes=20)
        result=calculate(value)
        window=result['modules']['human_design']['data']['time_window']
        self.assertEqual(window['sample_count'],5)
        self.assertFalse(window['interval_reliability_established'])
        center=compute.call_args_list[0].args[0]
        self.assertEqual({call.args[0] for call in compute.call_args_list},
                         {center+timedelta(minutes=i) for i in (-20,-5,0,10,20)})
        self.assertEqual(window['varied'],[])
        self.assertTrue(any('не доказывает' in warning for warning in result['warnings']))
        def varying(moment,*args,**kwargs):
            raw=fake_compute(moment,*args,**kwargs)
            if moment.minute!=0:
                raw['chart']['type']='Другой синтетический тип'
            return raw
        compute.side_effect=varying
        self.assertIn('human_design.type',calculate(value)['modules']['human_design']['data']['time_window']['varied'])

    def test_invalid_input(self):
        mutations=[{'confirmed':False},{'confirmed':1},{'birth_date':'1990-02-30'},
                   {'birth_date':'1990-1-15'},{'as_of':'1989-01-01'}, {'birth_time':'24:00'},
                   {'latitude':True},{'longitude':float('nan')},{'latitude':90},{'timezone':'No/Such_Zone'},
                   {'location_source':None},{'answers':[True]*36},{'answers':[3]*35},
                   {'time_accuracy':'approximate','time_window_minutes':False},
                   {'time_accuracy':'approximate','time_window_minutes':0},
                   {'time_accuracy':'approximate','time_window_minutes':721},
                   {'time_window_minutes':20},{'fold':True},{'backend':'fallback'},{'true_node':1},
                   {'time_accuracy':'unknown'},{'original_text':''},{'name':'AБ'},{'unknown_field':1}]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_input(dict(self.input,**mutation))

    def test_stale_hash_structural_changes_and_narrative_references(self):
        result=calculate(self.partial())
        validate_calculation(result)
        changed=deepcopy(result)
        next(fact for fact in changed['facts'] if fact['id']=='gem.total')['value']+=1
        with self.assertRaisesRegex(ValueError,'mismatch'): validate_calculation(changed)
        changed['calculation_id']=calculation_id(changed)
        changed['facts'].append(deepcopy(changed['facts'][0]))
        changed['calculation_id']=calculation_id(changed)
        with self.assertRaisesRegex(ValueError,'unique'): validate_calculation(changed)
        for mutation in ('source','id','section','synthesis','summary','missing'):
            narrative=narrative_for(result)
            if mutation=='source': narrative['sections']['purpose']['interpretation'][0]['sources']=['missing.fact']
            elif mutation=='id': narrative['calculation_id']='0'*64
            elif mutation=='section': narrative['sections']['numerology']['interpretation'][0]['sources']=[]
            elif mutation=='synthesis': narrative['sections']['finance']['interpretation'][0]['sources']=[]
            elif mutation=='summary': narrative['summary']=[]
            else: del narrative['sections']['purpose']
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): validate_narrative(result,narrative)

    def test_gematria_method_and_compact_word_sources(self):
        for language,name in (('en','AB-CD'),('ru','АБ ВГ'),('he','אב גד')):
            with self.subTest(language=language):
                value=self.partial()
                value.update(language=language,name=name)
                result=calculate(value)
                facts={fact['id']:fact for fact in result['facts']}
                method=facts['gem.method']
                self.assertEqual(method['value']['language'],language)
                self.assertEqual(method['value']['convention'],result['modules']['gematria']['data']['convention'])
                self.assertTrue(method['value']['method'])
                self.assertIn('NFC',method['detail'])
                self.assertIn('нижний регистр',method['detail'])
                self.assertIn('разделяют слова',method['detail'])
                words=facts['gem.words']['value']
                self.assertEqual(len(words),2)
                self.assertTrue(all(set(word)=={'word','total'} for word in words))
                self.assertEqual(sum(word['total'] for word in words),facts['gem.total']['value'])
                self.assertTrue(all(facts[key]['section']=='gematria' for key in ('gem.method','gem.words')))

    def test_v2_sections_and_topic_validation(self):
        result=calculate(self.partial())
        self.assertEqual(SECTIONS,('human_design','gematria','numerology','astrology','life_cycles',
                                  'archetypes','purpose','finance'))
        old=deepcopy(result)
        old['schema_version']=1
        old['calculation_id']=calculation_id(old)
        with self.assertRaisesRegex(ValueError,'schema_version'): validate_calculation(old)
        narrative=narrative_for(result)
        validate_narrative(result,narrative)
        self.assertEqual(summary(result)['schema_version'],2)
        for mutation in ('unknown_source','empty_source','empty_paragraphs','empty_title','bad_topic',
                         'empty_topics','summary_source','summary_empty_source','cycles_source','missing_cycles'):
            bad=deepcopy(narrative)
            topic=bad['sections']['numerology']['topics'][0]
            if mutation=='unknown_source': topic['paragraphs'][0]['sources']=['missing.fact']
            elif mutation=='empty_source': topic['paragraphs'][0]['sources']=[]
            elif mutation=='empty_paragraphs': topic['paragraphs']=[]
            elif mutation=='empty_title': topic['title']=' '
            elif mutation=='bad_topic': bad['sections']['numerology']['topics']=['text']
            elif mutation=='empty_topics': bad['sections']['numerology']['topics']=[]
            elif mutation=='summary_source': bad['summary_topics'][0]['paragraphs'][0]['sources']=['missing.fact']
            elif mutation=='summary_empty_source': bad['summary_topics'][0]['paragraphs'][0]['sources']=[]
            elif mutation=='cycles_source': bad['sections']['life_cycles']['topics'][0]['paragraphs'][0]['sources']=[]
            else: del bad['sections']['life_cycles']
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): validate_narrative(result,bad)
        # Optional topic fields may be absent without invalidating the base contract.
        for section in narrative['sections'].values():
            del section['topics']
        del narrative['summary_topics']
        validate_narrative(result,narrative)

    def test_strict_json_and_atomic_output_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'input.json'
            target=Path(directory)/'output.json'
            for contents in ('{"a":1,"a":2}','{"nested":{"a":1,"a":2}}','{"n":NaN}','{"n":Infinity}','{"n":1e999}'):
                source.write_text(contents)
                with self.assertRaises(ValueError): load_json(source)
            source.write_text('{}')
            with self.assertRaises(ValueError): write_atomic(source,'changed',(source,))
            self.assertEqual(source.read_text(),'{}')
            write_atomic(target,'complete',(source,))
            self.assertEqual(target.read_text(),'complete')
            alias=Path(directory)/'alias.json'
            alias.symlink_to(source)
            with self.assertRaises(ValueError): write_atomic(alias,'changed',(source,))
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()),['alias.json','input.json','output.json'])

    def test_cli_partial_check_render_summary_and_stale_error(self):
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()):
            source=Path(directory)/'input.json'
            calculation=Path(directory)/'calc.json'
            html=Path(directory)/'report.html'
            source.write_text(json.dumps(self.partial(),ensure_ascii=False))
            self.assertEqual(main(['calculate','--input',str(source),'--output',str(calculation)]),0)
            self.assertEqual(main(['check','--calculation',str(calculation)]),0)
            self.assertEqual(main(['render','--calculation',str(calculation),'--output',str(html)]),0)
            self.assertIn('Расчётный черновик',html.read_text())
            self.assertEqual(main(['summary','--calculation',str(calculation)]),0)
            self.assertEqual(main(['render','--calculation',str(calculation),'--output',str(calculation)]),2)
            value=load_json(calculation)
            value['as_of']='2026-11-06'
            calculation.write_text(json.dumps(value))
            self.assertEqual(main(['check','--calculation',str(calculation)]),2)
            out.seek(0);out.truncate(0)
            self.assertEqual(main(['questionnaire']),0)
            questionnaire=json.loads(out.getvalue())
            self.assertEqual(len(questionnaire['questions']),36)
            self.assertNotIn('key',questionnaire)

    @patch('hd.compute',side_effect=RuntimeError('missing explicit backend dependency'))
    def test_backend_failure_is_not_success(self,compute):
        with self.assertRaises(RuntimeError): calculate(self.input)
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stderr(io.StringIO()):
            output=Path(directory)/'not-created.json'
            self.assertEqual(main(['calculate','--input',str(ROOT/'examples/input.json'),'--output',str(output)]),2)
            self.assertFalse(output.exists())


if __name__=='__main__':
    unittest.main()
