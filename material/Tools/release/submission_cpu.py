"""Isolated synthetic D1 demonstration using the exported public contract.

This separate adapter never replaces D1's original G2 hash gate. No natural
inputs, providers or referenced private artifacts are opened.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from Tools.release.check_submission_safety import scan_submission, strict_json
    manifest = strict_json((root/'MANIFEST.json').read_bytes())
    checked = scan_submission(root, manifest)
    if not checked['passed']:
        raise ValueError('Package integrity/privacy check failed; inspect rule-only report')
    if args.output.exists():
        raise FileExistsError('Choose a new synthetic output directory')
    from Experiments.fair_v2_oct24.D1.run import software_versions
    from Experiments.fair_v2_oct24.D1.synthetic import build_native_fixture
    from Experiments.fair_v2_oct24.D1.native import normalize_native
    from Experiments.fair_v2_oct24.D1.analysis import analyze
    contract_path = root/'protocols/analysis_contract.public.json'
    contract = strict_json(contract_path.read_bytes())
    versions = software_versions()
    for name in ('python','numpy','scipy'):
        if versions[name] != contract['expected_versions'][name]:
            raise ValueError('Frozen software version mismatch: '+name)
    native = build_native_fixture(20261025, sources=contract['sources'], qa_blocks=contract['qa_blocks'])
    native['question_ids'] = list(contract['question_ids'])
    report = analyze(normalize_native(native), contract)
    if report['synthetic'] is not True:
        raise ValueError('Synthetic demonstration must remain synthetic')
    args.output.mkdir(parents=True)
    (args.output/'analysis.synthetic.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    receipt = {'status':'synthetic_only_complete','model_calls':0,'natural_inputs_opened':False,
        'original_G2_bytes_delivered':False,'public_contract_sha256':hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        'software':versions,'metadata':report['metadata']}
    (args.output/'result.synthetic.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'model_calls':0,'sources':report['metadata'].get('sources')}))
    return receipt


if __name__ == '__main__':
    main()
