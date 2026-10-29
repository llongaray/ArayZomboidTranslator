from arayzt.quality import review

def test_untranslated_is_review():
    assert review('Sleep on Ground with Pillow','Sleep on Ground with Pillow')[0]=='needs_review'

def test_good_translation():
    assert review('Open and Drink','Abrir e Beber')[0]=='approved'

def test_glossary_disagreement():
    assert 'glossary_mismatch' in review('Tie Escape Rope','Amarra Corda de Fuga')[1]

def test_empty_and_placeholders():
    assert review('A %1','')[0]=='rejected'
    assert review('A %1','B %2')[0]=='rejected'
