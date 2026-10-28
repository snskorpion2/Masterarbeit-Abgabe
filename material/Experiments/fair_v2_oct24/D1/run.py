"""Explicit D1 runner. The default creates and analyzes SYNTHETIC inputs only.

No automatic discovery of live/private inputs, no network and no model imports.
Later empirical use needs both an explicit manifest and --allow-real-inputs.
Every input is byte-hash verified before parsing; G2 references are never followed.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform

from .contract import load_contract, pin
from .native import normalize_native, validate_current_author_binding
from .synthetic import build_native_fixture

HERE = Path(__file__).resolve().parent
INPUTS = {'C1', 'C1_proof_values', 'C2', 'C3', 'C5', 'C6', 'C6_controls',
          'C7', 'C4', 'effort', 'K2_effort_csv', 'semantic_pairs', 'construction_diagnostics'}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def load_explicit_manifest(path, contract, *, allow_real=False):
    """Read only exact pinned input containers; no automatic discovery.

    The manifest itself is the explicit input selection. The caller must opt
    in before even opening it. An empirical manifest cannot claim synthetic.
    C1 proof pins may be followed ONLY via explicit from_C1_index_pins=True.
    Other embedded paths are never followed. Nested pin maps assemble C7
    key/annotations and C6 empty/gold controls without changing their formats.
    """
    if allow_real is not True:
        raise ValueError('Explicit --allow-real-inputs required before reading an input manifest')
    path = Path(path).resolve()
    manifest = json.loads(path.read_text(encoding='utf8'))
    if manifest.get('protocol') != 'D1-explicit-input-manifest-v1' or manifest.get('synthetic') is not False:
        raise ValueError('Empirical manifest protocol/data-origin flag required')
    if manifest.get('G2_sha256') != contract['frozen_pin']['sha256']:
        raise ValueError('Manifest G2 binding differs')
    files = manifest['inputs']
    if not {'C1','C1_proof_values','C2','C3','C5','C6'} <= set(files) <= INPUTS:
        raise ValueError('Explicit required/known native inputs only')
    receipts = []
    def read(item, *, csv=False):
        target = (path.parent / item['path']).resolve()
        raw = target.read_bytes()
        digest = sha256(raw).hexdigest()
        if digest != item['sha256'] or ('bytes' in item and item['bytes'] != len(raw)):
            raise ValueError('Input byte hash mismatch: '+str(target))
        receipts.append({'path': str(target), 'sha256': digest, 'bytes': len(raw)})
        if csv:
            from .efficiency import parse_k2_csv
            return parse_k2_csv(raw.decode('utf-8-sig'))
        return json.loads(raw)
    def tree(spec):
        if type(spec) is dict and {'path','sha256'} <= set(spec) <= {'path','sha256','bytes'}:
            return read(spec)
        if type(spec) is dict:
            return {key: tree(value) for key, value in spec.items()}
        raise ValueError('Only an explicit pinned-file tree is accepted')
    bundle = {'synthetic': False, 'sources': contract['sources'],
              'QA_blocks': contract['qa_blocks'], 'question_ids': contract['question_ids']}
    bundle['C1'] = tree(files['C1'])
    for key, spec in files.items():
        if key == 'C1':
            continue
        if key == 'C1_proof_values':
            bundle[key] = {}
            if spec == {'from_C1_index_pins': True}:
                pinned = {p['proof_pin']['sha256']: p['proof_pin'] for p in bundle['C1']['proofs']}
            else:
                pinned = spec
            for digest, item in pinned.items():
                if digest != item['sha256']:
                    raise ValueError('C1 proof-map key must be its original file-byte hash')
                bundle[key][digest] = read(item)
        elif key == 'K2_effort_csv':
            bundle['K2_effort'] = read(spec, csv=True)
        else:
            bundle[key] = tree(spec)
    if 'C7' in bundle and 'current_carrier' in bundle['C7']:
        validate_current_author_binding(bundle['C7'], c2_sha256=files['C2']['sha256'])
        expected = bundle['C7']['public_result']['D1_interface']['private_original_nominal_carrier_pin']
        actual = files['C7']['current_carrier']
        if any(actual[field] != expected[field] for field in ('sha256','bytes')):
            raise ValueError('Current C7 carrier bytes differ from the public end binding')
    return bundle, {'manifest': pin(path), 'input_files': receipts}


def software_versions():
    return {'python': platform.python_version(), 'numpy': version('numpy'), 'scipy': version('scipy'),
            'matplotlib': version('matplotlib')}


def implementation_receipt(contract, input_receipt, versions):
    for package in ('python', 'numpy', 'scipy'):
        if versions[package] != contract['expected_versions'][package]:
            raise ValueError('Frozen software version mismatch for '+package)
    return {'protocol': 'D1-implementation-receipt-v1',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'G2': contract['frozen_pin'], 'amendments': contract['amendments'],
        'N8_publication': contract['N8_publication_pin'],
        'N10_publication': contract['N10_publication_pin'],
        'N14_publication': contract['N14_publication_pin'],
        'C4_sampling_amendment': contract['second_evaluator_sampling_amendment_pin'],
        'code': [pin(p) for p in sorted(HERE.glob('*.py'))],
        'software': versions, 'inputs': input_receipt,
        'receipt_written_before_analysis': True, 'no_outcome_tuning': True,
        'interpretations_fixed_before_natural_inputs': {
            'N14_H2_missingness': ('G2 primary estimates and Holm family remain unchanged. '
                'Additionally analyze H2/K2/K4/K5 on sources with valid judgments in both respective contrast arms; '
                'retain within-source G2 missingness and fixed reference denominators. '
                'H2/K2/K4 noninferiority requires Holm confirmation in both analyses; '
                'report H2/K5 superiority only if confirmed in the additional analysis. '
                'No rerating, replay, outcome-based source selection or other reweighting.'),
            'Wilcoxon': 'Round absolute shifted differences to 12 decimals for ranks only; exact unrounded signs/zeros. Fixed +1 Monte Carlo correction.',
            'missing_QA': 'Keep planned Q60; null primary test when any primary score is missing.',
            'N2_H3': 'Two unchanged A6 fields, separate denominators, no whole-statement H3 test.',
            'distinct': 'NFC string values only; pooled AS/V1 deterministic human-confirmed clique groups.'}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE/'synthetic_output')
    parser.add_argument('--seed', type=int, default=20261025)
    parser.add_argument('--input-manifest', type=Path)
    parser.add_argument('--allow-real-inputs', action='store_true')
    parser.add_argument('--without-figures', action='store_true', help='Analysis JSON only, for CPU test pipelines')
    args = parser.parse_args(argv)
    if args.allow_real_inputs and args.input_manifest is None:
        parser.error('--allow-real-inputs also requires an explicit --input-manifest')
    # Never overwrite an output: it is an immutable binding of code and inputs.
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError('Choose a new output directory; existing outputs are preserved: '+str(output))
    contract = load_contract()
    if args.input_manifest:
        native, inputs = load_explicit_manifest(args.input_manifest, contract, allow_real=args.allow_real_inputs)
    else:
        native = build_native_fixture(args.seed, sources=contract['sources'], qa_blocks=contract['qa_blocks'])
        native['question_ids'] = list(contract['question_ids'])
        inputs = {'origin': 'synthetic generated in memory', 'seed': args.seed,
                  'natural_outputs_opened': False, 'model_calls': 0}
    normalized = normalize_native(native)
    versions = software_versions()
    receipt = implementation_receipt(contract, inputs, versions)
    output.mkdir(parents=True)
    # Bind the actual fixture before executing the first analysis.
    if native['synthetic']:
        write_json(output/'native_synthetic.json', native)
        inputs['native_fixture'] = pin(output/'native_synthetic.json')
    write_json(output/'implementation_receipt.json', receipt)
    from .analysis import analyze
    report = analyze(normalized, contract)
    write_json(output/'analysis.json', report)
    artifacts = [output/'analysis.json', output/'implementation_receipt.json']
    from .required_outputs import build_requested_summary, emit
    artifacts.extend(Path(p) for p in emit(build_requested_summary(report), output/'requested_outputs'))
    if not args.without_figures:
        from .render import render
        artifacts.extend(Path(p) for p in render(report, output, allow_real=args.allow_real_inputs))
    # Detect an edit during analysis/rendering; never report a mixed version.
    for code in receipt['code']:
        if pin(code['path'])['sha256'] != code['sha256']:
            raise ValueError('D1 implementation changed during execution')
    result = {'protocol': 'D1-run-result-v1', 'synthetic': report['synthetic'],
        'status': 'synthetic_complete' if report['synthetic'] else 'empirical_complete',
        'G2_sha256': contract['frozen_pin']['sha256'],
        'natural_outputs_opened': not report['synthetic'], 'model_calls': 0,
        'counts': report['metadata'], 'artifacts': [pin(p) for p in artifacts],
        'implementation_receipt': pin(output/'implementation_receipt.json')}
    write_json(output/'result.json', result)
    print(json.dumps({'status': result['status'], 'output': str(output), 'artifacts': len(artifacts)}, ensure_ascii=False))
    return result


if __name__ == '__main__':
    main()
