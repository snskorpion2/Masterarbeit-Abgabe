"""Nachträglich, explorativ: CPU projection of saved VV removals only."""
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
import argparse
import json

from Experiments.fair_v2_oct24.C1 import catalog
from Experiments.fair_v2_oct24.C1 import projection as c1


PROTOCOL = 'X3-confirmation24-VV-only-projection-v1'
CLASSIFICATION = 'nachträglich, explorativ'
PRIVATE = (Path.home() / 'withheld-artifact/e039ce5721ab39ed67f1'
           / 'LocalCache/Local/Masterarbeit-private-evidence')
B3_INDEX_PIN = {'path': str(PRIVATE / '2026-10-25-B3-final-technical-verification-v1'
                          / 'completed-cells-final.private.json'), 'bytes': 601305,
                'sha256': 'bd64f11d9e174f077ea23a22452087f47b4ede42b47b96e6308fa39eb1980a10'}
C1_ROSTER_PIN = {'path': str(PRIVATE / '2026-10-25-C1-confirmation-guard-final-audit-v1'
                           / 'parents.private.json'), 'bytes': 763439,
                 'sha256': '4908b116be78da64262ae42b17acde7493cd1bbf9505dfb530916c462fd0d8bb'}


class X3ProjectionError(ValueError):
    """Technical codes only; no source values in exceptions."""


def need(ok, code):
    if not ok:
        raise X3ProjectionError(code)


def _bytes(value):
    return catalog._bytes(value)


def _read(pin):
    return catalog._read(pin)


def _save(path, value):
    return catalog._save(path, value)


def project_bound_parent(bound, stored_result):
    """Restrict an unchanged saved removal decision; never call a guard."""
    inv = bound['inventory']
    need(bound['parent_id'] == inv['cell_id'] == stored_result['parent_id'], 'X3_PARENT_ID_DIFFERS')
    need(inv['removed_ids'] == [] and inv['records'] == inv['origin']['records'],
         'X3_FILTERED_PARENT_FORBIDDEN')
    try:
        units = c1._unit_map(inv, bound['global_unit_sidecar'])
    except (KeyError, TypeError, ValueError):
        raise X3ProjectionError('X3_ORIGINAL_GLOBAL_MAPPING_INVALID') from None
    inverse = {record['record_id']: uid for uid, record in units.items()}
    original = [inverse[record['record_id']] for record in inv['origin']['records']]
    need(all(units[u]['category'] in {'EE', 'EV', 'VV'} for u in original), 'X3_NATIVE_CATEGORY_INVALID')
    need(all(catalog.native.digest(units[u]['value']) == units[u]['value_sha256'] for u in original),
         'X3_ORIGINAL_VALUE_HASH_DIFFERS')
    removed = stored_result['removed_ids']
    records = stored_result['removals']
    need(type(removed) is list and all(type(u) is str for u in removed)
         and len(removed) == len(set(removed)) and set(removed) <= set(units),
         'X3_SAVED_REMOVAL_IDS_INVALID')
    need(type(records) is list and [r['record']['id'] for r in records] == removed,
         'X3_SAVED_REMOVAL_ORDER_DIFFERS')
    for item in records:
        record = item['record']; expected = units[record['id']]
        need(record['category'] == expected['category'], 'X3_SAVED_REMOVAL_CATEGORY_DIFFERS')
        need(record['category'] in {'EE', 'VV'}, 'X3_EV_REMOVAL_FORBIDDEN')
        need(record == {'id': record['id'], 'category': expected['category'], 'value': expected['value']},
             'X3_SAVED_REMOVAL_VALUE_DIFFERS')
    selected = set(removed)
    full_removed = [u for u in original if u in selected]
    vv = [u for u in full_removed if units[u]['category'] == 'VV']
    ee = [u for u in full_removed if units[u]['category'] == 'EE']
    need(set(full_removed) == set(vv) | set(ee) and not (set(vv) & set(ee)), 'X3_REMOVAL_PARTITION_INVALID')
    kept = [u for u in original if u not in set(vv)]
    full_kept = [u for u in original if u not in selected]
    projected = c1.project_parent(inv, bound['schema'], bound['graph'], bound['global_unit_sidecar'], vv)
    wanted = [units[u] for u in kept]
    protected = [units[u] for u in original if units[u]['category'] in {'EE', 'EV'}]
    for kind in ('original', 'relation_rows'):
        actual = projected[kind]['bound']['inventory']['records']
        need(_bytes(actual) == _bytes(wanted), 'X3_PROJECTED_OCCURRENCES_DIFFER')
        need(_bytes([r for r in actual if r['category'] in {'EE', 'EV'}]) == _bytes(protected),
             'X3_EE_EV_CONTENT_OR_ORDER_CHANGED')
    need(projected['original']['bound']['inventory'] == projected['relation_rows']['bound']['inventory'],
         'X3_EXPORT_MEMBERSHIPS_DIFFER')
    need(projected['proof']['removed_global_ids'] == vv and projected['proof']['kept_global_ids'] == kept,
         'X3_PROJECTED_GLOBAL_IDS_DIFFER')
    membership = {'original_unit_ids': original,
        'categoriesByUnitId': {u: units[u]['category'] for u in original},
        'original_values_sha256_by_unit_id': {u: units[u]['value_sha256'] for u in original},
        'full_removed_ids': full_removed, 'full_kept_ids': full_kept,
        'vv_removed_ids': vv, 'ee_restored_ids': ee, 'kept_ids': kept,
        'counts': {'original': len(original), 'full_removed': len(full_removed),
            'full_kept': len(full_kept), 'vv_removed': len(vv), 'ee_restored': len(ee), 'kept': len(kept)},
        'counts_by_category': {'original': dict(Counter(units[u]['category'] for u in original)),
            'kept': dict(Counter(units[u]['category'] for u in kept))},
        'EE_EV_byte_content_and_order_unchanged': True, 'both_exports_share_identical_membership': True}
    return {'projection': projected, 'membership': membership}


def _slot(value, *, index=False):
    return (value['source' if index else 'source_id'], catalog._arm(value['arm']), catalog._draw(value['draw']))


def _expected_slots():
    fresh = [f'A4-F{i:02d}' for i in range(1, 9)] + [f'A4-W{i:02d}' for i in range(1, 13)]
    return {(s, a, f'draw_{d}') for s in fresh + sorted(catalog.SEALED_IDS)
            for a in ('AS', 'V1') for d in ((1, 2) if s in catalog.SEALED_IDS else (1, 2, 3))}


def _validate_inputs(index, roster):
    expected = _expected_slots()
    need(type(roster) is list and len(roster) == len(expected)
         and {_slot(r) for r in roster} == expected, 'X3_EXACT_CONFIRMATION_ROSTER_REQUIRED')
    need(len({r['parent_id'] for r in roster}) == len(roster)
         and all(r['population'] in {'fresh20', 'sealed4'} for r in roster), 'X3_PARENT_SCOPE_INVALID')
    entries = index['completed_cells']
    need(index['protocol'] == 'B3-technical-completed-cell-index:v2'
         and index['completed_count'] == len(entries) == len(expected)
         and {_slot(e, index=True) for e in entries} == expected, 'X3_EXACT_FINAL_B3_INDEX_REQUIRED')
    by_id = {e['cell_id']: e for e in entries}
    need(len(by_id) == len(entries) and set(by_id) == {r['parent_id'] for r in roster},
         'X3_B3_C1_PARENT_ROSTERS_DIFFER')
    return by_id


def _saved_input(row, descriptor):
    stored, segment, parent = (_read(row[key]) for key in ('result_pin', 'segment_pin', 'input_pin'))
    need(stored['segment_pin'] == row['segment_pin'] and segment['input_pin'] == row['input_pin'],
         'X3_ORIGINAL_GUARD_PINS_DIFFER')
    need(stored['parent_id'] == parent['parent_id'] == segment['parent_id'] == row['parent_id']
         and stored['shared_guard_id'] == segment['shared_guard_id'] == row['shared_guard_id'],
         'X3_ORIGINAL_GUARD_PARENT_DIFFERS')
    need(stored['descriptor'] == segment['descriptor'] == parent['descriptor'],
         'X3_ORIGINAL_GUARD_DESCRIPTOR_DIFFERS')
    old = parent['descriptor']
    need(_slot(old) == _slot(descriptor) == _slot(row)
         and old['native_rows_pin']['sha256'] == descriptor['native_rows_pin']['sha256']
         and old['native_rows_pin']['bytes'] == descriptor['native_rows_pin']['bytes'],
         'X3_ORIGINAL_NATIVE_OWNER_DIFFERS')
    return stored, parent


def run_projection(output_dir, *, b3_index_pin=B3_INDEX_PIN, c1_roster_pin=C1_ROSTER_PIN):
    """Materialize the fixed 136-parent confirmation roster, serially, once."""
    output = Path(output_dir).resolve()
    repo = Path(__file__).resolve().parents[1]
    need(not output.exists() and not output.is_relative_to(repo), 'X3_FRESH_PRIVATE_OUTPUT_REQUIRED')
    index, roster = _read(b3_index_pin), _read(c1_roster_pin)
    by_id = _validate_inputs(index, roster)
    code = [catalog.pin(path) for path in (__file__, Path(__file__).with_name('test_projection.py'),
        catalog.__file__, c1.__file__, c1.a8.__file__, catalog.b3.__file__,
        catalog.native.__file__, c1.sdk_schema_cpu.__file__, c1.export_control.__file__)]
    protocol_pin = catalog.pin(Path(__file__).with_name('PROTOKOLL.md'))
    output.mkdir(parents=True, exist_ok=False)
    parents, all_ids = [], set()
    summary = {'parents': 0, 'sources': len({r['source_id'] for r in roster}),
        'source_draw_pairs': len({(_slot(r)[0], _slot(r)[2]) for r in roster}),
        'original': 0, 'full_removed': 0, 'full_kept': 0, 'vv_removed': 0, 'ee_restored': 0, 'kept': 0,
        'by_arm': {a: Counter() for a in ('AS', 'V1')}, 'new_model_calls': 0, 'new_guard_evaluations': 0,
        'new_schema_induction': False, 'export_views_are_not_additional_arms': True}
    try:
        for ordinal, row in enumerate(roster, 1):
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                entry = by_id[row['parent_id']]
                descriptor = catalog._b3_ready_descriptor(entry, b3_index_pin)
                stored, original_parent = _saved_input(row, descriptor)
                bound = catalog.load_bound_parent(descriptor)
                need(not ({u['unit_id'] for u in bound['global_unit_sidecar']['units']} & all_ids),
                     'X3_DUPLICATE_GLOBAL_UNIT_ACROSS_PARENTS')
                derived = project_bound_parent(bound, stored)
                member = derived['membership']
                original_guard = [{'id': uid, 'category': record['category'], 'value': record['value']}
                    for uid, record in zip(member['original_unit_ids'], bound['inventory']['origin']['records'], strict=True)]
                need(_bytes(original_guard) == _bytes(original_parent['guard_inventory']),
                     'X3_ORIGINAL_GUARD_VALUES_OR_ORDER_DIFFER')
                all_ids.update(member['original_unit_ids'])
                encoded = c1.jsonable_projection(derived['projection'])
                arm = _slot(row)[1]; name = 'AS+G(VV)' if arm == 'AS' else 'V1+G(VV)'
                folder = output / 'parents' / f'{ordinal:03d}'
                views = {kind: _save(folder/(kind+'.private.json'), {'protocol': PROTOCOL,
                    'classification': CLASSIFICATION, 'parent_id': row['parent_id'], 'derived_arm': name,
                    'view': kind, 'projection': encoded[kind], 'proof': encoded['proof']})
                    for kind in ('original', 'relation_rows')}
                member.update({k: row[k] for k in ('parent_id', 'source_id', 'draw', 'arm')})
                member.update(derived_arm=name, classification=CLASSIFICATION, result_pin=row['result_pin'],
                    input_pin=row['input_pin'], segment_pin=row['segment_pin'],
                    bound_manifest_pin=entry['bound_manifest_pin'], native_rows_pin=descriptor['native_rows_pin'],
                    global_unit_id_sidecar_pin=entry['global_unit_id_sidecar_pin'],
                    original_projection_pin=views['original'], row_projection_pin=views['relation_rows'])
                parents.append(member)
                for key, count in member['counts'].items():
                    summary[key] += count
                    summary['by_arm'][arm][key] += count
                summary['parents'] += 1
            print(json.dumps({'projected_parents': ordinal, 'total_parents': len(roster), 'new_model_calls': 0}), flush=True)
        summary['by_arm'] = {a: dict(v) for a, v in summary['by_arm'].items()}
        membership = {'protocol': PROTOCOL, 'classification': CLASSIFICATION,
            'scope': '24_confirmation_sources_only; excludes_Main12_and_MuSiQue', 'population_complete': True,
            'B3_final_index_pin': b3_index_pin, 'C1_parent_roster_pin': c1_roster_pin,
            'protocol_pin': protocol_pin, 'code_pins': code, 'parents': parents, 'summary': summary}
        membership_pin = _save(output/'membership.private.json', membership)
        need(_read(membership_pin) == membership, 'X3_MEMBERSHIP_READBACK_DIFFERS')
        manifest_pin = _save(output/'projection_manifest.private.json', {'protocol': PROTOCOL,
            'classification': CLASSIFICATION, 'membership_pin': membership_pin, 'summary': summary,
            'input_pins': [b3_index_pin, c1_roster_pin, protocol_pin], 'code_pins': code,
            'original_AS_V1_ASG_V2_unchanged': True, 'semantic_quality_claimed': False})
        return {'membership_pin': membership_pin, 'manifest_pin': manifest_pin, 'summary': summary}
    except BaseException as error:
        _save(output/'failure.private.json', {'protocol': PROTOCOL, 'classification': CLASSIFICATION,
            'completed_parents': len(parents), 'error_class': type(error).__name__,
            'technical_code': str(error) if isinstance(error, X3ProjectionError) else None,
            'automatic_resume': False, 'new_model_calls': 0})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_projection(args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
