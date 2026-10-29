import tempfile
import unittest
from pathlib import Path
from arayzt.core import audit, export_overlay, read_lua

class LuaTranslationTest(unittest.TestCase):
    def test_audit_and_export_txt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'game/media/lua/shared/Translate'
            en=root/'EN/UI_EN.txt'; pt=root/'PTBR/UI_PTBR.txt'
            en.parent.mkdir(parents=True);pt.parent.mkdir(parents=True)
            en.write_text('UI_EN = {\n UI_One = "Minor Bleeding",\n UI_Two = "Bandage required",\n UI_Three = "You have %s items",\n}\n',encoding='utf-8')
            pt.write_text('UI_PTBR = {\n UI_Two = "Precisa de bandagem",\n UI_Three = "Você tem %s itens",\n}\n',encoding='utf-8')
            report=audit(Path(d)/'game')
            self.assertEqual(report['counts']['missing'],1)
            res=export_overlay(report,[{'file':'UI_PTBR.txt','key':'UI_One','translation':'Sangramento leve'}],Path(d)/'output',Path(d)/'backup')
            self.assertEqual(res['translated'],1)
            result=read_lua(Path(res['output'])/'UI_PTBR.txt')
            self.assertEqual(result['UI_One'],'Sangramento leve')
            self.assertEqual(result['UI_Three'],'Você tem %s itens')
            self.assertEqual(read_lua(pt).get('UI_One'),None)
            self.assertTrue((Path(d)/'backup/PTBR/UI_PTBR.txt').exists())

    def test_new_ptbr_txt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'game/media/lua/shared/Translate'
            en=root/'EN/Recipes_EN.txt';en.parent.mkdir(parents=True)
            en.write_text('Recipes_EN = {\n Recipe_A = "Cook food",\n}\n',encoding='utf-8')
            rep=audit(Path(d)/'game')
            out=export_overlay(rep,[{'file':'Recipes_PTBR.txt','key':'Recipe_A','translation':'Cozinhar alimento'}],Path(d)/'out')
            self.assertEqual(read_lua(Path(out['output'])/'Recipes_PTBR.txt')['Recipe_A'],'Cozinhar alimento')

    def test_missing_dir_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError): audit(Path(d)/'invalid')

if __name__=='__main__':unittest.main()

class V030Test(unittest.TestCase):
    def test_duplicate_keys_last_wins_and_export(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'media/lua/shared/Translate'
            en=root/'EN/UI_EN.txt';en.parent.mkdir(parents=True)
            en.write_text('UI_EN = {\n UI_X = "Old",\n UI_X = "New",\n UI_Y = "Hello",\n}\n',encoding='utf-8')
            report=audit(root)
            self.assertEqual(report['counts']['missing'],2)
            self.assertTrue(any(p['kind']=='duplicate_key' for p in report['problems']))
            out=export_overlay(report,[{'file':'UI_PTBR.txt','key':'UI_X','translation':'Novo'}],Path(d)/'export')
            self.assertEqual(read_lua(Path(out['output'])/'UI_PTBR.txt')['UI_X'],'Novo')

    def test_free_text_separate_from_key_value(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'media/lua/shared/Translate'
            (root/'EN').mkdir(parents=True)
            (root/'EN/UI_EN.txt').write_text('UI_EN = {\n UI_X = "Hello",\n}\n',encoding='utf-8')
            (root/'EN/language.txt').write_text('English\n',encoding='utf-8')
            report=audit(root)
            self.assertEqual(len(report['free_text']),1)
            self.assertEqual(report['source_files'],2)
            self.assertEqual(report['parsed_files'],1)

    def test_json_mapping_filename(self):
        from arayzt.core import translation_rel
        self.assertEqual(translation_rel(Path('UI_EN.json')).name,'UI_PTBR.json')
