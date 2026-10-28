"""G2's frozen CPU inference, without file/provider/answer access.

Sources must already be planned-draw means, ordered identically in every cell.
Pass the same cluster_indices array to all paired cells/endpoints. QA blocks
are resampled as blocks but their question counts weight the estimator.
"""
from fractions import Fraction
from numbers import Real

import numpy as np
from scipy.stats import binom, rankdata

BOOTSTRAP_DRAWS = 10000
BOOTSTRAP_SEED = 2026102407
WILCOXON_SEED = 2026102408
PRIMARY_FAMILY = ('H1', 'H2', 'H4')
LABELS = ('supported', 'not_supported', 'unclear')


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _score(value):
    if value is None:
        return np.nan
    _need(isinstance(value, Real) and not isinstance(value, (bool, np.bool_)),
          'A numeric score or explicit None is required')
    number = float(value)
    _need(np.isfinite(number) and 0 <= number <= 1, 'Scores must be finite within [0,1]')
    return number


def _values(values):
    return np.array([_score(value) for value in values], dtype=np.float64)


def cluster_indices(n_clusters, draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED):
    """PCG64 with one shared B x number-of-clusters draw matrix."""
    _need(type(n_clusters) is int and n_clusters > 0, 'Positive cluster count required')
    _need(type(draws) is int and draws > 0 and type(seed) is int,
          'Positive integer draw count and integer seed required')
    return np.random.Generator(np.random.PCG64(seed)).integers(
        0, n_clusters, size=(draws, n_clusters), dtype=np.int64)


def _indices(indices, n_clusters, draws, seed):
    if indices is None:
        return cluster_indices(n_clusters, draws, seed)
    array = np.asarray(indices)
    _need(array.shape == (draws, n_clusters) and np.issubdtype(array.dtype, np.integer)
          and np.all((array >= 0) & (array < n_clusters)), 'Exact shared cluster index matrix required')
    return array


def _interval(samples, low=.025, high=.975):
    if samples is None or not np.isfinite(samples).all():
        return None
    quantiles = np.quantile(samples, [low, high], method='linear')
    return {'lower': float(quantiles[0]), 'upper': float(quantiles[1])}


def bootstrap_from_replicates(point_difference, replicates, *, cluster_count,
                              null_boundary=0., lower_replicates=None,
                              upper_replicates=None, draws=BOOTSTRAP_DRAWS,
                              seed=BOOTSTRAP_SEED, missing_reason=None,
                              return_samples=False):
    """Frozen null centering; descriptive CI survives a degenerate distribution.

    Degeneracy means exactly zero replicate variation. No outcome-selected
    variance threshold or alternative test is used. The percentile interval
    is marginal and must never be called a simultaneous Holm interval.
    """
    _need(type(cluster_count) is int and cluster_count >= 0, 'Integer cluster count required')
    _need(isinstance(null_boundary, Real) and not isinstance(null_boundary, (bool, np.bool_))
          and np.isfinite(null_boundary), 'Finite numeric null boundary required')
    result = {'point_difference': point_difference, 'raw_p': None, 'ci95': None,
        'identification_sensitivity95': None, 'testable': False,
        'undefined_reason': missing_reason, 'null_boundary': float(null_boundary),
        'cluster_count': cluster_count, 'bootstrap_draws': draws, 'seed': seed,
        'rng': 'numpy.random.Generator(PCG64)', 'CI_method': 'linear percentile',
        'CI_scope': 'marginal two-sided 95%, not simultaneous Holm-adjusted',
        'primary_statistic_is_identification_lower_bound': False}
    lower = None if lower_replicates is None else np.asarray(lower_replicates, dtype=float)
    upper = None if upper_replicates is None else np.asarray(upper_replicates, dtype=float)
    if lower is not None and upper is not None:
        _need(lower.shape == upper.shape == (draws,), 'Sensitivity replicate shape mismatch')
        if np.isfinite(lower).all() and np.isfinite(upper).all():
            result['identification_sensitivity95'] = {
                'lower': float(np.quantile(lower, .025, method='linear')),
                'upper': float(np.quantile(upper, .975, method='linear'))}
    samples = None if replicates is None else np.asarray(replicates, dtype=np.float64)
    if samples is not None:
        _need(samples.shape == (draws,), 'Primary replicate shape mismatch')
        result['ci95'] = _interval(samples)
        if return_samples:
            result['bootstrap_differences'] = [float(v) if np.isfinite(v) else None for v in samples]
    if missing_reason is not None:
        return result
    if point_difference is None or not np.isfinite(point_difference):
        result['undefined_reason'] = 'undefined_planned_primary_estimate'
    elif cluster_count < 2:
        result['undefined_reason'] = 'fewer_than_two_independent_clusters'
    elif samples is None or not np.isfinite(samples).all():
        result['undefined_reason'] = 'invalid_bootstrap_outputs'
    elif np.ptp(samples) == 0:
        result['undefined_reason'] = 'zero_bootstrap_statistic_variation'
    else:
        null_samples = float(null_boundary) + (samples - float(point_difference))
        result.update(testable=True,
            raw_p=float((1 + np.count_nonzero(null_samples >= point_difference)) / (draws + 1)))
    return result


def paired_source_bootstrap(control, treatment, *, control_lower=None, control_upper=None,
                            treatment_lower=None, treatment_upper=None, indices=None,
                            null_boundary=0., draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED,
                            return_samples=False):
    """Equal-source paired bootstrap after all planned draws have been averaged."""
    control, treatment = _values(control), _values(treatment)
    _need(control.ndim == treatment.ndim == 1 and control.shape == treatment.shape and len(control),
          'Matched nonempty planned source vectors required')
    n = len(control)
    shared = _indices(indices, n, draws, seed)
    c_low = control if control_lower is None else _values(control_lower)
    c_up = control if control_upper is None else _values(control_upper)
    t_low = treatment if treatment_lower is None else _values(treatment_lower)
    t_up = treatment if treatment_upper is None else _values(treatment_upper)
    _need(all(a.shape == control.shape for a in (c_low, c_up, t_low, t_up)), 'Source bounds shape mismatch')
    _need(not np.any(c_low > c_up) and not np.any(t_low > t_up), 'Inverted source bounds')
    complete = bool(np.isfinite(control).all() and np.isfinite(treatment).all())
    delta = float(np.mean(treatment - control)) if complete else None
    samples = (treatment - control)[shared].mean(axis=1) if complete else None
    lower = (t_low - c_up)[shared].mean(axis=1)
    upper = (t_up - c_low)[shared].mean(axis=1)
    result = bootstrap_from_replicates(delta, samples, cluster_count=n,
        null_boundary=null_boundary, lower_replicates=lower, upper_replicates=upper,
        draws=draws, seed=seed,
        missing_reason=None if complete else 'undefined_planned_source_pair',
        return_samples=return_samples)
    result.update(control_mean=float(np.mean(control)) if np.isfinite(control).all() else None,
        treatment_mean=float(np.mean(treatment)) if np.isfinite(treatment).all() else None,
        aggregation='mean planned draws within source, then equally weighted source mean',
        defined_source_pairs=int(np.count_nonzero(np.isfinite(control) & np.isfinite(treatment))))
    return result


def paired_question_bootstrap(control, treatment, blocks, *, control_lower=None, control_upper=None,
                              treatment_lower=None, treatment_upper=None, indices=None,
                              null_boundary=0., draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED,
                              return_samples=False):
    """Question-weighted resampling of complete overlapping-paragraph blocks.

    Explicit None denotes an unobserved question score. It gives [0,1] for
    bounds, never a zero primary score. No complete-subset H4 primary test.
    """
    _need(type(control) is dict and type(treatment) is dict and set(control) == set(treatment)
          and bool(control), 'Same complete fixed question-ID roster required')
    _need(type(blocks) in (list, tuple) and bool(blocks) and all(bool(b) for b in blocks),
          'Nonempty planned QA blocks required')
    question_ids = [q for block in blocks for q in block]
    _need(len(question_ids) == len(set(question_ids)) and set(question_ids) == set(control),
          'QA blocks must exactly partition the fixed questions')
    c = _values([control[q] for q in question_ids])
    t = _values([treatment[q] for q in question_ids])
    def bounds(explicit, observed, upper):
        if explicit is not None:
            _need(set(explicit) == set(control), 'Complete fixed QA bounds roster required')
            return _values([explicit[q] for q in question_ids])
        return np.where(np.isfinite(observed), observed, 1. if upper else 0.)
    c_low, c_up = bounds(control_lower, c, False), bounds(control_upper, c, True)
    t_low, t_up = bounds(treatment_lower, t, False), bounds(treatment_upper, t, True)
    _need(all(np.isfinite(v).all() for v in (c_low, c_up, t_low, t_up)), 'QA bounds must be finite')
    _need(not np.any(c_low > c_up) and not np.any(t_low > t_up), 'Inverted QA bounds')
    lengths = np.array([len(block) for block in blocks], dtype=np.int64)
    cuts = np.concatenate(([0], np.cumsum(lengths)))
    shared = _indices(indices, len(blocks), draws, seed)
    denominators = lengths[shared].sum(axis=1)
    def resample(values):
        sums = np.array([values[cuts[i]:cuts[i+1]].sum() for i in range(len(blocks))])
        return sums[shared].sum(axis=1) / denominators
    complete = bool(np.isfinite(c).all() and np.isfinite(t).all())
    paired = np.isfinite(c) & np.isfinite(t)
    delta = float(np.mean(t - c)) if complete else None
    result = bootstrap_from_replicates(delta, resample(t-c) if complete else None,
        cluster_count=len(blocks), null_boundary=null_boundary,
        lower_replicates=resample(t_low-c_up), upper_replicates=resample(t_up-c_low),
        draws=draws, seed=seed, missing_reason=None if complete else 'missing_fixed_QA_pairs',
        return_samples=return_samples)
    result.update(question_count=len(question_ids), completed_pair_count=int(paired.sum()),
        completed_pair_point_difference=float(np.mean((t-c)[paired])) if paired.any() else None,
        completed_pair_sensitivity_only=True,
        control_mean=float(np.mean(c)) if np.isfinite(c).all() else None,
        treatment_mean=float(np.mean(t)) if np.isfinite(t).all() else None,
        control_score_bounds={'lower': float(np.mean(c_low)), 'upper': float(np.mean(c_up))},
        treatment_score_bounds={'lower': float(np.mean(t_low)), 'upper': float(np.mean(t_up))},
        delta_identification_bounds={'lower': float(np.mean(t_low-c_up)), 'upper': float(np.mean(t_up-c_low))},
        aggregation='sum question scores divided by sampled question count, not mean block means')
    return result


def holm_primary(pvalues, alpha=.05):
    """Exactly three primary slots; an unavailable raw p occupies slot one."""
    _need(type(pvalues) is dict and set(pvalues) == set(PRIMARY_FAMILY), 'Holm family is exactly H1/H2/H4')
    _need(isinstance(alpha, Real) and 0 < alpha < 1, 'Valid alpha required')
    slots = {}
    for name in PRIMARY_FAMILY:
        value = pvalues[name]
        _need(value is None or isinstance(value, Real) and not isinstance(value, bool)
              and np.isfinite(value) and 0 <= value <= 1, 'Raw p must be finite [0,1] or None')
        slots[name] = 1. if value is None else float(value)
    ordered = sorted(PRIMARY_FAMILY, key=lambda name: (slots[name], PRIMARY_FAMILY.index(name)))
    results, running = {}, 0.
    for index, name in enumerate(ordered):
        running = max(running, (len(PRIMARY_FAMILY)-index)*slots[name])
        adjusted = min(1., running)
        results[name] = {'raw_p': None if pvalues[name] is None else float(pvalues[name]),
            'slot_p': slots[name], 'adjusted_p': adjusted,
            'reject': pvalues[name] is not None and adjusted <= alpha,
            'slot_is_missing_placeholder': pvalues[name] is None}
    return {'family': list(PRIMARY_FAMILY), 'family_size': 3, 'alpha': float(alpha),
            'results': {name: results[name] for name in PRIMARY_FAMILY}}


def wilcoxon_sensitivity(differences, *, null_boundary=0., draws=BOOTSTRAP_DRAWS,
                         seed=WILCOXON_SEED):
    """Pratt signed ranks, fixed sign permutations; no scipy auto/exact switch.

    Differences are shifted by -null_boundary. Their absolute values are
    rounded to 12 decimals for ranks only. Signs and exact Pratt-zero
    classification use the unrounded shifted differences. No 1e-12 zero
    tolerance is introduced. Estimation stays unrounded.
    The frozen 10,000 random sign draws use the +1 Monte Carlo correction
    (the randomized-test convention used by scipy.stats permutation tests).
    G2 specifies the sign permutations but not this finite-MC correction;
    this implementation convention is fixed here before natural-data access.
    """
    values = list(differences)
    _need(isinstance(null_boundary, Real) and not isinstance(null_boundary, (bool, np.bool_))
          and np.isfinite(null_boundary), 'Finite numeric null boundary required')
    result = {'role': 'prespecified sensitivity only', 'raw_p': None,
        'undefined_reason': None, 'statistic_W_plus': None,
        'source_count': len(values), 'zero_method': 'pratt', 'alternative': 'greater',
        'draws': draws, 'seed': seed, 'rounding_decimals': 12,
        'zero_classification': 'unrounded_exact',
        'original_nonzero_rankrounded_to_zero': None,
        'null_boundary': float(null_boundary),
        'MC_p_convention': '(1 + count(permuted_W_plus >= observed_W_plus))/(draws + 1)',
        'location_interpretation_requires_symmetric_differences': True}
    if not values or any(value is None for value in values):
        result['undefined_reason'] = 'undefined_planned_source_difference'
        return result
    _need(all(isinstance(v, Real) and not isinstance(v, bool) and np.isfinite(v) for v in values),
          'Finite planned source differences required')
    _need(type(draws) is int and draws > 0 and type(seed) is int, 'Fixed positive permutation count required')
    shifted = np.asarray(values, dtype=np.float64) - null_boundary
    rounded_absolute = np.round(np.abs(shifted), 12)
    ranks = rankdata(rounded_absolute, method='average')
    active = shifted != 0
    nonzero_ranks = ranks[active]
    observed = float(ranks[shifted > 0].sum())
    result.update(statistic_W_plus=observed, nonzero_sources=int(active.sum()),
                  original_nonzero_rankrounded_to_zero=int(np.count_nonzero(active & (rounded_absolute == 0))),
                  unrounded_mean_difference=float(np.mean(np.asarray(values))))
    if not active.any():
        result['raw_p'] = 1.
        return result
    rng = np.random.Generator(np.random.PCG64(seed))
    positive = rng.integers(0, 2, size=(draws, len(nonzero_ranks)), dtype=np.int8)
    permuted = positive @ nonzero_ranks
    result['raw_p'] = float((1 + np.count_nonzero(permuted >= observed))/(draws+1))
    return result


def mcnemar_sensitivity(control_em, treatment_em):
    """One-sided exact binomial working-model sensitivity over observed pairs."""
    _need(len(control_em) == len(treatment_em), 'Matched planned EM vectors required')
    table = [[0, 0], [0, 0]]
    for control, treatment in zip(control_em, treatment_em, strict=True):
        if control is None or treatment is None:
            continue
        _need(isinstance(control, Real) and not isinstance(control, (bool, np.bool_)) and control in (0, 1)
              and isinstance(treatment, Real) and not isinstance(treatment, (bool, np.bool_))
              and treatment in (0, 1), 'Observed EM is exactly binary')
        table[int(control)][int(treatment)] += 1
    win, loss = table[0][1], table[1][0]
    return {'role': 'EM-only secondary sensitivity; no Holm slot', 'W': win, 'L': loss,
        'paired_count': sum(map(sum, table)), 'planned_count': len(control_em),
        'excluded_missing_pair_count': len(control_em)-sum(map(sum, table)),
        'table_rows_control_columns_treatment': table,
        'raw_p': float(binom.sf(win-1, win+loss, .5)) if win+loss else 1.,
        'exactness_requires_independent_pairs': True,
        'shared_paragraphs_make_this_working_model_sensitivity_only': True}


def cohens_kappa(left_labels, right_labels):
    """Nominal three-class agreement, with technical missing excluded as None."""
    _need(len(left_labels) == len(right_labels), 'Same selected occurrence roster required')
    table = [[0 for _ in LABELS] for _ in LABELS]
    for left, right in zip(left_labels, right_labels, strict=True):
        _need(left is None or left in LABELS, 'Canonical left label or None required')
        _need(right is None or right in LABELS, 'Canonical right label or None required')
        if left is not None and right is not None:
            table[LABELS.index(left)][LABELS.index(right)] += 1
    n = sum(map(sum, table))
    result = {'labels': list(LABELS), 'confusion_matrix': table, 'N_selected': len(left_labels),
        'N_left': sum(v is not None for v in left_labels), 'N_right': sum(v is not None for v in right_labels),
        'N_pair': n, 'excluded_missing_either_count': len(left_labels)-n,
        'p_o': None, 'p_e': None, 'kappa': None, 'undefined_reason': None,
        'technical_missing_is_not_unclear': True, 'automatic_replacement_of_primary_labels': False}
    if not n:
        result['undefined_reason'] = 'no_complete_pairs'
        return result
    observed = Fraction(sum(table[i][i] for i in range(3)), n)
    row = [sum(r) for r in table]
    column = [sum(table[i][j] for i in range(3)) for j in range(3)]
    expected = sum((Fraction(a*b, n*n) for a, b in zip(row, column, strict=True)), Fraction())
    result.update(p_o=float(observed), p_e=float(expected))
    if expected == 1:
        result['undefined_reason'] = 'degenerate_marginals'
    else:
        result['kappa'] = float((observed-expected)/(1-expected))
    return result
