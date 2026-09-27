from pathlib import Path
import json


def html():
    return Path('ui_app.html').read_text(encoding='utf-8')


def test_release_version_1789():
    assert Path('VERSION').read_text(encoding='utf-8').strip() == '18.6.6'
    ed = json.loads(Path('BUILD_EDITION.json').read_text(encoding='utf-8'))
    assert ed['version'] == '18.6.6'
    assert 'Guided UX' in ed['label']


def test_first_launch_is_visual_research_or_simulation_choice():
    s = html()
    assert 'launchGrid1789' in s
    assert 'researchLaunchArt1789' in s and '<svg' in s
    assert 'simulationLaunchArt1789' in s
    assert 'Začít výzkum' in s
    assert 'Začít simulaci' in s
    assert 'onclick="startProductionResearch()"' in s
    assert 'onclick="startSimulationProduct1773()"' in s


def test_brief_supports_multiple_problem_types_and_persists_them():
    s = html()
    assert 'selectedProblemTypes1789' in s
    assert 'Můžete vybrat více možností' in s
    assert 'PROJECT.briefing.problem_types=arr' in s
    from research_project import normalize_project
    p = normalize_project({'briefing': {'problem_types': ['price', 'new_product'], 'problem_type': 'price'}})
    assert p['briefing']['problem_types'] == ['price', 'new_product']


def test_dimension_picker_is_catalog_first_and_custom_is_evidence_request():
    s = html()
    assert 'KATALOG DIMENZÍ' in s
    assert 'Vyberte ze seznamu systému' in s
    assert 'filterDimPicker1789' in s
    assert 'AI doporučí' in s
    assert 'Potřebuji dimenzi, která v systému není' in s
    assert "status:'needs_evidence'" in s
    assert 'Do LIVE modelu vstoupí až po evidenčním napojení' in s


def test_methodology_error_can_be_overridden_but_structural_error_cannot():
    from ui_server import _lint_is_overrideable, _apply_issue_override, _check_issue
    assert _lint_is_overrideable('Cenové body nejsou metodicky ideální pro tuto baterii.') is True
    assert _lint_is_overrideable('Kategorie chutí jsou metodicky heterogenní.') is True
    assert _lint_is_overrideable('Chybí text otázky') is False
    assert _lint_is_overrideable('ID otázek nejsou unikátní') is False

    issue = _check_issue('BLOCKER', 'QUESTION_LINT', 'Cenové body nejsou metodicky ideální.', where='q_price', scope='both')
    issue['overrideable'] = True
    first = _apply_issue_override(issue, {'ui_state': {}})
    assert first['overridden'] is False and first['level'] == 'BLOCKER'
    second = _apply_issue_override(issue, {'ui_state': {'validation_overrides': [first['override_id']]}})
    assert second['overridden'] is True
    assert second['level'] == 'WARNING'
    assert second['scope'] == 'claim'


def test_run_ui_has_override_checkbox_and_single_question_ai_repair():
    s = html()
    assert 'Rozumím varování a chci přesto pokračovat.' in s
    assert 'validation_overrides' in s
    assert 'Opravit otázku pomocí AI' in s
    assert '/api/questionnaire/repair' in s
    assert 'repairIssueAI1789' in s


def test_single_question_ai_repair_changes_only_target(monkeypatch):
    import ai_router
    from ui_server import repair_questionnaire_issue

    def fake_call_structured(**kwargs):
        return {
            'provider': 'claude_code_subscription',
            'model': 'sonnet',
            'data': {
                'text': 'Jak přijatelná je pro vás cena 199 Kč?',
                'typ': 'vyber',
                'kategorie': ['Velmi přijatelná', 'Spíše přijatelná', 'Spíše nepřijatelná', 'Velmi nepřijatelná'],
                'skala': [1, 10],
                'popisky_skaly': ['minimum', 'maximum'],
                'povolit_nevim': True,
                'filtr': None,
                'repair_note': 'Formulace byla zpřesněna bez odstranění ceny.'
            }
        }
    monkeypatch.setattr(ai_router, 'call_structured', fake_call_structured)
    project = {
        'title': 'Test', 'goal': 'Otestovat cenu', 'n': 120,
        'sections': [{'id': 's1', 'type': 'questions', 'title': 'Otázky', 'questions': [
            {'id': 'q_price', 'text': 'Cena 199?', 'typ': 'vyber', 'kategorie': ['Ano', 'Ne']},
            {'id': 'q_other', 'text': 'Jiná otázka?', 'typ': 'vyber', 'kategorie': ['Ano', 'Ne']},
        ]}],
    }
    out = repair_questionnaire_issue({'project': project, 'question_id': 'q_price', 'issue': {'message': 'Metodické varování'}})
    questions = out['project']['sections'][0]['questions']
    q1 = next(q for q in questions if q['id'] == 'q_price')
    q2 = next(q for q in questions if q['id'] == 'q_other')
    assert '199 Kč' in q1['text']
    assert q2['text'] == 'Jiná otázka?'
    assert out['question_id'] == 'q_price'


def test_sticky_next_is_on_research_and_simulation_wizard_steps():
    s = html()
    assert 'wizardNav1789' in s
    for marker in (
        'Další · vytvořit návrh', 'Další · dotazník', 'Další · cílová skupina',
        'Další · dimenze', 'Další · kontrola', 'Další · změna', 'Další · lidé',
        'Další · spuštění',
    ):
        assert marker in s


def test_step6_shows_findings_immediately_and_override_resets_ai_review():
    s = html()
    assert "let visibleBlockers=c?projectIssuesHtml(c):''" in s
    assert 'FINAL_AI_REVIEW=null;save(\'validation_override_1789\'' in s
    assert 'Zobrazuji pouze chyby a varování, která vyžadují rozhodnutí.' in s


def test_persona_ai_suggestions_are_catalog_enforced(monkeypatch):
    import ai_router
    import ui_server

    def fake_call_structured(**kwargs):
        return {
            'provider': 'claude_code_subscription',
            'model': 'sonnet',
            'data': {
                'dimensions': ['media', 'Made up dimension'],
                'reasoning': [
                    {'dimension': 'media', 'why': 'Relevantní.'},
                    {'dimension': 'Made up dimension', 'why': 'Mimo katalog.'},
                ],
                'research_used': False,
            },
        }
    monkeypatch.setattr(ai_router, 'call_structured', fake_call_structured)
    out = ui_server.suggest_persona_dimensions({
        'project': {'title': 'T', 'goal': 'G', 'n': 100, 'sections': []},
        'dimension_labels': {'media': 'Média'},
        'provider': 'claude_code_subscription',
        'model': 'sonnet',
    })
    assert out['dimensions'] == ['media']
    assert out['unsupported_dimensions'] == ['Made up dimension']
    assert any(x['dimension'] == 'Made up dimension' and x['supported'] is False for x in out['reasoning'])
