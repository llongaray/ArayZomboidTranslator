import unittest
from arayzt.summary import summarize, matches
try:
    from arayzt.web import app
except ModuleNotFoundError:
    app = None
from unittest.mock import patch

REPORT={'rows':[{'file':'UI_PTBR.txt','status':'missing'}, {'file':'UI_PTBR.txt','status':'translated'}, {'file':'Moodles_PTBR.txt','status':'missing'}, {'file':'ContextMenu_PTBR.txt','status':'identical'}], 'problems':[{'file':'UI_EN.txt','kind':'duplicate_key'}], 'source_files':4,'parsed_files':3}
class Dashboard032Tests(unittest.TestCase):
    def test_filter_exact_file_names(self):
        r=summarize(REPORT,'UI,Moodles',2)
        self.assertEqual(r['total'],3)
        self.assertEqual(r['counts']['missing'],2)
        self.assertEqual(r['selected'],2)
        self.assertEqual(r['filters'],'UI,Moodles')
    def test_unfiltered(self):
        self.assertEqual(summarize(REPORT)['total'],4)
    def test_filter_no_substring_false_matches(self):
        self.assertFalse(matches({'file':'SomeUI_PTBR.txt'},'UI'))
    @unittest.skipIf(app is None, "Flask indisponível no ambiente de testes")
    def test_html_kpis_and_filter_default(self):
        with app.test_client() as client:
            body=client.get('/').get_data(as_text=True)
        self.assertIn('id="metrics"',body)
        self.assertIn('id="fileRows"',body)
        self.assertIn('name="files" value="UI,ContextMenu,Moodles"',body)
    def test_summary_problem_aggregate(self):
        s=summarize(REPORT,'UI')
        self.assertEqual(s['problems'],1)
        self.assertEqual(s['problem_counts']['duplicate_key'],1)

if __name__=='__main__': unittest.main()
