"""Outcome-blind N16 sampling over completed T1 row-exact inventories."""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import platform
import random

from Experiments.fair_comparison_oct23_v1 import graph_contract as native
from Tools.experiments.c7_human_annotation_oct24_v1 import contracts as c

ROOT = Path(__file__).resolve().parents[1]
T1 = ROOT / 'Experiments/fair_v2_oct24/T1'
N16 = 'Experiments/fair_v2_oct24/G1/nachtrag_16_transfer_menschlich.md'
PROTOCOL = 'H16-N16-T1-human60-v1'
SEED = 2026102616
ARMS = ('AS', 'V2')
TYPES = ('EE', 'EV', 'VV')


def checked(pin):
    raw = Path(pin['path']).read_bytes()
    c.require(len(raw) == pin['bytes'] and sha256(raw).hexdigest() == pin['sha256'],
              'H16 upstream file binding changed')
    return json.loads(raw)


def validate_publication(receipt):
    c.require(receipt['remote_verified'] is True and receipt['changed_paths'] == [N16]
              and len(receipt['commit']) == 40, 'H16 N16 single-path publication required')
    c.require(sha256((ROOT / N16).read_bytes()).hexdigest() == receipt['raw_sha256'],
              'H16 N16 differs from the separately published version')


def load_population():
    """Read explicit T1 completion pins and active row inventories only.

    Guard labels/outcomes are not inspected or used to select candidates.
    No C2/C3/C7 inputs, provider, budget database or reference labels are opened.
    """
    paths = [T1 / name for name in ('result.json', 'construction-result.json',
                                    'final-technical-verification.json')]
    pins = [c.file_pin(path) for path in paths]
    result, constructor, verification = [checked(pin) for pin in pins]
    c.require(result['status'] == 'construction_guard_descriptive_readout_complete'
              and constructor['status'] == 'completed' and verification['passed'] is True,
              'H16 requires the existing completed T1 handoff')
    c.require(verification['result_pin'] == pins[0]
              and verification['guard_completion_pin'] == result['guard_completion_pin'],
              'H16 T1 completion binding differs')
    pins += [constructor['completion_bundle_pin'], result['guard_completion_pin']]
    original, final = [checked(pin) for pin in pins[-2:]]
    source_order = original['source_order']
    c.require(len(source_order) == len(set(source_order)) == 20
              and len(original['cells']) == len(final['parents']) == len(final['exports']) == 40,
              'H16 exact twenty-source T1 scope required')
    source_pins = [cell['source_manifest_pin'] for cell in original['cells']]
    c.require(all(pin == source_pins[0] for pin in source_pins), 'H16 source manifest differs')
    projected = checked(source_pins[0])
    c.require(projected['source_order'] == source_order, 'H16 frozen source order differs')
    manifest = checked(projected['original_A4_manifest_pin'])
    families = {row['source_id']: row['family'] for row in manifest['sources']}
    c.require(Counter(families[sid] for sid in source_order) == {'wikipedia': 12, 'factbook': 8},
              'H16 requires the original twelve/eight fresh-source roster')
    pins += [source_pins[0], projected['original_A4_manifest_pin']]
    expected = {(sid, arm) for sid in source_order for arm in ('AS', 'V1')}
    parents = {(p['source_id'], p['input_arm']): p for p in final['parents']}
    exports = {(e['source_id'], e['input_arm']): e for e in final['exports']}
    c.require(set(parents) == set(exports) == expected, 'H16 incomplete parent/export roster')
    rows, source_hashes = [], {}
    for sid in source_order:
        for input_arm, arm, view, field in (
                ('AS', 'AS', 'input', 'native_inventory'),
                ('V1', 'V2', 'filtered', 'filtered_inventory')):
            parent, export = parents[sid, input_arm], exports[sid, input_arm]
            row_export = checked(export['row_export_pin'])
            pins.append(export['row_export_pin'])
            c.require(row_export['proof']['export_kind'] == 'relation_rows'
                      and row_export['proof']['stable_original_occurrences'] is True,
                      'H16 row-exact occurrence preservation proof required')
            records = row_export[view]['active']['inventory']['records']
            c.require(records == parent[field]['records'],
                      'H16 active row inventory differs from completed T1 cell')
            contexts = parent['source_context']
            c.require(type(contexts) is list and len(contexts) == 1,
                      'H16 one complete original context per T1 source required')
            context = contexts[0]
            text = c.text(context['source_text'], 'original source text')
            source_hash = sha256(text.encode('utf8')).hexdigest()
            c.require(context['source_id'] == sid and context['source_sha256'] == source_hash
                      and source_hashes.setdefault(sid, source_hash) == source_hash,
                      'H16 original source text changed')
            source = {'id': sid, 'text': text, 'sha256': source_hash}
            for record in records:
                c.require(record['category'] in TYPES and record['source_id'] == sid
                          and record['source_sha256'] == source_hash
                          and native.digest(record['value']) == record['value_sha256'],
                          'H16 original whole occurrence binding differs')
                rows.append({'unit_id': f'T1|{arm}|{sid}|{record["record_id"]}',
                             'arm': arm, 'category': record['category'], 'source_id': sid,
                             'family': families[sid], 'value': record['value'],
                             'value_sha256': record['value_sha256'], 'sources': [source]})
    c.require(len({r['unit_id'] for r in rows}) == len(rows), 'H16 duplicate original occurrence')
    return {'rows': rows, 'input_pins': pins, 'source_count': 20,
            'source_family_counts': {'wikipedia': 12, 'factbook': 8},
            'selection_uses_guard_or_external_labels': False}


def quotas(counts):
    """N16: ten/type, only VV deficits redistributed proportionally to EE/EV."""
    c.require(set(counts) == set(TYPES) and all(type(n) is int and n >= 0 for n in counts.values()),
              'H16 explicit nonnegative type capacities required')
    c.require(counts['EE'] >= 10 and counts['EV'] >= 10 and sum(counts.values()) >= 30,
              'H16 N16 only permits a VV deficit, with thirty available per arm')
    q = {'EE': 10, 'EV': 10, 'VV': min(10, counts['VV'])}
    deficit = 10 - q['VV']
    if deficit:
        total = counts['EE'] + counts['EV']
        exact = {t: Fraction(deficit * counts[t], total) for t in ('EE', 'EV')}
        extra = {t: int(exact[t]) for t in exact}
        left = deficit - sum(extra.values())
        order = sorted(exact, key=lambda t: (-(exact[t] - extra[t]), TYPES.index(t)))
        for t in order[:left]:
            extra[t] += 1
        for t in extra:
            q[t] += extra[t]
        # A limited type transfers only its unavailable excess to the other type.
        for t, other in (('EE', 'EV'), ('EV', 'EE')):
            excess = max(0, q[t] - counts[t])
            q[t] -= excess
            q[other] += excess
    c.require(sum(q.values()) == 30 and all(q[t] <= counts[t] for t in TYPES),
              'H16 proportional fill exceeds the available population')
    return q


def draw_sample(rows, *, publication=None, synthetic=False):
    if not synthetic:
        validate_publication(publication)
    c.require(type(rows) is list and len({r['unit_id'] for r in rows}) == len(rows),
              'H16 distinct original occurrences required')
    c.require(all(r['arm'] in ARMS and r['category'] in TYPES for r in rows),
              'H16 explicit AS/V2 and EE/EV/VV required')
    rng = random.Random(SEED)
    selected, population_counts, type_counts, strata = [], {}, {}, []
    for arm in ARMS:
        pools = {t: sorted((r for r in rows if (r['arm'], r['category']) == (arm, t)),
                           key=lambda r: r['unit_id']) for t in TYPES}
        population_counts[arm] = {t: len(pools[t]) for t in TYPES}
        type_counts[arm] = quotas(population_counts[arm])
        for t in TYPES:
            n, total = type_counts[arm][t], len(pools[t])
            selected.extend(rng.sample(pools[t], n))
            strata.append({'arm': arm, 'type': t, 'population_N': total,
                           'selected_n': n, 'inclusion_probability': n / total if total else None})
    rng.shuffle(selected)
    c.require(len(selected) == len({r['unit_id'] for r in selected}) == 60,
              'H16 sixty unique occurrences without replacement required')
    design = {'seed': SEED, 'python_version': platform.python_version(),
              'rng': 'random.Random; sorted immutable occurrence IDs; AS/V2 then EE/EV/VV; sample then shuffle',
              'population_counts': population_counts, 'type_counts': type_counts, 'strata': strata,
              'VV_shortfall_documented': any(type_counts[a]['VV'] < 10 for a in ARMS),
              'VV_fill_rule': 'original EE/EV counts, exact largest remainder, EE first on ties, capacity spill to other type',
              'text_deduplication': False, 'quality_or_guard_status_selection': False,
              'estimator_scope': 'unweighted type-balanced selected statements; not the natural T1 arm population'}
    return {'selected_rows': selected, 'design': design}
