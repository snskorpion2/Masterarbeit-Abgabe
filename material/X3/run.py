"""Explicit CPU-only X3 execution; nachträglich, explorativ.

Read only the bound C2 export, saved projection membership, fixed H12 sample,
and existing D1a H1 result. No provider client or H2/QA data loader is used.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
from pathlib import Path

from Experiments.fair_v2_oct24.D1 import contract, native, n10_sampling, inference
from X3 import analysis, author


ROOT = Path(__file__).resolve().parents[1]
D1A = ROOT / 'Experiments/fair_v2_oct24/D1/vorlauf_ohne_H4'
D1A_SHA256 = 'b5c3ee325c300c4307c6414264eef892408486d54ca4c222c8a53cb61c3bce4c'
C2_SHA256 = '1dc354b2c480936f205975e65eb926109e09f4f16ab4d9ae6e566e295bc3fafb'


def pin(path):
    path = Path(path).absolute()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha256(data).hexdigest()}


def read_bound(binding):
    """Verify exact bytes before decoding; never infer a missing input."""
    found = pin(binding['path'])
    if found != {k: binding[k] for k in ('path', 'bytes', 'sha256')}:
        raise ValueError('X3_BOUND_INPUT_CHANGED')
    return json.loads(Path(binding['path']).read_bytes())


def public_pin(binding):
    return {k: binding[k] for k in ('bytes', 'sha256')}


def validate_projection_header(membership):
    if (membership.get('protocol') != 'X3-confirmation24-VV-only-projection-v1'
            or membership.get('population_complete') is not True
            or membership.get('classification') != analysis.CLASSIFICATION):
        raise ValueError('X3_COMPLETE_EXPLORATORY_PROJECTION_REQUIRED')


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('w', encoding='utf8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def reference_h1_matches(result, original):
    names = {'AS': 'AS_ORIGINAL', 'AS+G': 'AS_G_ORIGINAL',
             'V1': 'V1_ORIGINAL', 'V2': 'V2_ORIGINAL'}
    for name, cell in names.items():
        matches = [row for row in original['cells']
                   if row.get('cell') == cell and row.get('endpoint') == 'H1']
        if len(matches) != 1:
            raise ValueError('X3_D1A_UNIQUE_H1_REFERENCE_REQUIRED')
        previous, current = matches[0]['estimate'], result['cells'][name]['H1']['estimate']
        if previous is None or current is None or abs(previous - current) > 1e-15:
            raise ValueError('X3_EXISTING_H1_POINT_ESTIMATE_CHANGED')
    return True


def execute(membership_pin, handoff_path, private_output, *, output=ROOT / 'X3/result.json'):
    private_output = Path(private_output).absolute()
    output = Path(output).absolute()
    if private_output == ROOT or private_output.is_relative_to(ROOT):
        raise ValueError('X3_PRIVATE_EVIDENCE_MUST_REMAIN_OUTSIDE_REPOSITORY')
    if output.exists() or (private_output / 'execution.private.json').exists():
        raise ValueError('X3_EXPLICIT_OUTPUT_MUST_NOT_ALREADY_EXIST')
    code = {str(path.relative_to(ROOT)).replace('\\', '/'): pin(path) for path in
            [Path(analysis.__file__), Path(author.__file__), Path(__file__),
             ROOT / 'X3/projection.py', ROOT / 'X3/PROTOKOLL.md',
             Path(n10_sampling.__file__), Path(inference.__file__)]}
    adapter_sha = sha256(inspect.getsource(native._c2).encode('utf8')).hexdigest()

    d1a_pin = pin(D1A / 'analysis.json')
    if d1a_pin['sha256'] != D1A_SHA256:
        raise ValueError('X3_UNCHANGED_D1A_REFERENCE_REQUIRED')
    original = read_bound(d1a_pin)
    manifest_pin = pin(D1A / 'input-manifest.json')
    manifest = read_bound(manifest_pin)
    c2_pin = manifest['inputs']['C2']
    if c2_pin['sha256'] != C2_SHA256:
        raise ValueError('X3_FROZEN_C2_EXPORT_REQUIRED')
    c2 = read_bound(c2_pin)
    membership = read_bound(membership_pin)
    validate_projection_header(membership)
    parents = membership['parents']
    sources = contract.load_contract()['sources']
    rows, inventories = native._c2(c2, {s['source_id']: s for s in sources})
    reference, variant = analysis.prepare_bundles(rows, inventories, sources,
                                                  c2['sampling'], parents)

    handoff_pin = pin(handoff_path)
    handoff = read_bound(handoff_pin)
    if handoff.get('H12_author_confirmed') is not True or handoff.get('H12_annotation_origin') != 'human_ui_input':
        raise ValueError('X3_CONFIRMED_ORIGINAL_H12_AUTHOR_EXPORT_REQUIRED')
    author_pins = {name: handoff[name] for name in
                   ('H12_key_pin', 'H12_author_original_pin', 'H12_frozen_sample_pin')}
    key = read_bound(author_pins['H12_key_pin'])
    annotations = read_bound(author_pins['H12_author_original_pin'])
    # Bind the unchanged fixed sample without opening a new sampling route.
    read_bound(author_pins['H12_frozen_sample_pin'])
    h12_result_pin = pin(ROOT / handoff['H12_result_public'])
    if h12_result_pin['sha256'] != handoff['H12_result_sha256']:
        raise ValueError('X3_UNCHANGED_H12_PUBLIC_RESULT_REQUIRED')
    author_result = author.summarize_author(key, annotations, parents)
    result = analysis.estimate_h1(reference, variant, parents,
        draws=10000, seed=2026102407,
        expected_matrix_sha256=original['N10_H1_sampling']['source_group_matrix_sha256'])
    reference_h1_matches(result, original)

    inputs = {'D1a_H1_reference': d1a_pin, 'D1a_input_manifest': manifest_pin,
              'C2_original_export': c2_pin, 'X3_VV_only_membership': membership_pin,
              'H12_handoff': handoff_pin, **author_pins, 'H12_public_result': h12_result_pin,
              'G2_source_contract': pin(contract.G2)}
    result.update({'protocol': 'X3-post-hoc-VV-only-filter:v1',
        'created_UTC': datetime.now(timezone.utc).isoformat(), 'synthetic': False,
        'H12_fixed_sample': author_result,
        'H2': {'new_cells': ['AS+G(VV)', 'V1+G(VV)'],
               'status': 'nicht bewertet; nicht geschätzt', 'estimate': None,
               'classification': analysis.CLASSIFICATION},
        'validation': {'existing_four_D1a_H1_point_estimates_unchanged': True,
                       'D1a_source_group_matrix_unchanged': True,
                       'C2_codes_statuses_selection_and_values_inherited': True,
                       'no_statistical_hypothesis_test_called': True,
                       'main_V2_and_tests_unchanged': True},
        'resources': {'new_model_calls': 0, 'new_provider_requests': 0,
                      'new_external_judgments': 0, 'incremental_provider_cost_USD': 0},
        'input_pins': {name: public_pin(binding) for name, binding in inputs.items()},
        'code_pins': {name: public_pin(binding) for name, binding in code.items()},
        'D1_native_H1_adapter_function_sha256': adapter_sha,
        'limitations': [
            'Nachträglich, explorativ und hypothesenbildend; ausgelöst durch bekannte H12-Befunde.',
            'H1 bezeichnet das gesamte erhaltene Inventar einschließlich EE und EV, nicht nur VV.',
            'N10: kostenbedingt gestopptes C2-Präfix; gleiche Einschlusswahrscheinlichkeiten nicht nachgewiesen.',
            'Nicht ausgewählte Aussagen bleiben nicht ausgewählt; technische Fehlwerte bleiben separat ausgewiesen und werden nach N10 konservativ bewertet.',
            'Konfidenzintervalle sind marginal und ohne Tests, Multiplizitätskorrektur oder Entscheidungsgrenze.',
            'H12 ist eine feste, gezielt geschichtete Entwicklungsstichprobe; keine Prävalenz- oder unabhängige Bestätigungsschätzung.',
            'H2 ist für die neuen Zellen weder bewertet noch geschätzt.',
            'Kein Eingang in Haupttests oder Gesamturteil, keine Änderung an V2.']})
    # Recheck actual consumed inputs after computation, before publishing aggregates.
    for binding in [*inputs.values(), *code.values()]:
        if pin(binding['path']) != {k: binding[k] for k in ('path', 'bytes', 'sha256')}:
            raise ValueError('X3_INPUT_CHANGED_DURING_CPU_ANALYSIS')
    if sha256(inspect.getsource(native._c2).encode('utf8')).hexdigest() != adapter_sha:
        raise ValueError('X3_NATIVE_H1_ADAPTER_CHANGED_DURING_CPU_ANALYSIS')
    write_json(output, result)
    result_pin = pin(output)
    if read_bound(result_pin) != result:
        raise ValueError('X3_PUBLIC_RESULT_READBACK_DIFFERS')
    write_json(private_output / 'execution.private.json', {
        'classification': analysis.CLASSIFICATION, 'inputs': inputs, 'code': code,
        'result_pin': result_pin, 'new_model_calls': 0})
    return result


def main():
    parser = argparse.ArgumentParser(description='X3: nachträglich, explorativ; CPU only')
    parser.add_argument('--membership-pin', required=True, type=Path,
                        help='Explicit JSON pin (path/bytes/sha256), not discovery')
    parser.add_argument('--h12-handoff', required=True, type=Path)
    parser.add_argument('--private-output', required=True, type=Path)
    args = parser.parse_args()
    result = execute(json.loads(args.membership_pin.read_bytes()), args.h12_handoff,
                     args.private_output)
    print(json.dumps({'classification': result['classification'], 'scope': result['scope'],
                      'new_model_calls': 0, 'result': 'X3/result.json'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
