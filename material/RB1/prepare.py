"""Reproduce the text-free private RB1 input projection, without model calls."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from Experiments.fair_v2_oct24.D1.contract import load_contract
from Experiments.fair_v2_oct24.D1.run import load_explicit_manifest
from Experiments.fair_v2_oct24.D1.native import normalize_native


def project(manifest_path):
    repo = Path(__file__).resolve().parents[1]
    handoff = json.loads((repo/'Experiments/fair_v2_oct24/D1/final_native_oct26_v1/result.json').read_bytes())
    if sha256(Path(manifest_path).read_bytes()).hexdigest() != handoff['input_manifest_sha256']:
        raise ValueError('The final D1 input manifest is required')
    native, receipt = load_explicit_manifest(manifest_path, load_contract(), allow_real=True)
    normalized = normalize_native(native)
    keys = ['protocol', 'synthetic', 'sources', 'cells', 'H1', 'H1_inventories',
            'H1_sampling', 'H2', 'H2_roster']
    result = {key: normalized[key] for key in keys}
    keep = ['source_id', 'draw', 'cell', 'unit_id', 'category', 'raw_code',
            'measurement_status', 'selection_status']
    result['H1'] = [{key: row[key] for key in keep if key in row} for row in result['H1']]
    return result, receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--private-output', required=True, type=Path)
    args = p.parse_args()
    # A supplied existing directory is allowed, but original files are never overwritten.
    result, receipt = project(args.manifest)
    args.private_output.mkdir(parents=True, exist_ok=True)
    for name, value in [('bundle.private.json', result), ('input-receipt.private.json', receipt)]:
        target = args.private_output/name
        if target.exists():
            raise ValueError('Refusing to overwrite the original RB1 input: ' + name)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'private_output_written': True, 'model_calls': 0}))
