"""N15's fixed draw and exact C3 input join over explicitly supplied data.

Pure functions only: no files, models, construction, or new judgments. The
caller owns publication checks and byte-bound reads of the original C3 data.
All selection metadata and returned Sol codes belong in the private key only.
"""
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256

import numpy as np


SEED = 2026102615
ARMS = ('AS', 'V2')
ALL_C3_ARMS = frozenset(('AS', 'AS_G', 'V1', 'V2'))
FAMILIES = frozenset(('factbook', 'wikipedia'))
CODES = frozenset(('retained', 'partially_retained', 'not_retained',
                   'undetermined', 'not_assessable'))
TECHNICAL_STATUSES = frozenset(('technical_missing', 'technical_failure',
    'format_invalid', 'unknown_execution', 'failed', 'not_judged', 'pending'))


def _need(ok, code):
    if not ok:
        raise ValueError(code)


def _text(value):
    return type(value) is str and bool(value.strip())


def _quotas(counts, total):
    """Exact largest remainder; ties use lexical family order."""
    population = sum(counts.values())
    _need(population >= total > 0, 'H15_INSUFFICIENT_UNIQUE_MEANING_CAPACITY')
    exact = {family: Fraction(total * n, population) for family, n in counts.items()}
    quotas = {family: value.numerator // value.denominator for family, value in exact.items()}
    remainder_order = sorted(counts, key=lambda f: (-(exact[f] - quotas[f]), f))
    for family in remainder_order[:total - sum(quotas.values())]:
        quotas[family] += 1
    _need(sum(quotas.values()) == total and all(quotas[f] <= counts[f] for f in counts),
          'H15_QUOTA_CAPACITY_FAILURE')
    return quotas


def draw_sample(records, family_by_source, eligible_source_ids, *,
                sample_size=15, expected_source_count=17):
    """Choose unique meanings, one shared valid draw, then shuffle both arms.

    ``records`` is the original flat C3 aggregate ``records`` list. Validity,
    not raw label class, determines eligibility. The supplied source IDs must
    match the existing N14 AS/V2 source restriction derived from that list.
    Families use the unchanged frozen source metadata. Returned cases/private
    pairs contain original identities; they must not be embedded in the UI.
    """
    _need(type(records) is list and type(family_by_source) is dict,
          'H15_EXPLICIT_C3_RECORDS_AND_SOURCE_FAMILIES_REQUIRED')
    _need(type(eligible_source_ids) in (list, tuple) and
          all(_text(sid) for sid in eligible_source_ids) and
          len(set(eligible_source_ids)) == len(eligible_source_ids),
          'H15_UNIQUE_EXPLICIT_N14_SOURCE_IDS_REQUIRED')
    _need(type(expected_source_count) is int and expected_source_count > 0 and
          len(eligible_source_ids) == expected_source_count,
          'H15_N14_SOURCE_COUNT_DIFFERS')
    _need(type(sample_size) is int and sample_size > 0, 'H15_POSITIVE_SAMPLE_SIZE_REQUIRED')
    valid_sources = {arm: set() for arm in ARMS}
    indexed = {}
    for row in records:
        _need(type(row) is dict and all(_text(row.get(key)) for key in
              ('source_id', 'draw', 'arm', 'obligation_id')), 'H15_C3_IDENTITY_REQUIRED')
        arm = row['arm']
        _need(arm in ALL_C3_ARMS, 'H15_UNKNOWN_C3_ARM')
        if arm not in ARMS:
            continue
        key = tuple(row[k] for k in ('source_id', 'obligation_id', 'draw', 'arm'))
        _need(key not in indexed, 'H15_DUPLICATE_C3_POSITION')
        status, code = row.get('status'), row.get('raw_code')
        _need(type(status) is str and (status == 'valid' or status in TECHNICAL_STATUSES),
              'H15_UNKNOWN_C3_STATUS')
        _need(code is None or (type(code) is str and code in CODES), 'H15_UNKNOWN_C3_RETENTION_CODE')
        _need(status != 'valid' or code in CODES, 'H15_VALID_C3_CODE_REQUIRED')
        indexed[key] = row
        if status == 'valid':
            valid_sources[arm].add(row['source_id'])
    actual_sources = valid_sources['AS'] & valid_sources['V2']
    _need(actual_sources == set(eligible_source_ids), 'H15_N14_SOURCE_FRAME_DIFFERS')
    _need(all(type(family_by_source.get(sid)) is str and family_by_source[sid] in FAMILIES
              for sid in actual_sources),
          'H15_FROZEN_WIKIPEDIA_FACTBOOK_FAMILIES_REQUIRED')
    grouped = defaultdict(lambda: {arm: {} for arm in ARMS})
    for (sid, obligation, draw, arm), row in indexed.items():
        if sid in actual_sources and row['status'] == 'valid':
            grouped[sid, obligation][arm][draw] = row['raw_code']
    families = sorted({family_by_source[sid] for sid in actual_sources})
    pools = {family: [] for family in families}
    common_draws = {}
    for meaning in sorted(grouped):
        by_arm = grouped[meaning]
        shared = sorted(set(by_arm['AS']) & set(by_arm['V2']))
        if shared:
            pools[family_by_source[meaning[0]]].append(meaning)
            common_draws[meaning] = shared
    counts = {family: len(pools[family]) for family in families}
    quotas = _quotas(counts, sample_size)
    rng = np.random.Generator(np.random.PCG64(SEED))
    chosen = []
    for family in families:
        pool = sorted(pools[family])
        order = rng.permutation(len(pool))
        chosen.extend(pool[int(i)] for i in order[:quotas[family]])
    chosen = sorted(chosen)
    selected, cases = [], []
    for ordinal, (sid, obligation) in enumerate(chosen, 1):
        draws = sorted(common_draws[sid, obligation])
        draw = draws[int(rng.integers(len(draws)))]
        pair = {'pair_id': f'pair-{ordinal:03}', 'source_id': sid,
                'obligation_id': obligation, 'family': family_by_source[sid], 'draw': draw}
        selected.append(deepcopy(pair))
        for arm in ARMS:
            cases.append({**deepcopy(pair), 'arm': arm,
                          'sol_raw_code': indexed[sid, obligation, draw, arm]['raw_code']})
    order = rng.permutation(len(cases))
    shuffled = []
    for position, index in enumerate(order, 1):
        case = deepcopy(cases[int(index)])
        # Depends only on final presentation position, not original identity.
        neutral = sha256(f'H15-neutral-case|{SEED}|{position}'.encode('ascii')).hexdigest()[:24]
        case['item_id'] = 'case-' + neutral
        shuffled.append(case)
    return {'protocol': 'H15-N15-unique-meaning-fixed-draw:v1', 'seed': SEED,
            'selected_meanings': sample_size, 'case_count': len(shuffled),
            'eligible_source_ids': sorted(actual_sources),
            'eligible_unique_meanings_by_family': counts, 'quotas': quotas,
            'selected_pairs': selected, 'cases': shuffled,
            'selection_uses_actual_sol_class': False,
            'meaning_replacement_or_resampling': False,
            'rng': 'numpy.random.Generator(PCG64)',
            'chosen_meanings_sorted_before_draw_selection': True}


def original_case(case_rows, blind_mapping, selection):
    """Return one whole original C3 case, including all required aspects.

    Both arguments are decoded only after the caller checks the segment's
    original cases_pin/mapping_pin. This function never rebuilds an inventory.
    """
    _need(type(case_rows) is list and type(blind_mapping) is dict and type(selection) is dict,
          'H15_EXPLICIT_ORIGINAL_C3_CASES_AND_MAPPING_REQUIRED')
    keys = ('source_id', 'draw', 'arm', 'obligation_id')
    _need(all(_text(selection.get(k)) for k in keys) and selection['arm'] in ARMS,
          'H15_SELECTED_CASE_IDENTITY_REQUIRED')
    expected = tuple(selection[k] for k in keys)
    matches = []
    seen = set()
    for row in case_rows:
        _need(type(row) is dict and row.get('axis') == 'retention' and
              type(row.get('case')) is dict, 'H15_ORIGINAL_RETENTION_CASE_REQUIRED')
        case = row['case']
        ident = case.get('id')
        _need(_text(ident) and ident not in seen and ident in blind_mapping,
              'H15_ORIGINAL_CASE_ID_OR_MAPPING_DIFFERS')
        seen.add(ident)
        host = blind_mapping[ident]
        _need(type(host) is dict and all(_text(host.get(k)) for k in keys),
              'H15_ORIGINAL_HOST_IDENTITY_REQUIRED')
        if tuple(host[k] for k in keys) != expected:
            continue
        source, obligation, carrier = case.get('source'), case.get('obligation'), case.get('carrier')
        _need(type(source) is dict and source.get('id') == selection['source_id']
              and _text(source.get('text')), 'H15_ORIGINAL_SOURCE_BINDING_DIFFERS')
        _need(type(obligation) is dict and obligation.get('id') == selection['obligation_id']
              and _text(obligation.get('meaning')) and type(obligation.get('required_aspects')) is list
              and bool(obligation['required_aspects'])
              and all(_text(value) for value in obligation['required_aspects']),
              'H15_COMPLETE_ORIGINAL_REFERENCE_REQUIRED')
        neutral_inventory(carrier)  # Validate without reducing or changing it.
        matches.append(deepcopy(case))
    _need(len(matches) == 1, 'H15_EXPECTED_EXACTLY_ONE_ORIGINAL_C3_CASE')
    return matches[0]


def neutral_inventory(carrier):
    """Preserve whole values/order/duplicates and replace only witness IDs."""
    _need(type(carrier) is dict and carrier.get('status') == 'complete'
          and type(carrier.get('units')) is list, 'H15_COMPLETE_ORIGINAL_CARRIER_REQUIRED')
    inventory, mapping, seen = [], [], set()
    for ordinal, unit in enumerate(carrier['units'], 1):
        _need(type(unit) is dict and set(unit) == {'id', 'category', 'value'}
              and _text(unit.get('id')) and unit['id'] not in seen
              and unit.get('category') in ('EE', 'EV', 'VV')
              and type(unit.get('value')) is dict, 'H15_VALID_UNIQUE_ORIGINAL_WITNESS_REQUIRED')
        seen.add(unit['id'])
        ident = f'u{ordinal:06}'
        inventory.append({'id': ident, 'category': unit['category'], 'value': deepcopy(unit['value'])})
        mapping.append({'neutral_id': ident, 'original_unit_id': unit['id']})
    return inventory, mapping
