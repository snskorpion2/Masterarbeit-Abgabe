"""Requested final D1 readout from supplied, already calculated statistics.

No outcome files, model clients, bootstrap draws, tests or confidence intervals
are computed here. The extra VV means are explicitly descriptive means over
estimable source scores and never replace a frozen full-roster estimand.
"""
from copy import deepcopy
import csv
import json
from math import fsum, isfinite
from numbers import Real
from pathlib import Path


PROTOCOL = 'D1-requested-final-output-projection:v1'
CONTROL, TREATMENT = 'AS_ORIGINAL', 'V2_ROW'


def _need(condition, message):
    if not condition:
        raise ValueError('D1_REQUIRED_OUTPUTS: '+message)


def _dictionary(value, name):
    _need(type(value) is dict, name+' must be an explicit object')
    return value


def _score(value, name):
    _need(value is None or isinstance(value, Real) and not isinstance(value, bool)
          and isfinite(value) and 0 <= value <= 1, name+' must be finite [0,1] or null')


def _source_map(row, *, cell, endpoint, planned_n, expected_ids=None):
    sources = row.get('sources')
    _need(type(sources) is list, f'{endpoint}/{cell}: source estimates are missing; planned N is not estimable N')
    _need(len(sources) == planned_n, f'{endpoint}/{cell}: every planned source must be represented')
    values = {}
    for source in sources:
        _need(type(source) is dict and type(source.get('source_id')) is str and source['source_id'],
              f'{endpoint}/{cell}: explicit source ownership required')
        sid = source['source_id']
        _need(sid not in values, f'{endpoint}/{cell}: duplicate source ownership')
        _need('cell' not in source or source['cell'] == cell, f'{endpoint}/{cell}: source cell ownership differs')
        _need('endpoint' not in source or source['endpoint'] == endpoint,
              f'{endpoint}/{cell}: source endpoint ownership differs')
        _need('estimate' in source, f'{endpoint}/{cell}: source estimate must be explicit, including null')
        _score(source['estimate'], f'{endpoint}/{cell} estimate')
        values[sid] = source['estimate']
    if expected_ids is not None:
        _need(set(values) == set(expected_ids), f'{endpoint}/{cell}: source roster differs')
    return values


def _paired_counts(left, right, source_ids, *, endpoint, planned_n, eligible=None):
    scope = source_ids if eligible is None else [sid for sid in source_ids if sid in set(eligible)]
    counts = {'V2_better_sources': 0, 'equal_sources': 0, 'V2_worse_sources': 0,
              'not_estimable_sources': 0, 'pairwise_estimable_source_count': 0}
    for sid in scope:
        c, t = left[sid], right[sid]
        if c is None or t is None:
            counts['not_estimable_sources'] += 1
        else:
            counts['pairwise_estimable_source_count'] += 1
            counts['V2_better_sources' if t > c else 'V2_worse_sources' if t < c else 'equal_sources'] += 1
    return {'endpoint': endpoint, 'control': CONTROL, 'treatment': TREATMENT,
            'planned_source_count': planned_n, 'comparison_scope_source_count': len(scope),
            'outside_comparison_scope_source_count': planned_n-len(scope), **counts,
            'comparison': 'strict >, =, < on unrounded canonical source estimates; no tolerance',
            'scope': 'full planned population' if eligible is None else 'N14 contrast-specific eligible sources',
            'secondary_descriptive_only': True, 'new_hypothesis_test': False,
            'missing_judgment_scoring': 'Canonical conservative G2/N10 scores retained; a defined score is not proof of complete observed judgments.'}


def _effect(row, name):
    row = _dictionary(row, name)
    required = ('point_difference', 'ci95', 'raw_p', 'adjusted_p', 'reject',
                'delta_identification_bounds', 'identification_sensitivity95')
    _need(all(key in row for key in required), name+' lacks calculated effect/bounds/test fields')
    return {key: deepcopy(row[key]) for key in (
        *required, 'control_mean', 'treatment_mean', 'null_boundary', 'testable',
        'undefined_reason', 'cluster_count', 'defined_source_pairs') if key in row}


def build_requested_summary(report):
    """Project the requested outputs; read no inputs and change no decisions."""
    report = _dictionary(report, 'report')
    _need(type(report.get('synthetic')) is bool, 'explicit synthetic origin required')
    metadata = _dictionary(report.get('metadata'), 'metadata')
    planned_n = metadata.get('sources')
    _need(type(planned_n) is int and planned_n > 0, 'positive planned source count required')
    cells = report.get('cells')
    _need(type(cells) is list, 'canonical cell statistics required')
    indexed = {}
    for row in cells:
        _need(type(row) is dict, 'cell record must be an object')
        if row.get('endpoint') not in ('H1', 'H2'):
            continue
        key = row.get('endpoint'), row.get('cell')
        _need(key not in indexed, 'duplicate endpoint/cell statistics')
        indexed[key] = row
    _need(all((endpoint, cell) in indexed for endpoint in ('H1', 'H2')
              for cell in (CONTROL, TREATMENT)), 'both primary cells for H1/H2 required')
    left_h1 = _source_map(indexed['H1', CONTROL], cell=CONTROL, endpoint='H1', planned_n=planned_n)
    source_ids = list(left_h1)
    source_values = {('H1', CONTROL): left_h1}
    for endpoint in ('H1', 'H2'):
        for cell in (CONTROL, TREATMENT):
            if (endpoint, cell) not in source_values:
                source_values[endpoint, cell] = _source_map(indexed[endpoint, cell], cell=cell,
                    endpoint=endpoint, planned_n=planned_n, expected_ids=source_ids)

    primary = _dictionary(report.get('primary'), 'primary')
    effects = {endpoint:_effect(primary.get(endpoint), 'primary.'+endpoint) for endpoint in ('H1', 'H2', 'H4')}
    original = primary['H2']
    _need(type(original.get('g2_criterion_met')) is bool
          and type(original.get('n14_criterion_met')) is bool
          and type(original.get('criterion_met')) is bool,
          'separate G2, N14 and combined H2 criteria required')
    n14 = _dictionary(report.get('N14_H2_missingness'), 'N14_H2_missingness')
    _need(n14.get('enabled') is True, 'both explicitly calculated N14 H2 analyses required')
    additional = _dictionary(n14.get('primary'), 'N14 primary')
    extra_effect = _effect(additional, 'N14 primary')
    included, excluded = additional.get('included_source_ids'), additional.get('excluded_source_ids')
    _need(type(included) is list and type(excluded) is list
          and all(type(sid) is str for sid in included+excluded)
          and len(set(included+excluded)) == len(included+excluded)
          and set(included+excluded) == set(source_ids), 'N14 source populations must partition the original roster')
    _need(additional.get('eligible_source_count') == len(included)
          and additional.get('original_source_count') == planned_n, 'N14 source counts differ from its roster')
    _need(type(additional.get('criterion_met')) is bool
          and additional['criterion_met'] == original['n14_criterion_met'], 'N14 original/additional criteria disagree')

    sensitivities = _dictionary(report.get('sensitivities'), 'sensitivities')
    if ('H1_G2_draw_first_aggregation' not in sensitivities
            and 'N10_H1_sampling' in report and report['N10_H1_sampling'] is None):
        draw_first = {'status':'not_applicable_complete_C2_G2_aggregation_is_primary',
                      'role':'N10 budget-prefix fallback is inactive',
                      'primary_point_difference':None,'ci95':None,
                      'identification_sensitivity95':None,'cells':{}}
    else:
        draw_first = _dictionary(sensitivities.get('H1_G2_draw_first_aggregation'), 'N10 G2 draw-first sensitivity')
    _need(all(key in draw_first for key in ('primary_point_difference','ci95','identification_sensitivity95','cells')),
          'calculated N10 draw-first sensitivity fields required')
    draw_cells = _dictionary(draw_first['cells'], 'N10 draw-first cells')
    n10_projection = {key:deepcopy(draw_first[key]) for key in (
        'status','role','primary_point_difference','ci95','identification_sensitivity95',
        'CI_scope','not_a_N10_sampling_uncertainty_substitute') if key in draw_first}
    n10_projection['cells'] = {cell:{key:deepcopy(value[key]) for key in (
        'estimate','lower','upper','independent_source_count','planned_draw_count','undefined_denominators') if key in value}
        for cell,value in draw_cells.items()}
    wilcoxon = {}
    for endpoint in ('H1','H2'):
        row = _dictionary(sensitivities.get(endpoint+'_Wilcoxon'), endpoint+' Wilcoxon')
        _need('raw_p' in row and 'source_count' in row, 'calculated Wilcoxon fields required')
        wilcoxon[endpoint] = deepcopy(row)

    strata = report.get('strata')
    _need(type(strata) is list, 'category source statistics required')
    vv = {}
    for row in strata:
        if row.get('dimension') == 'category' and row.get('level') == 'VV' and row.get('endpoint') == 'H1' and row.get('cell') in ('V1_ROW','V2_ROW'):
            cell = row['cell']
            _need(cell not in vv, 'duplicate H1 VV cell statistic')
            values = _source_map(row, cell=cell, endpoint='H1', planned_n=planned_n, expected_ids=source_ids)
            selected = [values[sid] for sid in source_ids if values[sid] is not None]
            vv[cell] = {'estimate_over_estimable_sources': fsum(selected)/len(selected) if selected else None,
                        'estimable_source_count': len(selected), 'planned_source_count': planned_n,
                        'not_estimable_source_count': planned_n-len(selected),
                        'aggregation': 'unweighted mean over estimable canonical VV source estimates only',
                        'secondary_descriptive_only': True, 'replaces_primary_estimator': False,
                        'new_confidence_interval_computed': False, 'new_hypothesis_test': False}
    _need(set(vv) == {'V1_ROW','V2_ROW'}, 'H1 VV V1_ROW/V2_ROW source statistics are required')
    counts = {endpoint:_paired_counts(source_values[endpoint, CONTROL], source_values[endpoint, TREATMENT],
        source_ids,endpoint=endpoint,planned_n=planned_n) for endpoint in ('H1','H2')}
    counts['H2_N14_eligible'] = _paired_counts(source_values['H2', CONTROL],source_values['H2', TREATMENT],
        source_ids,endpoint='H2',planned_n=planned_n,eligible=included)
    return {'protocol': PROTOCOL, 'synthetic': report['synthetic'], 'planned_source_count': planned_n,
        'analysis_methods_changed': False, 'hypothesis_tests_recomputed': False,
        'N10_G2_draw_first_aggregation_sensitivity': n10_projection,
        'H2_analyses': {'G2': {'effect': effects['H2'], 'source_count': planned_n,
                                  'criterion_met': original['g2_criterion_met'], 'criterion_source': 'primary.H2.g2_criterion_met'},
                        'N14': {'effect': extra_effect, 'source_count': len(included),
                                'criterion_met': additional['criterion_met'],
                                'criterion_source': 'N14_H2_missingness.primary.criterion_met'},
                        'combined_criterion_met': original['criterion_met'],
                        'N14_source_selection_is_random': False},
        'identification_bounds': {endpoint:{'point_bounds': deepcopy(effects[endpoint]['delta_identification_bounds']),
            'bootstrap_sensitivity95': deepcopy(effects[endpoint]['identification_sensitivity95']),
            'marginal_ci95': deepcopy(effects[endpoint]['ci95'])} for endpoint in ('H1','H2','H4')},
        'Wilcoxon': wilcoxon, 'sourcewise_V2_vs_AS': counts,
        'H1_VV_over_estimable_sources': vv,
        'limits': ['All original estimands, hypothesis tests, confidence intervals and decisions remain unchanged.',
                   'Sourcewise wins/ties/losses are descriptive; no sign test or additional Holm slot is introduced.',
                   'VV complete-source means have their own explicit estimable N and do not replace frozen full-roster estimates.',
                   'Identification bounds, bootstrap sensitivity bounds and marginal confidence intervals are distinct.']}


def emit(summary, output):
    """Write JSON/CSV/Markdown to a new explicit directory, never overwrite."""
    _need(type(summary) is dict and summary.get('protocol') == PROTOCOL, 'known summary required')
    directory = Path(output).absolute()
    for parent in directory.parents:
        if parent.exists():
            _need(not parent.is_symlink() and not getattr(parent,'is_junction',lambda:False)(),
                  'linked output ancestor rejected')
    # Serialize before creating anything, so invalid values leave no output.
    raw = json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    directory.mkdir(exist_ok=False)
    json_path = directory/'requested_outputs.json'
    with json_path.open('x',encoding='utf-8') as stream:stream.write(raw)
    csv_path = directory/'requested_outputs.csv'
    def flatten(value, pointer=''):
        if isinstance(value,dict):
            for key,item in value.items():yield from flatten(item,pointer+'/'+str(key))
        elif isinstance(value,list):
            for index,item in enumerate(value):yield from flatten(item,pointer+'/'+str(index))
        else:yield pointer,json.dumps(value,ensure_ascii=False,allow_nan=False)
    with csv_path.open('x',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['JSON_pointer','canonical_JSON_value']);writer.writerows(flatten(summary))
    def show(value):return 'nicht schätzbar' if value is None else repr(value)
    lines=['# D1: ausdrücklich angeforderte Endausgaben','',
        'Reine Ausgabeprojektion vorhandener Zahlen. Keine neu berechneten Tests oder Konfidenzintervalle.','',
        '## N10: G2-Aggregation erst Durchläufe, dann Quellen','',
        '| Zelle | G2-Schätzer | Geplante Quellen |','| --- | ---: | ---: |']
    for cell,row in summary['N10_G2_draw_first_aggregation_sensitivity']['cells'].items():
        lines.append(f"| {cell} | {show(row.get('estimate'))} | {show(row.get('independent_source_count'))} |")
    n10=summary['N10_G2_draw_first_aggregation_sensitivity']
    if 'status' in n10:lines += ['', 'Status: '+n10['status']+'.']
    lines += ['',f"Primärkontrast dieser Sensitivität: {show(n10['primary_point_difference'])}; 95-%-KI {show(n10['ci95'])}.",
        '', '## H2: G2 und N14 getrennt','',
        '| Analyse | Quellen | Differenz | 95-%-KI | p roh | p Holm | Kriterium dieser Analyse |',
        '| --- | ---: | ---: | --- | ---: | ---: | --- |']
    for name in ('G2','N14'):
        row=summary['H2_analyses'][name];e=row['effect']
        lines.append(f"| {name} | {row['source_count']} | {show(e['point_difference'])} | {show(e['ci95'])} | {show(e['raw_p'])} | {show(e['adjusted_p'])} | {row['criterion_met']} |")
    lines += ['',f"Kombiniertes H2-Kriterium: {summary['H2_analyses']['combined_criterion_met']}.",
        '', '## Identifikationsschranken und Intervalle','',
        '| Endpunkt | Punkt-Schranken | Bootstrap-Sensitivität 95 % | Marginales 95-%-KI |',
        '| --- | --- | --- | --- |']
    for endpoint,row in summary['identification_bounds'].items():
        lines.append(f"| {endpoint} | {show(row['point_bounds'])} | {show(row['bootstrap_sensitivity95'])} | {show(row['marginal_ci95'])} |")
    lines += ['', '## Wilcoxon-Sensitivität','', '| Endpunkt | Quellen | W+ | p roh |', '| --- | ---: | ---: | ---: |']
    for endpoint,row in summary['Wilcoxon'].items():
        lines.append(f"| {endpoint} | {show(row.get('source_count'))} | {show(row.get('statistic_W_plus'))} | {show(row.get('raw_p'))} |")
    lines += ['', '## Quellenweise V2 gegenüber AS, beschreibend','',
        '| Analyse | Geplant | Vergleichsumfang | Paarweise schätzbar | V2 größer | Gleich | V2 kleiner | Nicht schätzbar |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,row in summary['sourcewise_V2_vs_AS'].items():
        fields=('planned_source_count','comparison_scope_source_count','pairwise_estimable_source_count',
                'V2_better_sources','equal_sources','V2_worse_sources','not_estimable_sources')
        lines.append('| '+name+' | '+' | '.join(str(row[key]) for key in fields)+' |')
    lines += ['', '## H1 bei VV über schätzbare Quellen, beschreibend','',
        '| Zelle | Mittelwert über schätzbare Quellen | Schätzbare Quellen n | Geplante Quellen N |',
        '| --- | ---: | ---: | ---: |']
    for cell,row in summary['H1_VV_over_estimable_sources'].items():
        lines.append(f"| {cell} | {show(row['estimate_over_estimable_sources'])} | {row['estimable_source_count']} | {row['planned_source_count']} |")
    lines += ['', 'Die VV-Mittelwerte ersetzen nicht die Primäranalyse und erhalten keine neu erfundenen Intervalle.',
              'Strikte Vergleiche auf ungerundeten Quellenwerten, ohne Toleranz. Quellenzahlen sind keine zusätzlichen Hypothesentests.',
              'Synthetische Eingaben ergeben ausschließlich synthetische Ergebnisse.' if summary['synthetic'] else
              'N14s ausgewählte Quellen sind keine belegte Zufallsstichprobe aller geplanten Quellen.', '']
    md_path=directory/'requested_outputs.md'
    with md_path.open('x',encoding='utf-8') as stream:stream.write('\n'.join(lines))
    return [str(json_path),str(csv_path),str(md_path)]
