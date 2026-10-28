"""Pinned-loader negative tests on tiny artificial files only."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from Experiments.fair_v2_oct24.D1 import run
from Experiments.fair_v2_oct24.D1.contract import load_contract


def store(path, value):
    path.write_text(json.dumps(value),encoding='utf8')
    return {'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}


def tiny_manifest(tmp_path):
    proof=store(tmp_path/'artificial-proof.json',{'synthetic':True,'proof':'invented'})
    c1=store(tmp_path/'artificial-index.json',{'proofs':[{'proof_pin':proof}]})
    unit=store(tmp_path/'artificial-container.json',{'synthetic':True})
    manifest={'protocol':'D1-explicit-input-manifest-v1','synthetic':False,
              'G2_sha256':run.load_contract()['frozen_pin']['sha256'],
              'inputs':{'C1':c1,'C1_proof_values':{'from_C1_index_pins':True},
                        **{key:unit for key in ('C2','C3','C5','C6')},
                        'C7':{'key':unit,'annotations':unit}}}
    path=tmp_path/'manifest.json';store(path,manifest)
    return path,manifest,proof


def test_manifest_is_never_read_without_explicit_opt_in(tmp_path):
    with pytest.raises(ValueError,match='allow-real-inputs'):
        run.load_explicit_manifest(tmp_path/'does-not-exist.json',{})


def test_explicit_c1_byte_pins_and_nested_c7_are_supported(tmp_path):
    path,_,proof=tiny_manifest(tmp_path)
    bundle,receipt=run.load_explicit_manifest(path,load_contract(),allow_real=True)
    assert bundle['synthetic'] is False
    assert bundle['C1_proof_values'][proof['sha256']]['proof']=='invented'
    assert bundle['C7']['key']==bundle['C7']['annotations']=={'synthetic':True}
    assert receipt['input_files'] and len(bundle['sources'])==24


def test_byte_corruption_is_rejected_before_json_parse(tmp_path):
    path,_,proof=tiny_manifest(tmp_path)
    Path(proof['path']).write_text('not JSON and not original bytes',encoding='utf8')
    with pytest.raises(ValueError,match='byte hash mismatch'):
        run.load_explicit_manifest(path,load_contract(),allow_real=True)


def test_foreign_g2_and_extra_input_are_rejected(tmp_path):
    path,manifest,_=tiny_manifest(tmp_path)
    altered=deepcopy(manifest);altered['G2_sha256']='0'*64;store(path,altered)
    with pytest.raises(ValueError,match='G2 binding'):
        run.load_explicit_manifest(path,load_contract(),allow_real=True)
    manifest['inputs']['auto_discover_private_sources']={};store(path,manifest)
    with pytest.raises(ValueError,match='known native inputs'):
        run.load_explicit_manifest(path,load_contract(),allow_real=True)


def test_versions_and_implementation_receipt_are_frozen():
    contract=load_contract()
    versions={'python':'3.13.12','numpy':'2.4.4','scipy':'1.17.1','matplotlib':'synthetic-test'}
    receipt=run.implementation_receipt(contract,{'origin':'synthetic'},versions)
    assert receipt['receipt_written_before_analysis'] and receipt['code']
    assert receipt['G2']['sha256']==contract['frozen_pin']['sha256']
    versions['numpy']='0.0'
    with pytest.raises(ValueError,match='software version mismatch'):
        run.implementation_receipt(contract,{},versions)


def test_output_is_not_overwritten_and_no_implicit_real_mode(tmp_path):
    with pytest.raises(FileExistsError):
        run.main(['--output',str(tmp_path)])
    with pytest.raises(SystemExit):
        run.main(['--allow-real-inputs'])


def test_explicit_k2_csv_is_byte_pinned_and_never_auto_discovered(tmp_path):
    import csv
    from io import StringIO
    from Experiments.fair_v2_oct24.D1.efficiency import K2_COLUMNS
    from Experiments.fair_v2_oct24.D1.synthetic import build_k2_effort_fixture
    path, manifest, _ = tiny_manifest(tmp_path)
    stream = StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=K2_COLUMNS)
    writer.writeheader()
    for row in build_k2_effort_fixture():
        writer.writerow({key: '' if value is None else str(value).lower() if type(value) is bool else value
                         for key, value in row.items()})
    csv_path = tmp_path/'invented-k2.csv'
    csv_path.write_text(stream.getvalue(), encoding='utf8')
    manifest['inputs']['K2_effort_csv'] = {'path': str(csv_path), 'bytes': csv_path.stat().st_size,
        'sha256': sha256(csv_path.read_bytes()).hexdigest()}
    store(path, manifest)
    with pytest.raises(ValueError, match='allow-real-inputs'):
        run.load_explicit_manifest(path, load_contract())
    bundle, receipt = run.load_explicit_manifest(path, load_contract(), allow_real=True)
    assert len(bundle['K2_effort']) == 7
    assert bundle['K2_effort'][0]['cost_complete'] is True
    assert any(row['path'] == str(csv_path) for row in receipt['input_files'])
    csv_path.write_text('changed', encoding='utf8')
    with pytest.raises(ValueError, match='byte hash mismatch'):
        run.load_explicit_manifest(path, load_contract(), allow_real=True)
