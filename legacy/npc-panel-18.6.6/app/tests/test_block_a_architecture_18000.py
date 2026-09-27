from pathlib import Path
import json,csv
ROOT=Path(__file__).resolve().parents[1]

def test_block_a_docs_exist():
    for f in ['REQUIREMENTS_AUDIT_BLOCK_A.md','ARCHITECTURE_18_0.md','BLOCK_ROADMAP_A_TO_F.md','INTERFACE_CONTRACTS.md','FEATURE_MATRIX_BLOCK_A.csv','MERGE_CONTRACT_BLOCK_A.json','SOURCE_PROVENANCE_BLOCK_A.json']:
        assert (ROOT/'docs'/'architecture_18'/f).exists()

def test_merge_contract_has_all_blocks_and_nonnegotiables():
    x=json.loads((ROOT/'docs/architecture_18/MERGE_CONTRACT_BLOCK_A.json').read_text(encoding='utf-8'))
    assert x['block_order']==['A','B','C','D','E','F']
    assert set(x['providers_target'])=={'claude_code_subscription','anthropic','openai'}
    for key in ['project_is_source_of_truth','no_silent_live_fallback','research_simulation_separation','static_population_immutable']:
        assert key in x['non_negotiables']

def test_feature_matrix_assigns_every_future_feature_to_a_block():
    rows=list(csv.DictReader((ROOT/'docs/architecture_18/FEATURE_MATRIX_BLOCK_A.csv').open(encoding='utf-8-sig')))
    assert len(rows)>=20
    assert all(r['target_block'] in {'B','C','D','E','F','B/E','C/E'} for r in rows)
    names={r['feature'] for r in rows}
    for required in ['Project Manager filters','Respondent visualization','AI interesting groups','Data Library','LIVE population']:
        assert required in names

def test_demo_and_live_visualization_contract_is_same():
    text=(ROOT/'docs/architecture_18/INTERFACE_CONTRACTS.md').read_text(encoding='utf-8')
    assert 'DEMO data musí používat stejný kontrakt jako ostrá data' in text
    assert 'Visualization nikdy nepřepisuje raw results' in text

def test_no_fake_live_respondents_rule_is_explicit():
    text=(ROOT/'docs/architecture_18/REQUIREMENTS_AUDIT_BLOCK_A.md').read_text(encoding='utf-8')
    assert 'systém nesmí vymyslet falešné respondenty' in text
    assert 'DEMO mapa používá explicitně připravený ilustrační respondentní dataset' in text
