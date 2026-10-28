"""Known-value N8 checks. Every input below is generated in memory."""
from copy import deepcopy

import numpy as np
import pytest

from Experiments.fair_v2_oct24.D1 import components as c
from Experiments.fair_v2_oct24.D1 import inference as inf


FOUR = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.int64)
SHARED = np.tile(FOUR, (2500, 1))


def fixture():
    vectors = {'AS': [0., 1.], 'AS_G': [.5, 1.],
               'V1': [.25, .75], 'V2': [.75, .75]}
    aggregate = {endpoint: {} for endpoint in ('H1', 'H2')}
    qa = {}
    for arm, values in vectors.items():
        for export in ('ORIGINAL', 'ROW'):
            cell = arm + '_' + export
            for endpoint in aggregate:
                aggregate[endpoint][cell] = {'sources': [
                    {'source_id': sid, 'estimate': value, 'lower': value, 'upper': value}
                    for sid, value in zip(('a', 'b'), values)]}
            qa['f1', cell] = dict(zip(('q1', 'q2'), values))
    return aggregate, qa, {'sources': [{'source_id': 'a'}, {'source_id': 'b'}],
                           'qa_blocks': [['q1'], ['q2']]}


def test_secondary_holm_known_values_and_separate_family():
    result = c.holm_secondary(dict(zip(c.COMPONENT_FAMILY, [.001, .008, .02, .04, .2, None])))
    assert result['family_size'] == 6
    assert [result['results'][name]['adjusted_p'] for name in c.COMPONENT_FAMILY] == pytest.approx(
        [.006, .04, .08, .12, .4, 1.])
    assert [result['results'][name]['reject'] for name in c.COMPONENT_FAMILY] == [True, True, False, False, False, False]
    assert result['results']['K6']['raw_p'] is None
    assert result['results']['K6']['slot_p'] == 1
    assert result['results']['K6']['slot_is_missing_placeholder'] is True


@pytest.mark.parametrize('values', [
    {'K1': .01}, dict.fromkeys(c.COMPONENT_FAMILY, True),
    dict.fromkeys(c.COMPONENT_FAMILY, float('nan')),
    dict.fromkeys(c.COMPONENT_FAMILY, -.001),
    dict.fromkeys(c.COMPONENT_FAMILY, 1.001),
])
def test_invalid_or_incomplete_holm_family_fails_closed(values):
    with pytest.raises(ValueError):
        c.holm_secondary(values)


def test_component_definitions_known_differences_and_noninferiority_boundaries():
    data, qa, contract = fixture()
    result = c.analyze_components(data, qa, contract, indices=SHARED, qa_indices=SHARED)
    expected = {'K1': ('H1', .25, 0.), 'K2': ('H2', .25, -.05),
                'K3': ('H1', .25, 0.), 'K4': ('H2', .25, -.05),
                'K5': ('H2', 0., 0.), 'K6': ('H1', 0., -.05)}
    for name, (endpoint, delta, boundary) in expected.items():
        row = result['contrasts'][name]
        assert row['endpoint'] == endpoint
        assert row['point_difference'] == delta
        assert row['null_boundary'] == boundary
    k1 = result['contrasts']['K1']
    assert k1['raw_p'] == pytest.approx(2501 / 10001)
    assert k1['ci95'] == {'lower': 0., 'upper': .5}
    assert result['holm']['family'] == list(c.COMPONENT_FAMILY)


def test_exact_existing_matrices_are_used_without_new_rng_or_primary_mutation(monkeypatch):
    data, qa, contract = fixture()
    before = deepcopy((data, qa, contract))
    matrix_before = SHARED.copy()
    primary_before = inf.paired_source_bootstrap([0., 1.], [.75, .75], indices=SHARED)
    holm_before = inf.holm_primary({'H1': .01, 'H2': .02, 'H4': None})
    source_original, qa_original = inf.paired_source_bootstrap, inf.paired_question_bootstrap
    seen = {'source': 0, 'qa': 0}
    def source_spy(*args, **kwargs):
        assert kwargs['indices'] is SHARED
        seen['source'] += 1
        return source_original(*args, **kwargs)
    def qa_spy(*args, **kwargs):
        assert kwargs['indices'] is SHARED
        seen['qa'] += 1
        return qa_original(*args, **kwargs)
    def forbidden(*args, **kwargs):
        raise AssertionError('A new cluster draw was attempted')
    monkeypatch.setattr(inf, 'cluster_indices', forbidden)
    monkeypatch.setattr(inf, 'paired_source_bootstrap', source_spy)
    monkeypatch.setattr(inf, 'paired_question_bootstrap', qa_spy)
    c.analyze_components(data, qa, contract, indices=SHARED, qa_indices=SHARED)
    assert seen == {'source': 6, 'qa': 6}
    assert (data, qa, contract) == before
    assert np.array_equal(SHARED, matrix_before)
    assert source_original([0., 1.], [.75, .75], indices=SHARED) == primary_before
    assert inf.holm_primary({'H1': .01, 'H2': .02, 'H4': None}) == holm_before


def test_h4_component_rows_are_descriptive_for_both_export_views():
    data, qa, contract = fixture()
    result = c.analyze_components(data, qa, contract, indices=SHARED, qa_indices=SHARED)
    rows = result['H4_descriptive']
    assert len(rows) == 6
    assert {(row['component'], row['export']) for row in rows} == {
        (component, export) for component, _, _ in c.H4_COMPONENTS
        for export in ('ORIGINAL', 'ROW')}
    for row in rows:
        assert row['control'].endswith('_' + row['export'])
        assert row['treatment'].endswith('_' + row['export'])
        assert row['no_hypothesis_test'] is True
        assert not {'raw_p', 'adjusted_p', 'reject', 'testable', 'null_boundary'} & set(row)
    assert rows[0]['point_difference'] == .25
    assert rows[0]['ci95'] == {'lower': 0., 'upper': .5}


def test_missing_source_preserves_six_holm_slots_and_missing_qa_preserves_full_roster():
    data, qa, contract = fixture()
    data['H1']['AS_G_ORIGINAL']['sources'][0]['estimate'] = None
    qa['f1', 'AS_G_ROW']['q1'] = None
    result = c.analyze_components(data, qa, contract, indices=SHARED, qa_indices=SHARED)
    row = result['contrasts']['K1']
    assert row['point_difference'] is None and row['raw_p'] is None
    assert result['holm']['results']['K1']['slot_p'] == 1.
    assert result['holm']['family_size'] == 6
    qa_row = next(row for row in result['H4_descriptive']
                  if row['component'] == 'guard_AS' and row['export'] == 'ROW')
    assert qa_row['point_difference'] is None and qa_row['ci95'] is None
    assert qa_row['question_count'] == 2 and qa_row['completed_pair_count'] == 1


def test_missing_matrices_or_source_order_drift_are_rejected():
    data, qa, contract = fixture()
    with pytest.raises(ValueError, match='existing primary draw matrices'):
        c.analyze_components(data, qa, contract, indices=None, qa_indices=SHARED)
    data['H1']['AS_G_ORIGINAL']['sources'].reverse()
    with pytest.raises(ValueError, match='source order'):
        c.analyze_components(data, qa, contract, indices=SHARED, qa_indices=SHARED)


@pytest.mark.parametrize('support,retention,expected,tradeoff', [
    (True, True, True, False), (True, False, False, True),
    (False, True, False, False), (False, False, False, False),
])
def test_guard_component_qualification_needs_the_predefined_pair(support, retention, expected, tradeoff):
    contrasts = {name: {'criterion_met': False} for name in c.COMPONENT_FAMILY}
    contrasts['K1']['criterion_met'] = support
    contrasts['K2']['criterion_met'] = retention
    verdict = c.component_verdicts(contrasts)['guard_AS']
    assert verdict['criterion_met'] is expected
    assert verdict['tradeoff'] is tradeoff


def test_extension_is_bundled_and_export_and_schema_have_no_test_or_improvement_claim():
    contrasts = {name: {'criterion_met': True} for name in c.COMPONENT_FAMILY}
    verdict = c.component_verdicts(contrasts)
    assert verdict['extraction_extension']['criterion_met'] is True
    assert verdict['extraction_extension']['individual_effects_identified'] is False
    assert verdict['export']['test'] is None
    assert verdict['schema']['component_contrast'] is None
    assert verdict['schema']['improvement_claim_allowed'] is False
