from arayzt.core import export_overlay
def test_no_changes_gives_success(tmp_path):
    report={'game':str(tmp_path),'rows':[]}
    result=export_overlay(report,[],tmp_path/'output')
    assert result['delivery_status']=='success'
    assert result['blocked_files']==[]
