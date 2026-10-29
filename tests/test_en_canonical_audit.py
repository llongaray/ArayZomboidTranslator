from arayzt.core import audit, canonical_audit_summary, select_rows
from pathlib import Path

def test_english_is_reference_for_files_and_keys(tmp_path):
    root=tmp_path/'media'/'lua'/'shared'/'Translate'
    en=root/'EN'
    pt=root/'PTBR'
    en.mkdir(parents=True);pt.mkdir(parents=True)
    (en/'UI_EN.txt').write_text('UI_EN = {\n  UI_Valid = "Good",\n  UI_New = "New",\n}\n',encoding='utf-8')
    (pt/'UI_PTBR.txt').write_text('UI_PTBR = {\n  UI_Valid = "Bom",\n  UI_WrongKey = "Nova",\n}\n',encoding='utf-8')
    (en/'Tooltip_EN.txt').write_text('Tooltip_EN = {\n  Tooltip_Test = "Test",\n}\n',encoding='utf-8')
    (pt/'OnlyPTBR_PTBR.txt').write_text('OnlyPTBR_PTBR = {\n  OnlyPTBR_Test = "Texto",\n}\n',encoding='utf-8')
    report=audit(tmp_path)
    summary=canonical_audit_summary(report)
    assert summary['ptbr_missing_files']==1
    assert summary['ptbr_orphan_files']==1
    assert summary['wrong_or_unknown_ptbr_keys']==1
    assert summary['missing_keys']==2
    pending=select_rows(report,'all','')
    assert {(r['file'],r['key']) for r in pending}=={('UI_PTBR.txt','UI_New'),('Tooltip_PTBR.txt','Tooltip_Test')}
    assert any(p['kind']=='extra_ptbr_key' and p['key']=='UI_WrongKey' for p in report['problems'])

def test_no_automatic_rewrite_of_noncanonical_keys(tmp_path):
    root=tmp_path/'media'/'lua'/'shared'/'Translate'
    (root/'EN').mkdir(parents=True);(root/'PTBR').mkdir(parents=True)
    (root/'EN'/'ItemName_EN.txt').write_text('ItemName_EN = {\n ItemName_Base.Pen = "Pen",\n}\n',encoding='utf-8')
    (root/'PTBR'/'ItemName_PTBR.txt').write_text('ItemName_PTBR = {\n ItemName_Base.Penn = "Caneta",\n}\n',encoding='utf-8')
    report=audit(tmp_path)
    assert report['rows'][0]['status']=='missing'
    assert report['rows'][0]['key']=='ItemName_Base.Pen'
    assert any(p['key']=='ItemName_Base.Penn' for p in report['problems'] if p['kind']=='extra_ptbr_key')
