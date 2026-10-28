"""N17 section 2 source, family and construction-draw sensitivities.

Pure arithmetic over supplied normalized inputs.  No file/provider access, new
judgments, bootstrap, test, outcome-dependent source replacement or new seed.
H1 reuses N10's pooled-within-source estimates and its selected by-draw scores.
H2 reuses D1's original G2 scoring and equal-source aggregation.  The N14 source
set is fixed once per contrast over all originally planned draws, including
when a separate construction draw has no technically valid judgment.
"""
from math import fsum, isfinite, isclose
from numbers import Real

from Experiments.fair_v2_oct24.D1.analysis import _h2_draws, _source_equal
from Experiments.fair_v2_oct24.D1.n14_missingness import _valid_count


CONTRASTS = (
    ('V2_ROW-AS_ORIGINAL', 'AS_ORIGINAL', 'V2_ROW'),
    ('V1_ROW-AS_ORIGINAL', 'AS_ORIGINAL', 'V1_ROW'),
    ('AS_G_ROW-AS_ORIGINAL', 'AS_ORIGINAL', 'AS_G_ROW'),
    ('V2_ROW-V1_ROW', 'V1_ROW', 'V2_ROW'),
)
REQUIRED_CELLS = tuple(dict.fromkeys(c for _, a, b in CONTRASTS for c in (a, b)))


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _mean(values):
    return fsum(values) / len(values) if values and all(v is not None for v in values) else None


def _value(row):
    value = row.get('estimate') if row is not None else None
    _need(value is None or (isinstance(value, Real) and not isinstance(value, bool)
          and isfinite(value) and 0 <= value <= 1), 'Source estimate must be a finite rate or None')
    return float(value) if value is not None else None


def _source_map(rows, sources):
    allowed = {s['source_id'] for s in sources}
    result = {}
    for row in rows:
        sid = row['source_id']
        _need(sid in allowed and sid not in result, 'Foreign or duplicate source estimate')
        source = next(s for s in sources if s['source_id'] == sid)
        for field in ('family', 'cohort'):
            _need(field not in row or row[field] == source[field], 'Frozen source metadata differs')
        result[sid] = _value(row)
    # An absent H1 source statistic is unknown, never a sampled failure or zero.
    return {s['source_id']: result.get(s['source_id']) for s in sources}


def _draw_maps(by_draw, sources, cell):
    planned = {(s['source_id'], d) for s in sources for d in s['draws']}
    result = {}
    for row in by_draw.get(cell, []):
        key = row['source_id'], row['draw']
        _need(key in planned and key not in result, 'Foreign or duplicate source/draw estimate')
        result[key] = _value(row)
    return result


def _point(ids, control, treatment):
    c_values, t_values = [control[sid] for sid in ids], [treatment[sid] for sid in ids]
    c, t = _mean(c_values), _mean(t_values)
    difference = t - c if c is not None and t is not None else None
    return {
        'source_count': len(ids), 'control_mean': c, 'treatment_mean': t,
        'point_difference': difference, 'difference': difference,
        'defined': c is not None and t is not None,
        'undefined_control_source_ids': [sid for sid in ids if control[sid] is None],
        'undefined_treatment_source_ids': [sid for sid in ids if treatment[sid] is None],
    }


def _omission_summary(rows, full_delta, *, key):
    for row in rows:
        delta = row['point_difference']
        deviation = delta - full_delta if delta is not None and full_delta is not None else None
        row.update(deviation_from_full=deviation,
                   absolute_deviation_from_full=abs(deviation) if deviation is not None else None)
    defined = [r['point_difference'] for r in rows if r['point_difference'] is not None]
    influential = [r for r in rows if r['absolute_deviation_from_full'] is not None]
    maximum = max((r['absolute_deviation_from_full'] for r in influential), default=None)
    ties = [r for r in influential if isclose(r['absolute_deviation_from_full'], maximum,
                                            rel_tol=1e-12, abs_tol=1e-15)] if maximum is not None else []
    return {
        'rows': rows,
        'range': {'minimum': min(defined) if defined else None,
                  'maximum': max(defined) if defined else None,
                  'defined_omissions': len(defined), 'total_omissions': len(rows)},
        'most_influential': ties[0] if ties else None,
        'equally_influential_omissions': [r[key] for r in ties],
        'influence_defined': full_delta is not None and bool(influential),
        'unknown_values_omitted_from_range_only': len(defined) != len(rows),
    }


def _contrast(sources, maps, identifier, control, treatment, included, *, exclusions=None):
    ids = [s['source_id'] for s in sources if s['source_id'] in included]
    full = _point(ids, maps[control], maps[treatment])
    loo = [{**_point([x for x in ids if x != sid], maps[control], maps[treatment]),
            'omitted_source_id': sid, 'omitted_family': next(s['family'] for s in sources if s['source_id'] == sid)}
           for sid in ids]
    families = list(dict.fromkeys(s['family'] for s in sources if s['source_id'] in included))
    family_rows = []
    for family in families:
        omitted = [s['source_id'] for s in sources if s['source_id'] in included and s['family'] == family]
        family_rows.append({**_point([sid for sid in ids if sid not in omitted], maps[control], maps[treatment]),
                            'omitted_family': family, 'omitted_source_ids': omitted})
    return {
        'contrast': identifier, 'control': control, 'treatment': treatment,
        'included_source_ids': ids,
        'excluded_source_ids': [s['source_id'] for s in sources if s['source_id'] not in included],
        'source_count': len(ids), 'full': full,
        'source_differences': [{'source_id': sid,
            'point_difference': maps[treatment][sid] - maps[control][sid]
            if maps[treatment][sid] is not None and maps[control][sid] is not None else None}
            for sid in ids],
        'leave_one_source_out': _omission_summary(loo, full['point_difference'], key='omitted_source_id'),
        'leave_one_family_out': _omission_summary(family_rows, full['point_difference'], key='omitted_family'),
        'eligibility': exclusions,
        'aggregation': 'equal source mean of the supplied original source rates; paired treatment minus control',
    }


def analyze(bundle, h1_estimate):
    """Return descriptive LOO and fixed-population draw contrasts.

    ``h1_estimate`` is D1 n10_sampling.SampleEstimate.  No method is called on
    that object: only ``aggregates[cell]['sources']`` and ``by_draw`` are read.
    Return keys: metadata, endpoints[H1/H2_G2/H2_N14], by_draw.  Endpoint values
    are four contrast records, each with full, source/family omission rows,
    ranges and the greatest absolute deviation from its own full contrast.
    """
    sources, cells = bundle['sources'], bundle['cells']
    ids = [s['source_id'] for s in sources]
    _need(bool(ids) and len(ids) == len(set(ids)), 'Unique nonempty frozen source roster required')
    _need(set(REQUIRED_CELLS) <= set(cells) and len(cells) == len(set(cells)), 'Required unique contrast cells missing')
    _need(all(s.get('family') and s.get('cohort') and s.get('draws')
              and len(s['draws']) == len(set(s['draws'])) for s in sources), 'Frozen source metadata/draws required')
    h1 = {c: _source_map(h1_estimate.aggregates[c]['sources'], sources) for c in REQUIRED_CELLS}
    h1_draw = {c: _draw_maps(h1_estimate.by_draw, sources, c) for c in REQUIRED_CELLS}
    scores = _h2_draws(bundle, cells)
    h2_aggregates = {c: _source_equal(scores[c], sources) for c in cells}
    h2 = {c: _source_map(h2_aggregates[c]['sources'], sources) for c in REQUIRED_CELLS}
    valid = {c: {r['source_id']: _valid_count(r) for r in h2_aggregates[c]['sources']} for c in cells}
    no_valid = [sid for sid in ids if not any(valid[c][sid] for c in cells)]
    eligibility = {}
    for name, control, treatment in CONTRASTS:
        eligible = [sid for sid in ids if valid[control][sid] > 0 and valid[treatment][sid] > 0]
        eligibility[name] = {
            'included_source_ids': eligible,
            'excluded_source_ids': [sid for sid in ids if sid not in eligible],
            'all_cells_no_valid_judgment_source_ids': list(no_valid),
            'selection_basis': 'at least one technically valid H2 judgment in each arm over all originally planned draws',
            'selection_is_random_sample': False, 'fixed_across_draw_sensitivities': True,
            'valid_does_not_mean_retained': True,
        }

    endpoints = {
        'H1': [_contrast(sources, h1, *item, ids) for item in CONTRASTS],
        'H2_G2': [_contrast(sources, h2, *item, ids,
            exclusions={'planned_sources_including_G2_missing_zeros': True,
                        'all_cells_no_valid_judgment_source_ids': list(no_valid)}) for item in CONTRASTS],
        'H2_N14': [_contrast(sources, h2, *item, eligibility[item[0]]['included_source_ids'],
                            exclusions=eligibility[item[0]]) for item in CONTRASTS],
    }
    draws = list(dict.fromkeys(draw for s in sources for draw in s['draws']))
    by_draw = []
    for draw in draws:
        planned = [s for s in sources if draw in s['draws']]
        planned_ids = [s['source_id'] for s in planned]
        h1_values = {c: {sid: h1_draw[c].get((sid, draw)) for sid in planned_ids} for c in REQUIRED_CELLS}
        h2_values = {c: _source_map([r for r in scores[c] if r['draw'] == draw], planned)
                     for c in REQUIRED_CELLS}
        per_draw = {
            'H1': [_contrast(planned, h1_values, *item, planned_ids) for item in CONTRASTS],
            'H2_G2': [_contrast(planned, h2_values, *item, planned_ids) for item in CONTRASTS],
            'H2_N14': [_contrast(planned, h2_values, *item,
                [sid for sid in eligibility[item[0]]['included_source_ids'] if sid in planned_ids],
                exclusions=eligibility[item[0]]) for item in CONTRASTS],
        }
        by_draw.append({'draw': draw, 'source_count': len(planned), 'planned_source_ids': planned_ids,
                        'not_planned_source_ids': [sid for sid in ids if sid not in planned_ids],
                        'scope': 'only sources originally planned for this construction draw',
                        'additional_draw_with_restricted_roster': len(planned) != len(sources),
                        'endpoints': per_draw})
    return {
        'metadata': {'protocol': 'RB1-N17-robustness-v1', 'descriptive_only': True,
            'statistical_tests_performed': False, 'bootstrap_performed': False,
            'source_count': len(sources), 'planned_source_draw_units': sum(len(s['draws']) for s in sources),
            'family_definition': 'unchanged frozen source.family; sealed4 is a source cohort, not a text genre',
            'family_counts': {f: sum(s['family'] == f for s in sources) for f in dict.fromkeys(s['family'] for s in sources)},
            'H1_aggregation': 'reuse N10 pooled sampled occurrences within source, then equal source mean',
            'H1_by_draw': 'reuse N10 selected-occurrence by_draw rates; unsampled source/draw rates stay unknown',
            'H2_aggregation': 'reuse D1 _h2_draws and _source_equal; original G2 missing scores unchanged',
            'H2_no_valid_judgment_source_ids': no_valid,
            'N14_no_op_sources_are_robustness_cases': False,
            'no_new_judgments_or_replays': True},
        'endpoints': endpoints, 'by_draw': by_draw,
    }
