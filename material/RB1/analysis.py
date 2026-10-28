"""N17 section 2: descriptive CPU sensitivity, no hypothesis tests.

Inputs are supplied in memory. No source texts, provider calls, or input mutation.
"""
from collections import Counter
from math import fsum, isfinite

import numpy as np

TYPES = ('EE', 'EV', 'VV')
AS = 'AS_ORIGINAL'
CONTRASTS = ((AS, 'V2_ROW'), (AS, 'V1_ROW'),
             (AS, 'AS_G_ROW'), ('V1_ROW', 'V2_ROW'))


def mean(values):
    values = list(values)
    return fsum(values) / len(values) if values and all(x is not None for x in values) else None


def inventory_weights(bundle, cells, source_ids):
    """Complete native occurrence inventories, exactly one export per arm."""
    if len(cells) != len(set(cells)):
        raise ValueError('Duplicate weighting cell')
    if len({c.rsplit('_', 1)[0] for c in cells}) != len(cells):
        raise ValueError('Export views of one arm must not be double counted')
    ids = set(source_ids)
    counts = Counter(r['category'] for r in bundle['H1']
                     if r['source_id'] in ids and r['cell'] in cells)
    if set(counts) - set(TYPES):
        raise ValueError('Unknown category')
    n = sum(counts.values())
    return {'counts': {t: counts[t] for t in TYPES}, 'denominator': n,
            'weights': {t: counts[t] / n if n else None for t in TYPES},
            'cells': list(cells), 'source_count': len(ids)}


def standardized(type_means, weights, raw_delta):
    """N17 is undefined if any arm/type mean is undefined, without imputation."""
    missing = [f'{side}:{t}' for side in ('control', 'treatment')
               for t in TYPES if type_means[side][t] is None]
    if any(weights.get(t) is None for t in TYPES):
        missing.append('weight_denominator')
    if not missing and (any(weights[t] < 0 for t in TYPES)
                        or not np.isclose(fsum(weights.values()), 1., atol=1e-12, rtol=0)):
        raise ValueError('Nonnegative weights summing to one required')
    if missing:
        return {'defined': False, 'control': None, 'treatment': None,
                'difference': None, 'mix_remainder': None,
                'undefined_components': missing}
    control = fsum(weights[t] * type_means['control'][t] for t in TYPES)
    treatment = fsum(weights[t] * type_means['treatment'][t] for t in TYPES)
    delta = treatment - control
    return {'defined': True, 'control': control, 'treatment': treatment,
            'difference': delta,
            'mix_remainder': raw_delta - delta if raw_delta is not None else None,
            'undefined_components': [],
            'mix_remainder_definition': 'unstandardized minus standardized, same sources',
            'causal_explained_fraction': False}


def type_decomposition(bundle, h1, typed):
    all_ids = [s['source_id'] for s in bundle['sources']]
    rows = {cell: {r['source_id']: r for r in h1.aggregates[cell]['sources']}
            for cell in h1.cells}
    tr = {t: {cell: {r['source_id']: r for r in obj.aggregates[cell]['sources']}
              for cell in obj.cells} for t, obj in typed.items()}

    def calculate(control, treatment, ids):
        p = {side: {t: mean(tr[t][cell][sid]['estimate'] for sid in ids) for t in TYPES}
             for side, cell in [('control', control), ('treatment', treatment)]}
        raw_c = mean(rows[control][sid]['estimate'] for sid in ids)
        raw_t = mean(rows[treatment][sid]['estimate'] for sid in ids)
        raw = raw_t - raw_c if raw_t is not None and raw_c is not None else None
        aw = inventory_weights(bundle, [AS], ids)
        pw = inventory_weights(bundle, [control, treatment], ids)
        missing = []
        for cell in (control, treatment):
            for t in TYPES:
                for sid in ids:
                    if tr[t][cell][sid]['estimate'] is None:
                        full = sum(r['cell'] == cell and r['category'] == t and r['source_id'] == sid
                                   for r in bundle['H1'])
                        missing.append({'cell': cell, 'category': t, 'source_id': sid,
                                        'full_type_occurrences': full,
                                        'selected_type_occurrences': tr[t][cell][sid]['denominator'],
                                        'reason': 'structural_type_absence' if full == 0 else 'no_sampled_type'})
        return {'source_count': len(ids), 'source_ids': list(ids),
                'unstandardized': {'control': raw_c, 'treatment': raw_t, 'difference': raw},
                'type_means': p, 'AS_inventory_weights': aw,
                'pooled_contrast_inventory_weights': pw,
                'AS_standardized': standardized(p, aw['weights'], raw),
                'pooled_standardized': standardized(p, pw['weights'], raw),
                'missing_type_sources': missing}

    result = []
    for control, treatment in CONTRASTS:
        full = calculate(control, treatment, all_ids)
        common = [sid for sid in all_ids
                  if all(tr[t][cell][sid]['estimate'] is not None
                         for t in TYPES for cell in (control, treatment))]
        value = {'control': control, 'treatment': treatment, 'N17_full_population': full}
        if common != all_ids:
            value['common_estimable_sensitivity'] = {
                **calculate(control, treatment, common),
                'excluded_source_ids': [sid for sid in all_ids if sid not in common],
                'role': 'additional conditional source-coverage sensitivity, not the N17 24-source result',
                'weights_recomputed_within_same_source_population': True,
                'complete_case_selection_is_not_random_sampling': True}
        else:
            value['common_estimable_sensitivity'] = None
        result.append(value)
    return result


def reduction(control, treatment):
    """Relative reduction of conservative non-supported share, aggregate first."""
    if control is None or treatment is None or control == 1:
        return None
    if not (isfinite(control) and isfinite(treatment) and 0 <= control <= 1 and 0 <= treatment <= 1):
        raise ValueError('Finite proportions in [0,1] required')
    return 1 - (1 - treatment) / (1 - control)


def relative_reductions(h1):
    c = h1.aggregates[AS]['estimate']
    control_boot = h1.replicates['estimate'][:, h1.cells.index(AS)]
    results = []
    for treatment in ('V2_ROW', 'V1_ROW', 'AS_G_ROW'):
        target_boot = h1.replicates['estimate'][:, h1.cells.index(treatment)]
        valid = np.isfinite(control_boot) & np.isfinite(target_boot) & (control_boot != 1)
        transformed = np.full(control_boot.shape, np.nan)
        transformed[valid] = 1 - (1 - target_boot[valid]) / (1 - control_boot[valid])
        # Missing replicates are never discarded to manufacture a full interval.
        ci = (dict(zip(('lower', 'upper'), map(float, np.quantile(transformed, [.025, .975], method='linear'))))
              if valid.all() else None)
        results.append({'control': AS, 'treatment': treatment,
            'control_non_supported_share': None if c is None else 1 - c,
            'treatment_non_supported_share': 1 - h1.aggregates[treatment]['estimate']
                if h1.aggregates[treatment]['estimate'] is not None else None,
            'relative_reduction': reduction(c, h1.aggregates[treatment]['estimate']),
            'ci95': ci, 'valid_replicates': int(valid.sum()), 'planned_replicates': len(valid),
            'seed': h1.matrix.seed, 'N10_matrix_sha256': h1.matrix.digest,
            'method': 'same paired two-stage N10 draws, linear percentile; no new test',
            'non_supported_includes': ['semantic_negative', 'semantic_unclear', 'selected_technical_missing'],
            'not_a_count_of_proven_false_statements': True})
    return results
