import tempfile
import unittest
from pathlib import Path
from arayzt.core import audit, select_rows, export_overlay, read_lua, parse_lua

class Safety031Tests(unittest.TestCase):
    def test_protect_names_and_existing_translation(self):
        report={'rows': [
            {'file':'SurvivorNames_PTBR.txt','key':'S_1','en':'Smith','status':'missing'},
            {'file':'UI_PTBR.txt','key':'UI_1','en':'New text','status':'missing'},
            {'file':'UI_PTBR.txt','key':'UI_2','en':'Old text','status':'identical'},
            {'file':'Moodles_PTBR.txt','key':'M_1','en':'Bleeding','status':'missing'},
        ]}
        self.assertEqual([x['key'] for x in select_rows(report,'all')],['UI_1','M_1'])
        self.assertEqual([x['key'] for x in select_rows(report,'all','UI')],['UI_1'])
        self.assertEqual([x['key'] for x in select_rows(report,'all','UI',True)],['UI_1','UI_2'])
    def test_existing_translation_requires_approval_to_export(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'media/lua/shared/Translate'
            en=root/'EN/UI_EN.txt'; pt=root/'PTBR/UI_PTBR.txt'
            en.parent.mkdir(parents=True); pt.parent.mkdir(parents=True)
            en.write_text('UI_EN = {\n UI_x = "Same text",\n UI_y = "Need translation",\n}\n')
            pt.write_text('UI_PTBR = {\n UI_x = "Same text",\n}\n')
            report=audit(root)
            a=[{'file':'UI_PTBR.txt','key':'UI_x','translation':'Novo'}, {'file':'UI_PTBR.txt','key':'UI_y','translation':'Tradução necessária'}]
            out=export_overlay(report,a,Path(d)/'export')
            translated=read_lua(Path(out['output'])/'UI_PTBR.txt')
            self.assertEqual(translated['UI_x'],'Same text')
            self.assertEqual(translated['UI_y'],'Tradução necessária')
            self.assertEqual(read_lua(pt)['UI_x'],'Same text')
    def test_standard_lua_no_false_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'UI_EN.txt'
            p.write_text('UI_EN = {\n  UI_a = "One",\n  UI_b = "Two",\n}\n')
            data,warnings=parse_lua(p)
            self.assertEqual(len(data),2)
            self.assertFalse(warnings)

if __name__=='__main__': unittest.main()
