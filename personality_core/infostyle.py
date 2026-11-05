"""Addressed cards from a pinned local copywriting dependency, without copying it."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess

from .pipeline import load_json

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _PROJECT_ROOT / 'dependencies.json'
_CARD_HEADING = re.compile(r'^## (?P<id>[1-9]\d*\.[1-9]\d*)\. .+$',re.MULTILINE)
_HEADING = re.compile(r'^#{1,2} .+$',re.MULTILINE)


def _git(root, *arguments):
    try:
        result = subprocess.run(['git','-C',str(root),*arguments],check=True,
                                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,text=True,timeout=10,
                                env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    except (OSError,subprocess.SubprocessError) as exc:
        raise ValueError('Инфостиль: локальный Git-репозиторий недоступен или не соответствует контракту.') from exc
    return result.stdout.strip()


def _cards(root=None, *, _manifest_path=None):
    """Validate provenance before reading cards; test fixtures use a private manifest."""
    try:
        manifest=load_json(_manifest_path if _manifest_path is not None else _MANIFEST_PATH)
        dependency=manifest['dependencies']['infostyle']
        filename=dependency['file']
        revision=dependency['revision']
        digest=dependency['sha256']
    except (KeyError,TypeError,ValueError,OSError) as exc:
        raise ValueError('Инфостиль: манифест зависимости недоступен или некорректен.') from exc
    if (not isinstance(filename,str) or not filename or Path(filename).is_absolute()
            or not isinstance(revision,str) or not re.fullmatch('[0-9a-f]{40}',revision)
            or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest)):
        raise ValueError('Инфостиль: манифест должен задавать относительный файл, полную ревизию и SHA-256.')
    supplied=Path(root).expanduser().resolve() if root is not None else (_PROJECT_ROOT.parent/'promt-copywriting').resolve()
    if not supplied.is_dir():
        raise ValueError('Инфостиль: локальная зависимость не найдена; подготовьте clone и checkout по docs/copywriting-integration.md.')
    actual=Path(_git(supplied,'rev-parse','--show-toplevel')).resolve()
    if actual!=supplied:
        raise ValueError('Инфостиль: --root должен указывать точно на корень репозитория.')
    if _git(supplied,'rev-parse','HEAD')!=revision:
        raise ValueError('Инфостиль: HEAD зависимости не совпадает с закреплённой ревизией; автоматический checkout не выполняется.')
    source=(supplied/filename).resolve()
    if not source.is_relative_to(supplied) or not source.is_file():
        raise ValueError('Инфостиль: исходный файл должен существовать внутри корня зависимости.')
    content=source.read_bytes()
    if hashlib.sha256(content).hexdigest()!=digest:
        raise ValueError('Инфостиль: SHA-256 исходного файла изменился; выборка карточек остановлена.')
    try:
        text=content.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('Инфостиль: исходный файл должен иметь кодировку UTF-8.') from exc
    headings=list(_HEADING.finditer(text))
    cards={}
    for index,heading in enumerate(headings):
        match=_CARD_HEADING.fullmatch(heading.group())
        if match is None:
            continue
        identifier=match['id']
        if identifier in cards:
            raise ValueError('Инфостиль: повторяющийся номер карточки в методичке.')
        end=headings[index+1].start() if index+1<len(headings) else len(text)
        cards[identifier]=(heading.group(),text[heading.start():end].rstrip())
    if not cards:
        raise ValueError('Инфостиль: карточки с заголовками ## не найдены.')
    return cards


def list_cards(root=None, *, _manifest_path=None):
    """Return only the ## card-heading index after dependency checks."""
    cards=_cards(root,_manifest_path=_manifest_path)
    return '\n'.join(title for title,_ in cards.values())+'\n'


def select_cards(identifiers, root=None, *, _manifest_path=None):
    """Return complete addressed cards, in requested order, or fail without output."""
    if not isinstance(identifiers,str):
        raise ValueError('Инфостиль: --cards требует номера через запятую, например 1.9,12.2.')
    selected=[item.strip() for item in identifiers.split(',')]
    if any(not re.fullmatch('[1-9]\d*\.[1-9]\d*',item) for item in selected):
        raise ValueError('Инфостиль: неверный формат номеров карточек; ожидается 1.9,12.2.')
    if len(set(selected))!=len(selected):
        raise ValueError('Инфостиль: номера карточек не должны повторяться.')
    cards=_cards(root,_manifest_path=_manifest_path)
    unknown=[item for item in selected if item not in cards]
    if unknown:
        raise ValueError('Инфостиль: неизвестные карточки: '+', '.join(unknown))
    return '\n\n'.join(cards[item][1] for item in selected)+'\n'
