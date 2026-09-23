from __future__ import annotations
import json, tempfile
from pathlib import Path
import ai_router
from reality_alignment import compare, build_calibration_profile, export_profile, calibration_text
from workflow_engine import STANDARD


def fake_call_structured(**kwargs):
    return {'provider':'claude_code_subscription','model':'sonnet','data':{
      'overall_alignment_score':72,'verdict':'Většina směru sedí, dvě oblasti potřebují kalibraci.',
      'what_matches':[{'topic':'A','npc_result':'NPC 45 %','external_context':'Externě 43–47 %','assessment':'Shoda','confidence':'high','evidence_refs':['q1','src1']}],
      'what_does_not_match':[{'topic':'B','npc_result':'NPC 60 %','external_context':'Externě kolem 48 %','gap':'+12 p.b.','likely_causes':['příliš silný modelový prior'],'what_to_change':'Snížit pozitivní prior u q2.','priority':'high','evidence_refs':['q2','src2']}],
      'missing_evidence':['Segment 65+ nemá přímý benchmark.'],
      'ten_out_of_ten_plan':[{'priority':1,'action':'Kalibrovat q2','why':'Externí triangulace ukazuje systematický rozdíl.','expected_effect':'Přiblížení výsledku o několik p.b.','evidence_basis':['q2','src2']}],
      'calibration_candidates':[{'rule_id':'q2_down','title':'Konzervativnější q2','question_ids':['q2'],'topics':['tema'],'segments':[],'anchor_type':'directional','target_anchor':'Nižší pozitivní odpovědi; externí střed kolem 48 %.','strength':0.25,'evidence_strength':'strong','rationale':'Přímý benchmark.','expected_effect':'Pokles top-box.','evidence_refs':['q2','src2']},
                                {'rule_id':'weak','title':'Slabý prior','question_ids':['q3'],'topics':[],'segments':[],'anchor_type':'context_prior','target_anchor':'Nejasný směr.','strength':0.2,'evidence_strength':'weak','rationale':'Proxy.','expected_effect':'Malý.','evidence_refs':['src3']}],
      'closing_conclusion':'Standard Panel zachovat; AI Panel použít pro sensitivity běh.'}}


def main():
    old=ai_router.call_structured; ai_router.call_structured=fake_call_structured
    try:
        project={'title':'T','goal':'RQ','research_plan':{'research_questions':['RQ']},'audience':{},'run_policy':{'provider':'claude_code_subscription'}}
        a=compare(project,{'n':100,'vysledky':{}},{'executive_answer':'x'},{'accepted':[]},{'findings':[]})
        assert a['overall_alignment_score']==72
        p=build_calibration_profile(a,project=project,workflow_id='wf1')
        assert p['schema']=='npc_ai_panel_calibration/v1'
        assert p['rules'][0]['enabled'] is True and p['rules'][1]['enabled'] is False
        assert p['rules'][0]['strength']<=0.35
        txt=calibration_text(p,question_id='q2',topics=['tema'])
        assert 'Konzervativnější q2' in txt and 'soft prior' in txt
        assert calibration_text(p,question_id='other',topics=['other'])==''
        with tempfile.TemporaryDirectory() as td:
            jp,cp=export_profile(p,Path(td)/'p.json',Path(td)/'p.csv')
            assert Path(jp).is_file() and Path(cp).is_file()
        keys=[x[0] for x in STANDARD]
        assert keys.index('alignment')>keys.index('verify') and keys.index('report')>keys.index('alignment')
        print('REALITY_ALIGNMENT_ACCEPTANCE_PASS 10/10')
    finally:
        ai_router.call_structured=old

if __name__=='__main__': main()
