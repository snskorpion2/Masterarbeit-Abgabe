"""Explicit CPU-only RB1 runner over the completed, pinned D1 handoff."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from Experiments.fair_v2_oct24.D1 import n10_sampling as n10
from RB1.analysis import CONTRASTS, TYPES, type_decomposition, relative_reductions
from RB1.robustness import analyze


def read(path, expected=None):
    raw = Path(path).read_bytes()
    digest = sha256(raw).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError('Pinned input changed: ' + str(path))
    return json.loads(raw), {'file': Path(path).name, 'sha256': digest, 'bytes': len(raw)}


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run(bundle_path, original_analysis_path, output, private_output):
    repo = Path(__file__).resolve().parents[1]
    handoff, handoff_pin = read(repo/'Experiments/fair_v2_oct24/D1/final_native_oct26_v1/result.json')
    old, original_pin = read(original_analysis_path, handoff['original_analysis']['sha256'])
    bundle, bundle_pin = read(bundle_path)
    if bundle.get('synthetic') is not False:
        raise ValueError('This entry point requires the explicit completed natural D1 bundle')
    h1 = n10.estimate(bundle, tuple(bundle['cells']))
    if h1.matrix.digest != handoff['primary']['H1']['source_group_matrix_sha256']:
        raise ValueError('Bootstrap source/group matrix differs from final D1')
    typed = {t: n10.estimate(bundle, tuple(bundle['cells']), matrix=h1.matrix, category=t) for t in TYPES}
    checks = []
    for row in old['cells']:
        if row['endpoint'] != 'H1':
            continue
        actual = h1.aggregates[row['cell']]['estimate']
        if not np.isclose(actual, row['estimate'], atol=1e-13, rtol=0):
            raise ValueError('H1 aggregate mismatch')
        checks.append('H1:' + row['cell'])
    for row in old['strata']:
        if row.get('dimension') != 'category':
            continue
        actual = typed[row['level']].aggregates[row['cell']]['estimate']
        if (actual is None) != (row['estimate'] is None) or actual is not None and not np.isclose(
                actual, row['estimate'], atol=1e-13, rtol=0):
            raise ValueError('Strict type estimate differs from D1')
        checks.append('type:' + row['cell'] + ':' + row['level'])
    # Check the old marginal interval by direct quantiles, without running a new test.
    ci = h1.cells.index('AS_ORIGINAL')
    ti = h1.cells.index('V2_ROW')
    delta_boot = h1.replicates['estimate'][:, ti] - h1.replicates['estimate'][:, ci]
    actual_interval = np.quantile(delta_boot, [.025, .975], method='linear')
    if not np.allclose(actual_interval, list(handoff['primary']['H1']['ci95'].values()), atol=1e-13, rtol=0):
        raise ValueError('The reused H1 bootstrap does not reproduce D1')
    robustness = analyze(bundle, h1)
    for endpoint, point in [('H1', handoff['primary']['H1']['point_difference']),
                            ('H2_G2', handoff['primary']['H2']['point_difference']),
                            ('H2_N14', handoff['H2_analyses']['N14']['effect']['point_difference'])]:
        result = robustness['endpoints'][endpoint][0]['full']['difference']
        if not np.isclose(result, point, atol=1e-13, rtol=0):
            raise ValueError('Robustness baseline does not reproduce D1: ' + endpoint)
        checks.append('primary:' + endpoint)
    code = [repo/'Experiments/fair_v2_oct24/D1'/name for name in (
        'analysis.py', 'n10_sampling.py', 'n14_missingness.py', 'inference.py', 'native.py')]
    code.extend(Path(__file__).parent/name for name in ('analysis.py', 'robustness.py', 'run.py'))
    code_pins = [{'file': p.relative_to(repo).as_posix(), 'sha256': sha256(p.read_bytes()).hexdigest()}
                 for p in code]
    result = {'protocol': 'RB1-N17-section2-descriptive-sensitivity-v1', 'synthetic': False,
        'model_calls': 0, 'new_tests_of_natural_hypotheses': 0,
        'primary_Holm_and_N8_unchanged': True,
        'post_D1_selection_chronology': 'N17 after D1 preview; supplemental common-estimable-source analysis after observing type availability',
        'sources': len(bundle['sources']), 'planned_source_draws': sum(len(s['draws']) for s in bundle['sources']),
        'families': dict(Counter(s['family'] for s in bundle['sources'])),
        'family_label_caveat': 'sealed4 is a frozen cohort, not a common text genre',
        'type_decomposition': type_decomposition(bundle, h1, typed),
        'relative_non_supported_reductions': relative_reductions(h1),
        'robustness': robustness,
        'reproduction': {'matched_D1_aggregates': checks, 'same_N10_matrix': h1.matrix.digest,
                         'H1_original_CI_reproduced': True},
        'inputs': [handoff_pin, original_pin, bundle_pin], 'code': code_pins,
        'limits': ['conservative non-supported includes uncertain and selected missing, not just false statements',
                   'N10 cost-stopped inclusion is approximate; bootstrap does not remove selection bias',
                   'N14 availability is not random source sampling',
                   'standardized missing structural type is undefined, never imputed',
                   'mix remainder is arithmetic and also depends on source/type aggregation, not a causal attribution',
                   'no new model, source, or annotation, and no independently proven semantic truth']}
    private_output = Path(private_output)
    np.savez_compressed(private_output/'paired-H1-replicates.private.npz',
                        estimates=h1.replicates['estimate'], cells=np.array(h1.cells))
    save(output, result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', required=True, type=Path)
    p.add_argument('--original-analysis', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--private-output', required=True, type=Path)
    args = p.parse_args()
    result = run(args.bundle, args.original_analysis, args.output, args.private_output)
    print(json.dumps({'output': str(args.output), 'reused_N10_matrix': result['reproduction']['same_N10_matrix'],
                      'model_calls': 0}, ensure_ascii=False))
