"""N14 known-value checks using invented counts and synthetic labels only."""
from copy import deepcopy

import numpy as np
import pytest

from . import analysis as a, components as comp, inference as inf
from . import n14_missingness as n14
from .contract import load_contract
from .native import normalize_native
from .synthetic import build_native_fixture


def aggregates(vectors, *, sources=None):
    """vectors[cell][source] is a list of (success,failure,unclear,technical)."""
    count = len(next(iter(vectors.values())))
    sources = sources or [{'source_id': f's{i}', 'draws': ['d1'], 'cohort': 'synthetic',
                          'family': 'synthetic'} for i in range(count)]
    result = {}
    for cell, values in vectors.items():
        rows = []
        for source, draws in zip(sources, values):
            for draw, values in zip(source['draws'], draws):
                rows.append(a.ratio_record(*values, sum(values), source_id=source['source_id'],
                                           draw=draw, cell=cell))
        result[cell] = a._source_equal(rows, sources)
    return result, sources


def source_fixture():
    # s0: negative but valid in both; s1: valid only in control;
    # s2: unclear but valid in both; s3: valid only in treatment.
    left = [[(0, 1, 0, 0)], [(1, 0, 0, 0)], [(0, 0, 1, 0)], [(0, 0, 0, 1)]]
    right = [[(1, 0, 0, 0)], [(0, 0, 0, 1)], [(0, 0, 1, 0)], [(0, 1, 0, 0)]]
    return aggregates({'c': left, 't': right})


def test_source_selection_is_both_arm_technical_validity_not_retention_or_clarity():
    values, sources = source_fixture()
    result = n14.SourceRestriction(values, sources, inf.cluster_indices(4)).contrast('c', 't')
    assert result['included_source_ids'] == ['s0', 's2']
    assert result['excluded_source_ids'] == ['s1', 's3']
    assert result['point_difference'] == .5
    assert result['source_selection_depends_on_semantic_success'] is False
    assert result['missingness']['full']['control']['pooled_missing_rate'] == .25
    assert result['missingness']['full']['control']['pooled_G2_zero_or_unclear_rate'] == .5
    assert result['missingness']['eligible']['control']['pooled_missing_rate'] == 0
    assert result['missingness']['eligible']['control']['pooled_G2_zero_or_unclear_rate'] == .5


def test_normalized_h2_status_not_success_determines_technical_counts():
    cells = ['c', 't']
    sources = [{'source_id': 'a', 'draws': ['d1'], 'cohort': 'test', 'family': 'test'},
               {'source_id': 'b', 'draws': ['d1'], 'cohort': 'test', 'family': 'test'}]
    data = {'sources': sources, 'H2_roster': [{'source_id': sid, 'obligation_id': 'r'} for sid in ('a', 'b')],
            'H2': [{'source_id': sid, 'draw': 'd1', 'cell': cell, 'obligation_id': 'r',
                    'status': status, 'raw_code': code}
                   for sid, cell, status, code in [('a', 'c', 'valid', 'not_retained'),
                       ('a', 't', 'valid', 'undetermined'), ('b', 'c', 'valid', 'partially_retained'),
                       ('b', 't', 'timeout', None)]]}
    rows = a._h2_draws(data, cells)
    values = {cell: a._source_equal(rows[cell], sources) for cell in cells}
    result = n14.SourceRestriction(values, sources, inf.cluster_indices(2)).contrast('c', 't')
    assert result['included_source_ids'] == ['a']
    assert result['excluded_source_ids'] == ['b']
    assert result['eligible_source_count'] == 1 and result['raw_p'] is None
    assert result['undefined_reason'] == 'fewer_than_two_independent_clusters'


def test_restriction_keeps_all_planned_draws_and_fixed_reference_denominators():
    sources = [{'source_id': sid, 'draws': ['d1', 'd2'], 'cohort': 'test', 'family': 'test'}
               for sid in ('s0', 's1', 's2')]
    values, sources = aggregates({
        'c': [[(2, 0, 0, 2), (0, 0, 0, 4)], [(1, 3, 0, 0), (0, 0, 0, 4)],
              [(0, 0, 0, 4), (0, 0, 0, 4)]],
        't': [[(4, 0, 0, 0), (0, 0, 0, 4)], [(3, 1, 0, 0), (0, 0, 0, 4)],
              [(0, 0, 0, 4), (0, 0, 0, 4)]]}, sources=sources)
    before = deepcopy(values)
    result = n14.SourceRestriction(values, sources, inf.cluster_indices(3)).contrast('c', 't')
    assert result['control_mean'] == .1875  # mean(.25,.125), all planned draws retained
    assert result['treatment_mean'] == .4375
    assert result['point_difference'] == .25
    assert result['missingness']['eligible']['control']['denominator'] == 16
    assert values == before


def test_all_missing_zero_dilution_can_pass_G2_but_must_fail_final_N14():
    left = [[(100, 0, 0, 0)], [(100, 0, 0, 0)]] + [[(0, 0, 0, 100)] for _ in range(22)]
    right = [[(90, 10, 0, 0)], [(92, 8, 0, 0)]] + [[(0, 0, 0, 100)] for _ in range(22)]
    values, sources = aggregates({'c': left, 't': right})
    matrix = inf.cluster_indices(24)
    original = inf.paired_source_bootstrap([r['estimate'] for r in values['c']['sources']],
        [r['estimate'] for r in values['t']['sources']], indices=matrix, null_boundary=-.05)
    h = inf.holm_primary({'H1': .0001, 'H2': original['raw_p'], 'H4': .0001})
    original.update(adjusted_p=h['results']['H2']['adjusted_p'], reject=h['results']['H2']['reject'],
                    criterion_met=h['results']['H2']['reject'])
    assert original['criterion_met'] is True
    old = deepcopy(original)
    extra = n14.SourceRestriction(values, sources, matrix).contrast('c', 't')
    hh = inf.holm_primary({'H1': .0001, 'H2': extra['raw_p'], 'H4': .0001})
    n14.apply_decision(original, extra, hh['results']['H2'])
    assert extra['point_difference'] == pytest.approx(-.09)
    assert extra['criterion_met'] is False
    assert original['g2_criterion_met'] is True and original['criterion_met'] is False
    for field in ('point_difference', 'raw_p', 'adjusted_p', 'reject', 'ci95'):
        assert original[field] == old[field]
    from .judgment import overall_judgment
    primary = {'H1': {'point_difference': .3, 'criterion_met': True, 'reject': True},
               'H2': old,
               'H4': {'point_difference': .2, 'criterion_met': True, 'reject': True,
                      'ci95': {'lower': .1, 'upper': .3}}}
    assert overall_judgment(primary)['stage'] == 'A'
    primary['H2'] = original
    assert overall_judgment(primary)['stage'] == 'D'


def test_no_eligible_source_is_not_a_zero_difference_or_success():
    values, sources = aggregates({'c': [[(0, 0, 0, 1)], [(0, 0, 0, 1)]],
                                 't': [[(0, 0, 0, 1)], [(0, 0, 0, 1)]]})
    restriction = n14.SourceRestriction(values, sources, inf.cluster_indices(2))
    extra = restriction.contrast('c', 't')
    assert extra['eligible_source_count'] == 0
    assert extra['point_difference'] is extra['raw_p'] is extra['ci95'] is None
    assert extra['undefined_reason'] == 'no_sources_with_valid_judgments_in_both_arms'
    assert restriction.coverage()['sources_without_valid_judgments_in_any_cell'] == ['s0', 's1']
    h = inf.holm_primary({'H1': .0001, 'H2': None, 'H4': .0001})
    assert h['results']['H2']['slot_p'] == 1
    original = {'criterion_met': True}
    n14.apply_decision(original, extra, h['results']['H2'])
    assert original['criterion_met'] is False


def test_same_subset_reuses_fixed_size_seeded_matrix_and_full_subset_reuses_original(monkeypatch):
    values, sources = source_fixture()
    matrix = inf.cluster_indices(4)
    restriction = n14.SourceRestriction(values, sources, matrix)
    extra = restriction.contrast('c', 't')
    assert restriction.cache[('s0', 's2')].shape == (10000, 2)
    assert np.array_equal(restriction.cache[('s0', 's2')], inf.cluster_indices(2))
    def forbidden(*args, **kwargs):
        raise AssertionError('Repeated subset or full roster must reuse its matrix')
    monkeypatch.setattr(inf, 'cluster_indices', forbidden)
    assert restriction.contrast('t', 'c')['source_matrix_sha256'] == extra['source_matrix_sha256']
    complete, ss = aggregates({'c': [[(1, 0, 0, 0)] for _ in range(4)],
                              't': [[(0, 1, 0, 0)] for _ in range(4)]})
    all_valid = n14.SourceRestriction(complete, ss, matrix)
    all_valid.contrast('c', 't')
    assert all_valid.cache[tuple(all_valid.source_ids)] is matrix


@pytest.mark.parametrize('g2,extra,final', [(True, True, True), (True, False, False),
                                         (False, True, False), (False, False, False)])
def test_final_criterion_requires_both_Holm_passes(g2, extra, final):
    original = {'criterion_met': g2, 'reject': g2, 'raw_p': .001 if g2 else .8}
    additional = {'point_difference': .1, 'null_boundary': -.05}
    n14.apply_decision(original, additional, {'adjusted_p': .001 if extra else .8, 'reject': extra})
    assert original['criterion_met'] is final
    assert original['reject'] is g2


@pytest.fixture(scope='module')
def integrated():
    contract = load_contract()
    contract['amendments'] = [r for r in contract['amendments'] if r['identifier'] != 'N14']
    native = build_native_fixture(sources=contract['sources'], qa_blocks=contract['qa_blocks'])
    native['question_ids'] = list(contract['question_ids'])
    bundle = normalize_native(native)
    old = a.analyze(bundle, contract)
    new_contract = deepcopy(contract)
    new_contract['amendments'].append({'identifier': 'N14'})
    new = a.analyze(bundle, new_contract)
    return old, new


def test_primary_and_component_numerical_G2_results_unchanged(integrated):
    old, new = integrated
    assert old['holm'] == new['holm']
    assert old['components']['holm'] == new['components']['holm']
    for key in ('H1', 'H2', 'H4'):
        for field in ('point_difference', 'raw_p', 'adjusted_p', 'reject', 'ci95', 'identification_sensitivity95'):
            assert old['primary'][key][field] == new['primary'][key][field]
    for key in comp.COMPONENT_FAMILY:
        for field in ('point_difference', 'raw_p', 'adjusted_p', 'reject', 'ci95'):
            assert old['components']['contrasts'][key][field] == new['components']['contrasts'][key][field]
    assert old['primary']['H1'] == new['primary']['H1']
    assert old['primary']['H4'] == new['primary']['H4']
    for key in ('K1', 'K3', 'K6'):
        assert old['components']['contrasts'][key] == new['components']['contrasts'][key]


def test_additional_Holm_families_keep_original_slot_count_and_unaffected_raw_p(integrated):
    _, new = integrated
    extra = new['N14_H2_missingness']
    assert extra['primary_holm']['family_size'] == 3
    assert extra['component_holm']['family_size'] == 6
    for key in ('H1', 'H4'):
        assert extra['primary_holm']['results'][key]['raw_p'] == new['primary'][key]['raw_p']
    for key in ('K1', 'K3', 'K6'):
        assert extra['component_holm']['results'][key]['raw_p'] == new['components']['contrasts'][key]['raw_p']
    assert set(extra['components']) == {'K2', 'K4', 'K5'}
    assert new['primary']['H2']['superiority_claim_allowed'] is False
    assert extra['H2_superiority_claim_allowed'] is False


def test_source_order_drift_fails_closed():
    values, sources = source_fixture()
    values['t']['sources'].reverse()
    with pytest.raises(ValueError, match='source order'):
        n14.SourceRestriction(values, sources, inf.cluster_indices(4))


def test_component_source_intersections_are_contrast_specific_and_holm_keeps_six_slots():
    # The same four source positions deliberately qualify differently by arm.
    valid = {'AS': {0, 1, 2}, 'AS_G': {0, 1}, 'V1': {1, 2, 3}, 'V2': {2, 3}}
    vectors = {arm + '_' + export: [[(i + 1, 4 - i, 0, 0)] if i in indices
                else [(0, 0, 0, 5)] for i in range(4)]
               for arm, indices in valid.items() for export in ('ORIGINAL', 'ROW')}
    h2, sources = aggregates(vectors)
    matrix = inf.cluster_indices(4)
    qa = {('f1', cell): {'q1': .2, 'q2': .8} for cell in vectors}
    contract = {'sources': sources, 'qa_blocks': [['q1'], ['q2']]}
    restriction = n14.SourceRestriction(h2, sources, matrix)
    result = comp.analyze_components({'H1': deepcopy(h2), 'H2': h2}, qa, contract,
        indices=matrix, qa_indices=inf.cluster_indices(2), h2_restriction=restriction)
    extra = result['N14_H2_missingness']
    assert extra['contrasts']['K2']['included_source_ids'] == ['s0', 's1']
    assert extra['contrasts']['K4']['included_source_ids'] == ['s2', 's3']
    assert extra['contrasts']['K5']['included_source_ids'] == ['s1', 's2']
    assert extra['holm']['family_size'] == 6
    for key in ('K2', 'K4', 'K5'):
        value = result['contrasts'][key]
        assert value['criterion_met'] == (value['g2_criterion_met'] and value['n14_criterion_met'])
    for key in ('K1', 'K3', 'K6'):
        assert extra['holm']['results'][key]['raw_p'] == result['contrasts'][key]['raw_p']


def test_N14_gate_reaches_final_overall_and_component_judgments(integrated):
    _, result = integrated
    assert result['overall_judgment']['N14_H2_missingness_required'] is True
    assert any('N14' in row for row in result['overall_judgment']['qualifications'])
    for component, support, retention in (('guard_AS', 'K1', 'K2'), ('guard_V1', 'K3', 'K4')):
        c = result['components']['contrasts']
        assert result['components']['verdicts'][component]['criterion_met'] == (
            c[support]['criterion_met'] and c[retention]['criterion_met'])


@pytest.mark.parametrize('contract', [{}, {'amendments': []},
                                    {'amendments': [{'identifier': 'N14'}]}])
def test_direct_natural_API_cannot_bypass_N14_with_a_legacy_or_missing_contract(contract, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No estimator may run before the N14 publication gate')
    monkeypatch.setattr(inf, 'cluster_indices', forbidden)
    monkeypatch.setattr(a, '_h2_draws', forbidden)
    with pytest.raises(ValueError, match='N14'):
        # This deliberately incomplete invented object is not a real manifest.
        a.analyze({'synthetic': False}, contract)


@pytest.mark.parametrize('field,value', [('publication_commit', '0' * 40),
                                       ('sha256', '0' * 64), ('remote_bytes_identical', False),
                                       ('protocol', 'draft'), ('path', 'invented.md')])
def test_direct_natural_API_rejects_fabricated_publication_metadata(field, value, monkeypatch):
    from .contract import load_n14_publication
    receipt = load_n14_publication()  # published protocol metadata, no outcomes
    receipt[field] = value
    def forbidden(*args, **kwargs):
        raise AssertionError('No estimator may run before the N14 publication gate')
    monkeypatch.setattr(inf, 'cluster_indices', forbidden)
    monkeypatch.setattr(a, '_h2_draws', forbidden)
    with pytest.raises(ValueError, match='N14'):
        a.analyze({'synthetic': False}, {'amendments': [{'identifier': 'N14'}],
                                        'N14_publication': receipt})
