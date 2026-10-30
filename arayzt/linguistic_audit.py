"""Deterministic linguistic screening plus a source-bound BodyParts review.

Screening findings require investigation; they are not semantic certification of
all approved translations. Only the reviewed anatomy table is auto-corrected.
"""
from .validation import validate_candidate
import json, re
from pathlib import Path
CONTEXTS={(r["file"],r["key"],r["en"]):r["translation"] for r in json.loads((Path(__file__).parent/"data"/"linguistic_contexts_ptbr.json").read_text(encoding="utf-8"))}
BODY_PARTS={
 'BODYPART_PELVIS':('Pelvis','Pelve'),
 'BODYPART_SPINE':('Spine','Coluna vertebral'),
 'BODYPART_HEAD':('Head','Cabeça'),
 'BODYPART_LEFT_UPPER_LEG':('Left Upper Leg','Coxa esquerda'),
 'BODYPART_LEFT_LOWER_LEG':('Left Lower Leg','Perna esquerda'),
 'BODYPART_RIGHT_UPPER_LEG':('Right Upper Leg','Coxa direita'),
 'BODYPART_RIGHT_LOWER_LEG':('Right Lower Leg','Perna direita'),
 'BODYPART_LEFT_UPPER_ARM':('Left Upper Arm','Braço esquerdo'),
 'BODYPART_LEFT_LOWER_ARM':('Left Lower Arm','Antebraço esquerdo'),
 'BODYPART_RIGHT_UPPER_ARM':('Right Upper Arm','Braço direito'),
 'BODYPART_RIGHT_LOWER_ARM':('Right Lower Arm','Antebraço direito'),
}
def reviewed_translation(row):
    rule=BODY_PARTS.get(row['key']) if row['file']=='BodyParts_PTBR.txt' else None
    return rule[1] if rule and row['en']==rule[0] else CONTEXTS.get((row['file'],row['key'],row['en']))

def screen(report, approved):
    original={(r['file'],r['key']):r for r in report['rows']}
    findings=[];body=[]
    for item in approved:
        row=original[(item['file'],item['key'])];value=item['translation']
        status,reasons=validate_candidate(row['en'],value,row['key'])
        expected=reviewed_translation(row)
        if expected is not None and row['file']=='BodyParts_PTBR.txt':
            body.append({'file':row['file'],'key':row['key'],'en':row['en'],
                         'before':value,'reviewed':expected,'changed':value!=expected})
        checks=list(reasons)
        for english,portuguese in [('left','esquerd'),('right','direit')]:
            if re.search(r'(?:^| - )'+english+r'(?:\s|$)',row['en'].casefold()) and portuguese not in value.casefold():
                checks.append('possible_missing_laterality_'+english)
        if checks:findings.append({'file':row['file'],'key':row['key'],'en':row['en'],
                                   'translation':value,'checks':checks,'automatic_correction':expected})
    return {'screened':len(approved),'scope':'Automated screening of all approvals; contextual review of BodyParts and six individually reviewed cases. Other findings are candidates for further audit.',
            'bodyparts_review':body,'findings':findings}
