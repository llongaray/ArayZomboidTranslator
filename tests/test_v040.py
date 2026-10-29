import json, tempfile, unittest
from pathlib import Path
from arayzt.jobs import Pipeline, fingerprint, load_memory
from arayzt.core import select_rows

class Pipeline040Tests(unittest.TestCase):
    def make_game(self, root):
        base=Path(root)/'media/lua/shared/Translate'
        (base/'EN').mkdir(parents=True)
        (base/'PTBR').mkdir()
        (base/'EN/UI_EN.txt').write_text('UI_EN = {\n    UI_Action = "Open Door",\n    UI_Foo = "Take %1",\n}\n',encoding='utf-8')
        (base/'PTBR/UI_PTBR.txt').write_text('UI_PTBR = {\n    UI_Action = "Abrir porta",\n}\n',encoding='utf-8')
        return base
    def test_audit_filter_and_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            game=self.make_game(temp)
            result=Pipeline().run(game,Path(temp)/'work',files='UI')
            self.assertEqual(result['selected'],1)
            self.assertEqual(result['counts']['translated'],1)
            self.assertTrue(Path(result['review_csv']).exists())
            self.assertEqual(result['filters'],'UI')
    def test_checkpoint_resume_and_export_without_ollama(self):
        with tempfile.TemporaryDirectory() as temp:
            game=self.make_game(temp); work=Path(temp)/'work'
            report=__import__('arayzt.core',fromlist=['audit']).audit(game)
            row=select_rows(report,'all','UI')[0]
            work.mkdir(); (work/'checkpoint-v040.json').write_text(json.dumps({fingerprint(row):'Pegar %1'}),encoding='utf-8')
            # Nenhuma chamada a Ollama porque todas as pendências foram atendidas pelo checkpoint.
            result=Pipeline().run(game,work,translate=True,files='UI')
            self.assertEqual(result['reused'],1)
            self.assertEqual(result['translated'],1)
            output=Path(result['output'])/'UI_PTBR.txt'
            self.assertIn('Pegar %1',output.read_text(encoding='utf-8'))
            self.assertNotIn('Pegar %1',(game/'PTBR/UI_PTBR.txt').read_text(encoding='utf-8'))
    def test_exact_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            game=self.make_game(temp)
            self.assertEqual(Pipeline().run(game,Path(temp)/'w',files='ItemName')['selected'],0)
    def test_sha_stable(self):
        row={'file':'UI_PTBR.txt','key':'foo','en':'bar'}
        self.assertEqual(fingerprint(row),fingerprint(row))
        self.assertEqual(len(fingerprint(row)),64)

if __name__=='__main__': unittest.main()
