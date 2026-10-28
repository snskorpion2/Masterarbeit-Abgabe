"""N8 integration checks on generated data, never natural judgments or answers."""
from copy import deepcopy
from hashlib import sha256
import json
from math import isclose

import pytest

from Experiments.fair_v2_oct24.D1 import grok_sensitivity as grok
from Experiments.fair_v2_oct24.D1.analysis import analyze
from Experiments.fair_v2_oct24.D1.contract import load_contract
from Experiments.fair_v2_oct24.D1.native import normalize_native
from Experiments.fair_v2_oct24.D1.synthetic import build_native_fixture


@pytest.fixture(scope='module')
def n8_report():
    contract = load_contract()
    raw = build_native_fixture(sources=contract['sources'], qa_blocks=contract['qa_blocks'])
    raw['question_ids'] = list(contract['question_ids'])
    return analyze(normalize_native(raw), contract)


def quarter_core_bundle():
    cells = ['AS_ORIGINAL', 'AS_ROW', 'AS_G_ORIGINAL', 'AS_G_ROW',
             'V1_ORIGINAL', 'V1_ROW', 'V2_ORIGINAL', 'V2_ROW']
    value = {'synthetic': True, 'sources': [{'source_id': 'SYNTHETIC', 'draws': ['draw_1']}],
             'cells': cells, 'H1': [], 'H1_inventories': [], 'agreement': {'grok': []}}
    for cell in cells:
        arm = 'AS' if cell.startswith('AS') else 'V1'
        value['H1'].extend({'source_id': 'SYNTHETIC', 'draw': 'draw_1', 'cell': cell,
                           'unit_id': arm + '-' + str(i), 'category': 'EE'} for i in range(10))
        value['H1_inventories'].append({'source_id': 'SYNTHETIC', 'draw': 'draw_1',
            'cell': cell, 'occurrence_count': 10, 'completed': True,
            'positive_retained_membership_verified': True})
    for arm in ('AS', 'V1'):
        for i in range(3):
            label = 'supported' if arm == 'V1' or i == 0 else 'not_supported'
            value['agreement']['grok'].append({'unit_id': arm + '-' + str(i),
                'label': label, 'reference_label': label, 'weight': 10/3,
                'in_base_sample': True, 'in_removal_panel': False})
    return value


def test_existing_c4_amendment_quarter_core_is_usable_not_rejected_as_fifteen_percent():
    bundle = quarter_core_bundle()
    before = deepcopy(bundle)
    result = grok.summarize(bundle, core_fraction=.25)
    assert bundle == before
    assert isclose(result['direction']['point_difference'], 2/3)
    assert result['random_core_fraction'] == .25
    assert all(row['original_random_core_roster_complete'] for row in result['draws'])
    assert all(row['original_random_core_design']['EE']['planned_core_count'] == 3
               for row in result['draws'])


@pytest.mark.parametrize('fraction', [None, True, 0, -0.1, 1.1, float('nan')])
def test_c4_core_fraction_is_explicit_and_validated(fraction):
    with pytest.raises(ValueError, match='fraction'):
        grok.summarize(quarter_core_bundle(), core_fraction=fraction)


def test_n8_addition_preserves_exact_preimplementation_primary_result(n8_report):
    # Captured from the unchanged D1 on the same generated fixture before N8 edits.
    value = deepcopy({key: n8_report[key] for key in ('primary', 'holm')})
    # N14 adds a stricter final interpretation, while the G2 numerical test
    # and original criterion remain exactly the pre-N8 pinned result below.
    h2 = value['primary']['H2']
    if h2.get('n14_analysis_required'):
        h2['criterion_met'] = h2.pop('g2_criterion_met')
        for field in ('n14_criterion_met', 'n14_analysis_required', 'n14_decision_rule',
                      'superiority_claim_allowed'):
            h2.pop(field)
    digest = sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    assert digest == '40c7d0a43138bf1d6aac1447d33499aee29cfe969dc63e4871309ec8ab0afc0c'
    assert n8_report['holm']['family_size'] == 3
    assert n8_report['components']['holm']['family_size'] == 6
    assert all('raw_p' not in row for row in n8_report['components']['H4_descriptive'])


def test_n8_contract_binds_published_text_and_existing_c4_quarter_amendment():
    contract = load_contract()
    assert contract['N8_publication']['initial_publication']['commit'] == '3de7fce495c38124096c25418bedd7a8d0cf9d97'
    assert contract['N8_publication']['published_commit'] != contract['N8_publication']['initial_publication']['commit']
    assert contract['N8_publication']['single_path_commit'] is True
    assert contract['N8_publication']['full_team_outcome_blindness'] is False
    assert contract['second_evaluator_core_fraction'] == .25
    assert contract['natural_outcomes_opened'] is False


def test_n8_efficiency_is_integrated_without_dependent_view_doublecount(n8_report):
    rows = n8_report['efficiency']['rows']
    assert len(rows) == 4
    lookup = {row['arm']: row for row in rows}
    assert lookup['V1']['construction_tokens_known'] == lookup['V2']['construction_tokens_known'] == 22000
    assert lookup['V2']['guard_tokens_known'] == 3300
    assert lookup['AS']['construction_tokens_known'] == lookup['AS+G']['construction_tokens_known'] == 11000
    assert all(row['population'] == 'Konfirmation' for row in rows)


def test_h1_type_breakdown_keeps_descriptive_source_confidence_intervals(n8_report):
    rows = [row for row in n8_report['strata'] if row['dimension'] == 'category']
    assert len(rows) == 24 and {row['level'] for row in rows} == {'EE', 'EV', 'VV'}
    assert all('ci95' in row and 'raw_p' not in row for row in rows)
    assert all(row['ci95'] is None or 0 <= row['ci95']['lower'] <= row['ci95']['upper'] <= 1 for row in rows)
