"""Frozen descriptive distinctness and design-weighted human validation.

Pure supplied-data functions: no files, models, labels loaded, or sampling.
Semantic groups are pooled across original AS/V1 before cell intersections.
"""
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
import math
import unicodedata

from .native import support_label

LABELS = ('supported', 'not_supported', 'unclear')
STRATA = tuple((arm, category) for arm in ('AS', 'V1') for category in ('EE', 'EV', 'VV'))
ORIGINAL_CELLS = frozenset(('AS_ORIGINAL', 'AS_ROW', 'V1_ORIGINAL', 'V1_ROW'))


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _nfc_values(value):
    if type(value) is str:
        return unicodedata.normalize('NFC', value)
    if type(value) is list:
        return [_nfc_values(item) for item in value]
    if type(value) is dict:
        _need(all(type(key) is str for key in value), 'Semantic JSON keys must remain original strings')
        # Deliberately preserve each KEY byte sequence. Only string VALUES NFC.
        return {key: _nfc_values(item) for key, item in value.items()}
    _need(value is None or type(value) in (int, float, bool), 'Semantic payload must be JSON')
    return value


def canonical_payload(value):
    """Only value is semantic content; outer unit/provenance IDs are excluded."""
    return json.dumps(_nfc_values(value), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf8')


def _payload_id(value):
    return sha256(value).hexdigest()


def _mean(values):
    values = list(values)
    return sum(values)/len(values) if values and all(v is not None for v in values) else None


def _pair_catalog(bundle, pools):
    pairs = defaultdict(dict)
    outside_eligible_pool = Counter()
    supplied = bundle.get('semantic_pairs', [])
    _need(type(supplied) is list, 'Explicit semantic pair list required')
    for row in supplied:
        owner = row['source_id'], row['draw']
        _need(owner in pools, 'Semantic pair has a foreign source/draw')
        left, right = canonical_payload(row['left_payload']), canonical_payload(row['right_payload'])
        _need(row['judgment'] in ('equivalent', 'not_equivalent', 'unclear')
              and type(row.get('human_confirmed')) is bool, 'Recorded pair label and human confirmation required')
        if left not in pools[owner] or right not in pools[owner]:
            outside_eligible_pool[owner] += 1
            continue
        _need(left != right, 'Semantic pair must compare distinct exact forms')
        key = tuple(sorted((left, right)))
        record = pairs[owner].setdefault(key, {'judgments': set(), 'human_confirmed_equivalent': False})
        record['judgments'].add(row['judgment'])
        record['human_confirmed_equivalent'] |= row['judgment'] == 'equivalent' and row['human_confirmed']
        # Optional cell/parent fields are host metadata, never grouping scopes.
    return pairs, outside_eligible_pool


def distinct_supported(bundle):
    """Exact observed counts plus comparison-limited, human-confirmed cliques.

    The exact AS/V1 pool contains only original semantic forms whose whole
    occurrences receive a valid supported C2 label. It is pooled across parent
    arms before any Guard/export cell intersection. Unsupported/unknown forms
    never influence first-fit order or clique membership.
    Deterministic first-fit requires confirmed equivalence to ALL members.
    Cell counts then intersect these shared groups with retained supported
    occurrences. Unassessed/conflicting/unclear pairs never create a merge.
    """
    sources, cells = bundle['sources'], bundle['cells']
    planned = {(s['source_id'], draw, cell) for s in sources for draw in s['draws'] for cell in cells}
    _need(len(planned) == sum(len(s['draws'])*len(cells) for s in sources), 'Distinct planned source/draw/cells required')
    inventories = {}
    for row in bundle['H1_inventories']:
        key = row['source_id'], row['draw'], row['cell']
        _need(key in planned and key not in inventories, 'Foreign/duplicate distinct-count inventory')
        inventories[key] = row
    _need(set(inventories) == planned, 'Every planned inventory must be explicit')
    grouped, supported, owners, seen_units = defaultdict(list), defaultdict(set), {}, defaultdict(set)
    for row in bundle['H1']:
        key = row['source_id'], row['draw'], row['cell']
        _need(key in planned and type(row['unit_id']) is str, 'Distinct count row owner/occurrence required')
        _need(row['unit_id'] not in seen_units[key], 'Duplicate retained occurrence in one cell')
        seen_units[key].add(row['unit_id'])
        label = support_label(row.get('raw_code'), row.get('measurement_status', 'technical_missing'))
        payload = canonical_payload(row['value']) if row.get('value') is not None else None
        occurrence = row['source_id'], row['draw'], row['unit_id']
        _need(occurrence not in owners or owners[occurrence] == payload, 'Inherited occurrence semantic payload changed')
        owners[occurrence] = payload
        grouped[key].append({'unit_id': row['unit_id'], 'label': label, 'payload': payload})
        if payload is not None:
            if label == 'supported':
                supported[key].add(payload)
    pools, pool_complete = {}, {}
    for source in sources:
        sid = source['source_id']
        for draw in source['draws']:
            original = [(sid, draw, cell) for cell in cells if cell in ORIGINAL_CELLS]
            forms = set().union(*(supported[key] for key in original)) if original else set()
            pools[sid, draw] = forms
            arms = {cell.split('_')[0] for _, _, cell in original}
            complete = arms == {'AS', 'V1'} and bool(original)
            for key in original:
                inventory = inventories[key]
                complete &= (inventory.get('completed') is True
                    and inventory.get('occurrence_count') == len(grouped[key])
                    and all(r['label'] not in (None, 'unclear') for r in grouped[key])
                    and all(r['payload'] is not None for r in grouped[key] if r['label'] == 'supported'))
            pool_complete[sid, draw] = bool(complete)
    pairs, outside_eligible_pool = _pair_catalog(bundle, pools)
    partition, pair_reports = {}, []
    for owner, forms in pools.items():
        catalog = pairs[owner]
        qualified = {key for key, row in catalog.items()
                     if row['judgments'] == {'equivalent'} and row['human_confirmed_equivalent']}
        groups = []
        for form in sorted(forms):  # canonical bytes: explicit UTF-8 lexicographic order
            for group in groups:
                if all(tuple(sorted((form, other))) in qualified for other in group):
                    group.append(form)
                    break
            else:
                groups.append([form])
        possible = len(forms)*(len(forms)-1)//2
        conflicting = sum(len(row['judgments']) != 1 for row in catalog.values())
        unclear = sum(row['judgments'] == {'unclear'} for row in catalog.values())
        unconfirmed = sum(row['judgments'] == {'equivalent'} and not row['human_confirmed_equivalent']
                          for row in catalog.values())
        non_equivalent = sum(row['judgments'] == {'not_equivalent'} for row in catalog.values())
        unassessed = possible-len(catalog)
        complete = pool_complete[owner] and not (conflicting or unclear or unconfirmed or unassessed)
        partition[owner] = groups, complete
        pair_reports.append({'source_id': owner[0], 'draw': owner[1], 'pooled_exact_forms': len(forms),
            'possible_pairs': possible, 'assessed_unique_pairs': len(catalog), 'unassessed_pairs': unassessed,
            'pair_coverage': len(catalog)/possible if possible else None,
            'human_confirmed_equivalent_pairs': len(qualified), 'not_equivalent_pairs': non_equivalent,
            'unclear_pairs': unclear, 'unconfirmed_equivalent_pairs': unconfirmed, 'conflicting_pairs': conflicting,
            'pair_records_outside_supported_original_pool': outside_eligible_pool[owner],
            'complete_original_payload_pool': pool_complete[owner], 'semantic_review_complete': bool(complete),
            'groups': [{'_group_id': _payload_id(group[0]), 'payload_sha256s': [_payload_id(x) for x in group]}
                       for group in groups]})
    output = []
    for source in sources:
        sid = source['source_id']
        for draw in source['draws']:
            groups, semantic_complete = partition[sid, draw]
            for cell in cells:
                key = sid, draw, cell
                rows, inventory = grouped[key], inventories[key]
                count, complete_inventory = inventory.get('occurrence_count'), inventory.get('completed') is True
                _need(count is None or type(count) is int and count >= 0, 'Known occurrence count or None required')
                _need(count is None or len(rows) <= count, 'More judgments than native inventory occurrences')
                absent = count-len(rows) if count is not None else None
                technical = sum(r['label'] is None for r in rows)
                unclear = sum(r['label'] == 'unclear' for r in rows)
                missing_payload = sum(r['label'] == 'supported' and r['payload'] is None for r in rows)
                complete_support = complete_inventory and count == len(rows) and not (technical or unclear)
                exact_count = len(supported[key])
                unpooled = len(supported[key] - pools[sid, draw])
                _need(not unpooled or not pool_complete[sid, draw],
                      'Retained supported payload not present in complete original AS/V1 pool')
                merged_count = (sum(bool(set(group) & supported[key]) for group in groups)
                                if not unpooled else None)
                exact_complete = bool(complete_support and not missing_payload)
                output.append({'source_id': sid, 'draw': draw, 'cell': cell,
                    'exact_supported_observed_count': exact_count,
                    'exact_supported_distinct_count': exact_count if exact_complete else None,
                    'semantic_supported_observed_count': merged_count,
                    'semantic_supported_distinct_count': merged_count if exact_complete and semantic_complete else None,
                    'accepted_observed_merge_count': exact_count-merged_count if merged_count is not None else None,
                    'supported_forms_outside_observed_original_pool': unpooled,
                    'inventory_completed': complete_inventory, 'native_occurrence_count': count,
                    'unprovided_judgment_rows': absent, 'technical_missing_judgments': technical,
                    'semantic_unclear_judgments': unclear, 'semantic_payload_missing': missing_payload,
                    'complete_support_membership': bool(complete_support),
                    'exact_count_complete': exact_complete,
                    'semantic_review_complete': semantic_complete,
                    'observed_count_is_not_complete_source_fact_count': True})
    source_aggregates = []
    by_cell = {}
    for cell in cells:
        cell_sources = []
        for source in sources:
            rows = [r for r in output if r['source_id'] == source['source_id'] and r['cell'] == cell]
            item = {'source_id': source['source_id'], 'cell': cell, 'planned_draws': len(source['draws'])}
            for field in ('exact_supported_observed_count', 'exact_supported_distinct_count',
                          'semantic_supported_observed_count', 'semantic_supported_distinct_count'):
                item[field] = _mean(row[field] for row in rows)
            source_aggregates.append(item)
            cell_sources.append(item)
        by_cell[cell] = {field: _mean(row[field] for row in cell_sources) for field in (
            'exact_supported_observed_count', 'exact_supported_distinct_count',
            'semantic_supported_observed_count', 'semantic_supported_distinct_count')}
        by_cell[cell]['planned_sources'] = len(sources)
    return {'role': 'secondary_descriptive', 'exact_only': output, 'source_aggregates': source_aggregates,
        'by_cell': by_cell, 'pair_reviews': pair_reports,
        'semantic_merges_completed': all(r['semantic_review_complete'] for r in pair_reports),
        'semantic_grouping_scope': 'pooled AS/V1 source/draw before export; count cell intersections',
        'semantic_grouping': 'canonical UTF8 order, first-fit confirmed-equivalence CLIQUE, never union-find',
        'aggregation': 'planned-draw mean within source, then equally weighted source mean',
        'string_values_normalization': 'NFC', 'JSON_key_normalization': False,
        'not_exhaustive_source_recall': True, 'semantic_pair_task_B1_qualified': False}


def human_weighted_prevalence(rows, strata):
    """Full population-arm support prevalence bounds using exact N_h/n_h.

    The point is None when support membership is unresolved. The lower
    fraction of independently verified supported statements is named
    separately, never promoted into an identified true prevalence estimate.
    """
    _need(type(rows) is list and type(strata) is list, 'Human records and six design strata required')
    if not rows and not strata:
        return []  # C7 is optional/unavailable, not a fabricated empty population.
    designs = {}
    for design in strata:
        key = design['arm'], design['type']
        N, n = design['population_count'], design['sample_count']
        _need(key in STRATA and key not in designs and type(N) is int and type(n) is int
              and 0 <= n <= N, 'Six unique valid population/sample strata required')
        designs[key] = design
    _need(set(designs) == set(STRATA), 'All six fixed C7 strata required')
    grouped, units = defaultdict(list), set()
    for row in rows:
        key = row['arm'], row['category']
        _need(key in designs and type(row['unit_id']) is str and row['unit_id'] not in units,
              'Unique selected human occurrence and design stratum required')
        _need(row.get('stratum', row['arm']+'-'+row['category']) == row['arm']+'-'+row['category']
              and row.get('in_base_sample', True) is True,
              'Human population prevalence requires matching probability-sample stratum')
        units.add(row['unit_id'])
        _need(row.get('label') is None or row['label'] in LABELS, 'Canonical human class or None required')
        _need(row.get('status') in ('rated', 'valid', 'missing', 'technical_missing', 'technical_failure',
                                   'unknown_execution', 'pending'), 'Known human rating status required')
        label = row.get('label') if row['status'] in ('rated', 'valid') else None
        _need(label is not None or row['status'] not in ('rated', 'valid'), 'Rated human row requires a class')
        grouped[key].append((row, label))
    details = []
    for arm, category in STRATA:
        design = designs[arm, category]
        N, n = design['population_count'], design['sample_count']
        selected = grouped[arm, category]
        _need(len(selected) <= n, 'More selected records than the fixed sample size')
        for row, _ in selected:
            _need(n > 0, 'Selected record in a zero-size design sample')
            if row.get('weight') is not None:
                _need(isinstance(row['weight'], (int,float)) and math.isfinite(row['weight'])
                      and math.isclose(row['weight'], N/n, rel_tol=1e-12, abs_tol=1e-12),
                      'Recorded human weight differs from N_h/n_h')
        counts = Counter(label for _, label in selected)
        missing = counts[None] + n-len(selected)
        unclear, supported, unsupported = counts['unclear'], counts['supported'], counts['not_supported']
        weight = Fraction(N,n) if n else None
        unknown_unsampled = N if N and not n else 0
        lower_total = weight*supported if weight is not None else Fraction()
        upper_total = weight*(supported+unclear+missing) if weight is not None else Fraction(unknown_unsampled)
        details.append({'arm':arm, 'category':category, 'population_count':N, 'sample_count':n,
            'provided_rows':len(selected), 'unprovided_selected_rows':n-len(selected),
            'weight':float(weight) if weight is not None else None,
            'supported_count':supported, 'not_supported_count':unsupported, 'unclear_count':unclear,
            'technical_missing_count':missing, 'unclear_or_missing_count':unclear+missing,
            'technical_missing_sample_rate':missing/n if n else None,
            'unclear_sample_rate':unclear/n if n else None,
            'unclear_or_missing_sample_rate':(unclear+missing)/n if n else None,
            'weighted_supported_total':float(lower_total), 'weighted_support_upper_total':float(upper_total),
            'weighted_technical_missing_total':float(weight*missing) if weight is not None else None,
            'weighted_unclear_total':float(weight*unclear) if weight is not None else None,
            'population_not_sampled':bool(unknown_unsampled),
            'estimate':float(lower_total/N) if N and not (unclear or missing or unknown_unsampled) else None,
            'lower':float(lower_total/N) if N else None, 'upper':float(upper_total/N) if N else None})
    result = []
    for arm in ('AS','V1'):
        selected = [d for d in details if d['arm'] == arm]
        N, n = sum(d['population_count'] for d in selected), sum(d['sample_count'] for d in selected)
        lower_total = sum(d['weighted_supported_total'] for d in selected)
        upper_total = sum(d['weighted_support_upper_total'] for d in selected)
        missing = sum(d['technical_missing_count'] for d in selected)
        unclear = sum(d['unclear_count'] for d in selected)
        unresolved = bool(missing or unclear or any(d['population_not_sampled'] for d in selected))
        unsampled = sum(d['population_count'] for d in selected if d['population_not_sampled'])
        weighted_missing = sum(d['weighted_technical_missing_total'] or 0 for d in selected)
        weighted_unclear = sum(d['weighted_unclear_total'] or 0 for d in selected)
        result.append({'arm':arm, 'population_count':N, 'sample_count':n,
            'estimate':lower_total/N if N and not unresolved else None,
            'lower':lower_total/N if N else None, 'upper':upper_total/N if N else None,
            'conservative_verified_supported_fraction':lower_total/N if N else None,
            'supported_count':sum(d['supported_count'] for d in selected),
            'not_supported_count':sum(d['not_supported_count'] for d in selected),
            'unclear_count':unclear, 'technical_missing_count':missing,
            'technical_missing_sample_rate':missing/n if n else None,
            'unclear_sample_rate':unclear/n if n else None,
            'unclear_or_missing_sample_rate':(unclear+missing)/n if n else None,
            'weighted_technical_missing_population_fraction':weighted_missing/N if N and not unsampled else None,
            'weighted_unclear_population_fraction':weighted_unclear/N if N and not unsampled else None,
            'unsampled_population_fraction':unsampled/N if N else None,
            'support_prevalence_point_identified':bool(N and not unresolved),
            'unweighted_sample_is_population_prevalence':False,
            'estimator':'inverse-inclusion weighted N_h/n_h totals divided by population-arm N',
            'bounds_are_identification_not_sampling_CI':True, 'strata':selected})
    return result
