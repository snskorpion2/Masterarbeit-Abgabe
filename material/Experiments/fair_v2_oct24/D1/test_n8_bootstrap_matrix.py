"""Additional NI decision counterprobes, generated in memory only.

Seed/matrix identity, primary-family invariance and descriptive H4 output are
already covered by test_inference.py and test_n8_components.py. These tests
add the missing negative-but-noninferior and clearly inferior effect cases.
"""
import numpy as np
import pytest

from . import components as c


FOUR = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.int64)
SOURCE_MATRIX = np.tile(FOUR, (2500, 1))
QA_MATRIX = np.tile(FOUR[::-1], (2500, 1))


def generated_inputs(near):
    """Every component's source differences are near[0]-0.5, near[1]-0.5."""
    deltas = np.asarray(near) - .5
    vectors = {'AS': np.array([.5, .5]),
               'AS_G': np.asarray(near),
               'V1': np.asarray(near),
               'V2': np.asarray(near) + deltas}
    aggregates = {endpoint: {} for endpoint in ('H1', 'H2')}
    qa = {}
    for arm, vector in vectors.items():
        for export in ('ORIGINAL', 'ROW'):
            cell = arm+'_'+export
            for endpoint in aggregates:
                aggregates[endpoint][cell] = {'sources': [
                    {'source_id': sid, 'estimate': float(score),
                     'lower': float(score), 'upper': float(score)}
                    for sid, score in zip(('synthetic-a', 'synthetic-b'), vector, strict=True)]}
            qa['f1', cell] = {'synthetic-q1': .2, 'synthetic-q2': .7}
    contract = {'sources': [{'source_id': 'synthetic-a'}, {'source_id': 'synthetic-b'}],
                'qa_blocks': [['synthetic-q1'], ['synthetic-q2']]}
    return aggregates, qa, contract


def test_negative_effect_inside_margin_confirms_only_the_three_NI_criteria():
    aggregates, qa, contract = generated_inputs([.47, .46])
    result = c.analyze_components(aggregates, qa, contract,
                                 indices=SOURCE_MATRIX, qa_indices=QA_MATRIX)
    # Nondegenerate source differences -0.03/-0.04 have a negative mean, but
    # even their lowest resample is above the frozen -0.05 NI boundary.
    for name in c.COMPONENT_FAMILY:
        row = result['contrasts'][name]
        assert row['point_difference'] == pytest.approx(-.035)
        assert row['ci95']['lower'] == pytest.approx(-.04)
        assert row['ci95']['upper'] == pytest.approx(-.03)
        if name in ('K2', 'K4', 'K6'):
            assert row['null_boundary'] == -.05
            assert row['raw_p'] == 1/10001
            assert row['adjusted_p'] == 6/10001
            assert row['reject'] is True and row['criterion_met'] is True
        else:
            assert row['null_boundary'] == 0.
            assert row['raw_p'] == row['adjusted_p'] == 1.
            assert row['reject'] is False and row['criterion_met'] is False


def test_negative_effect_beyond_margin_cannot_be_declared_noninferior():
    aggregates, qa, contract = generated_inputs([.44, .43])
    result = c.analyze_components(aggregates, qa, contract,
                                 indices=SOURCE_MATRIX, qa_indices=QA_MATRIX)
    for name in c.COMPONENT_FAMILY:
        row = result['contrasts'][name]
        assert row['point_difference'] == pytest.approx(-.065)
        assert row['ci95']['lower'] == pytest.approx(-.07)
        assert row['ci95']['upper'] == pytest.approx(-.06)
        assert row['raw_p'] == row['adjusted_p'] == 1.
        assert row['reject'] is False and row['criterion_met'] is False
    assert result['holm']['family_size'] == 6
