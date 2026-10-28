"""N10 integration over freshly invented 24-source fixtures only."""
from copy import deepcopy
import random

import pytest

from .analysis import analyze
from .contract import load_contract
from .native import normalize_native
from .synthetic import build_native_fixture
from . import n10_sampling as n10


def attach_sample(raw, selected_count=96):
    originals = raw['C2']['occurrence_labels']
    units = sorted(row['unit_id'] for row in originals)
    random.Random(2026102411).shuffle(units)
    assert len(units) % 6 == 0
    groups = [{'group_id': f'group-{i // 6 + 1:04d}', 'unit_ids': units[i:i + 6]}
              for i in range(0, len(units), 6)]
    selected = {uid for g in groups[:selected_count] for uid in g['unit_ids']}
    for row in originals:
        if row['unit_id'] not in selected:
            row.update(measurement_status='not_selected', raw_code=None, label=None)
    lookup = {row['unit_id']: row for row in originals}
    for cell in raw['C2']['cells']:
        for row in cell.get('labels') or ():
            parent = lookup[row['unit_id']]
            row.update({field: parent.get(field) for field in ('measurement_status', 'raw_code', 'label')})
    for item in raw['C7']['key']['items']:
        parent = lookup[item['original_id']]
        item.update(c2_status='rated' if parent['measurement_status'] == 'valid' else 'missing',
                    c2_label=parent['label'] if parent['measurement_status'] == 'valid' else None)
    raw['C4'] = []
    raw['C2']['sampling'] = {
        'protocol': n10.PROTOCOL, 'groups': groups,
        'selected_group_ids': [g['group_id'] for g in groups[:selected_count]],
        'budget_stopped': selected_count < len(groups),
        'global_permutation_before_packing': True, 'order_metadata_verified': True,
        'approximate_design_approved': True,
    }
    return raw


@pytest.fixture(scope='module')
def sampled_data():
    contract = load_contract()
    raw = build_native_fixture(sources=contract['sources'], qa_blocks=contract['qa_blocks'])
    raw['question_ids'] = list(contract['question_ids'])
    return raw, attach_sample(deepcopy(raw)), contract


@pytest.fixture(scope='module')
def sampled_report(sampled_data):
    _, raw, contract = sampled_data
    return analyze(normalize_native(raw), contract)


def test_optional_native_sampling_metadata_preserves_not_selected_separately(sampled_data):
    _, raw, _ = sampled_data
    normalized = normalize_native(raw)
    assert normalized['H1_sampling'] == raw['C2']['sampling']
    unseen = [r for r in normalized['H1'] if r['measurement_status'] == 'not_selected']
    assert unseen and all(r['selection_status'] == 'not_selected' and r['raw_code'] is None for r in unseen)
    original_rows = [r for r in normalized['H1'] if r['cell'] in ('AS_ORIGINAL', 'V1_ORIGINAL')]
    assert len(original_rows) == 816
    assert sum(r['selection_status'] == 'selected' for r in original_rows) == 96 * 6


def test_no_selected_or_observed_labels_can_be_reclassified_to_change_prefix(sampled_data):
    _, raw, _ = sampled_data
    copied = deepcopy(raw)
    row = next(r for c in copied['C2']['cells'] for r in c['labels'] if r['measurement_status'] == 'not_selected')
    row.update(measurement_status='valid', raw_code='supported', label='supported')
    with pytest.raises(ValueError, match='selection status'):
        normalize_native(copied)
    copied = deepcopy(raw)
    copied['C2'].pop('sampling')
    with pytest.raises(ValueError, match='measurement status'):
        normalize_native(copied)


def test_N10_H1_and_three_H1_component_slots_share_one_group_matrix(sampled_report):
    key = sampled_report['N10_H1_sampling']['source_group_matrix_sha256']
    assert sampled_report['primary']['H1']['source_group_matrix_sha256'] == key
    for slot in ('K1', 'K3', 'K6'):
        row = sampled_report['components']['contrasts'][slot]
        assert row['source_group_matrix_sha256'] == key
        assert row['shared_primary_source_group_matrix'] is True
        assert row['approximate_cost_stopped_sampling'] is True
        assert row['exact_inclusion_probabilities_established'] is False
    assert sampled_report['holm']['family_size'] == 3
    assert sampled_report['components']['holm']['family_size'] == 6


def test_H2_H4_estimators_and_raw_tests_are_unchanged(sampled_data, sampled_report):
    raw, _, contract = sampled_data
    original = analyze(normalize_native(raw), contract)
    for endpoint in ('H2', 'H4'):
        for field in ('point_difference', 'raw_p', 'ci95', 'identification_sensitivity95',
                      'null_boundary', 'bootstrap_draws', 'seed'):
            assert sampled_report['primary'][endpoint][field] == original['primary'][endpoint][field]


def test_N10_uses_sample_denominator_and_does_not_count_unselected_as_technical(sampled_report):
    rows = [r for r in sampled_report['cells'] if r['endpoint'] == 'H1']
    for cell in rows:
        assert cell['denominator'] <= 96 * 6
        assert sum(r['technical_missing'] for r in cell['sources']) < 816 - 96 * 6
        assert cell['aggregation'].startswith('pooled sampled')
    assert 'H1_G2_draw_first_aggregation' in sampled_report['sensitivities']
    assert sampled_report['metadata']['aggregation_order'].startswith('N10 H1')
    assert any('Informative stopping' in line for line in sampled_report['limits'])
    assert any('näherungsweise' in line for line in sampled_report['overall_judgment']['qualifications'])
    assert any('Fehlende C3-Urteile' in line for line in sampled_report['overall_judgment']['qualifications'])


def test_sampled_support_rate_is_not_a_census_efficiency_denominator(sampled_report):
    rows = sampled_report['efficiency']['rows']
    assert rows
    for row in rows:
        assert row['support_complete'] is False
        assert row['tokens_per_supported'] is None and row['cost_per_supported'] is None
        assert row['supported_per_1000_construction_tokens'] is None
        assert 'N10_supported_census_count_not_identified' in row['reasons']


def test_C7_only_valid_C2_pairs_and_missing_C4_is_not_confirmation(sampled_report):
    human = sampled_report['agreement']['human']
    assert human['N_pair'] < human['N_selected'] == 150
    assert human['excluded_missing_either_count'] > 0
    assert sampled_report['agreement']['grok']['N_pair'] == 0
    assert 'C4' in sampled_report['overall_judgment']['missing_counterchecks']


def test_all_groups_selected_delegates_to_unmodified_G2_path(sampled_data):
    raw, _, contract = sampled_data
    full = attach_sample(deepcopy(raw), selected_count=136)
    normalized = normalize_native(full)
    assert n10.active(normalized) is False
    report = analyze(normalized, contract)
    assert report['N10_H1_sampling'] is None
    assert report['metadata']['aggregation_order'] == 'planned draws, then equal sources'
    assert 'N10_budget_prefix' not in report['primary']['H1']


def test_publication_is_required_before_sample_analysis_and_bound_to_final_text(sampled_data):
    _, raw, contract = sampled_data
    assert contract['N10_publication']['published_commit'] == '3d180e5bd92e1ecd74a185fc362e8860fd5091e4'
    assert contract['N10_publication']['inclusion_probabilities_exactly_equal_established'] is False
    altered = deepcopy(contract)
    altered.pop('N10_publication')
    with pytest.raises(ValueError, match='published before'):
        analyze(normalize_native(raw), altered)
