import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from personality import main
from personality_core.infostyle import list_cards, select_cards


class InfostyleTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base=Path(self.temporary.name)
        self.root=self.base/'copywriting'
        self.root.mkdir()
        self.git('init','-q')
        self.first='## 1.9. Синтетическая первая карточка\n\n**Что это.** Пример.\n\n**Когда включается.** Проверка.\n\n**Как применить.** Применить.\n\n**Как проверить.** Первый критерий.\n'
        self.second='## 12.2. Синтетическая вторая карточка\n\n**Что это.** Пример два.\n\n### Внутреннее пояснение\n\nОстаётся внутри карточки.\n\n**Как проверить.** Второй критерий.\n'
        self.source=self.root/'methodology-copywriting.md'
        self.source.write_text('# Вступление, которое не выбирается\n\n'+self.first+'\n# Блок, который не выбирается\n\nВводный текст блока.\n\n'+self.second,encoding='utf-8')
        self.git('add',self.source.name)
        self.git('-c','user.name=Roman Berman','-c','user.email=romanebrman90@ya.ru',
                 '-c','core.hooksPath=/dev/null','commit','-qm','Synthetic dependency fixture')
        self.manifest=self.base/'dependencies.json'
        self.data={'schema_version':1,'dependencies':{'infostyle':{
            'source':'https://example.invalid/synthetic', 'file':self.source.name,
            'revision':self.git('rev-parse','HEAD'),
            'sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()}}}
        self.write_manifest()

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args],text=True,stderr=subprocess.DEVNULL).strip()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.data),encoding='utf-8')

    def test_index_and_selected_complete_cards_only(self):
        self.assertEqual(list_cards(self.root,_manifest_path=self.manifest),
                         '## 1.9. Синтетическая первая карточка\n## 12.2. Синтетическая вторая карточка\n')
        selected=select_cards('12.2, 1.9',self.root,_manifest_path=self.manifest)
        self.assertEqual(selected,self.second.rstrip()+'\n\n'+self.first.rstrip()+'\n')
        self.assertNotIn('Вводный текст блока',selected)
        self.assertNotIn('Вступление',selected)
        self.assertIn('### Внутреннее пояснение',selected)
        self.assertIn('**Как проверить.** Первый критерий.',selected)
        self.assertIn('**Как проверить.** Второй критерий.',selected)

    def test_unknown_and_invalid_cards(self):
        for selection in ('99.1','1.9,99.1','',',','1.9,','1','01.9','1.9,1.9'):
            with self.subTest(selection=selection),self.assertRaises(ValueError):
                select_cards(selection,self.root,_manifest_path=self.manifest)

    def test_changed_source_is_rejected_without_loading_other_files(self):
        self.source.write_text(self.source.read_text()+'\nИзменение.\n')
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            list_cards(self.root,_manifest_path=self.manifest)

    def test_wrong_revision_is_rejected_even_with_same_source(self):
        (self.root/'unrelated.txt').write_text('Synthetic unrelated file')
        self.git('add','unrelated.txt')
        self.git('-c','user.name=Roman Berman','-c','user.email=romanebrman90@ya.ru',
                 '-c','core.hooksPath=/dev/null','commit','-qm','Synthetic new revision')
        with self.assertRaisesRegex(ValueError,'HEAD'):
            select_cards('1.9',self.root,_manifest_path=self.manifest)

    def test_wrong_root_missing_source_and_outside_path(self):
        nested=self.root/'nested'
        nested.mkdir()
        with self.assertRaisesRegex(ValueError,'точно на корень'):
            list_cards(nested,_manifest_path=self.manifest)
        with self.assertRaisesRegex(ValueError,'не найдена'):
            list_cards(self.base/'absent',_manifest_path=self.manifest)
        self.source.unlink()
        with self.assertRaisesRegex(ValueError,'внутри корня'):
            list_cards(self.root,_manifest_path=self.manifest)
        outside=self.base/'outside.md'
        outside.write_text('Synthetic outside content')
        self.data['dependencies']['infostyle']['file']='../outside.md'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError,'внутри корня'):
            list_cards(self.root,_manifest_path=self.manifest)

    def test_public_cli_is_local_only_and_returns_two_on_failure(self):
        with patch('personality_core.infostyle._MANIFEST_PATH',self.manifest),contextlib.redirect_stdout(io.StringIO()) as output,contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(['infostyle','--root',str(self.root),'--cards','1.9']),0)
            self.assertEqual(output.getvalue(),self.first)
            output.seek(0);output.truncate(0)
            self.assertEqual(main(['infostyle','--root',str(self.root),'--list']),0)
            self.assertEqual(len(output.getvalue().splitlines()),2)
            output.seek(0);output.truncate(0)
            self.assertEqual(main(['infostyle','--root',str(self.root),'--cards','99.1']),2)
            self.assertEqual(output.getvalue(),'')
            self.assertIn('неизвестные карточки',error.getvalue())
            self.source.write_text('Modified synthetic data')
            self.assertEqual(main(['infostyle','--root',str(self.root),'--list']),2)
            self.assertEqual(output.getvalue(),'')


if __name__=='__main__':
    unittest.main()
