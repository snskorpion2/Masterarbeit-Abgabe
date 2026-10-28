"""Synthetic, known-value CPU tests for the frozen G2 inference algorithms."""
import json
from fractions import Fraction

import numpy as np
import pytest

from Experiments.fair_v2_oct24.D1 import inference as s


FOUR_DRAWS = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.int64)


def test_frozen_rng_count_seed_and_shared_indices_are_reproducible():
    actual = s.cluster_indices(24)
    expected = np.random.Generator(np.random.PCG64(2026102407)).integers(
        0, 24, size=(10000, 24), dtype=np.int64)
    assert np.array_equal(actual, expected)
    assert np.array_equal(actual, s.cluster_indices(24))


def test_source_bootstrap_known_four_replicates_null_centering_and_linear_ci():
    report = s.paired_source_bootstrap([0, 1], [.5, 1], draws=4,
                                     indices=FOUR_DRAWS, return_samples=True)
    assert report['point_difference'] == .25
    assert report['bootstrap_differences'] == [.5, .25, .25, 0.]
    assert report['raw_p'] == float(Fraction(2, 5))
    assert report['ci95']['lower'] == pytest.approx(.01875)
    assert report['ci95']['upper'] == pytest.approx(.48125)
    h2 = s.paired_source_bootstrap([0, 1], [.5, 1], draws=4,
                                 indices=FOUR_DRAWS, null_boundary=-.05)
    assert h2['raw_p'] == .2


def test_identification_sensitivity_lower_bound_is_not_primary_statistic():
    result = s.paired_source_bootstrap([0, 1], [.5, 1],
        control_lower=[0, 1], control_upper=[.5, 1],
        treatment_lower=[.5, 1], treatment_upper=[1, 1],
        draws=4, indices=FOUR_DRAWS)
    assert result['point_difference'] == .25
    assert result['identification_sensitivity95']['lower'] == 0
    assert result['identification_sensitivity95']['upper'] == pytest.approx(.9625)
    assert result['raw_p'] == .4


def test_source_undefined_planned_pair_is_not_silently_dropped_or_zero_filled():
    report = s.paired_source_bootstrap([None, .5], [.75, .8])
    assert report['point_difference'] is None
    assert report['raw_p'] is None and not report['testable']
    assert report['undefined_reason'] == 'undefined_planned_source_pair'
    assert report['cluster_count'] == 2 and report['defined_source_pairs'] == 1
    assert report['control_mean'] is None


def test_degenerate_h2_does_not_pass_even_with_favorable_margin():
    result = s.paired_source_bootstrap([.5, .5], [.5, .5], null_boundary=-.05)
    assert result['point_difference'] == 0
    assert result['ci95'] == {'lower': 0., 'upper': 0.}
    assert result['raw_p'] is None and result['undefined_reason'] == 'zero_bootstrap_statistic_variation'


def test_one_source_keeps_point_and_descriptive_interval_without_test():
    result = s.paired_source_bootstrap([0], [.5])
    assert result['point_difference'] == .5
    assert result['ci95'] == {'lower': .5, 'upper': .5}
    assert result['raw_p'] is None and result['undefined_reason'] == 'fewer_than_two_independent_clusters'


def test_invalid_bootstrap_outputs_and_index_drift_are_refused():
    result = s.bootstrap_from_replicates(.1, np.full(4, np.nan), cluster_count=2, draws=4)
    assert result['raw_p'] is None and result['undefined_reason'] == 'invalid_bootstrap_outputs'
    with pytest.raises(ValueError, match='index matrix'):
        s.paired_source_bootstrap([0, 1], [1, 1], draws=4, indices=np.zeros((4, 3), dtype=int))


def test_same_source_multiplicities_preserve_paired_antisymmetry():
    indices = s.cluster_indices(3)
    forward = s.paired_source_bootstrap([.1, .2, .3], [.5, .4, .8], indices=indices, return_samples=True)
    reverse = s.paired_source_bootstrap([.5, .4, .8], [.1, .2, .3], indices=indices, return_samples=True)
    assert np.array_equal(forward['bootstrap_differences'], -np.asarray(reverse['bootstrap_differences']))


def test_qa_unequal_blocks_use_sampled_question_counts_not_block_mean_average():
    control = dict.fromkeys(('a', 'b', 'c', 'd'), 0.)
    treatment = {'a': 1., 'b': 0., 'c': 0., 'd': 0.}
    report = s.paired_question_bootstrap(control, treatment, [['a'], ['b', 'c', 'd']],
        draws=4, indices=FOUR_DRAWS, return_samples=True)
    assert report['point_difference'] == .25  # An unweighted block mean would be .5.
    assert report['bootstrap_differences'] == [1., .25, .25, 0.]
    assert report['ci95']['lower'] == pytest.approx(.01875)
    assert report['ci95']['upper'] == pytest.approx(.94375)
    assert report['raw_p'] == .4


def test_missing_qa_keeps_all_questions_bounds_and_no_complete_subset_primary():
    result = s.paired_question_bootstrap({'a': 0., 'b': None, 'c': 0., 'd': 0.},
        {'a': 1., 'b': 0., 'c': 0., 'd': 0.}, [['a'], ['b', 'c', 'd']])
    assert result['question_count'] == 4 and result['completed_pair_count'] == 3
    assert result['point_difference'] is None and result['raw_p'] is None
    assert result['undefined_reason'] == 'missing_fixed_QA_pairs'
    assert result['completed_pair_point_difference'] == pytest.approx(1/3)
    assert result['control_score_bounds'] == {'lower': 0., 'upper': .25}
    assert result['delta_identification_bounds'] == {'lower': 0., 'upper': .25}
    assert result['identification_sensitivity95'] is not None


def test_empty_observed_answer_score_zero_is_a_complete_score_not_missing():
    result = s.paired_question_bootstrap({'a': 0., 'b': 1.}, {'a': .5, 'b': 1.}, [['a'], ['b']])
    assert result['completed_pair_count'] == 2 and result['point_difference'] == .25


def test_qa_block_partition_must_not_duplicate_or_drop_fixed_question_ids():
    with pytest.raises(ValueError, match='exactly partition'):
        s.paired_question_bootstrap({'a': 0, 'b': 0}, {'a': 1, 'b': 0}, [['a'], ['a']])


def test_invalid_numeric_boundaries_or_explicit_qa_bounds_fail_before_inference():
    with pytest.raises(ValueError, match='null boundary'):
        s.wilcoxon_sensitivity([.1, -.1], null_boundary=float('nan'))
    with pytest.raises(ValueError, match='QA bounds'):
        s.paired_question_bootstrap({'a': None, 'b': 1}, {'a': 1, 'b': 1}, [['a'], ['b']],
            control_lower={'a': None, 'b': 1})


def test_holm_keeps_three_slots_and_none_is_never_an_observed_p_or_rejection():
    report = s.holm_primary({'H1': .01, 'H2': .04, 'H4': None})
    assert report['family_size'] == 3
    assert report['results']['H1']['adjusted_p'] == .03
    assert report['results']['H1']['reject']
    assert report['results']['H2']['adjusted_p'] == .08
    assert not report['results']['H2']['reject']
    assert report['results']['H4']['raw_p'] is None
    assert report['results']['H4']['slot_p'] == 1 and not report['results']['H4']['reject']


def test_holm_ties_family_drift_and_invalid_p_values():
    result = s.holm_primary({'H1': .02, 'H2': .02, 'H4': None})
    assert result['results']['H1']['adjusted_p'] == result['results']['H2']['adjusted_p'] == .06
    with pytest.raises(ValueError, match='exactly'):
        s.holm_primary({'H1': .01, 'H2': .02, 'H3': .03})
    with pytest.raises(ValueError, match='finite'):
        s.holm_primary({'H1': float('nan'), 'H2': .02, 'H4': None})


def test_wilcoxon_pratt_zeros_ties_and_fixed_monte_carlo_known_tail():
    result = s.wilcoxon_sensitivity([0, 1, -1])
    assert result['statistic_W_plus'] == 2.5  # Pratt ranks the zero before excluding it.
    assert result['nonzero_sources'] == 2
    signs = np.random.Generator(np.random.PCG64(2026102408)).integers(
        0, 2, size=(10000, 2), dtype=np.int8)
    expected = (1 + np.count_nonzero(np.any(signs, axis=1)))/10001
    assert result['raw_p'] == expected


def test_wilcoxon_all_zero_and_h2_shift_are_explicit_sensitivities():
    assert s.wilcoxon_sensitivity([0, 0, 0])['raw_p'] == 1.
    boundary = s.wilcoxon_sensitivity([-.05, -.05], null_boundary=-.05)
    assert boundary['raw_p'] == 1. and boundary['nonzero_sources'] == 0
    shifted = s.wilcoxon_sensitivity([-.04, -.02], null_boundary=-.05)
    assert shifted['statistic_W_plus'] == 3 and .2 < shifted['raw_p'] < .3
    assert shifted['unrounded_mean_difference'] == pytest.approx(-.03)
    assert s.wilcoxon_sensitivity([None, .5])['raw_p'] is None


def test_wilcoxon_rank_rounding_does_not_reclassify_a_nonzero_difference_as_zero():
    result = s.wilcoxon_sensitivity([0., 1e-14, 1.])
    assert result['zero_classification'] == 'unrounded_exact'
    assert result['nonzero_sources'] == 2
    assert result['original_nonzero_rankrounded_to_zero'] == 1
    # Rounded absolute values [0,0,1] have average ranks [1.5,1.5,3].
    # The original +1e-14 still contributes its positive rank, actual zero does not.
    assert result['statistic_W_plus'] == 4.5


def test_mcnemar_known_binomial_tail_complete_pair_count_and_no_holm_slot():
    result = s.mcnemar_sensitivity([0, 0, 0, 0, 1, 0, 1, None], [1, 1, 1, 1, 0, 0, 1, 1])
    assert (result['W'], result['L'], result['paired_count'], result['planned_count']) == (4, 1, 7, 8)
    assert result['raw_p'] == .1875
    assert result['table_rows_control_columns_treatment'] == [[1, 4], [1, 1]]
    assert s.mcnemar_sensitivity([0, 1], [0, 1])['raw_p'] == 1.


def test_kappa_known_three_class_value_technical_missing_and_degeneracy():
    result = s.cohens_kappa(['supported', 'supported', 'not_supported', 'not_supported', 'unclear', 'unclear', None],
        ['supported', 'not_supported', 'not_supported', 'not_supported', 'unclear', 'supported', 'supported'])
    assert result['confusion_matrix'] == [[1, 1, 0], [0, 2, 0], [1, 0, 1]]
    assert (result['N_selected'], result['N_left'], result['N_right'], result['N_pair']) == (7, 6, 7, 6)
    assert result['p_o'] == pytest.approx(2/3) and result['p_e'] == pytest.approx(1/3)
    assert result['kappa'] == .5
    assert s.cohens_kappa(['supported'], ['supported'])['kappa'] is None
    assert s.cohens_kappa([None], ['unclear'])['undefined_reason'] == 'no_complete_pairs'


def test_outputs_are_standard_json_serializable_without_nan_or_numpy_scalars():
    reports = [s.paired_source_bootstrap([0, 1], [.5, 1]),
        s.paired_question_bootstrap({'a':None,'b':1}, {'a':0,'b':1}, [['a'],['b']]),
        s.holm_primary({'H1':None,'H2':.01,'H4':None}), s.wilcoxon_sensitivity([0, 1, -1]),
        s.cohens_kappa([None], [None]), s.mcnemar_sensitivity([0, None], [1, 0])]
    assert json.loads(json.dumps(reports, allow_nan=False))[2]['family_size'] == 3
