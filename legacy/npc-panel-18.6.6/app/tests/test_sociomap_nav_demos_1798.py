from pathlib import Path
import numpy as np
import pandas as pd


def test_correlation_relation_matrix_is_full_1_10_zero_diagonal_and_symmetric():
    from sociomap import derive_relation_matrix
    df=pd.DataFrame({'a':[1,2,3,4,5,6,7],'b':[1,2,3,4,5,6,7],'c':[7,6,5,4,3,2,1],'d':[2,5,3,6,4,7,1]})
    R,s=derive_relation_matrix(df,['a','b','c','d'])
    assert R.shape==(4,4)
    assert np.allclose(np.diag(R),0)
    off=R[~np.eye(4,dtype=bool)]
    assert np.all((off>=1)&(off<=10))
    assert np.allclose(R,R.T)
    assert R[0,1]>9.9 and R[0,2]<1.1


def test_explicit_directional_matrix_preserves_asymmetry_but_layout_uses_one_mutual_distance():
    from sociomap import fit_relational_landscape
    M=np.array([[0,9,2,4],[4,0,8,7],[7,3,0,6],[5,2,9,0]],float)
    r=fit_relational_landscape(M,['A','B','C','D'],[8,7,6,5])
    assert r.relation_matrix[0,1]==9
    assert r.relation_matrix[1,0]==4
    assert np.allclose(np.diag(r.relation_matrix),0)
    assert r.metadata['relation_scale']=='1-10'
    assert r.metadata['input_asymmetry_mean_abs']>0


def test_production_html_is_offline_interactive_3d_and_has_audit_matrix(tmp_path):
    from sociomap import fit_relational_landscape, export_relational_html
    M=np.array([[0,9,2],[4,0,8],[7,3,0]],float)
    r=fit_relational_landscape(M,['A','B','C'],[8,6,4])
    s=export_relational_html(tmp_path/'map.html',r).read_text(encoding='utf-8')
    assert 'Vizualizace vztahů' in s and 'Normativní skóre' in s
    assert 'Rozbalit vztahovou matici' in s
    assert 'cv.onwheel' in s
    assert 'unpkg.com' not in s and 'three.min.js' not in s.lower()


def test_demo_catalog_contains_five_real_simulation_seeds():
    import demo_showcase
    rows=demo_showcase.project_catalog()
    sims=[x for x in rows if x.get('project_type')=='simulation']
    assert len(rows)==34 and len(sims)==6
    for x in sims:
        d=demo_showcase.load(x['project_id'])
        assert d['project_type']=='simulation'
        assert len(d.get('worlds') or [])>=1
        assert any(f['name']=='SIMULATION_PREVIEW.html' for f in d.get('files') or [])


def test_demo_research_sociomap_has_all_pairs_1_10_matrix():
    import demo_showcase
    rid=next(x['project_id'] for x in demo_showcase.catalog() if x.get('collection')=='showcase')
    d=demo_showcase.load(rid)
    sm=d.get('sociomap') or {}; nodes=sm.get('nodes') or []; M=sm.get('relation_matrix_1_10')
    assert nodes and len(M)==len(nodes)
    assert all(len(row)==len(nodes) for row in M)
    for i,row in enumerate(M):
        for j,v in enumerate(row):
            if i==j: assert v==0
            else: assert 1<=float(v)<=10


def test_static_top_navigation_is_compact_and_diagnostics_is_only_in_settings_menu():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    marker='<main class="workspace"><div class="topbar"'
    a=s.index(marker); b=s.index('<div id="view">',a)
    top=s[a:b]
    assert top.count('>Úvod</button>')==1
    assert top.count('>Výzkum</button>')==1
    assert top.count('>Simulace</button>')==1
    assert top.count('>Správa projektů</button>')==1
    assert '>Dema</button>' not in top
    assert '>Diagnostika</button>' not in top
    side=s[s.index('<aside class="sidebar"'):a]
    assert 'AI asistent' in side and 'Data Library' in side and 'Správa projektů' in side
    assert '>Diagnostika</button>' in side


def test_final_runtime_navigation_is_compact():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    a=s.index('function applyFinalNav1798()'); b=s.index('setTimeout(applyFinalNav1798',a)
    block=s[a:b]
    top=block.split("let side=",1)[0]
    assert 'Dema' not in top and 'Diagnostika' not in top and 'AI asistent' not in top and 'Data Library' not in top
    assert 'Úvod' in top and 'Výzkum' in top and 'Simulace' in top and 'Správa projektů' in top
