"""N10 arithmetic, pairing and missingness on invented labels only."""
from copy import deepcopy

import numpy as np
import pytest

from . import inference as inf
from . import n10_sampling as n10


CELLS = ['AS_ORIGINAL', 'AS_ROW', 'AS_G_ORIGINAL', 'AS_G_ROW',
         'V1_ORIGINAL', 'V1_ROW', 'V2_ORIGINAL', 'V2_ROW']
FOUR = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.int64)


def sample_bundle(*, third_source=False):
    # Every original group has exactly six rows, deliberately mixing sources.
    shape = [
        [('a', 'AS', 1, 1), ('a', 'AS', 1, 0), ('a', 'V1', 1, 1),
         ('a', 'V1', 1, 1), ('b', 'AS', 1, 1), ('b', 'V1', 1, 0)],
        [('a', 'AS', 2, 1), ('a', 'V1', 2, 1), ('b', 'AS', 2, 0),
         ('b', 'AS', 2, 1), ('b', 'V1', 2, 1), ('b', 'V1', 2, 1)],
    ]
    shape.extend(deepcopy(shape))
    if third_source:
        shape[2] = [('c', arm, draw, label) for _, arm, draw, label in shape[2]]
        shape[3] = [('c', arm, draw, label) for _, arm, draw, label in shape[3]]
    sources = [{'source_id': sid, 'draws': ['draw_1', 'draw_2'],
                'cohort': 'SYNTHETIC', 'family': 'invented'}
               for sid in (('a', 'b', 'c') if third_source else ('a', 'b'))]
    original, groups = [], []
    for gi, group in enumerate(shape, 1):
        units = []
        for ri, (sid, arm, draw, label) in enumerate(group, 1):
            uid = f'g{gi}-r{ri}'
            units.append(uid)
            original.append({'source_id': sid, 'draw': f'draw_{draw}', 'unit_id': uid,
                             'arm': arm, 'category': 'EE' if ri % 2 else 'VV',
                             'raw_code': 'supported' if label else 'not_supported',
                             'measurement_status': 'valid'})
        groups.append({'group_id': f'g{gi}', 'unit_ids': units})
    rows, inventories = [], []
    for source in sources:
        for draw in source['draws']:
            for cell in CELLS:
                arm = cell.rsplit('_', 1)[0]
                base = 'AS' if arm.startswith('AS') else 'V1'
                selected = [r for r in original if r['source_id'] == source['source_id']
                            and r['draw'] == draw and r['arm'] == base
                            and (arm not in ('AS_G', 'V2') or r['raw_code'] == 'supported')]
                rows.extend({**r, 'cell': cell} for r in selected)
                inventories.append({'source_id': source['source_id'], 'draw': draw, 'cell': cell,
                                    'completed': True, 'occurrence_count': len(selected),
                                    'positive_retained_membership_verified': True})
    return {'synthetic': True, 'sources': sources, 'cells': CELLS,
            'H1': rows, 'H1_inventories': inventories,
            'H1_sampling': {'protocol': n10.PROTOCOL, 'budget_stopped': True,
                            'groups': groups, 'selected_group_ids': ['g1', 'g2'],
                            'global_permutation_before_packing': True,
                            'order_metadata_verified': True,
                            'approximate_design_approved': True}}


def exact_matrix():
    inner = np.array([[0, 0], [1, 1], [0, 1], [1, 0]], dtype=np.uint8)
    other = np.array([[0, 0], [1, 1], [0, 1], [1, 0]], dtype=np.uint8)
    return n10.SharedIndices(('a', 'b'), (('g1', 'g2'), ('g1', 'g2')),
                             FOUR.copy(), (inner, other), 4, inf.BOOTSTRAP_SEED)


def test_source_ratios_pool_planned_draws_before_equal_source_weight():
    value = n10.estimate(sample_bundle(), CELLS, draws=4)
    assert value.aggregates['AS_ORIGINAL']['estimate'] == pytest.approx(2 / 3)
    assert value.aggregates['V1_ORIGINAL']['estimate'] == pytest.approx(5 / 6)
    # G2 draw-first sensitivity would yield .75 versus .75, not these ratios.
    rows = value.by_draw['AS_ORIGINAL']
    assert np.mean([r['estimate'] for r in rows]) == pytest.approx(.75)
    assert value.contrast('AS_ORIGINAL', 'V1_ORIGINAL')['point_difference'] == pytest.approx(1 / 6)


def test_unselected_rows_are_neither_zero_scores_nor_missing_judgments():
    bundle = sample_bundle()
    for row in bundle['H1']:
        if row['unit_id'].startswith(('g3-', 'g4-')):
            row.update(raw_code=None, measurement_status='technical_missing')
    value = n10.estimate(bundle, CELLS, draws=4)
    source = value.aggregates['AS_ORIGINAL']['sources'][0]
    assert source['denominator'] == 3 and source['not_selected_occurrences'] == 3
    assert source['technical_missing'] == 0
    assert value.aggregates['AS_ORIGINAL']['missing_rate'] == 0
    assert value.sampling_info['not_selected_is_missing'] is False


def test_selected_administrative_or_unknown_groups_remain_in_the_denominator():
    bundle = sample_bundle()
    for row in bundle['H1']:
        if row['unit_id'].startswith('g1-'):
            row.update(raw_code=None, measurement_status='technical_missing')
    value = n10.estimate(bundle, CELLS, draws=4)
    rows = value.aggregates['AS_ORIGINAL']['sources']
    assert [r['denominator'] for r in rows] == [3, 3]
    assert [r['technical_missing'] for r in rows] == [2, 1]
    assert value.aggregates['AS_ORIGINAL']['estimate'] == pytest.approx(1 / 3)
    assert value.aggregates['AS_ORIGINAL']['upper'] == pytest.approx(5 / 6)


def test_two_stage_bootstrap_has_known_replicates_and_independent_repeated_source_draws():
    value = n10.estimate(sample_bundle(), CELLS, matrix=exact_matrix(), draws=4)
    result = value.contrast('AS_ORIGINAL', 'V1_ORIGINAL', return_samples=True)
    assert result['bootstrap_differences'] == pytest.approx([.25, -1 / 3, 5 / 12, 0.])
    expected = np.quantile([.25, -1 / 3, 5 / 12, 0.], [.025, .975], method='linear')
    assert list(result['ci95'].values()) == pytest.approx(expected)
    # The first replicate draws source a twice but resamples its groups differently.
    assert result['bootstrap_differences'][0] == pytest.approx(.25)


def test_reversed_contrast_uses_identical_matrix_and_negates_every_replicate():
    value = n10.estimate(sample_bundle(), CELLS, matrix=exact_matrix(), draws=4)
    forward = value.contrast('AS_ORIGINAL', 'V1_ORIGINAL', return_samples=True)
    reverse = value.contrast('V1_ORIGINAL', 'AS_ORIGINAL', return_samples=True)
    assert reverse['bootstrap_differences'] == pytest.approx(-np.array(forward['bootstrap_differences']))
    assert forward['source_group_matrix_sha256'] == reverse['source_group_matrix_sha256']


def test_filtered_cells_inherit_exact_parent_sample_membership_and_judgments():
    bundle = sample_bundle()
    value = n10.estimate(bundle, CELLS, draws=4)
    assert value.aggregates['AS_G_ORIGINAL']['estimate'] == 1
    assert value.aggregates['V2_ROW']['estimate'] == 1
    left, right = deepcopy(value.aggregates['AS_ROW']), deepcopy(value.aggregates['AS_ORIGINAL'])
    for aggregate in (left, right):
        for row in aggregate['sources']:
            row.pop('cell')
    assert left == right
    # Different cell labels are the only allowed difference in the paired views.
    row = next(r for r in bundle['H1'] if r['cell'] == 'V2_ROW')
    row['raw_code'] = 'not_supported'
    with pytest.raises(ValueError, match='inherit exactly'):
        n10.estimate(bundle, CELLS, draws=4)


def test_empty_filtered_bootstrap_cell_is_not_resampled_away_or_filled_with_zero():
    value = n10.estimate(sample_bundle(), CELLS, matrix=exact_matrix(), draws=4)
    result = value.contrast('AS_ORIGINAL', 'V2_ROW', return_samples=True)
    assert result['point_difference'] == pytest.approx(1 / 3)
    assert None in result['bootstrap_differences']
    assert result['raw_p'] is None and result['ci95'] is None
    assert result['undefined_reason'] == 'invalid_bootstrap_outputs'
    assert result['identification_sensitivity95'] is not None


def test_unsampled_source_stays_in_source_mean_with_zero_one_sensitivity_bounds():
    bundle = sample_bundle(third_source=True)
    value = n10.estimate(bundle, CELLS, draws=4)
    report = value.aggregates['AS_ORIGINAL']
    assert report['independent_source_count'] == 3
    assert report['estimate'] is None
    assert report['lower'] == pytest.approx(4 / 9)
    assert report['upper'] == pytest.approx(7 / 9)
    assert report['sources'][2]['estimate'] is None
    assert (report['sources'][2]['lower'], report['sources'][2]['upper']) == (0., 1.)
    assert value.contrast('AS_ORIGINAL', 'V1_ORIGINAL')['raw_p'] is None


def test_original_group_source_intersections_are_not_source_local_sixpacks():
    value = n10.estimate(sample_bundle(), CELLS, draws=4)
    assert value.matrix.groups_by_source == (('g1', 'g2'), ('g1', 'g2'))
    assert value.aggregates['AS_ORIGINAL']['sources'][0]['denominator'] == 3
    assert value.aggregates['AS_ORIGINAL']['sources'][1]['denominator'] == 3


def test_selection_distributions_count_parent_occurrences_only_including_missing():
    bundle = sample_bundle()
    for row in bundle['H1']:
        if row['unit_id'].startswith('g1-'):
            row.update(raw_code=None, measurement_status='technical_missing')
    report = n10.estimate(bundle, CELLS, draws=4).sampling_info
    for dimension in ('source', 'arm', 'category'):
        rows = report['selection_distributions'][dimension]
        assert sum(r['population_count'] for r in rows) == 24
        assert sum(r['selected_count'] for r in rows) == 12
    assert report['population_groups'] == 4 and report['selected_groups'] == 2
    assert report['sampling_fraction'] == .5
    assert report['sampling_fraction_is_proven_inclusion_probability'] is False
    assert report['informative_cost_stopping_possible'] is True
    assert report['selection_distributions_establish_quality_or_exact_inclusion'] is False


def test_seeded_matrix_is_shared_readonly_and_preserves_original_outer_matrix():
    value = n10.estimate(sample_bundle(), CELLS, draws=4)
    again = n10.estimate(sample_bundle(), CELLS, draws=4)
    assert value.matrix.digest == again.matrix.digest
    assert np.array_equal(value.matrix.sources, inf.cluster_indices(2, draws=4))
    assert value.matrix.sources.flags.writeable is False
    assert all(m.flags.writeable is False for m in value.matrix.groups)
    with pytest.raises(ValueError):
        value.matrix.groups[0][0, 0] = 1
    assert value.contrast('AS_ORIGINAL', 'V1_ORIGINAL')['source_group_matrix_sha256'] == value.matrix.digest


@pytest.mark.parametrize('change,reason', [
    (lambda s: s.update(selected_group_ids=['g1', 'g3']), 'unchanged original prefix'),
    (lambda s: s.update(order_metadata_verified=False), 'externally verified order'),
    (lambda s: s.update(approximate_design_approved=False), 'explicitly approved'),
    (lambda s: s['groups'][0].update(unit_ids=['invented']), 'six-occurrence'),
    (lambda s: s['groups'][0]['unit_ids'].__setitem__(0, 'g1-r2'), 'partition distinct'),
    (lambda s: s['groups'][0]['unit_ids'].__setitem__(0, 'foreign'), 'complete parent inventories'),
])
def test_sampling_contract_refuses_drift_and_unadmitted_design(change, reason):
    bundle = sample_bundle()
    change(bundle['H1_sampling'])
    with pytest.raises(ValueError, match=reason):
        n10.estimate(bundle, CELLS, draws=4)


def test_no_N10_without_budget_stop_or_when_census_is_complete():
    bundle = sample_bundle()
    assert n10.active(bundle) is True
    bundle['H1_sampling']['selected_group_ids'] = ['g1', 'g2', 'g3', 'g4']
    assert n10.active(bundle) is False
    bundle.pop('H1_sampling')
    assert n10.active(bundle) is False


def test_missing_C1_retained_proof_or_partial_original_inventory_is_rejected():
    bundle = sample_bundle()
    next(r for r in bundle['H1_inventories'] if r['cell'] == 'V2_ROW')['positive_retained_membership_verified'] = False
    with pytest.raises(ValueError, match='C1 retained proof'):
        n10.estimate(bundle, CELLS, draws=4)
    bundle = sample_bundle()
    bundle['H1'].pop()
    with pytest.raises(ValueError, match='full inventory membership'):
        n10.estimate(bundle, CELLS, draws=4)


def test_input_is_unchanged_and_type_diagnostics_reuse_exact_common_plan():
    bundle = sample_bundle()
    before = deepcopy(bundle)
    all_types = n10.estimate(bundle, CELLS, draws=4)
    typed = n10.estimate(bundle, CELLS, matrix=all_types.matrix, category='EE', draws=4)
    assert bundle == before
    assert typed.matrix is all_types.matrix
    assert typed.matrix.digest == all_types.matrix.digest


def test_countercheck_roster_is_fixed_but_stale_C2_key_labels_are_not_counted():
    bundle = sample_bundle()
    selected = next(r for r in bundle['H1'] if r['cell'] == 'AS_ORIGINAL' and r['unit_id'] == 'g1-r1')
    selected.update(measurement_status='technical_missing', raw_code=None)
    rows = [{'unit_id': uid, 'reference_label': 'supported', 'label': 'not_supported', 'weight': 3.}
            for uid in ('g1-r1', 'g2-r1', 'g3-r1')]
    before = deepcopy(rows)
    mapped = n10.current_reference_rows(bundle, rows)
    assert rows == before
    assert [r['unit_id'] for r in mapped] == ['g1-r1', 'g2-r1', 'g3-r1']
    assert [r['reference_label'] for r in mapped] == [None, 'supported', None]
    assert [r['reference_status'] for r in mapped] == ['technical_missing', 'valid', 'not_selected']
    assert all(r['weight'] == 3 and r['label'] == 'not_supported' for r in mapped)
