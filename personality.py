#!/usr/bin/env python3
"""Local JSON calculation and offline HTML report commands."""
import argparse
import json
from pathlib import Path
import sys

from personality_core.pipeline import (calculate, load_json, summary, validate_calculation,
                                       validate_narrative, write_atomic)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    calc=commands.add_parser('calculate',help='Calculate from explicitly confirmed input')
    calc.add_argument('--input',required=True)
    calc.add_argument('--output',required=True)
    for name in ('render','check'):
        command=commands.add_parser(name)
        command.add_argument('--calculation',required=True)
        command.add_argument('--narrative')
        if name=='render':
            target=command.add_mutually_exclusive_group(required=True)
            target.add_argument('--output',help='Один автономный HTML-файл (стили и сцены внутри)')
            target.add_argument('--site',help='Папка страницы для сайта: index.html, assets/, .htaccess, manifest.json и рядом .zip')
    compact=commands.add_parser('summary',help='Print compact facts without raw activations')
    compact.add_argument('--calculation',required=True)
    commands.add_parser('questionnaire',help='Print 36 questions without the scoring key')
    infostyle=commands.add_parser('infostyle',help='Read addressed cards from the pinned local infostyle dependency')
    selection=infostyle.add_mutually_exclusive_group(required=True)
    selection.add_argument('--list',action='store_true',help='Print only the card-title index')
    selection.add_argument('--cards',help='Comma-separated card IDs, for example 1.9,12.2')
    infostyle.add_argument('--root',help='Local promt-copywriting repository root; default: sibling repository')
    args=parser.parse_args(argv)
    try:
        if args.command=='infostyle':
            from personality_core.infostyle import list_cards,select_cards
            selected=list_cards(args.root) if args.list else select_cards(args.cards,args.root)
            sys.stdout.write(selected)
            return 0
        if args.command=='questionnaire':
            data=load_json(Path(__file__).resolve().parent/'data/archetypes.json')
            print(json.dumps({'scale':{'1':'совсем не про меня','2':'скорее нет','3':'когда как','4':'скорее да','5':'точно про меня'},
                              'questions':[{'number':i,'text':text} for i,text in enumerate(data['questions'],1)]},ensure_ascii=False,indent=2))
            return 0
        if args.command=='calculate':
            result=calculate(load_json(args.input))
            write_atomic(args.output,json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',(args.input,))
            print('Расчёт сохранён: '+str(args.output))
            return 0
        result=validate_calculation(load_json(args.calculation))
        narrative=None
        if getattr(args,'narrative',None):
            narrative=validate_narrative(result,load_json(args.narrative))
        if args.command=='check':
            print('Структура, идентификатор и связи проверены. Семантическая вычитка не выполнялась.')
            if narrative is not None:
                from personality_core.pipeline import narrative_warnings
                notes=narrative_warnings(narrative)
                if notes:
                    print('Предупреждения стиля (не блокируют выпуск): '+str(len(notes)))
                    for note in notes:
                        print('- '+note)
        elif args.command=='summary':
            print(json.dumps(summary(result),ensure_ascii=False,indent=2,allow_nan=False))
        else:
            protected=[args.calculation]+([args.narrative] if args.narrative else [])
            if args.site:
                from personality_core.package import write_site
                folder,archive=write_site(args.site,result,narrative,tuple(protected))
                print('Страница для сайта: '+str(folder)+'\nАрхив: '+str(archive))
            else:
                from personality_core.report import render_report
                write_atomic(args.output,render_report(result,narrative),protected)
                print('Отчёт сохранён: '+str(args.output))
        return 0
    except (ValueError,TypeError,KeyError,OSError,RuntimeError,OverflowError) as exc:
        print('Ошибка: '+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
