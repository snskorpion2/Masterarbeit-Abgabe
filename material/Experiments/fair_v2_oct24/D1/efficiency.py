"""N8 descriptive efficiency from an explicitly supplied K2 CSV and H1 counts.

This module never opens files or discovers inputs. Cost meters and source-bound
H1 counts must belong to the same declared population. ORIGINAL/ROW are views,
not additional constructions. No value here is an efficiency hypothesis test.
"""
from collections import defaultdict
import csv
from decimal import Decimal, InvalidOperation
from io import StringIO
from itertools import product
import json
import re


K2_COLUMNS = (
    'package', 'population', 'arm', 'stage', 'scope', 'model', 'pricing_scenario',
    'call_kind', 'status', 'snapshot_UTC', 'calls_known', 'calls_unknown',
    'pending_positions', 'call_count', 'physical_POSTs', 'physical_POSTs_known_subtotal',
    'prompt_tokens_known', 'output_tokens_known', 'usage_missing',
    'cache_read_tokens_known', 'cache_write_tokens_known', 'currency', 'cost_known',
    'cost_missing', 'cost_complete', 'reserved_or_held_cost', 'invoice_verified',
    'used_by_arms', 'notes', 'receipt_set_sha256')
COUNT_COLUMNS = frozenset(K2_COLUMNS[10:21]) | {'cost_missing'}
BOOL_COLUMNS = {'cost_complete', 'invoice_verified'}
MONEY_COLUMNS = {'cost_known', 'reserved_or_held_cost'}
ARMS = ('AS', 'AS+G', 'V1', 'V2')
CELLS = {'AS': 'AS', 'AS+G': 'AS_G', 'V1': 'V1', 'V2': 'V2'}
BASE = {'AS': 'AS', 'AS+G': 'AS', 'V1': 'V1', 'V2': 'V1'}
CONSTRUCTION_STAGES = {'Extraktion', 'Ergänzung', 'Schema'}


def _need(value, reason):
    if not value:
        raise ValueError(reason)


def _number(value, field):
    if value in ('', None):
        return None
    _need(isinstance(value, str) and re.fullmatch(r'\d+', value) is not None,
          'K2 nonnegative integer required: ' + field)
    return int(value)


def _money(value, field):
    if value in ('', None):
        return None
    _need(type(value) is not bool, 'K2 finite nonnegative money required: ' + field)
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('K2 finite nonnegative money required: ' + field) from None
    _need(result.is_finite() and result >= 0,
          'K2 finite nonnegative money required: ' + field)
    return str(result)


def parse_k2_csv(text):
    """Parse the actual 30-column K2 format, without guessing nulls or booleans."""
    _need(type(text) is str, 'K2 CSV text required')
    reader = csv.DictReader(StringIO(text.removeprefix('\ufeff'), newline=''))
    _need(reader.fieldnames is not None and len(reader.fieldnames) == len(K2_COLUMNS)
          and set(reader.fieldnames) == set(K2_COLUMNS), 'Exact K2 CSV columns required')
    rows = []
    for raw in reader:
        _need(None not in raw and all(v is not None for v in raw.values()),
              'K2 malformed CSV row')
        row = dict(raw)
        for field in COUNT_COLUMNS:
            row[field] = _number(raw[field], field)
        for field in BOOL_COLUMNS:
            value = raw[field]
            _need(value in ('', 'true', 'false'), 'K2 literal true/false required: ' + field)
            row[field] = None if value == '' else value == 'true'
        for field in MONEY_COLUMNS:
            row[field] = _money(raw[field], field)
        for field in K2_COLUMNS:
            if field not in COUNT_COLUMNS | BOOL_COLUMNS | MONEY_COLUMNS:
                row[field] = raw[field] or None
        digest = row['receipt_set_sha256']
        _need(digest is None or re.fullmatch(r'[0-9a-fA-F]{64}', digest),
              'K2 receipt-set SHA-256 required when present')
        if digest:
            row['receipt_set_sha256'] = digest.lower()
        currency = row['currency']
        _need(currency is None or re.fullmatch(r'[A-Z]{3}', currency),
              'K2 currency must be a three-letter code or empty')
        rows.append(row)
    return rows


def _canonical_arm(arm):
    return 'AS+G' if arm == 'AS_G' else arm


def _meter_rows(rows):
    """Exact duplicate meter views collapse, conflicting same-price views fail."""
    seen, fingerprints, observations = {}, set(), {}
    result = []
    for row in rows:
        _need(type(row) is dict and set(K2_COLUMNS) <= set(row), 'Parsed K2 row required')
        fingerprint = json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        digest = row.get('receipt_set_sha256')
        scope_key = tuple(row.get(k) for k in
                          ('package', 'population', 'arm', 'stage', 'scope', 'model', 'call_kind'))
        identity = ('receipt_set', digest) if digest else ('unidentified_scope', scope_key)
        metered_fields = tuple(k for k in K2_COLUMNS if k not in
            {'currency', 'pricing_scenario', 'cost_known', 'cost_missing', 'cost_complete',
             'reserved_or_held_cost', 'invoice_verified', 'notes', 'snapshot_UTC'})
        observation = tuple(row.get(k) for k in metered_fields)
        _need(identity not in observations or observations[identity] == observation,
              'Conflicting K2 observation across pricing views')
        observations[identity] = observation
        price_key = identity, row.get('currency'), row.get('pricing_scenario')
        if price_key in seen:
            _need(seen[price_key] == row, 'Conflicting duplicate K2 meter')
        seen[price_key] = row
        result.append((identity, row))
    return result


def _classify(row):
    if row.get('scope') == 'pilot_extra':
        return None, 'pilot_extra_excluded'
    if (row.get('scope') or '').startswith('historical_reused_schema_outside_'):
        return None, 'historical_schema_kept_separate'
    if row.get('call_kind') == 'not_executed':
        return None, 'not_executed_not_incurred'
    if row.get('package') in ('B3', 'B4') and row.get('stage') in CONSTRUCTION_STAGES:
        if _canonical_arm(row.get('arm')) not in ('AS', 'V1'):
            return None, 'construction_owner_not_a_base_arm'
        return 'construction', None
    if row.get('package') == 'C1' and row.get('stage') == 'Prüffilter':
        if _canonical_arm(row.get('arm')) not in ('AS+G', 'V2'):
            return None, 'guard_owner_not_a_filtered_arm'
        return 'guard', None
    return None, 'qualification_or_external_evaluation_excluded'


def _support_count(arm, population, h1_draws, sources, population_sources):
    ids = population_sources.get(population)
    if ids is None:
        return None, False, ['population_has_no_H1_source_mapping']
    _need(type(ids) in (list, tuple, set) and len(ids) == len(set(ids)) and bool(ids),
          'Nonempty explicit population source IDs required')
    source_map = {s['source_id']: s for s in sources}
    _need(len(source_map) == len(sources) and set(ids) <= set(source_map),
          'Population mapping contains foreign or duplicate source IDs')
    expected = {(sid, draw) for sid in ids for draw in source_map[sid]['draws']}
    base = CELLS[arm]
    views = []
    for suffix in ('ORIGINAL', 'ROW'):
        rows = h1_draws.get(base + '_' + suffix)
        if rows is None:
            views.append(None)
            continue
        indexed = {}
        for row in rows:
            key = row['source_id'], row['draw']
            _need(key[0] in source_map and key[1] in source_map[key[0]]['draws'],
                  'Foreign H1 source/draw in efficiency input')
            _need(key not in indexed, 'Duplicate H1 source/draw in efficiency input')
            indexed[key] = row
        _need(expected <= set(indexed), 'Missing planned H1 source/draw for efficiency')
        views.append({key: indexed[key] for key in expected})
    if views[0] is None:
        return None, False, ['original_H1_view_not_available']
    if views[1] is not None:
        fields = ('success', 'denominator', 'defined', 'technical_missing', 'semantic_unclear')
        _need(all(all(views[0][key].get(k) == views[1][key].get(k) for k in fields)
                  for key in expected), 'H1 export views differ; cannot count once')
    selected = list(views[0].values())
    for row in selected:
        _need(row.get('success') is None or type(row['success']) is int and row['success'] >= 0,
              'Nonnegative H1 supported occurrence count required')
        _need(row.get('denominator') is None or type(row['denominator']) is int
              and row['denominator'] >= (row.get('success') or 0),
              'H1 support count must not exceed its denominator')
    known = [row['success'] for row in selected if row.get('success') is not None]
    supported = sum(known) if known else None
    if any(row.get('success') is None or row.get('defined') is not True for row in selected):
        return supported, False, ['H1_supported_count_not_identified']
    # Semantic unclear is an observed G2 code, not a missing technical judgment.
    # An absent technical-coverage field, however, cannot certify a full roster.
    complete = all(row.get('technical_missing') == 0 for row in selected)
    reasons = [] if complete else ['H1_technical_missing_not_false']
    return supported, complete, reasons


def _stage_coverage(construction, guard, arm, packages):
    """Document whole required stages independently of their usage/cost values."""
    required_construction = []
    for package in packages:
        required_construction.append(package + ':Extraktion')
        if package == 'B3':
            required_construction.append(package + ':Schema')
        if BASE[arm] == 'V1':
            required_construction.append(package + ':Ergänzung')
    if not required_construction:
        # Guard-only input cannot identify an absent constructor as B3 or B4.
        required_construction = ['B3/B4:Konstruktion']
    present = {r['package'] + ':' + r['stage'] for r in construction + guard}
    construction_missing = [s for s in required_construction if s not in present]
    required = list(required_construction)
    if arm in ('AS+G', 'V2'):
        required.append('C1:Prüffilter')
    missing = [s for s in required if s not in present]
    return required, missing, not construction_missing


def _usage(rows):
    values = [r.get('prompt_tokens_known') for r in rows]
    values += [r.get('output_tokens_known') for r in rows]
    _need(all(v is None or type(v) is int and v >= 0 for v in values),
          'Nonnegative token meters required')
    known = sum(v for v in values if v is not None) if any(v is not None for v in values) else None
    complete = bool(rows) and all(r.get('usage_missing') == 0
        and r.get('prompt_tokens_known') is not None and r.get('output_tokens_known') is not None
        and r.get('calls_unknown') == 0 and r.get('pending_positions') == 0
        and r.get('status') == 'abgeschlossen' for r in rows)
    return known, complete


def _cost(rows):
    values = [_money(r.get('cost_known'), 'cost_known') for r in rows]
    known = sum((Decimal(v) for v in values if v is not None), Decimal()) if any(v is not None for v in values) else None
    complete = bool(rows) and all(r.get('cost_complete') is True and r.get('cost_known') is not None
        and r.get('cost_missing') == 0 and r.get('calls_unknown') == 0
        and r.get('pending_positions') == 0 and r.get('status') == 'abgeschlossen' for r in rows)
    return known, complete


def compute_efficiency(rows, h1_draws, sources, *, population_sources=None):
    """Return descriptive arm/population profiles, never an efficiency winner.

    population_sources explicitly binds K2 population names to the H1 source
    roster. An unmapped population is retained with an unknown support count.
    Different-model list-price components may be added within one currency.
    Alternative price views of one receipt set are separate profiles instead.
    """
    _need(type(rows) is list and type(h1_draws) is dict and type(sources) is list,
          'Explicit in-memory K2/H1/source inputs required')
    population_sources = {} if population_sources is None else population_sources
    _need(type(population_sources) is dict, 'Explicit population/source mapping required')
    relevant, excluded = [], []
    for row in rows:
        _need(type(row) is dict and set(K2_COLUMNS) <= set(row), 'Parsed K2 row required')
        kind, reason = _classify(row)
        if kind:
            relevant.append(row)
        else:
            excluded.append({'package': row.get('package'), 'population': row.get('population'),
                'arm': row.get('arm'), 'scope': row.get('scope'), 'reason': reason})
    included = [(identity, row, _classify(row)[0]) for identity, row in _meter_rows(relevant)]
    output = []
    for population in dict.fromkeys(row['population'] for _, row, _ in included):
        packages = sorted({row['package'] for _, row, kind in included
                           if row['population'] == population and kind == 'construction'})
        for arm in ARMS:
            selected = [(identity, row, kind) for identity, row, kind in included
                if row['population'] == population and (
                    kind == 'construction' and _canonical_arm(row['arm']) == BASE[arm]
                    or kind == 'guard' and _canonical_arm(row['arm']) == arm)]
            variants = defaultdict(list)
            for identity, row, kind in selected:
                variants[identity].append((row, kind))
            _need(len(variants) == 0 or max(len(v) for v in variants.values()) <= 16,
                  'Too many alternative pricing views for one meter')
            profiles = product(*variants.values()) if variants else [()]
            for profile_number, profile in enumerate(profiles):
                _need(profile_number < 256, 'Too many K2 pricing profile combinations')
                construction = [r for r, kind in profile if kind == 'construction']
                guard = [r for r, kind in profile if kind == 'guard']
                all_rows = construction + guard
                supported, support_complete, reasons = _support_count(
                    arm, population, h1_draws, sources, population_sources)
                needs_guard = arm in ('AS+G', 'V2')
                base_present, guard_present = bool(construction), bool(guard) or not needs_guard
                if not base_present:
                    reasons.append('base_construction_not_documented')
                if not guard_present:
                    reasons.append('required_guard_not_documented')
                required_stages, missing_stages, construction_stages_complete = _stage_coverage(
                    construction, guard, arm, packages)
                stage_coverage_complete = not missing_stages
                if missing_stages:
                    reasons.append('required_stages_not_documented')
                historical = [r for r in excluded if r['population'] == population
                    and _canonical_arm(r['arm']) == BASE[arm]
                    and r['reason'] == 'historical_schema_kept_separate']
                if historical:
                    reasons.append('historical_schema_scope_requires_separate_accounting')
                construction_tokens, construction_complete = _usage(construction)
                construction_complete = construction_complete and construction_stages_complete
                guard_tokens, guard_complete = _usage(guard) if needs_guard else (0, True)
                total_tokens = _usage(all_rows)[0]
                usage_complete = (stage_coverage_complete and base_present and guard_present
                                  and construction_complete and guard_complete and not historical)
                if not usage_complete:
                    reasons.append('construction_or_guard_usage_incomplete')
                currencies = list(dict.fromkeys(r.get('currency') for r in all_rows)) or [None]
                components = [{'package': r.get('package'), 'arm': r.get('arm'), 'stage': r.get('stage'),
                    'scope': r.get('scope'), 'model': r.get('model'), 'currency': r.get('currency'),
                    'pricing_scenario': r.get('pricing_scenario'), 'receipt_set_sha256': r.get('receipt_set_sha256')}
                    for r in all_rows]
                profile_id = json.dumps(sorted({(r.get('model') or '', r.get('pricing_scenario') or '')
                    for r in all_rows}), ensure_ascii=False, separators=(',', ':'))
                global_cost_complete = (stage_coverage_complete and base_present and guard_present
                                        and not historical and _cost(all_rows)[1])
                for currency in currencies:
                    part = [r for r in all_rows if r.get('currency') == currency]
                    known_cost, part_complete = _cost(part)
                    same_currency = len(currencies) == 1 and currency is not None
                    cost_complete = bool(global_cost_complete and same_currency and part_complete)
                    local_reasons = list(reasons)
                    if not cost_complete:
                        local_reasons.append('cost_incomplete_or_not_one_currency')
                    positive_support = supported is not None and supported > 0
                    if supported == 0:
                        local_reasons.append('zero_supported_denominator')
                    output.append({'arm': arm, 'population': population, 'currency': currency,
                        'pricing_scenario': profile_id, 'pricing_components': components,
                        'profile_number': profile_number, 'supported_count': supported,
                        'support_complete': support_complete,
                        'supported_count_basis': 'valid H1-supported occurrences, planned source/draw roster, ORIGINAL only',
                        'stage_coverage_complete': stage_coverage_complete,
                        'construction_stage_coverage_complete': construction_stages_complete,
                        'required_stages': required_stages, 'missing_stages': missing_stages,
                        'construction_tokens_known': construction_tokens, 'guard_tokens_known': guard_tokens,
                        'total_tokens_known': total_tokens, 'usage_complete': usage_complete,
                        'construction_usage_complete': construction_complete and not historical,
                        'cost_known': str(known_cost) if known_cost is not None else None,
                        'cost_complete': cost_complete,
                        'cost_scope': 'full_arm' if same_currency else 'currency_component_only',
                        'cost_per_supported': str(known_cost / supported)
                            if positive_support and support_complete and cost_complete else None,
                        'currency_component_cost_per_supported': str(known_cost / supported)
                            if positive_support and support_complete and stage_coverage_complete
                            and not historical and part_complete and currency is not None else None,
                        'tokens_per_supported': total_tokens / supported
                            if positive_support and support_complete and usage_complete else None,
                        'supported_per_1000_construction_tokens': supported * 1000 / construction_tokens
                            if supported is not None and support_complete and construction_complete and not historical
                            and construction_tokens is not None and construction_tokens > 0 else None,
                        'complete_for_efficiency_comparison': bool(cost_complete and usage_complete and support_complete
                            and positive_support), 'efficiency_superiority_claimed': False,
                        'reserved_cost_is_spend': False, 'invoice_verified': bool(all_rows)
                            and all(r.get('invoice_verified') is True for r in all_rows),
                        'reasons': sorted(set(local_reasons))})
    return {'rows': output, 'excluded_rows': excluded,
        'status': 'provided' if rows else 'not_provided',
        'limits': ['Descriptive only, no efficiency test or superiority conclusion.',
            'ORIGINAL and ROW are dependent views and do not double construction or supported counts.',
            'V2 reuses V1 construction once, AS+G reuses AS construction once.',
            'Qualification, external evaluation and pilot extras are not allocated to arms.',
            'Known subtotals do not replace unknown costs, missing usage or unfinished stage scopes.',
            'Receipt-set equality removes exact duplicate meters, not unproven partial overlap.',
            'No currency conversion. Cache meters are not added again to prompt token totals.']}
