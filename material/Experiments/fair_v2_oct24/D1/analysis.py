"""Frozen estimands and descriptive tables over normalized, explicit inputs.

No outcome-file, source, model, provider or answer-text access. N14 publication
checks read protocol metadata only. Planned denominators and draws are never
selected using outcomes. Original fields remain in the input.
"""
from collections import Counter, defaultdict
from decimal import Decimal
from math import fsum, isfinite

NEGATIVE = {'contradicted', 'unsupported', 'mixed', 'not_in_source', 'not_supported'}
UNCLEAR = {'ambiguous', 'undetermined', 'not_assessable', 'unclear'}
RETENTION = {'retained', 'partially_retained', 'not_retained', 'undetermined', 'not_assessable'}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def mean(values):
    values = list(values)
    return fsum(values) / len(values) if values and all(v is not None for v in values) else None


def ratio_record(success, failure, unclear, technical, denominator, **metadata):
    """Symmetric conservative scores; a zero/unknown N is undefined."""
    if denominator is None or denominator == 0:
        return {**metadata, 'estimate': None, 'lower': None, 'upper': None,
            'denominator': denominator, 'missing_rate': None, 'technical_missing_rate': None,
            'semantic_unclear_rate': None, 'defined': False,
            'reason': 'unknown_denominator' if denominator is None else 'empty_denominator'}
    need(type(denominator) is int and denominator > 0
         and all(type(v) is int and v >= 0 for v in (success, failure, unclear, technical))
         and success + failure + unclear + technical == denominator, 'Exact numerator/denominator partition required')
    missing = unclear + technical
    return {**metadata, 'estimate': success / denominator, 'lower': success / denominator,
        'upper': (success + missing) / denominator, 'denominator': denominator,
        'success': success, 'resolved_failure': failure, 'semantic_unclear': unclear, 'technical_missing': technical,
        'missing_rate': missing / denominator, 'technical_missing_rate': technical / denominator,
        'semantic_unclear_rate': unclear / denominator, 'defined': True,
        'resolved_only_diagnostic': success / (success + failure) if success + failure else None}


def _source_equal(rows, sources):
    by_source = defaultdict(dict)
    for row in rows:
        sid, draw = row['source_id'], row['draw']
        need(draw not in by_source[sid], 'Duplicate source/draw statistic')
        by_source[sid][draw] = row
    need(set(by_source) <= {s['source_id'] for s in sources}, 'Foreign source statistic')
    need(all(set(by_source[s['source_id']]) == set(s['draws']) for s in sources), 'Foreign or missing planned draw')
    output = []
    fields = ('estimate', 'lower', 'upper', 'missing_rate', 'technical_missing_rate', 'semantic_unclear_rate')
    for source in sources:
        planned = [by_source[source['source_id']].get(draw) for draw in source['draws']]
        need(all(row is not None for row in planned), 'Every planned draw must have an explicit row')
        item = {field: mean(r.get(field) for r in planned) for field in fields}
        item.update(source_id=source['source_id'], planned_draws=len(planned),
                    cohort=source['cohort'], family=source['family'],
                    planned_draw_statistics=planned)
        output.append(item)
    result = {field: mean(row.get(field) for row in output) for field in fields}
    result.update(defined=result['estimate'] is not None, sources=output,
        independent_source_count=len(sources), planned_draw_count=len(rows),
        denominator=sum(r['denominator'] for r in rows) if all(r['denominator'] is not None for r in rows) else None,
        undefined_denominators=sum(not r['defined'] for r in rows),
        undefined_denominator_states=dict(Counter(r.get('reason', 'undefined') for r in rows if not r['defined'])),
        aggregation='mean planned draws within source, then equal source mean')
    if all(r['denominator'] is not None and r['denominator'] > 0 for r in rows):
        result['pooled_missing_rate'] = sum(r.get('semantic_unclear', 0) + r.get('technical_missing', 0) for r in rows) / result['denominator']
    else:
        result['pooled_missing_rate'] = None
    result['missing_rate_over_10_percent'] = any(v is not None and v > .10 for v in
        (result['missing_rate'], result['pooled_missing_rate']))
    return result


def _index(rows, keyfields):
    result = {}
    for row in rows:
        key = tuple(row[k] for k in keyfields)
        need(key not in result, 'Duplicate normalized record: ' + repr(key))
        result[key] = row
    return result


def _h1_draws(bundle, cells, category=None):
    inventories = _index(bundle['H1_inventories'], ('source_id', 'draw', 'cell'))
    groups = defaultdict(list)
    for row in bundle['H1']:
        groups[row['source_id'], row['draw'], row['cell']].append(row)
    planned = {(s['source_id'], d, c) for s in bundle['sources'] for d in s['draws'] for c in cells}
    need(set(inventories) <= planned and set(groups) <= planned, 'Foreign H1 source/draw/cell')
    output = defaultdict(list)
    for source in bundle['sources']:
        for draw in source['draws']:
            for cell in cells:
                key = source['source_id'], draw, cell
                inv = inventories.get(key)
                rows = groups[key]
                need(len({r['unit_id'] for r in rows}) == len(rows), 'Duplicate H1 occurrence within a cell')
                denominator = inv['occurrence_count'] if inv is not None else None
                if denominator is not None:
                    need(type(denominator) is int and denominator >= 0 and len(rows) <= denominator,
                         'H1 census cannot exceed the original native denominator')
                if category is not None:
                    # No type denominator is invented from a partial census.
                    denominator = sum(r['category'] == category for r in rows) if denominator is not None and len(rows) == denominator else None
                    rows = [r for r in rows if r['category'] == category]
                counts = Counter()
                for row in rows:
                    code, status = row['raw_code'], row['measurement_status']
                    need(code is None or code in NEGATIVE | UNCLEAR | {'supported', 'failed', 'not_judged'},
                         'Unrecognized H1 raw code')
                    if status != 'valid' or code in (None, 'failed', 'not_judged'):
                        counts['technical'] += 1
                    elif code == 'supported':
                        counts['success'] += 1
                    elif code in NEGATIVE:
                        counts['failure'] += 1
                    else:
                        counts['unclear'] += 1
                if denominator is not None:
                    counts['technical'] += denominator - len(rows)
                output[cell].append(ratio_record(counts['success'], counts['failure'], counts['unclear'], counts['technical'],
                    denominator, source_id=source['source_id'], draw=draw, cell=cell, category=category))
    return output


def _h2_draws(bundle, cells):
    roster = defaultdict(set)
    for row in bundle['H2_roster']:
        need(row['obligation_id'] not in roster[row['source_id']], 'Duplicate fixed H2 reference')
        roster[row['source_id']].add(row['obligation_id'])
    need(set(roster) <= {s['source_id'] for s in bundle['sources']}, 'Foreign H2 roster source')
    observed = _index(bundle['H2'], ('source_id', 'draw', 'cell', 'obligation_id'))
    planned_keys = set()
    output = defaultdict(list)
    for source in bundle['sources']:
        sid = source['source_id']
        need(bool(roster[sid]), 'Every planned source requires a positive fixed H2 denominator')
        for draw in source['draws']:
            for cell in cells:
                counts = Counter()
                for obligation in sorted(roster[sid]):
                    key = sid, draw, cell, obligation
                    planned_keys.add(key)
                    row = observed.get(key)
                    if row is None or row['status'] != 'valid':
                        counts['technical'] += 1
                        continue
                    code = row['raw_code']
                    need(code in RETENTION, 'Unrecognized valid H2 raw code')
                    if code == 'retained':
                        counts['success'] += 1
                    elif code in ('partially_retained', 'not_retained'):
                        counts['failure'] += 1
                    else:
                        counts['unclear'] += 1
                output[cell].append(ratio_record(counts['success'], counts['failure'], counts['unclear'], counts['technical'],
                    len(roster[sid]), source_id=sid, draw=draw, cell=cell))
    need(set(observed) <= planned_keys, 'Foreign H2 reference/source/draw/cell')
    return output


def _h3_draws(bundle, cells):
    raw = _index(bundle.get('H3', []), ('source_id', 'draw', 'cell'))
    need(set(raw) <= {(s['source_id'], d, c) for s in bundle['sources'] for d in s['draws'] for c in cells},
         'Foreign H3 source/draw/cell')
    output = {name: defaultdict(list) for name in ('H3_direct_content_fraction', 'H3_occurrence_capacity')}
    for source in bundle['sources']:
        for draw in source['draws']:
            for cell in cells:
                row = raw.get((source['source_id'], draw, cell))
                for endpoint in output:
                    if endpoint == 'H3_direct_content_fraction':
                        value = (row.get('categories') or {}).get('ALL', {}) if row else {}
                        numerator, denominator = value.get('direct_content_found'), value.get('native_objects')
                        ratio = value.get('H3_direct_content_fraction')
                        raw_metric = 'categories.ALL.H3_direct_content_fraction'
                    else:
                        value = (row.get('projected_occurrence_capacity') or {}) if row else {}
                        numerator, denominator = value.get('retained_occurrences'), value.get('expected_occurrences')
                        ratio = value.get('occurrence_fraction')
                        raw_metric = 'projected_occurrence_capacity.occurrence_fraction'
                    if denominator is None or denominator == 0:
                        item = ratio_record(0, 0, 0, 0, denominator)
                    elif ratio is None:
                        item = ratio_record(0, 0, 0, denominator, denominator)
                        item.update(estimate=None, defined=False, reason='A6 field not measured')
                    else:
                        need(type(numerator) is int and type(denominator) is int and 0 <= numerator <= denominator
                             and abs(ratio - numerator / denominator) <= 1e-12, 'Original A6 ratio/count mismatch')
                        item = ratio_record(numerator, denominator - numerator, 0, 0, denominator)
                    output[endpoint][cell].append({**item, 'source_id': source['source_id'], 'draw': draw,
                        'cell': cell, 'raw_metric': raw_metric, 'whole_statement_multiplicity_metric_identified': False})
    return output


def _qa(bundle, cells, questions):
    rows = _index(bundle['QA'], ('question_id', 'cell', 'context_mode'))
    allowed = set(questions)
    need(all(key[0] in allowed for key in rows), 'Foreign frozen QA question')
    need(all((key[2] == 'graph' and key[1] in cells) or
             (key[2] in ('empty', 'gold') and key[1] == key[2].upper()) for key in rows),
         'Foreign QA cell/context; N6 passage route is not performed')
    results, maps = {}, {}
    for cell in cells:
        paired = {}
        for metric in ('f1', 'em'):
            values = {}
            for qid in questions:
                row = rows.get((qid, cell, 'graph'))
                value = row.get(metric) if row is not None and row['observed'] else None
                need(value is None or (type(value) in (int, float) and isfinite(value)
                     and 0 <= value <= 1 and (metric != 'em' or value in (0, 1))), 'Invalid unrounded QA metric')
                values[qid] = value
            known = [v for v in values.values() if v is not None]
            missing = len(questions) - len(known)
            result = {'cell': cell, 'endpoint': 'F1' if metric == 'f1' else 'EM',
                'estimate': mean(values.values()), 'lower': fsum(known) / len(questions),
                'upper': (fsum(known) + missing) / len(questions), 'denominator': len(questions),
                'missing_rate': missing / len(questions), 'technical_missing_rate': missing / len(questions),
                'semantic_unclear_rate': 0, 'defined': missing == 0, 'observed_questions': len(known),
                'completed_subset_descriptive': mean(known), 'completed_subset_denominator': len(known),
                'missing_never_scored_as_empty_answer': True}
            results[metric, cell], maps[metric, cell] = result, values
    return results, maps


def _difference(treatment, control):
    return treatment - control if treatment is not None and control is not None else None


def _effort(rows):
    groups = defaultdict(list)
    seen = {}
    for index, row in enumerate(rows):
        # Alternative tariff projections stay separate. Only an explicit
        # accounting identity justifies collapsing two metering records.
        identity = row.get('receipt_id') or row.get('request_id')
        if identity is not None:
            identity = identity, row.get('pricing_scenario'), row.get('currency')
        if identity is not None:
            if identity in seen:
                need(seen[identity] == row, 'Conflicting duplicate effort receipt')
                continue
            seen[identity] = row
        arm = row.get('arm') or 'shared/unallocated'
        groups[row.get('package', 'unspecified'), row.get('population', 'unspecified'),
               arm, row.get('currency'), row.get('pricing_scenario', 'unspecified')].append(row)
    result = []
    for (package, population, arm, currency, scenario), entries in groups.items():
        def subtotal(field):
            values = [r.get(field) for r in entries if r.get(field) is not None]
            need(all(type(v) is int and v >= 0 for v in values), 'Nonnegative integer usage meter required')
            return sum(values) if values else None
        costs = [Decimal(str(r['known_cost'])) for r in entries if r.get('known_cost') is not None]
        holds = [Decimal(str(r['reserved_or_held_cost'])) for r in entries if r.get('reserved_or_held_cost') is not None]
        need(all(v.is_finite() and v >= 0 for v in costs + holds), 'Finite nonnegative cost required')
        result.append({'package': package, 'population': population, 'arm': arm, 'currency': currency,
            'pricing_scenario': scenario, 'accounting_rows': len(entries),
            'calls_known': subtotal('call_count'), 'calls_unknown': sum(r.get('call_count') is None for r in entries),
            'physical_POSTs_known': subtotal('physical_POSTs'),
            'physical_POSTs_unknown_records': sum(r.get('physical_POSTs') is None for r in entries),
            'prompt_tokens_known': subtotal('prompt_tokens'), 'output_tokens_known': subtotal('completion_tokens'),
            'cache_write_tokens_known': subtotal('cache_write_tokens'), 'cache_read_tokens_known': subtotal('cache_read_tokens'),
            'usage_missing': sum(r.get('prompt_tokens') is None or r.get('completion_tokens') is None for r in entries),
            'cost_known': str(sum(costs)) if costs else None,
            'reserved_or_held_cost_known': str(sum(holds)) if holds else None,
            'held_cost_is_spend': False,
            'cost_complete': all(r.get('cost_complete') is True and r.get('known_cost') is not None for r in entries),
            'unknown_execution': sum(r.get('unknown_execution') is not False for r in entries),
            'invoice_verified': all(r.get('invoice_verified') is True for r in entries),
            'identity_missing_rows': sum(not (r.get('receipt_id') or r.get('request_id')) for r in entries),
            'counting_scope': 'request/receipt IDs deduplicated; dependent cells are not new calls',
            'currency_conversion': False})
    return result


def _descriptive_source_interval(control, treatment, indices):
    """Same paired cluster draws, percentile intervals only; no secondary test."""
    import numpy as np
    def samples(left_field, right_field):
        left, right = [r[left_field] for r in control], [r[right_field] for r in treatment]
        if any(v is None for v in left + right):
            return None
        return (np.asarray(right)-np.asarray(left))[indices].mean(axis=1)
    def interval(low, high):
        if low is None or high is None:
            return None
        return {'lower': float(np.quantile(low, .025, method='linear')),
                'upper': float(np.quantile(high, .975, method='linear'))}
    point = samples('estimate', 'estimate')
    return {'ci95': interval(point, point),
            'identification_sensitivity95': interval(samples('upper', 'lower'), samples('lower', 'upper')),
            'CI_scope': 'marginal descriptive percentile; no secondary test or multiplicity claim'}


def _descriptive_score_interval(rows, indices):
    """N8 type scores, same source draws, no additional hypothesis test."""
    import numpy as np
    values = [row.get('estimate') for row in rows]
    if any(value is None for value in values):
        return None
    samples = np.asarray(values, dtype=float)[indices].mean(axis=1)
    return {'lower': float(np.quantile(samples, .025, method='linear')),
            'upper': float(np.quantile(samples, .975, method='linear'))}


def _construction_diagnostics(bundle):
    supplied = bundle.get('construction_diagnostics', {})
    joint = supplied.get('N5_joint', {})
    attempted, rejected = joint.get('completed_joint_responses'), joint.get('rejected_joint_responses')
    need(attempted is None or type(attempted) is int and attempted >= 0, 'Invalid N5 denominator')
    need(rejected is None or type(rejected) is int and rejected >= 0 and
         (attempted is None or rejected <= attempted), 'Invalid N5 rejection count')
    return {'N2_guard': supplied.get('N2_guard', {'status': 'not_provided',
                'retained_unverified_count': None, 'failed_guard_is_not_evaluation_missingness': True}),
        'N5_joint': {'V1': {**joint, 'completed_joint_responses': attempted,
            'rejected_joint_responses': rejected,
            'rejection_rate': rejected/attempted if attempted and rejected is not None else None,
            'status': 'provided' if joint else 'not_provided',
            'spent_tokens_and_cost_are_effort_even_when_rejected': True},
            'AS': {'status': 'not_applicable', 'rejection_rate': None},
            'prospective_B4_change_not_original_G2_confirmation': True, 'B3_bindings_rewritten': False},
        'N6': {'passage_endpoint': 'not_performed', 'reason': 'resource_scope_decision',
            'planned_graph_answer_positions': 480, 'planned_control_answer_positions': 120,
            'answer_positions_are_not_physical_POSTs': True}}


def analyze(bundle, contract):
    """Execute the frozen primary family and all descriptive cell endpoints."""
    from . import inference as inf
    from .secondary import distinct_supported, human_weighted_prevalence
    from .grok_sensitivity import summarize as grok_sensitivity
    from .components import analyze_components
    from .judgment import overall_judgment
    from .efficiency import compute_efficiency
    from . import n10_sampling as n10
    from . import n14_missingness as n14
    if bundle.get('synthetic') is not True:
        n14.require_publication(contract)
    cells, sources = contract['cells'], bundle['sources']
    need(bundle['cells'] == cells, 'All eight frozen cells required in order')
    expected = {s['source_id']: (s['draws'], s['cohort'], s['family']) for s in contract['sources']}
    need(len(sources) == len(expected) and
         {s['source_id']: (s['draws'], s['cohort'], s['family']) for s in sources} == expected,
         'Frozen source/planned-draw/cohort/family roster differs')
    need([s['source_id'] for s in sources] == [s['source_id'] for s in contract['sources']],
         'Frozen source order must bind the seeded bootstrap indices')
    need(bundle['question_ids'] == contract['question_ids'], 'Frozen question order differs')
    need(bundle['QA_blocks'] == contract['qa_blocks'], 'Frozen QA overlap blocks cannot be regrouped')
    need(len(bundle['H2_roster']) == 200, 'Frozen 200-reference H2 roster required')
    roster_counts = Counter(r['source_id'] for r in bundle['H2_roster'])
    need(all(roster_counts[s['source_id']] == s['reference_count'] for s in contract['sources']
             if 'reference_count' in s), 'Frozen per-source H2 reference count differs')
    indices = inf.cluster_indices(len(sources))
    sampled_h1 = None
    if n10.active(bundle):
        need(contract.get('N10_publication', {}).get('single_path_commit') is True,
             'N10 must be published before the sampled H1 analysis')
        sampled_h1 = n10.estimate(bundle, cells, indices=indices)
    scores = {'H1': sampled_h1.by_draw if sampled_h1 is not None else _h1_draws(bundle, cells),
              'H2': _h2_draws(bundle, cells), **_h3_draws(bundle, cells)}
    aggregates = {endpoint: sampled_h1.aggregates if endpoint == 'H1' and sampled_h1 is not None else
                  {cell: _source_equal(rows[cell], sources) for cell in cells}
                  for endpoint, rows in scores.items()}
    qa, qa_maps = _qa(bundle, cells, contract['question_ids'])
    control, treatment = contract['primary_control'], contract['primary_treatment']
    primary, sensitivity = {}, {}
    for hypothesis in ('H1', 'H2'):
        left, right = aggregates[hypothesis][control]['sources'], aggregates[hypothesis][treatment]['sources']
        boundary = -.05 if hypothesis == 'H2' else 0.
        primary[hypothesis] = (sampled_h1.contrast(control, treatment, null_boundary=boundary)
            if hypothesis == 'H1' and sampled_h1 is not None else
            inf.paired_source_bootstrap([r['estimate'] for r in left], [r['estimate'] for r in right],
                control_lower=[r['lower'] for r in left], control_upper=[r['upper'] for r in left],
                treatment_lower=[r['lower'] for r in right], treatment_upper=[r['upper'] for r in right],
                indices=indices, null_boundary=boundary))
        c, t = aggregates[hypothesis][control], aggregates[hypothesis][treatment]
        primary[hypothesis]['delta_identification_bounds'] = {
            'lower': _difference(t['lower'], c['upper']),
            'upper': _difference(t['upper'], c['lower'])}
        differences = [_difference(b['estimate'], a['estimate']) for a, b in zip(left, right)]
        sensitivity[hypothesis + '_Wilcoxon'] = inf.wilcoxon_sensitivity(differences, null_boundary=boundary)
    if sampled_h1 is not None:
        draw_first = {cell: _source_equal(sampled_h1.by_draw[cell], sources) for cell in cells}
        sensitivity['H1_G2_draw_first_aggregation'] = {
            'role': 'prespecified_descriptive_sensitivity_on_the_same_selected_occurrences',
            'cells': draw_first,
            'not_a_N10_sampling_uncertainty_substitute': True,
            'primary_point_difference': _difference(draw_first[treatment]['estimate'], draw_first[control]['estimate']),
            **_descriptive_source_interval(draw_first[control]['sources'], draw_first[treatment]['sources'], indices)}
    qa_indices = inf.cluster_indices(len(contract['qa_blocks']))
    primary['H4'] = inf.paired_question_bootstrap(qa_maps['f1', control], qa_maps['f1', treatment],
        contract['qa_blocks'], indices=qa_indices)
    sensitivity['EM_McNemar'] = inf.mcnemar_sensitivity(
        [qa_maps['em', control][q] for q in contract['question_ids']],
        [qa_maps['em', treatment][q] for q in contract['question_ids']])
    holm = inf.holm_primary({h: primary[h]['raw_p'] for h in ('H1', 'H2', 'H4')})
    for hypothesis, value in primary.items():
        value.update(control=control, treatment=treatment,
            adjusted_p=holm['results'][hypothesis]['adjusted_p'], reject=holm['results'][hypothesis]['reject'])
        delta = value['point_difference']
        value['criterion_met'] = value['reject'] and (hypothesis == 'H2' or delta is not None and delta > 0)
    primary['H4']['descriptive_nondecrease'] = (primary['H4']['point_difference'] >= 0
        if primary['H4']['point_difference'] is not None else None)
    h2_restriction = n14.SourceRestriction(aggregates['H2'], sources, indices) if n14.active(contract) else None
    n14_result = None
    if h2_restriction is not None:
        additional = h2_restriction.contrast(control, treatment, null_boundary=-.05)
        additional['identifier'] = 'H2'
        additional_holm = inf.holm_primary({'H1': primary['H1']['raw_p'],
                                           'H2': additional['raw_p'], 'H4': primary['H4']['raw_p']})
        n14.apply_decision(primary['H2'], additional, additional_holm['results']['H2'])
        primary['H2']['superiority_claim_allowed'] = False
        n14_result = {'enabled': True, 'primary': additional, 'primary_holm': additional_holm,
            'coverage': h2_restriction.coverage(),
            'rule': 'Noninferiority requires G2 and N14 Holm confirmation; original G2 numbers/decisions remain separately reported',
            'unchanged_primary_slots': ['H1', 'H4'], 'H2_superiority_claim_allowed': False,
            'H2_superiority_reason': 'H2 is the preregistered noninferiority test, not a new superiority test',
            'replay_or_new_judgments': False, 'G2_primary_numerical_results_unchanged': True}
    table = [{**value, 'endpoint': endpoint, 'cell': cell} for endpoint, values in aggregates.items() for cell, value in values.items()]
    table.extend(qa.values())
    comparisons = [(cell, control) for cell in cells if cell != control]
    # Controlled component contrasts are descriptive; V1 is a bundled SCOPE+Joint arm.
    comparisons.extend([('AS_G_ORIGINAL', 'AS_ORIGINAL'), ('V2_ORIGINAL', 'V1_ORIGINAL'),
        ('V1_ORIGINAL', 'AS_ORIGINAL'), *[(arm+'_ROW', arm+'_ORIGINAL') for arm in ('AS','AS_G','V1','V2')]])
    ablations = []
    for endpoint in (*aggregates, 'F1', 'EM'):
        values = aggregates.get(endpoint) or {cell: qa['f1' if endpoint == 'F1' else 'em', cell] for cell in cells}
        for t, b in dict.fromkeys(comparisons):
            if endpoint in aggregates:
                if endpoint == 'H1' and sampled_h1 is not None:
                    result = sampled_h1.contrast(b, t)
                    intervals = {key: result[key] for key in ('ci95', 'identification_sensitivity95')}
                else:
                    intervals = _descriptive_source_interval(values[b]['sources'], values[t]['sources'], indices)
            else:
                metric = 'f1' if endpoint == 'F1' else 'em'
                res = inf.paired_question_bootstrap(qa_maps[metric, b], qa_maps[metric, t],
                    contract['qa_blocks'], indices=qa_indices)
                intervals = {key: res[key] for key in ('ci95', 'identification_sensitivity95')}
            ablations.append({'endpoint': endpoint, 'control': b, 'treatment': t,
                'point_difference': _difference(values[t]['estimate'], values[b]['estimate']),
                **intervals,
                'role': 'secondary_descriptive', 'no_extra_primary_family': True})
    agreement = {}
    current_author_rows = []
    for name in ('human', 'grok'):
        rows = bundle.get('agreement', {}).get(name, [])
        if sampled_h1 is not None:
            rows = n10.current_reference_rows(bundle, rows)
        panels = {'all': rows}
        if name == 'grok':
            panels.update(random_core=[r for r in rows if r.get('in_base_sample')],
                augmentation_only=[r for r in rows if not r.get('in_base_sample') and r.get('in_removal_panel')])
        reports = {panel: inf.cohens_kappa([r['reference_label'] for r in data], [r['label'] for r in data])
                   for panel, data in panels.items()}
        agreement[name] = {**reports['all'], 'panels': reports, 'n_selected': len(rows),
            'labels_never_replace_primary_C2': True, 'unweighted_sample_is_population_prevalence': False}
        if name == 'human':
            current_author_rows = rows
            design = bundle.get('agreement', {}).get('human_strata', [])
            agreement[name]['weighted_prevalence'] = human_weighted_prevalence(rows, design) if design else None
        else:
            agreement[name]['directional_sensitivity'] = grok_sensitivity(bundle,
                core_fraction=contract['second_evaluator_core_fraction']) if rows else None
    components = analyze_components(aggregates, qa_maps, contract, indices=indices, qa_indices=qa_indices,
        h1_bootstrap=sampled_h1.contrast if sampled_h1 is not None else None,
        h2_restriction=h2_restriction)
    if n14_result is not None:
        component_extra = components['N14_H2_missingness']
        n14_result['components'] = component_extra['contrasts']
        n14_result['component_holm'] = component_extra['holm']
    grok_direction = ((agreement['grok'].get('directional_sensitivity') or {}).get('direction') or {})
    from .author_qualification import author_qualification
    author_check = author_qualification(agreement['human'], bundle.get('agreement', {}), current_author_rows)
    agreement['human']['N8_qualification_statistic'] = author_check
    overall = overall_judgment(primary, human_kappa=author_check['kappa'],
        grok_h1_difference=grok_direction.get('point_difference'),
        c4_available=grok_direction.get('point_difference') is not None,
        c7_available=agreement['human']['N_pair'] > 0)
    if n14_result is not None:
        overall['N14_H2_missingness_required'] = True
        overall['qualifications'].append(
            'H2-Nichtunterlegenheit setzt nach N14 die Holm-Bestätigung sowohl in der unveränderten G2-Analyse '
            'als auch auf Quellen mit gültigen Urteilen in beiden Kontrastarmen voraus. '
            'Die eingeschränkte Quellenmenge ist keine nachgewiesene Zufallsstichprobe aller geplanten Quellen.')
    if sampled_h1 is not None:
        overall['qualifications'].append(
            'H1 beruht auf dem kostenbegrenzt gezogenen N10-Präfix mit nur näherungsweise gleichen Inklusionswahrscheinlichkeiten.')
        if any(row['technical_missing'] > 0 for values in scores['H2'].values() for row in values):
            overall['qualifications'].append(
                'Fehlende C3-Urteile werden nach G2 behandelt. Das H2-Ergebnis ist kein Nachweis einer vollständigen Quellenprüfung.')
    for verdict in components['verdicts'].values():
        if verdict.get('H1_evaluator_qualification_required'):
            verdict['H1_qualification'] = overall['H1_qualification']
            verdict['missing_counterchecks'] = list(overall['missing_counterchecks'])
            if overall['evaluator_dependent']:
                verdict['statement'] += ' Aussagen zur H1-Quellenstützung sind bewerterabhängig.'
            if sampled_h1 is not None:
                verdict['H1_sampling_qualification'] = 'N10: nur näherungsweise gleiche Inklusion im kostenbegrenzten Präfix'
                verdict['statement'] += ' H1 beruht auf der N10-Stichprobennäherung.'
    efficiency = compute_efficiency(bundle.get('K2_effort', []), dict(scores['H1']), sources,
        population_sources={'Konfirmation': [source['source_id'] for source in sources]})
    if sampled_h1 is not None:
        # N10 estimates a rate, not the census count needed by per-supported-unit efficiency.
        for row in efficiency['rows']:
            row.update(support_complete=False, complete_for_efficiency_comparison=False,
                       supported_count_basis='observed supported occurrences only, N10 sample not a census')
            for field in ('cost_per_supported', 'currency_component_cost_per_supported',
                          'tokens_per_supported', 'supported_per_1000_construction_tokens'):
                row[field] = None
            row['reasons'] = sorted(set(row['reasons']) | {'N10_supported_census_count_not_identified'})
    strata = []
    for dimension in ('cohort', 'family'):
        for level in dict.fromkeys(s[dimension] for s in sources):
            selection = [s for s in sources if s[dimension] == level]
            ids = {s['source_id'] for s in selection}
            for endpoint, groups in scores.items():
                for cell in cells:
                    value = (n10.aggregate_sources(
                        [r for r in aggregates['H1'][cell]['sources'] if r['source_id'] in ids], selection)
                        if endpoint == 'H1' and sampled_h1 is not None else
                        _source_equal([r for r in groups[cell] if r['source_id'] in ids], selection))
                    strata.append({'dimension': dimension, 'level': level, 'endpoint': endpoint, 'cell': cell,
                        'estimate': value['estimate'], 'lower': value['lower'], 'upper': value['upper'],
                        'missing_rate': value['missing_rate'], 'source_count': len(selection), 'role': 'secondary_descriptive'})
    for category in ('EE', 'EV', 'VV'):
        typed = (n10.estimate(bundle, cells, matrix=sampled_h1.matrix, category=category)
                 if sampled_h1 is not None else None)
        groups = typed.by_draw if typed is not None else _h1_draws(bundle, cells, category)
        for cell in cells:
            value = typed.aggregates[cell] if typed is not None else _source_equal(groups[cell], sources)
            strata.append({'dimension': 'category', 'level': category, 'endpoint': 'H1', 'cell': cell,
                'estimate': value['estimate'], 'lower': value['lower'], 'upper': value['upper'],
                'sources': value['sources'],
                'missing_rate': value['missing_rate'], 'source_count': len(sources), 'role': 'secondary_descriptive',
                'ci95': typed.score_interval(cell) if typed is not None else _descriptive_score_interval(value['sources'], indices),
                'CI_scope': ('marginal descriptive two-stage source/group percentile, approximate N10 sampling, no additional test'
                             if typed is not None else 'marginal descriptive source-bootstrap percentile, no additional test')})
    controls = []
    for mode in ('empty', 'gold'):
        rows = {r['question_id']: r for r in bundle['QA'] if r['context_mode'] == mode}
        values = [rows[q]['f1'] if q in rows and rows[q]['observed'] else None for q in contract['question_ids']]
        known = [v for v in values if v is not None]
        controls.append({'mode': mode, 'planned': len(contract['question_ids']), 'provided': len(rows),
            'observed': len(known), 'F1': mean(values),
            'lower': fsum(known)/len(values), 'upper': (fsum(known)+len(values)-len(known))/len(values),
            'scope': 'secondary context control; not a graph-only H4 substitute'})
    return {'synthetic': bundle.get('synthetic') is True,
        'metadata': {'sources': len(sources), 'paired_source_draw_units': sum(len(s['draws']) for s in sources),
            'QA_questions': len(contract['question_ids']), 'QA_blocks': len(contract['qa_blocks']),
            'bootstrap_draws': 10000, 'bootstrap_seed': 2026102407,
            'analysis_contract_pin': contract['frozen_pin'],
            'aggregation_order': ('N10 H1 pooled sampled occurrences within source, then equal sources; H2 unchanged'
                                  if sampled_h1 is not None else 'planned draws, then equal sources')},
        'primary': primary, 'holm': holm, 'sensitivities': sensitivity, 'cells': table,
        'components': components, 'overall_judgment': overall, 'efficiency': efficiency,
        'ablations': ablations, 'strata': strata, 'effort': _effort(bundle.get('effort', [])),
        'missing_rate_limitations': [{'endpoint': endpoint, 'cell': cell,
            'source_equal_missing_rate': value['missing_rate'], 'pooled_missing_rate': value['pooled_missing_rate'],
            'limitation': 'More than 10 percent unclear/technical missing judgments; no row exclusion.'}
            for endpoint in ('H1','H2') for cell, value in aggregates[endpoint].items()
            if value['missing_rate_over_10_percent']],
        'agreement': agreement, 'distinct_supported': distinct_supported(bundle), 'QA_controls': controls,
        'H3_original_measurements': bundle.get('H3', []),
        'construction_diagnostics': _construction_diagnostics(bundle),
        'amendments': contract['amendments'],
        'N14_H2_missingness': n14_result,
        'N10_H1_sampling': sampled_h1.sampling_info if sampled_h1 is not None else None,
        'limits': ['SYNTHETIC preparation is not empirical evidence.',
            'H1 and H2 unclear/technical missing judgments score symmetrically zero, not factual false.',
            'H3 original A6 fields retain different denominators; no whole-statement multiplicity score identified.',
            'QA missing values are unknown; no complete-case primary substitution.',
            'Bootstrap CIs are marginal; K1-K6 form a separate secondary Holm family. Other ablations/strata/H3/EM remain descriptive.',
            'One constructor model, selected reference meanings, no universal or schema-superiority claim.',
            'N5 is a later construction rule; N6 passage endpoint is not performed.'] + (
                ['N10 H1 uses an approximately probability-sampled cost-stopped prefix. Informative stopping is possible.',
                 'Unselected occurrences are not missing judgments. Empty sampled source/cells remain nonestimable with [0,1] sensitivity bounds.',
                 'N10 H1/K1/K3/K6 reuse one two-stage source/original-group matrix, without finite-population correction.']
                if sampled_h1 is not None else [])}
