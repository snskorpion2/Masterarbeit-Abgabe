"""N8 tables and a two-family vector forest plot over supplied CPU results.

No natural input discovery, answer access, inference or effect calculation.
All intervals are marginal. Holm decisions belong to their own fixed family.
"""
from pathlib import Path

from .render import (BLUE, GRAY, ORANGE, SYNTHETIC_BANNER, _count, _finite, _n10_note,
                     _interval, _money, _need, _number, _save,
                     _write_longtable)
from .n14_render import (enabled as n14_enabled, end_status as n14_end_status,
                         final_confirmation as n14_final_confirmation,
                         note as n14_note)


PRIMARY = ('H1', 'H2', 'H4')
COMPONENTS = ('K1', 'K2', 'K3', 'K4', 'K5', 'K6')
PRIMARY_LABELS = {'H1': 'H1 Quellenstützung', 'H2': 'H2 Bedeutungserhalt',
                  'H4': 'H4 Antwort-F1'}
COMPONENT_LABELS = {
    'K1': 'K1 AS+G - AS / H1', 'K2': 'K2 AS+G - AS / H2',
    'K3': 'K3 V2 - V1 / H1', 'K4': 'K4 V2 - V1 / H2',
    'K5': 'K5 V1 - AS / H2', 'K6': 'K6 V1 - AS / H1'}
COMPONENT_BOUNDARIES = {name: -.05 if name in ('K2', 'K4', 'K6') else 0.
                        for name in COMPONENTS}


def _banner(report, banner):
    _need(type(report) is dict and type(report.get('synthetic')) is bool,
          'D1_N8_RENDER_SYNTHETIC_FLAG_REQUIRED')
    _need(type(banner) is str and bool(banner.strip()), 'D1_N8_RENDER_BANNER_REQUIRED')
    return SYNTHETIC_BANNER if report['synthetic'] else banner


def _families(report):
    """Normalize known identifiers without replacing missing values with zero."""
    primary = report.get('primary', {})
    components = report.get('components', {}).get('contrasts', {})
    _need(type(primary) is dict and set(primary) == set(PRIMARY),
          'D1_N8_RENDER_EXACT_PRIMARY_FAMILY_REQUIRED')
    _need(type(components) is dict and set(components) == set(COMPONENTS),
          'D1_N8_RENDER_EXACT_COMPONENT_FAMILY_REQUIRED')
    output = []
    for identifiers, values, labels, family in (
        (PRIMARY, primary, PRIMARY_LABELS, 'primary'),
        (COMPONENTS, components, COMPONENT_LABELS, 'components')):
        entries = []
        for identifier in identifiers:
            row = values[identifier]
            _need(type(row) is dict, 'D1_N8_RENDER_EFFECT_RECORD_REQUIRED')
            point = row.get('point_difference')
            interval = _interval(row.get('ci95'))
            boundary = (-.05 if identifier == 'H2' else 0.) if family == 'primary' else COMPONENT_BOUNDARIES[identifier]
            _need(point is None or _finite(point) and -1 <= point <= 1,
                  'D1_N8_RENDER_FINITE_FRACTIONAL_EFFECT_REQUIRED')
            _need(interval is None or all(-1 <= value <= 1 for value in interval),
                  'D1_N8_RENDER_FRACTIONAL_INTERVAL_REQUIRED')
            _need('null_boundary' not in row or row['null_boundary'] == boundary,
                  'D1_N8_RENDER_FROZEN_NULL_BOUNDARY_REQUIRED')
            adjusted = row.get('adjusted_p')
            _need(adjusted is None or _finite(adjusted) and 0 <= adjusted <= 1,
                  'D1_N8_RENDER_ADJUSTED_P_REQUIRED')
            testable = row.get('testable') is True
            reject = row.get('reject') is True
            _need(not reject or testable and adjusted is not None and adjusted <= .05,
                  'D1_N8_RENDER_INCONSISTENT_HOLM_DECISION')
            _need(not testable or adjusted is None or reject == (adjusted <= .05),
                  'D1_N8_RENDER_INCONSISTENT_HOLM_DECISION')
            entries.append({'identifier': identifier, 'label': labels[identifier],
                'family': family, 'point': point, 'ci95': interval,
                'boundary': boundary, 'adjusted_p': adjusted,
                'testable': testable, 'reject': reject, 'raw': row})
        output.append(entries)
    return output


def _make_forest_figure(report, banner):
    """Return an inspectable figure; values are displayed in percentage points."""
    import matplotlib
    matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt

    families = _families(report)
    values = [0., -5.]
    for rows in families:
        for row in rows:
            if row['point'] is not None:
                values.append(row['point'] * 100)
            if row['ci95'] is not None:
                values.extend(value * 100 for value in row['ci95'])
    lower, upper = min(values), max(values)
    padding = max(1.8, (upper - lower) * .14)
    fig, axes = plt.subplots(2, 1, figsize=(6.10, 7.40), sharex=True,
                            gridspec_kw={'height_ratios': [3.25, 6]})
    titles = ('Primärfamilie (m = 3)', 'Sekundäre Komponentenfamilie (m = 6)')
    for ax, rows, title in zip(axes, families, titles, strict=True):
        ax.axvline(0, color=GRAY, linewidth=.8, zorder=0)
        for y, row in enumerate(rows):
            color = BLUE if row['family'] == 'primary' else '#5b467d'
            ax.vlines(row['boundary'] * 100, y - .18, y + .18,
                      color=ORANGE, linestyles='--', linewidth=1.4, zorder=3)
            if row['ci95'] is not None:
                interval = [value * 100 for value in row['ci95']]
                ax.hlines(y, *interval, color=color, linewidth=1.5)
                ax.plot(interval, [y, y], '|', color=color, markersize=6)
            if row['point'] is not None:
                if row['testable']:
                    confirmed = n14_final_confirmation(report, row['identifier'], row['raw'])
                    ax.plot(row['point'] * 100, y, 'o', markersize=5,
                            markeredgecolor=color,
                            markerfacecolor=color if confirmed else 'white',
                            zorder=4)
                else:
                    ax.plot(row['point'] * 100, y, 'x', markersize=5,
                            markeredgewidth=1.3, color=color, zorder=4)
            else:
                ax.text(.98, y, 'n. b.', transform=ax.get_yaxis_transform(),
                        ha='right', va='center', fontsize=8, color=GRAY)
            ax.text(1.035, y, _number(row['adjusted_p'], 5) if row['testable'] else 'n. b.',
                    transform=ax.get_yaxis_transform(), ha='left', va='center',
                    fontsize=8.0, color='#333333')
        ax.text(1.035, 1.02, 'p Holm', transform=ax.transAxes,
                ha='left', va='bottom', fontsize=8)
        ax.set_xlim(lower - padding, upper + padding)
        ax.set_ylim(len(rows) - .58, -.58)
        ax.set_yticks(range(len(rows)), [row['label'] for row in rows], fontsize=8.5)
        ax.tick_params(axis='y', length=0, pad=7)
        ax.tick_params(axis='x', labelsize=8, labelbottom=True)
        ax.set_title(title, fontsize=10, loc='left', pad=13)
        ax.grid(axis='x', color='#dddddd', linewidth=.6)
        ax.spines[['top', 'right', 'left']].set_visible(False)
    axes[1].set_xlabel('Differenz in Prozentpunkten', fontsize=9, labelpad=8)
    fig.subplots_adjust(left=.33, right=.82, top=.845,
                        bottom=.29 if n14_enabled(report) else .22, hspace=.60)
    fig.text(.5, .988, banner, ha='center', va='top', fontsize=8.8,
             fontweight='bold', color='#8a2633')
    fig.text(.5, .944, 'Pipeline- und Komponentenkontraste', ha='center',
             va='top', fontsize=11, fontweight='bold')
    fig.text(.5, .908, 'Primär: V2 (Zeilen) - AS (Original)', ha='center',
             va='top', fontsize=8.5)
    decision_legend = ('Gefüllte Kreise: Endkriterium bestätigt. Offen: nicht bestätigt.\n'
                       'p Holm: G2. H2/K2/K4/K5 zusätzlich nach N14 geprüft.\n'
                       'Zusatzschätzer und Endurteil stehen in der N14-Tabelle.\n'
                       if n14_enabled(report) else
                       'Gefüllte Kreise: Holm-bestätigt. Offene Kreise: nicht bestätigt.\n')
    fig.text(.5, .018,
        'Linien: marginale 95%-KI, keine simultanen Holm-Intervalle.\n'
        + decision_legend +
        'Kreuze: nicht testbar. Fehlende Werte: n. b., nicht null.\n'
        'Kurze Striche: Nullrand 0 bzw. NI-Grenze -5 Prozentpunkte.\n'
        'Getrennte Holm-Familien, gleiche gepaarte Cluster-Ziehungen.' +
        ('\nH1/K1/K3/K6: N10-Näherung, kostenbegrenzter Präfix.\n'
         'Gemeinsamer zweistufiger Quellen-/Originalgruppenbootstrap.'
         if report.get('N10_H1_sampling') else ''),
        ha='center', va='bottom', fontsize=7.8, color='#333333', linespacing=1.4)
    return fig


def _effect_text(point, interval):
    point_text = _number(point * 100 if _finite(point) else None, 2)
    limits = _interval(interval)
    return point_text + (' [' + _number(limits[0] * 100, 2) + ', ' +
                         _number(limits[1] * 100, 2) + ']' if limits else ' [n. b.]')


def _component_table(report, output, banner):
    rows = []
    for row in _families(report)[1]:
        goal = 'NI > -5 pp' if row['boundary'] else 'Überlegenheit > 0'
        status = 'nicht testbar' if not row['testable'] else ('bestätigt' if row['reject'] else 'nicht bestätigt')
        final = n14_end_status(report, row['identifier'], row['raw'])
        if final:
            status = 'G2-Test: ' + status + '; ' + final
        rows.append([row['identifier'], row['label'].split(' ', 1)[1] + ', ' + goal,
                     _effect_text(row['point'], row['ci95']),
                     _number(row['adjusted_p'], 5) + ', ' + status])
    note = ('Eigene Holm-Familie mit sechs Slots. Marginale zweiseitige 95%-Intervalle sind '
        'keine simultanen Holm-Intervalle. H1 und H2 verwenden dieselben gepaarten '
        'Quellenziehungen wie die Primäranalyse. H1-Aussagen tragen gegebenenfalls dieselbe '
        'Bewerterqualifikation wie das Gesamturteil. Die unveränderte Schemainduktion '
        'wird nicht als Verbesserung bewertet.')
    judgment = report.get('overall_judgment') or {}
    if judgment.get('evaluator_dependent'):
        note += ' Aktuelle H1-Qualifikation: ' + str(judgment.get('H1_qualification') or 'bewerterabhängig') + '.'
    note += _n10_note(report) + n14_note(report)
    return _write_longtable(output, 'component_contrasts.tex',
        'N8: sekundäre Komponentenfamilie, sechs vorab festgelegte Kontraste.',
        ['Kontrast', 'Vergleich und Prüfziel', 'Differenz [pp] und 95%-KI', 'p Holm und Urteil'], rows,
        note, banner,
        r'p{.10\linewidth}p{.28\linewidth}p{.27\linewidth}p{.24\linewidth}')


def _overall_table(report, output, banner):
    value = report.get('overall_judgment') or {}
    stage = value.get('stage', value.get('base_stage'))
    qualifications = value.get('qualifications') or []
    if isinstance(qualifications, str):
        qualifications = [qualifications]
    rows = [['Stufe', str(stage) if stage is not None else 'nicht bestimmbar'],
            ['Regelgebundene Formulierung', value.get('statement') or 'nicht bestimmbar']]
    rows.extend(['Qualifikation', str(text).replace('Cohen-κ', 'Cohen-kappa')]
                for text in qualifications)
    if value.get('undefined_reason'):
        rows.append(['Fehlende Voraussetzung', str(value['undefined_reason'])])
    if not qualifications and value.get('evaluator_dependent'):
        rows.append(['H1-Qualifikation', 'bewerterabhängig'])
    return _write_longtable(output, 'overall_judgment.tex',
        'N8: gebundenes Gesamturteil, keine zusätzliche Testfamilie.',
        ['Bestandteil', 'Aussage'], rows,
        'A bis F folgt ausschließlich den vorab festgelegten Regeln. Cohen-kappa unter '
        '0,40 oder ein entgegengesetztes Grok-Vorzeichen qualifiziert H1 als '
        'bewerterabhängig. Fehlende Gegenprüfungen sind keine Bestätigung. '
        'Synthetische Beispielwerte begründen keine empirische Überlegenheit.', banner,
        r'p{.25\linewidth}p{.67\linewidth}')


def _h4_table(report, output, banner):
    entries = report.get('components', {}).get('H4_descriptive', [])
    rows = [[row.get('export', ''), str(row.get('treatment', '')) + ' - ' + str(row.get('control', '')),
             _effect_text(row.get('point_difference'), row.get('ci95'))] for row in entries]
    return _write_longtable(output, 'H4components_descriptive.tex',
        'N8: beschreibende F1-Komponentenkontraste nach Export.',
        ['Export', 'Vergleich', 'Differenz [pp] und 95%-KI'], rows,
        'Drei Komponentenkontraste je bereits festgelegtem Exportweg. Rein beschreibende '
        'marginale 95%-Intervalle aus denselben gepaarten QA-Clusterziehungen. '
        'Kein p-Wert, keine zusätzliche Holm-Familie und keine ergebnisabhängige Exportwahl.',
        banner, r'p{.13\linewidth}p{.48\linewidth}p{.29\linewidth}')


def _efficiency_table(report, output, banner):
    entries = report.get('efficiency', {}).get('rows', [])
    rows = []
    for index, row in enumerate(entries, start=1):
        label = 'E' + str(index).zfill(2) + ': ' + ' / '.join(str(row.get(key) or 'unbekannt')
                                                              for key in ('population', 'arm', 'currency'))
        support_complete = row.get('support_complete') is True
        missing_stages = row.get('missing_stages') or []
        stages_complete = row.get('stage_coverage_complete') is True and not missing_stages
        construction_stages_complete = row.get('construction_stage_coverage_complete') is True
        construction_stages_complete &= not any(
            str(stage).startswith(('B3:', 'B4:')) for stage in missing_stages)
        usage_complete = row.get('usage_complete') is True
        construction_usage_complete = row.get('construction_usage_complete') is True
        cost_complete = row.get('cost_complete') is True
        costs = _money(row.get('cost_per_supported')
                       if support_complete and stages_complete and cost_complete else None)
        if row.get('cost_scope') == 'currency_component_only':
            costs = 'n. b. (Währungsteil)'
        tokens = _number(row.get('tokens_per_supported')
                         if support_complete and stages_complete and usage_complete else None, 2)
        reciprocal = _number(row.get('supported_per_1000_construction_tokens')
                             if support_complete and construction_stages_complete
                             and construction_usage_complete else None, 3)
        incomplete = []
        if not support_complete:
            incomplete.append('H1-Zähler unvollständig')
        if not stages_complete:
            incomplete.append('Stufen fehlen: ' + ', '.join(map(str, missing_stages))
                              if missing_stages else 'Stufenabdeckung unbelegt')
        if not usage_complete or not construction_usage_complete:
            incomplete.append('Tokens unvollständig')
        if not cost_complete:
            incomplete.append('Kosten unvollständig')
        status = 'unvollständig: ' + '. '.join(incomplete) if incomplete else 'vollständig'
        if row.get('supported_count') == 0:
            status += '. Keine gestützten Vorkommen, kein Quotient je gestützt'
        rows.append([label, costs, tokens, reciprocal, status])
    return _write_longtable(output, 'efficiency_supported.tex',
        'N8: beschreibender Aufwand je quellengestützter Aussage.',
        ['Profil: Population / Arm / Währung', 'Kosten je gestützt', 'Tokens je gestützt',
         'Gestützt je 1.000 Konstruktionstokens', 'Status'], rows,
        'Je Zeile ein getrenntes Kostenprofil in der Reihenfolge des Auswertungsartefakts. '
        'Kosten und Tokens je gestütztem Vorkommen umfassen Konstruktion und gegebenenfalls '
        'Prüffilter. Der letzte Quotient verwendet nur Konstruktionstokens. '
        'Gemeinsame Qualifikation und externe Bewertung sind ausgeschlossen. '
        'Währungen werden nicht umgerechnet. n. b. ist nicht bestimmbar, etwa bei '
        'fehlenden Angaben oder Nullnenner, und bedeutet keinen Nullaufwand. '
        'Unvollständige H1-Zähler sperren alle drei Quotienten. Fehlende Stufen '
        'sperren den jeweiligen Gesamtaufwand. Der letzte Quotient kann bei '
        'fehlendem Prüffilter nur auf vollständiger reiner Konstruktion beruhen. '
        'Unvollständiger Aufwand begründet keine Effizienzüberlegenheit. '
        'Profilbestandteile und Fehlgründe bleiben im JSON-Artefakt erhalten.', banner,
        r'p{.16\linewidth}p{.115\linewidth}p{.115\linewidth}p{.25\linewidth}p{.24\linewidth}')


def render_n8(report, output_dir, *, banner, allow_real=False):
    """Write only derived tables/PDFs. Empirical inputs require an explicit opt-in."""
    banner = _banner(report, banner)
    _need(report['synthetic'] or allow_real is True,
          'D1_N8_RENDER_REAL_INPUTS_REQUIRE_EXPLICIT_ENABLE')
    _families(report)
    output = Path(output_dir).absolute()
    output.mkdir(parents=True, exist_ok=True)
    paths = [_component_table(report, output, banner), _overall_table(report, output, banner),
             _h4_table(report, output, banner), _efficiency_table(report, output, banner)]
    import matplotlib
    matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt
    with plt.rc_context({'font.family': 'DejaVu Sans', 'font.size': 9,
                         'pdf.fonttype': 42, 'ps.fonttype': 42, 'axes.unicode_minus': False}):
        figure = _make_forest_figure(report, banner)
        paths.append(_save(plt, figure, output / 'forest_primary_components.pdf',
                           'N8: getrennte primäre und sekundäre Holm-Familien', banner))
    return paths
