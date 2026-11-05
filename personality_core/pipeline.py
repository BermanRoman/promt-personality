"""Validated local calculation pipeline and fact-bound narrative contract."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .arithmetic import CONVENTION, archetypes, gematria, numerology

SCHEMA_VERSION = 2
MODULES = ('human_design', 'gematria', 'numerology', 'astrology', 'archetypes')
SECTIONS = ('human_design', 'gematria', 'numerology', 'astrology', 'life_cycles', 'archetypes', 'purpose', 'finance')
FACT_MODULES = {section: section for section in MODULES}
FACT_MODULES['life_cycles'] = 'numerology'
PLANETS = dict(zip(('sun','moon','mercury','venus','mars','jupiter','saturn','uranus','neptune','pluto'),
                   ('Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн','Уран','Нептун','Плутон')))
INPUT_KEYS = {'name','language','birth_date','birth_time','birth_place','timezone','latitude','longitude',
              'location_source','time_accuracy','time_window_minutes','fold','as_of','answers',
              'original_text','confirmed','backend','true_node'}


def canonical_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError('value must be finite JSON data') from exc


def calculation_id(calculation):
    return hashlib.sha256(canonical_json({k:v for k,v in calculation.items() if k != 'calculation_id'}).encode('utf-8')).hexdigest()


def load_json(path):
    """Reject duplicate object keys and NaN/Infinity, including nested values."""
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    with Path(path).open(encoding='utf-8') as source:
        result=json.load(source,object_pairs_hook=pairs,parse_constant=constant)
    canonical_json(result)  # Also reject overflowing numeric literals such as 1e999.
    return result


def write_atomic(path, text, protected_paths=()):
    destination=Path(path).resolve()
    if any(destination == Path(p).resolve() or
           (destination.exists() and Path(p).exists() and os.path.samefile(destination,p))
           for p in protected_paths):
        raise ValueError('output must differ from every input path')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=destination.parent,
                                         prefix='.'+destination.name+'.',delete=False) as output:
            temporary=Path(output.name)
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _object(value,label):
    if not isinstance(value,dict):
        raise ValueError(label+' must be an object')


def _text(value,label):
    if not isinstance(value,str) or not value.strip():
        raise ValueError(label+' must be a nonempty string')


def _iso_date(value,label):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError(label+' must use YYYY-MM-DD')
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(label+' is not a valid date') from exc


def _coordinate(value,label,lower,upper,exclusive=False):
    if type(value) not in (int,float) or not math.isfinite(value) or not (
            lower < value < upper if exclusive else lower <= value <= upper):
        raise ValueError(label+' is outside its finite numeric range')


def validate_input(value):
    _object(value,'input')
    if set(value)-INPUT_KEYS:
        raise ValueError('unknown input fields: '+', '.join(sorted(set(value)-INPUT_KEYS)))
    for key in ('name','language','birth_place','time_accuracy','original_text'):
        _text(value.get(key),key)
    if value.get('confirmed') is not True:
        raise ValueError('confirmed must be true after the person checks the input')
    birth=_iso_date(value.get('birth_date'),'birth_date')
    as_of=_iso_date(value.get('as_of'),'as_of')
    if as_of < birth:
        raise ValueError('as_of must not precede birth_date')
    gematria(value['name'],value['language'])
    if 'answers' not in value:
        raise ValueError('answers is required; use null when unanswered')
    if value['answers'] is not None:
        archetypes(value['answers'])
    accuracy=value['time_accuracy']
    if accuracy not in ('exact','approximate','unknown'):
        raise ValueError('time_accuracy must be exact, approximate, or unknown')
    if 'birth_time' not in value:
        raise ValueError('birth_time is required; use null when unknown')
    birth_time=value['birth_time']
    if birth_time is not None:
        if not isinstance(birth_time,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',birth_time):
            raise ValueError('birth_time must use HH:MM')
    if accuracy=='unknown' and birth_time is not None:
        raise ValueError('unknown time_accuracy requires birth_time=null')
    if accuracy!='unknown' and birth_time is None:
        raise ValueError('exact/approximate time_accuracy requires birth_time')
    fold=value.get('fold')
    if fold is not None and (type(fold) is not int or fold not in (0,1)):
        raise ValueError('fold must be null, 0, or 1')
    window=value.get('time_window_minutes')
    if accuracy=='approximate':
        if type(window) is not int or not 0 < window <= 720:
            raise ValueError('approximate time requires time_window_minutes in 1..720')
    elif window is not None:
        raise ValueError('time_window_minutes only applies to approximate time')
    if value.get('backend','astronomy') not in ('astronomy','legacy'):
        raise ValueError('backend must be astronomy or explicit legacy')
    if type(value.get('true_node',False)) is not bool:
        raise ValueError('true_node must be boolean')
    for label,lower,upper,exclusive in (('latitude',-90,90,True),('longitude',-180,180,False)):
        if value.get(label) is not None:
            _coordinate(value[label],label,lower,upper,exclusive)
        elif accuracy!='unknown':
            raise ValueError(label+' is required for a known birth time')
    if value.get('timezone') is not None:
        _text(value['timezone'],'timezone')
        try:
            ZoneInfo(value['timezone'])
        except (ZoneInfoNotFoundError,ValueError) as exc:
            raise ValueError('timezone must be an installed IANA zone') from exc
    elif accuracy!='unknown':
        raise ValueError('timezone is required for a known birth time')
    if value.get('location_source') is not None:
        _text(value['location_source'],'location_source')
    elif accuracy!='unknown':
        raise ValueError('location_source is required for a known birth time')
    canonical_json(value)
    return value


def _astrology(raw):
    return {'planets': {key:{'longitude': raw['personality'][name]['longitude'],
                              'sign': raw['personality'][name]['sign']} for key,name in PLANETS.items()},
            'ascendant': {'longitude':raw['astro']['asc_deg'],'sign':raw['astro']['Асцендент']},
            'midheaven': {'longitude':raw['astro']['mc_deg'],'sign':raw['astro']['Середина неба']},
            'provenance':raw['provenance']}


def _snapshot(raw):
    return {'local_iso':raw['input']['local_iso'],'utc_iso':raw['input']['utc_iso'],
            'human_design': {'type':raw['chart']['type'],'profile':raw['profile'],
                             'authority':raw['chart']['authority'],'channels':raw['chart']['channels'],
                             'defined_centers':raw['chart']['defined_centers']},
            'astrology':_astrology(raw)}


def _astronomical_modules(value):
    # Imported lazily: the arithmetic-only path requires no astronomy dependency.
    import hd
    center=datetime.fromisoformat(value['birth_date']+'T'+value['birth_time'])
    def compute(moment, sample=False):
        fold=value.get('fold')
        if sample and fold is not None:
            zone=ZoneInfo(value['timezone'])
            if moment.replace(tzinfo=zone,fold=0).utcoffset()==moment.replace(tzinfo=zone,fold=1).utcoffset():
                fold=None
        return hd.compute(moment,value['timezone'],value['latitude'],value['longitude'],
                          true_node=value.get('true_node',False),fold=fold,
                          backend=value.get('backend','astronomy'))
    raw=compute(center)
    astro=_astrology(raw)
    warnings=[]
    if value['time_accuracy']=='approximate':
        width=value['time_window_minutes']
        offsets=sorted(set(range(-width,width+1,15))|{-width,0,width})
        snapshots=[_snapshot(raw if offset==0 else compute(center+timedelta(minutes=offset),sample=True)) for offset in offsets]
        varying=[]
        for key in snapshots[0]['human_design']:
            if len({canonical_json(s['human_design'][key]) for s in snapshots})>1:
                varying.append('human_design.'+key)
        for planet in PLANETS:
            for key in ('longitude','sign'):
                if len({canonical_json(s['astrology']['planets'][planet][key]) for s in snapshots})>1:
                    varying.append('astrology.'+planet+'.'+key)
        for body in ('ascendant','midheaven'):
            for key in ('longitude','sign'):
                if len({canonical_json(s['astrology'][body][key]) for s in snapshots})>1:
                    varying.append('astrology.'+body+'.'+key)
        window={'method':'wall-time samples every 15 minutes plus endpoints and center',
                'half_width_minutes':width,'sample_count':len(snapshots),'varied':varying,
                'samples':snapshots,'interval_reliability_established':False}
        raw['time_window']=window
        astro['time_window']=window
        warnings.append('Время приблизительное: факты относятся к центральному отсчёту; выполнена дискретная выборка окна, совпадение выборок не доказывает устойчивость на всём интервале.')
    for layer in ('personality','design'):
        if any(point['line_edge'] for point in raw[layer].values()):
            name = 'на момент рождения' if layer == 'personality' else 'для расчётной даты дизайна'
            warnings.append('В карте '+name+' есть положения рядом с границей между линиями — категориями Human Design; небольшая погрешность времени или модели может изменить такую категорию.')
    warnings.append('Лунные узлы — точки пересечения орбиты Луны с эклиптикой — и угловые точки карты рассчитаны приближённо; точность положений планет не означает одинаковой точности всех показателей.')
    if value.get('backend','astronomy')=='legacy':
        warnings.append('Явно выбран legacy: приближённые эфемериды; точность профессионального калькулятора не заявляется.')
    return raw,astro,warnings


def calculate(input_dict):
    validate_input(input_dict)
    # A JSON round trip isolates the result from subsequent caller mutations.
    value=json.loads(canonical_json(input_dict))
    birth=date.fromisoformat(value['birth_date'])
    as_of=date.fromisoformat(value['as_of'])
    gem=gematria(value['name'],value['language'])
    num=numerology(birth,as_of,gem)
    modules={'gematria':{'status':'computed','data':gem},'numerology':{'status':'computed','data':num}}
    warnings=[]
    if value['answers'] is None:
        modules['archetypes']={'status':'unavailable','data':{},'reason':'Ответы на 36 утверждений не предоставлены.'}
    else:
        modules['archetypes']={'status':'computed','data':archetypes(value['answers'])}
    if value['time_accuracy']=='unknown':
        for key in ('human_design','astrology'):
            modules[key]={'status':'unavailable','data':{},'reason':'Время рождения неизвестно; подстановка времени не выполнялась.'}
        warnings.append('Время рождения неизвестно: Human Design и астрология не рассчитаны.')
    else:
        raw,astro,notices=_astronomical_modules(value)
        modules['human_design']={'status':'computed','data':raw}
        modules['astrology']={'status':'computed','data':astro}
        warnings.extend(notices)
    if not gem['split_available']:
        warnings.append('В выбранном методе для иврита не выделяются гласные и согласные, поэтому числа душевного стремления и личности не рассчитываются.')
    facts=[]
    def fact(identifier,section,label,result,detail=None):
        item={'id':identifier,'section':section,'label':label,'value':result}
        if detail is not None:
            item['detail']=detail
        facts.append(item)
    def reduction_detail(number):
        return ' → '.join(map(str,number['steps']))+'; однозначно: '+' → '.join(map(str,number['single_steps']))
    gem_methods={
        'en':'A1Z26: A=1…Z=26; гласные A/E/I/O/U, Y — согласная.',
        'ru':'Транслитерация по явной таблице ISO 9 → удаление диакритики → A1Z26; Ь/Ъ дают ноль; гласные определяются по исходным русским буквам.',
        'he':'Стандартные значения иврита от 1 до 400; конечные формы имеют обычные значения; разделение гласных и согласных не выполняется.'}
    normalization="Нормализация: NFC и нижний регистр; ASCII-пробел, дефис и апострофы '/’ разделяют слова, повторные разделители сворачиваются; неизвестные знаки и смешанные алфавиты отклоняются."
    fact('gem.method','gematria','Метод счёта имени',
         {'language':gem['language'],'convention':gem['convention'],'method':gem_methods[gem['language']]},normalization)
    fact('gem.words','gematria','Суммы слов имени',
         [{'word':word['word'],'total':word['total']} for word in gem['words']],
         'Слова после нормализации; сумма значений слов равна общей сумме имени. Посимвольная трасса сохранена в модуле гематрии.')
    fact('gem.total','gematria','Сумма имени',gem['total'],reduction_detail(gem['reduction']))
    for key,label in (('vowels','Гласные'),('consonants','Согласные')):
        if gem[key] is not None:
            fact('gem.'+key,'gematria',label,gem[key]['total'],reduction_detail(gem[key]['reduction']))
    number_labels={'life_path':'Жизненный путь','birthday':'День рождения','destiny':'Судьба имени',
                   'soul':'Душевное стремление','personality':'Личность','maturity':'Зрелость'}
    for key,number in num['key_numbers'].items():
        if number is not None:
            fact('num.'+key,'numerology',number_labels[key],number['master'],reduction_detail(number))
    for digit,count in num['square']['cells'].items():
        fact('num.matrix.'+digit,'numerology','Количество цифры '+digit,count,'Только цифры даты DDMMYYYY, без рабочих чисел.')
    cycle_labels={'month':'Жизненный цикл месяца','day':'Жизненный цикл дня','year':'Жизненный цикл года'}
    for key,number in num['life_cycles'].items():
        fact('num.cycle.'+key,'life_cycles',cycle_labels[key],number['master'],reduction_detail(number))
    for i,peak in enumerate(num['pinnacles'],1):
        fact('num.pinnacle.'+str(i),'life_cycles','Пик '+str(i),peak['number']['master'],
             reduction_detail(peak['number'])+'; возраст ['+str(peak['age_start_inclusive'])+', '+str(peak['age_end_exclusive'])+')')
    for i,challenge in enumerate(num['challenges'],1):
        fact('num.challenge.'+str(i),'life_cycles','Вызов '+str(i),challenge)
    personal_labels={'year':'Личный год','month':'Личный месяц','day':'Личный день'}
    for key in ('year','month','day'):
        number=num['personal_cycles'][key]
        fact('num.personal.'+key,'life_cycles',personal_labels[key],number['master'],reduction_detail(number))
    if modules['archetypes']['status']=='computed':
        key_data=json.loads((Path(__file__).resolve().parent.parent/'data/archetypes.json').read_text(encoding='utf-8'))
        scores={row['name']:row for row in modules['archetypes']['data']['scores']}
        for i,name in enumerate(key_data['key'],1):
            row=scores[name]
            fact('arch.'+str(i),'archetypes',name,row['score'],'Плотный ранг: '+str(row['rank'])+'; сумма трёх ответов, внешних норм нет.')
    if modules['human_design']['status']=='computed':
        raw=modules['human_design']['data']
        central='Центральный отсчёт приблизительного времени; устойчивость на интервале не доказана.' if value['time_accuracy']=='approximate' else 'Из hd.compute, см. полный расчёт и provenance.'
        hd_labels={'type':'Тип','authority':'Авторитет','strategy':'Стратегия','definition':'Определение',
                   'channels':'Каналы','profile':'Профиль','quarter':'Четверть',
                   'cross':'Ворота креста','determination':'Цвет и тон'}
        for key in ('type','authority','strategy','definition','channels'):
            fact('hd.'+key,'human_design',hd_labels[key],raw['chart'][key],central)
        fact('hd.centers','human_design','Определённые центры',raw['chart']['defined_centers'],central)
        fact('hd.undefined_centers','human_design','Неопределённые центры',raw['chart']['undefined_centers'],central)
        fact('hd.completely_open_centers','human_design','Полностью открытые центры',raw['chart']['completely_open_centers'],central)
        for key in ('profile','quarter','cross','determination'):
            fact('hd.'+key,'human_design',hd_labels[key],raw[key],central)
        for layer,layer_label in (('personality','Личность'),('design','Дизайн')):
            for body,body_label in (('sun','Солнце'),('earth','Земля')):
                point=raw[layer][body_label]
                fact('hd.'+layer+'.'+body,'human_design',layer_label+': '+body_label,
                     {'gate':point['gate'],'line':point['line']},central)
        fact('hd.design_date','human_design','Дата дизайна UTC',raw['provenance']['design_utc_iso'],
             'Расчётный момент солнечной дуги 88° до рождения; '+central)
        for planet,point in modules['astrology']['data']['planets'].items():
            fact('astro.'+planet+'.longitude','astrology',PLANETS[planet],point['longitude'],str(point['sign'])+'; '+central)
        for key,label in (('ascendant','Асцендент'),('midheaven','Середина неба')):
            point=modules['astrology']['data'][key]
            fact('astro.'+key+'.longitude','astrology',label,point['longitude'],str(point['sign'])+'; приближённая модель ASC/MC. '+central)
    calculation={'schema_version':SCHEMA_VERSION,'input':value,'as_of':value['as_of'],'modules':modules,'facts':facts,
                 'warnings':warnings,'provenance':{'arithmetic_convention':CONVENTION,
                  'backend':value.get('backend','astronomy') if value['time_accuracy']!='unknown' else None,
                  'validation_scope':'structure and references, not semantic review'}}
    if modules['human_design']['status']=='computed':
        calculation['provenance']['ephemeris']=modules['human_design']['data']['provenance']
    calculation['calculation_id']=calculation_id(calculation)
    validate_calculation(calculation)
    return calculation


def validate_calculation(value):
    _object(value,'calculation')
    if type(value.get('schema_version')) is not int or value['schema_version']!=SCHEMA_VERSION:
        raise ValueError('schema_version must be 2')
    identifier=value.get('calculation_id')
    if not isinstance(identifier,str) or not re.fullmatch('[0-9a-f]{64}',identifier) or identifier!=calculation_id(value):
        raise ValueError('calculation_id mismatch: calculation changed or is incomplete')
    validate_input(value.get('input'))
    if value.get('as_of')!=value['input']['as_of']:
        raise ValueError('as_of differs from input')
    modules=value.get('modules')
    _object(modules,'modules')
    if set(modules)!=set(MODULES):
        raise ValueError('calculation requires all five module statuses')
    for name,module in modules.items():
        _object(module,'module '+name)
        if module.get('status') not in ('computed','unavailable'):
            raise ValueError('invalid module status')
        _object(module.get('data'),'module data')
        if module['status']=='unavailable':
            _text(module.get('reason'),'unavailable reason')
    if not isinstance(value.get('facts'),list):
        raise ValueError('facts must be an array')
    seen=set()
    for fact in value['facts']:
        _object(fact,'fact')
        for key in ('id','section','label'):
            _text(fact.get(key),'fact '+key)
        if fact['id'] in seen or fact['section'] not in FACT_MODULES or 'value' not in fact:
            raise ValueError('fact IDs must be unique and sections must map to calculated modules')
        if modules[FACT_MODULES[fact['section']]]['status']!='computed':
            raise ValueError('unavailable modules cannot provide facts')
        if 'detail' in fact and not isinstance(fact['detail'],str):
            raise ValueError('fact detail must be text')
        seen.add(fact['id'])
    if not isinstance(value.get('warnings'),list) or not all(isinstance(w,str) for w in value['warnings']):
        raise ValueError('warnings must be an array of strings')
    _object(value.get('provenance'),'provenance')
    return value


def validate_narrative(calculation,narrative):
    validate_calculation(calculation)
    _object(narrative,'narrative')
    if narrative.get('calculation_id')!=calculation['calculation_id']:
        raise ValueError('narrative calculation_id mismatch')
    sections=narrative.get('sections')
    _object(sections,'narrative sections')
    if set(sections)!=set(SECTIONS):
        raise ValueError('narrative requires exactly all eight sections')
    facts={f['id']:f for f in calculation['facts']}
    def grounded(items,label,allow_empty=False):
        if not isinstance(items,list) or not items:
            raise ValueError(label+' must be a nonempty array')
        for item in items:
            _object(item,label+' item')
            _text(item.get('text'),label+' text')
            sources=item.get('sources')
            if not isinstance(sources,list) or (not sources and not allow_empty):
                raise ValueError(label+' requires existing fact sources')
            if any(not isinstance(s,str) or s not in facts for s in sources):
                raise ValueError(label+' contains an unknown fact source')
    def topics(items,label,allow_empty_sources=False):
        if not isinstance(items,list) or not items:
            raise ValueError(label+' must be a nonempty array')
        for topic in items:
            _object(topic,label+' topic')
            _text(topic.get('title'),label+' title')
            grounded(topic.get('paragraphs'),label+' paragraphs',allow_empty_sources)
    for key,section in sections.items():
        _object(section,'section '+key)
        _text(section.get('intro'),'section intro')
        unavailable=key in MODULES and calculation['modules'][key]['status']=='unavailable'
        grounded(section.get('interpretation'),key+' interpretation',unavailable)
        if 'topics' in section:
            topics(section['topics'],key+' topics',unavailable)
        actions=section.get('actions')
        if not (unavailable and actions==[]):
            grounded(actions,key+' actions')
    grounded(narrative.get('summary'),'summary')
    if 'summary_topics' in narrative:
        topics(narrative['summary_topics'],'summary_topics')
    canonical_json(narrative)
    return narrative


def summary(calculation):
    validate_calculation(calculation)
    return {'schema_version':SCHEMA_VERSION,'calculation_id':calculation['calculation_id'],'as_of':calculation['as_of'],
            'module_statuses':{k:{'status':m['status'],**({'reason':m['reason']} if m['status']=='unavailable' else {})}
                               for k,m in calculation['modules'].items()},
            'facts':calculation['facts'],'warnings':calculation['warnings'],'provenance':calculation['provenance']}
