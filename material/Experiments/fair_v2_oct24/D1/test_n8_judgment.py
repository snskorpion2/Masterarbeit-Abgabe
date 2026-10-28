"""N8 A--F and dependency thresholds, generated synthetic decisions only."""
from copy import deepcopy

import pytest

from Experiments.fair_v2_oct24.D1.judgment import overall_judgment


def primary(h1=True, h2=True, h4=True, upper=.2, lower=-.1):
    result = {name: {'criterion_met': flag, 'reject': flag,
                     'point_difference': .1, 'testable': True}
              for name, flag in [('H1', h1), ('H2', h2), ('H4', h4)]}
    result['H4']['ci95'] = None if upper is None else {'lower': lower, 'upper': upper}
    return result


@pytest.mark.parametrize('h1,h2,h4,upper,lower,stage', [
    (True, True, True, .2, -.1, 'A'),
    (True, True, False, .2, -.1, 'B'),
    (True, True, False, 0., -.1, 'B'),
    (True, True, False, -.01, -.2, 'C'),
    (True, False, True, .2, -.1, 'D'),
    (True, False, False, .2, -.1, 'D'),
    (False, False, True, .2, -.1, 'E'),
    (False, True, True, .2, -.1, 'E'),
    (False, False, False, .2, -.1, 'F'),
    (False, True, False, .2, -.1, 'F'),
])
def test_exact_ordered_A_to_F_decision_table(h1, h2, h4, upper, lower, stage):
    report = overall_judgment(primary(h1, h2, h4, upper, lower))
    assert report['base_stage'] == report['stage'] == stage
    assert report['undefined_reason'] is None


def test_missing_h4_interval_never_invents_B_or_C_or_treats_missing_as_nonnegative():
    result = overall_judgment(primary(h4=False, upper=None))
    assert result['stage'] is None
    assert 'B/C not identifiable' in result['undefined_reason']
    assert result['H4_upper_95_bound'] is None


@pytest.mark.parametrize('kappa,dependent', [(.399999, True), (.40, False), (.400001, False), (-1., True), (1., False)])
def test_kappa_threshold_is_strict_and_does_not_invent_a_letter_change(kappa, dependent):
    result = overall_judgment(primary(), human_kappa=kappa, c7_available=True)
    assert result['evaluator_dependent'] is dependent
    assert result['base_stage'] == result['stage'] == 'A'
    assert ('bewerterabhängig' in result['statement']) is dependent
    assert result['letter_downgrade_invented'] is False


@pytest.mark.parametrize('main,grok,dependent', [
    (.1, -.1, True), (-.1, .1, True), (.1, .1, False),
    (-.1, -.1, False), (0., -.1, False), (.1, 0., False), (0., 0., False),
])
def test_grok_requires_strictly_opposite_nonzero_H1_signs(main, grok, dependent):
    data = primary()
    data['H1']['point_difference'] = main
    result = overall_judgment(data, grok_h1_difference=grok, c4_available=True)
    assert result['evaluator_dependent'] is dependent
    assert result['base_stage'] == 'A'


def test_both_dependency_causes_remain_visible_and_qualify_even_a_no_superiority_stage():
    data = primary(h1=False, h2=False, h4=False)
    result = overall_judgment(data, human_kappa=.2, grok_h1_difference=-.2,
                              c4_available=True, c7_available=True)
    assert result['stage'] == 'F'
    assert result['dependence_reasons'] == [
        'C7_kappa_below_0.40', 'C4_opposite_H1_point_estimate_sign']
    assert 'bewerterabhängig' in result['statement']


def test_absent_counterchecks_are_not_positive_confirmation_and_do_not_use_inactive_values():
    result = overall_judgment(primary(), human_kappa=.1, grok_h1_difference=-.1)
    assert set(result['missing_counterchecks']) == {'C4', 'C7'}
    assert len(result['qualifications']) == 2
    assert result['counterchecks_confirm_independence'] is False
    assert result['evaluator_dependent'] is False


def test_available_but_undefined_checks_are_not_assumed_passes():
    result = overall_judgment(primary(), c4_available=True, c7_available=True)
    assert result['missing_counterchecks'] == []
    assert any('nicht bestimmbar' in text for text in result['qualifications'])
    assert result['counterchecks_confirm_independence'] is False
    assert not result['evaluator_dependent']


def test_criterion_needs_both_original_reject_and_criterion_flags_without_recomputation():
    data = primary()
    data['H1']['reject'] = False
    result = overall_judgment(data)
    assert result['stage'] == 'E'
    data['H1']['reject'] = True
    data['H1']['criterion_met'] = False
    assert overall_judgment(data)['stage'] == 'E'


def test_input_primary_is_not_mutated_and_scope_is_explicitly_limited():
    data = primary()
    before = deepcopy(data)
    result = overall_judgment(data, human_kappa=.7, grok_h1_difference=.1,
                              c4_available=True, c7_available=True)
    assert data == before
    assert result['scope']['confirmation_sources'] == 24
    assert result['scope']['MuSiQue_questions'] == 60
    assert result['scope']['universal_superiority_claim_allowed'] is False


@pytest.mark.parametrize('kwargs', [
    {'human_kappa': float('nan')}, {'human_kappa': 1.01}, {'human_kappa': True},
    {'grok_h1_difference': float('inf')}, {'grok_h1_difference': -1.1},
    {'c4_available': 1}, {'c7_available': 'yes'},
])
def test_invalid_external_check_values_are_rejected(kwargs):
    with pytest.raises(ValueError):
        overall_judgment(primary(), **kwargs)


def test_inverted_h4_interval_is_not_interpreted_as_a_valid_negative_interval():
    with pytest.raises(ValueError, match='inverted'):
        overall_judgment(primary(h4=False, upper=-.2, lower=-.1))
