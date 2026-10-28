"""Pure N15 evaluation of the fixed 30 H15 author/Sol judgments.

No files, sources, inventories, models or provider IO. The caller must supply
the direct packet-bound UI export and explicitly confirm author attribution.
Point kappa reuses D1's existing nominal implementation through an explicit
bijection of class names. The returned labels always use H15 meanings.
"""
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import re

import numpy as np

from Experiments.fair_v2_oct24.D1 import inference
from .annotation import validate_annotations


PROTOCOL = 'H15-N15-author-retention-validation:v1'
KEY_FORMAT = 'h15-private-key-v1'
LABELS = ('retained', 'partially_retained', 'not_retained', 'undetermined')
CLEAR_LABELS = LABELS[:3]
SOL_CODES = (*CLEAR_LABELS, 'undetermined', 'not_assessable')
ARMS = ('AS', 'V2')
N_PAIRS, N_CASES = 15, 30
BOOTSTRAP_DRAWS, CI_SEED = 10000, 2026102616
KAPPA_THRESHOLD = .40
_NOMINAL_BIJECTION = dict(zip(CLEAR_LABELS, inference.LABELS, strict=True))


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _nonempty(value):
    return type(value) is str and bool(value.strip())


def _key(key):
    _need(type(key) is dict and key.get('format') == KEY_FORMAT, 'H15 private key format required')
    _need(_nonempty(key.get('dataset_id')), 'H15 key dataset ID required')
    _need(type(key.get('packet_sha256')) is str
          and re.fullmatch('[0-9a-f]{64}', key['packet_sha256']) is not None,
          'H15 key packet SHA256 required')
    rows = key.get('items')
    _need(type(rows) is list and len(rows) == N_CASES, 'Exactly thirty H15 key cases required')
    seen, pairs = set(), defaultdict(dict)
    for row in rows:
        _need(type(row) is dict, 'Explicit H15 key case object required')
        item, pair, arm = row.get('item_id'), row.get('pair_id'), row.get('arm')
        _need(_nonempty(item) and item not in seen and _nonempty(pair) and arm in ARMS,
              'Distinct H15 item ID, pair ID and AS/V2 arm required')
        _need(arm not in pairs[pair], 'Duplicate H15 arm within one meaning pair')
        _need(row.get('sol_raw_code') in SOL_CODES, 'Valid original C3 Sol code required')
        seen.add(item)
        pairs[pair][arm] = row
    _need(len(pairs) == N_PAIRS and all(set(value) == set(ARMS) for value in pairs.values()),
          'Exactly fifteen complete AS/V2 meaning pairs required')
    for pair in pairs.values():
        for field in ('source_id', 'obligation_id', 'draw'):
            if any(field in row for row in pair.values()):
                _need(all(field in row for row in pair.values())
                      and pair['AS'][field] == pair['V2'][field],
                      'H15 pair changes source, meaning or shared construction draw')
    if all(all(field in pair['AS'] for field in ('source_id', 'obligation_id')) for pair in pairs.values()):
        meanings = [(pair['AS']['source_id'], pair['AS']['obligation_id']) for pair in pairs.values()]
        _need(len(set(meanings)) == N_PAIRS, 'A reference meaning must not occur in two H15 pairs')
    return sorted(rows, key=lambda row: row['item_id'])


def _sol_label(raw_code):
    return 'undetermined' if raw_code == 'not_assessable' else raw_code


def _point_kappa(author, sol, *, binary):
    if binary:
        # The unused third D1 class remains empty; the public table is 2x2.
        convert = lambda label: inference.LABELS[0] if label == 'retained' else inference.LABELS[1]
        left, right = list(map(convert, author)), list(map(convert, sol))
        labels = ['retained', 'other_valid']
    else:
        left = [_NOMINAL_BIJECTION.get(label) for label in author]
        right = [_NOMINAL_BIJECTION.get(label) for label in sol]
        labels = list(CLEAR_LABELS)
    point = inference.cohens_kappa(left, right)
    size = len(labels)
    # Do not propagate D1's support-label or technical-missing interpretations.
    return {'method': 'unweighted nominal Cohen kappa', 'labels': labels,
        'matrix_rows': 'author', 'matrix_columns': 'Sol',
        'confusion_matrix': [row[:size] for row in point['confusion_matrix'][:size]],
        'N_selected': len(author), 'N_pair': point['N_pair'],
        'p_o': point['p_o'], 'p_e': point['p_e'], 'kappa': point['kappa'],
        'undefined_reason': ('no_pairs_with_three_clear_classes' if not binary and not point['N_pair']
                             else point['undefined_reason']),
        'semantic_unclear_counts_as_rest': binary,
        'excluded_unclear_either_count': 0 if binary else len(author)-point['N_pair']}


def _bootstrap_kappa(author_codes, sol_codes, indices, *, binary):
    """C7 count formula, with N15's per-resample three-class exclusion.

    Code 3 denotes semantic unclear. It is removed inside each nominal
    resample and retained as binary rest. No missing rating is zero-imputed.
    """
    a, b = np.asarray(author_codes, dtype=np.int64)[indices], np.asarray(sol_codes, dtype=np.int64)[indices]
    if binary:
        a, b = (a != 0).astype(np.int64), (b != 0).astype(np.int64)
        valid = np.ones_like(a, dtype=bool)
        classes = range(2)
    else:
        valid = (a < 3) & (b < 3)
        classes = range(3)
    n = valid.sum(axis=1)
    observed = ((a == b) & valid).sum(axis=1)
    expected = sum(((a == label) & valid).sum(axis=1)*((b == label) & valid).sum(axis=1)
                   for label in classes)
    denominator = n*n-expected
    defined = (n > 0) & (denominator != 0)
    values = (observed[defined]*n[defined]-expected[defined])/denominator[defined]
    count = int(defined.sum())
    interval = ({'lower': float(np.quantile(values, .025, method='linear')),
                 'upper': float(np.quantile(values, .975, method='linear'))} if count >= 2 else None)
    return {'ci95': interval, 'defined_replicates': count,
        'undefined_replicates': int((~defined).sum()), 'requested_replicates': int(len(indices)),
        'CI_condition': 'percentiles conditional on defined kappa replicates; at least two required',
        'undefined_replicates_zero_imputed': False,
        'semantic_unclear_filtered_inside_each_draw': not binary}


def _agreement(items, labels):
    author = [labels[row['item_id']] for row in items]
    sol_raw = [row['sol_raw_code'] for row in items]
    sol = list(map(_sol_label, sol_raw))
    indices = np.random.Generator(np.random.PCG64(CI_SEED)).integers(
        0, N_CASES, size=(BOOTSTRAP_DRAWS, N_CASES), dtype=np.int64)
    code = {label: index for index, label in enumerate(LABELS)}
    author_codes, sol_codes = [code[label] for label in author], [code[label] for label in sol]
    three, binary = _point_kappa(author, sol, binary=False), _point_kappa(author, sol, binary=True)
    three.update(_bootstrap_kappa(author_codes, sol_codes, indices, binary=False))
    binary.update(_bootstrap_kappa(author_codes, sol_codes, indices, binary=True))
    excluded = Counter((a, raw) for a, b, raw in zip(author, sol, sol_raw, strict=True)
                       if a == 'undetermined' or b == 'undetermined')
    three['excluded_unclear_original_codes'] = [
        {'author_label': a, 'Sol_original_code': raw, 'count': n} for (a, raw), n in sorted(excluded.items())]
    return {'three_class': three, 'binary_fully_retained_vs_rest': binary,
        'Sol_original_code_counts': {label: sol_raw.count(label) for label in SOL_CODES},
        'not_assessable_mapping': 'unclear only for comparison; original private-key code unchanged',
        'bootstrap': {'draws': BOOTSTRAP_DRAWS, 'seed': CI_SEED, 'rng': 'numpy.random.Generator(PCG64)',
            'quantiles': [.025, .975], 'quantile_method': 'linear', 'resampling_unit': 'case',
            'case_order': 'lexicographic opaque item_id', 'matrix_shape': list(indices.shape),
            'matrix_dtype': str(indices.dtype), 'matrix_sha256': sha256(indices.tobytes()).hexdigest(),
            'same_draw_matrix_for_three_class_and_binary': True,
            'meaning_pair_dependence_corrected': False, 'source_cluster_bootstrap': False,
            'source_and_construction_dependence_corrected': False}}


def _descriptive_retention(items, labels):
    arms, pairs = {}, defaultdict(dict)
    for row in items:
        pairs[row['pair_id']][row['arm']] = labels[row['item_id']]
    for arm in ARMS:
        counts = Counter(labels[row['item_id']] for row in items if row['arm'] == arm)
        arms[arm] = {'N': N_PAIRS, 'fully_retained': counts['retained'],
            'fully_retained_rate': float(Fraction(counts['retained'], N_PAIRS)),
            'label_counts': {label: counts[label] for label in LABELS}}
    deltas = [int(pair['V2'] == 'retained')-int(pair['AS'] == 'retained') for _, pair in sorted(pairs.items())]
    outcomes = Counter((pair['AS'] == 'retained', pair['V2'] == 'retained') for pair in pairs.values())
    return {'arms': arms, 'n_meaning_pairs': N_PAIRS,
        'paired_difference_V2_minus_AS': float(Fraction(sum(deltas), N_PAIRS)),
        'difference_unit': 'fraction, not percentage points',
        'pair_outcomes': {'both_fully_retained': outcomes[True, True],
            'AS_only_fully_retained': outcomes[True, False], 'V2_only_fully_retained': outcomes[False, True],
            'neither_fully_retained': outcomes[False, False]},
        'partial_absent_unclear_are_not_full_retention': True,
        'missing_labels_zero_imputed': False, 'hypothesis_test_performed': False,
        'population_prevalence_estimate': False}


def _qualification(value):
    return {'binary_kappa_threshold': KAPPA_THRESHOLD, 'comparison': 'strictly_less',
        'H2_reviewer_dependent': value < KAPPA_THRESHOLD if value is not None else None,
        'status': ('indeterminate' if value is None else 'H2_bewerterabhaengig'
                   if value < KAPPA_THRESHOLD else 'threshold_not_triggered'),
        'higher_kappa_proves_general_correctness': False,
        'new_G2_N8_Holm_slots': 0, 'native_primary_scores_changed': False,
        'overall_judgment_changed': False}


def evaluate(key, annotations, *, author_confirmed=False):
    """Return aggregate N15 metrics only after the complete direct UI export."""
    _need(author_confirmed is True, 'Explicit author attribution is required')
    _need(type(annotations) is dict and annotations.get('annotation_origin') == 'human_ui_input',
          'Direct human_ui_input export origin required')
    items = _key(key)
    ratings = validate_annotations(annotations, dataset_id=key['dataset_id'],
        packet_sha256=key['packet_sha256'], item_ids=[row['item_id'] for row in items], require_complete=False)
    labels = {row['item_id']: ratings.get(row['item_id'], {}).get('label') for row in items}
    valid = sum(label in LABELS for label in labels.values())
    complete = valid == N_CASES
    result = {'protocol': PROTOCOL, 'status': 'complete_author_analysis' if complete else 'pending_author_annotations',
        'annotation_origin': 'human_ui_input', 'annotation_classification': 'Autorenannotation',
        'author_confirmed': True, 'complete_author_export': complete,
        'annotation_entries': len(ratings), 'valid_author_labels': valid,
        'missing_annotation_rows': N_CASES-len(ratings),
        'null_author_labels': sum(row.get('label') is None for row in ratings.values()),
        'fixed_sample_size': N_CASES, 'distinct_meaning_pairs': N_PAIRS,
        'agreement': None, 'descriptive_retention': None, 'H2_qualification': None,
        'interpretation': {'secondary_N15_only': True, 'general_evaluator_qualification': False,
            'new_G2_N8_Holm_slots': 0, 'native_primary_scores_changed': False,
            'overall_judgment_changed': False}, 'model_calls': 0,
        'natural_files_opened_by_evaluator': False}
    if complete:
        result['agreement'] = _agreement(items, labels)
        result['descriptive_retention'] = _descriptive_retention(items, labels)
        result['H2_qualification'] = _qualification(result['agreement']['binary_fully_retained_vs_rest']['kappa'])
    return result
