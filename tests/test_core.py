import json
from pathlib import Path
import tempfile
import unittest
from arayzt.core import audit, protect, restore, tokens, export_overlay, read_json, select_rows
from arayzt.ollama import OllamaClient

class CoreTest(unittest.TestCase):
    def test_placeholders_roundtrip(self):
        original = "Bandage %1 on {name} <color=red>\\n %s"
        protected,mapping=protect(original)
        self.assertEqual(restore(protected,mapping),original)
        self.assertEqual(tokens(original),tokens(restore(protected,mapping)))
        with self.assertRaises(ValueError):restore(protected.replace("⟦AZT0000⟧","oops"),mapping)
    def test_detect_and_export(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"game/media/lua/shared/Translate"
            for lang,content in [("EN",{"x":"Minor Bleeding","y":"Already okay","z":"Use %s"}), ("PTBR",{"y":"Já está bem","z":"Use %s"})]:
                p=root/lang/"UI.json";p.parent.mkdir(parents=True);p.write_text(json.dumps(content))
            report=audit(Path(d)/"game")
            self.assertEqual(report['counts']['missing'],1)
            self.assertEqual(report['counts']['identical'],1)
            accepted=[{"file":"UI.json","key":"x","translation":"Sangramento leve"}]
            res=export_overlay(report,accepted,Path(d)/"out",Path(d)/"backup")
            self.assertEqual(res['translated'],1)
            output=read_json(Path(res['output'])/"UI.json")
            self.assertEqual(output['x'],"Sangramento leve")
            self.assertEqual(read_json(root/"PTBR/UI.json")['y'],"Já está bem")
            self.assertTrue((Path(d)/"backup/PTBR/UI.json").exists())
    def test_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"t.json";p.write_text('{"a":"1","a":"2"}')
            with self.assertRaises(ValueError):read_json(p)
    def test_nonlocal_ollama_rejected(self):
        with self.assertRaises(ValueError):OllamaClient(url="http://remote.example:11434")

if __name__=='__main__': unittest.main()
