"""AB2: publication-sized figures from saved D1a estimates only.

This renderer does not aggregate observations, bootstrap, correct p-values, or
select an inferential decision. The existing D1a adapter supplies all effects.
Input JSON and historical figures are read-only. Matplotlib is imported lazily.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path

from .vorlauf_ohne_H4.raw_render import bounds, effect_rows, finite, need, number


CELL_BINDINGS = (('AS', 'AS_ORIGINAL'), ('AS+G', 'AS_G_ORIGINAL'),
                 ('V1', 'V1_ORIGINAL'), ('V2', 'V2_ROW'))
NI_IDENTIFIERS = frozenset(('H2', 'K2', 'K4', 'K6'))
FAMILY_LEVELS = (('wikipedia', 'Wikipedia'), ('factbook', 'Factbook'),
                 ('sealed4', 'Versiegelte Quellen'))
ENDPOINT_LABELS = {'H1': 'Quellenstützung', 'H2': 'Bedeutungserhalt', 'F1': 'Antwort-F1'}
MAIN_NAME = 'hauptabbildung.pdf'
DETAIL_NAME = 'aufteilungen.pdf'
FIGURE_WIDTH_INCHES = 6.0
INK, LIGHT_INK = '#202020', '#555555'


def _origin(report, allow_real):
    need(report.get('synthetic') is True or allow_real is True,
         'AB2_REAL_INPUT_REQUIRES_EXPLICIT_ENABLE')
    return ('SYNTHETISCH - KEINE EMPIRISCHEN ERGEBNISSE' if report['synthetic']
            else 'VORLÄUFIGE ERGEBNISSE - H4 AUSSTEHEND')


def forest_rows(report):
    """Normalize the supplied scalars, without recomputing a measurement."""
    rows = effect_rows(report)
    for row in rows:
        expected = -.05 if row['identifier'] in NI_IDENTIFIERS else 0.
        need(finite(row['null_boundary']) and row['null_boundary'] == expected,
             'AB2_FROZEN_TEST_BOUNDARY_MISMATCH')
        need(row['status'] == 'pending' or type(row['source_count']) is int
             and row['source_count'] > 0, 'AB2_EXPLICIT_SOURCE_COUNT_REQUIRED')
    return rows


def detail_rows(report):
    """Select exactly one declared export per method; never pool export views."""
    strata = report.get('strata')
    need(type(strata) is list, 'AB2_SAVED_STRATA_REQUIRED')
    result = []
    for endpoint, dimension, levels in (
            ('H1', 'category', [(x, x) for x in ('EE', 'EV', 'VV')]),
            ('H2', 'family', FAMILY_LEVELS)):
        for level, label in levels:
            for method, cell in CELL_BINDINGS:
                matches = [r for r in strata if r.get('endpoint') == endpoint
                           and r.get('dimension') == dimension
                           and r.get('level') == level and r.get('cell') == cell]
                need(len(matches) == 1, 'AB2_UNIQUE_SAVED_STRATUM_REQUIRED')
                raw = matches[0]
                point, lower, upper = (raw.get(k) for k in ('estimate', 'lower', 'upper'))
                for value in (point, lower, upper, raw.get('missing_rate')):
                    need(value is None or finite(value) and 0 <= value <= 1,
                         'AB2_FINITE_FRACTION_OR_NULL_REQUIRED')
                need((lower is None and upper is None) or finite(lower)
                     and finite(upper) and lower <= upper, 'AB2_VALID_IDENTIFICATION_BOUNDS_REQUIRED')
                interval = bounds(raw.get('ci95'))
                if endpoint == 'H2':
                    need(interval is None, 'AB2_NO_FAMILY_CI_IN_CURRENT_CONTRACT')
                need(type(raw.get('source_count')) is int and raw['source_count'] >= 0,
                     'AB2_PLANNED_SOURCE_COUNT_REQUIRED')
                result.append({'endpoint': endpoint, 'dimension': dimension,
                    'level': level, 'label': label, 'method': method, 'cell': cell,
                    'estimate': point, 'lower': lower, 'upper': upper,
                    'ci95': list(interval) if interval is not None else None,
                    'missing_rate': raw.get('missing_rate'),
                    'source_count': raw['source_count'], 'CI_scope': raw.get('CI_scope')})
    return result


def _arm(cell):
    return str(cell).removesuffix('_ORIGINAL').removesuffix('_ROW').replace('AS_G', 'AS+G')


def _effect_text(row):
    if row['status'] == 'pending':
        return 'ausstehend'
    point, lo, hi = (row[k] for k in ('point_difference', 'ci95_lower', 'ci95_upper'))
    if point is None:
        return 'nicht schätzbar'
    value = number(point * 100, 2)
    return value + (' [' + number(lo * 100, 2) + '; ' + number(hi * 100, 2) + ']'
                    if lo is not None else ' [KI fehlt]')


def _detail_text(row):
    point = number(row['estimate'] * 100, 1) if row['estimate'] is not None else 'n. b.'
    if row['endpoint'] == 'H2':
        missing = number(row['missing_rate'] * 100, 1) if row['missing_rate'] is not None else 'n. b.'
        return point + ('*' if row['missing_rate'] == 1 else '') + '\nm = ' + missing + ' %'
    if row['ci95'] is not None:
        lo, hi = row['ci95']
        return point + '\nKI [' + number(lo * 100, 1) + '; ' + number(hi * 100, 1) + ']'
    if row['lower'] is not None:
        return point + '\nS [' + number(row['lower'] * 100, 1) + '; ' + number(row['upper'] * 100, 1) + ']'
    return point + '\nKI fehlt'


def _pyplot():
    import matplotlib
    matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt
    return plt


def make_forest(report, *, allow_real=False):
    """One main figure, two explicitly separate families, shared difference scale."""
    banner = _origin(report, allow_real)
    rows = forest_rows(report)
    plt = _pyplot()
    fig, axes = plt.subplots(2, 1, figsize=(FIGURE_WIDTH_INCHES, 7.0), sharex=True,
                            gridspec_kw={'height_ratios': [4.2, 9.4]})
    values = [-5., 0.]
    for row in rows:
        values.extend(row[k] * 100 for k in ('point_difference', 'ci95_lower', 'ci95_upper')
                      if row[k] is not None)
    padding = max(2., (max(values) - min(values)) * .09)
    limits = (min(values) - padding, max(values) + padding)
    titles = ('Primärfamilie: H1, H2, H4', 'Sekundäre Komponentenfamilie: K1-K6')
    for axis, family, title in zip(axes, ('primary', 'components'), titles, strict=True):
        selected = [r for r in rows if r['family'] == family]
        axis.axvline(0, color=INK, lw=.9, zorder=0, label='Null')
        axis.axvline(-5, color=LIGHT_INK, lw=1.1, ls=(0, (4, 3)), zorder=0,
                     label='NI-Grenze -5 Pp.')
        for y, row in enumerate(selected):
            n14 = row['analysis'] == 'N14'
            identifier = row['identifier']
            metric = ENDPOINT_LABELS.get(row['endpoint'], row['endpoint'])
            first = identifier + ' ' + metric
            comparison = (_arm(row['treatment']) + ' - ' + _arm(row['control']))
            if row['status'] != 'pending':
                comparison += ' / ' + row['analysis']
                if identifier in NI_IDENTIFIERS:
                    comparison += ' / NI'
            axis.text(-.06, y, first + '\n' + comparison,
                      transform=axis.get_yaxis_transform(), ha='right', va='center',
                      fontsize=9.2, color=INK, linespacing=1.18)
            value = _effect_text(row)
            if row['status'] != 'pending':
                value += '\nn = ' + str(row['source_count'])
                if row['ci95_lower'] is not None:
                    lo, hi = row['ci95_lower'] * 100, row['ci95_upper'] * 100
                    axis.hlines(y, lo, hi, color=INK, lw=1.2,
                                linestyles='dashed' if n14 else 'solid', zorder=2)
                    axis.plot([lo, hi], [y, y], '|', color=INK, ms=5, mew=.9)
                if row['point_difference'] is not None:
                    axis.plot([row['point_difference'] * 100], [y],
                              marker='D' if n14 else 'o', ms=4.8, linestyle='none',
                              mfc='white' if n14 else INK, mec=INK, mew=1., zorder=4)
            axis.text(1.065, y, value, transform=axis.get_yaxis_transform(),
                      ha='left', va='center', fontsize=9.2, color=INK, linespacing=1.18)
        axis.set_xlim(*limits)
        axis.set_ylim(len(selected) - .55, -.65)
        axis.set_yticks([])
        axis.set_xticks([-5, 0, 10, 20])
        axis.set_xticklabels(['-5', '0', '10', '20'])
        axis.tick_params(axis='x', labelsize=9, length=3, labelbottom=True)
        axis.set_title(title, fontsize=10, fontweight='bold', loc='left', pad=15)
        axis.spines[['left', 'top', 'right']].set_visible(False)
        axis.spines['bottom'].set_color('#888888')
    axes[-1].set_xlabel('Differenz in Prozentpunkten (Pp.)', fontsize=9.5, labelpad=7)
    fig.subplots_adjust(left=.345, right=.715, top=.872, bottom=.205, hspace=.28)
    fig.text(.025, .979, banner, fontsize=9, fontweight='bold', color=INK, va='top')
    fig.text(.025, .953, 'Pipeline- und Komponenteneffekte', fontsize=12,
             fontweight='bold', color=INK, va='top')
    fig.text(.755, .912, 'Differenz [95%-KI]\nQuellen n', fontsize=9,
             color=INK, va='top', linespacing=1.15)
    fig.text(.025, .120,
             'Kreis/durchgezogen: G2/N10. Offene Raute/gestrichelt: N14.\n'
             'Senkrecht: Null (durchgezogen), NI-Grenze -5 Pp. (gestrichelt).\n'
             'NI: H2/K2/K4/K6. Marginale 95%-KI, keine simultanen Intervalle.\n'
             'Holm-Entscheidungen stehen aus. H4: Platzhalter ohne Messwert.',
             fontsize=9, color=INK, va='top', linespacing=1.25)
    return fig


def make_details(report, *, allow_real=False):
    """A compact table; stored confidence and identification limits stay distinct."""
    banner = _origin(report, allow_real)
    rows = detail_rows(report)
    plt = _pyplot()
    fig = plt.figure(figsize=(FIGURE_WIDTH_INCHES, 5.9))
    fig.text(.025, .975, banner, va='top', fontsize=9, fontweight='bold', color=INK)
    fig.text(.025, .927, 'Quellenstützung nach Typ, Bedeutungserhalt nach Quellfamilie',
             va='top', fontsize=10.5, fontweight='bold', color=INK)
    for endpoint, rect, title in (
            ('H1', [.025, .550, .95, .290], 'a) H1 nach Aussagetyp - Quellenstützung [%]'),
            ('H2', [.025, .230, .95, .250], 'b) H2 nach Quellfamilie - Bedeutungserhalt [%]')):
        axis = fig.add_axes(rect)
        axis.set_axis_off()
        subset = [r for r in rows if r['endpoint'] == endpoint]
        levels = list(dict.fromkeys(r['level'] for r in subset))
        data = []
        for level in levels:
            group = [r for r in subset if r['level'] == level]
            n = {r['source_count'] for r in group}
            need(len(n) == 1, 'AB2_SAME_PLANNED_SOURCE_COUNT_WITHIN_LEVEL_REQUIRED')
            label = group[0]['label'] + '\n(' + str(next(iter(n))) + ' Quellen)'
            data.append([label] + [_detail_text(next(r for r in group if r['method'] == method))
                                   for method, _ in CELL_BINDINGS])
        table = axis.table(cellText=data, colLabels=[''] + [m for m, _ in CELL_BINDINGS],
                           colWidths=[.25] + [.1875] * 4, loc='center',
                           bbox=[0, 0, 1, 1], cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        for (y, x), cell in table.get_celld().items():
            cell.set_linewidth(.5)
            cell.set_edgecolor('#aaaaaa')
            cell.set_facecolor('#eeeeee' if y == 0 else 'white')
            if y == 0:
                cell.get_text().set_fontweight('bold')
            if x == 0:
                cell.get_text().set_ha('left')
            cell.PAD = .07
        axis.set_title(title, loc='left', fontsize=9.8, fontweight='bold', pad=7)
    fig.text(.025, .173,
             'KI: marginales 95%-Intervall. S: Identifikationsschranken, kein KI.\n'
             'n. b.: nicht schätzbar. Familienwerte besitzen keine gespeicherten KI.\n'
             'm: Anteil fehlender oder unklarer Urteile. * G2-Nullwertung bei 100 % Fehlwerten.',
             fontsize=9, va='top', color=INK, linespacing=1.3)
    fig.text(.025, .075,
             'Quellen gleich gewichtet. AS, AS+G, V1: Originalexport; V2: Zeilenexport.\n'
             'Aufteilungen sind beschreibend und bilden keine zusätzliche Testfamilie.',
             fontsize=9, va='top', color=INK, linespacing=1.25)
    return fig


def _write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v
                             for k, v in row.items()})


def _save_pdf(fig, path):
    fig.savefig(path, metadata={'Title': path.stem, 'Creator': 'D1 AB2 renderer',
                               'CreationDate': None, 'ModDate': None})


def render(report, output_dir, *, allow_real=False):
    """Render a new directory only; never overwrite existing scientific outputs."""
    _origin(report, allow_real)
    effects, details = forest_rows(report), detail_rows(report)
    output = Path(output_dir)
    need(not output.exists(), 'AB2_OUTPUT_DIRECTORY_MUST_BE_NEW')
    output.mkdir(parents=True)
    plt = _pyplot()
    for name, builder in ((MAIN_NAME, make_forest), (DETAIL_NAME, make_details)):
        fig = builder(report, allow_real=allow_real)
        try:
            _save_pdf(fig, output / name)
        finally:
            plt.close(fig)
    _write_csv(output / 'hauptabbildung_daten.csv', effects)
    _write_csv(output / 'aufteilungen_daten.csv', details)
    (output / 'LESEHILFE.md').write_text(
        '# AB2: Ergebnisabbildungen\n\n'
        '**Einzige Hauptabbildung:** `hauptabbildung.pdf`. '
        '`aufteilungen.pdf` ist die ergänzende kompakte Tabelle. '
        'Die früheren beiden Effekt-PDFs bleiben historische Fassungen.\n\n'
        '## Caption der Hauptabbildung\n\n'
        'Vorläufige Pipeline- und Komponenteneffekte. Primär wird V2 (Zeilenexport) mit AS '
        '(Originalexport) verglichen. Die weiteren Kontraste stehen an den Zeilen. '
        'Punkte zeigen Differenzen in Prozentpunkten, Linien marginale zweiseitige '
        '95%-Bootstrap-Perzentilintervalle. G2 umfasst alle festgelegten Quellen. N14 ergänzt '
        'je Kontrast Quellen mit gültigen Urteilen in beiden Armen. Fehlende Positionen '
        'innerhalb einbezogener Quellen behalten die G2-Wertung. N14 ist keine weitere '
        'Hypothese oder belegte Zufallsstichprobe. H1 beruht auf dem kostenbegrenzten '
        'N10-Teilbestand. Die Testfamilien bleiben getrennt, H4 und die abschließenden '
        'Holm-Entscheidungen stehen aus.\n\n'
        '## Methodische Lesart\n\n'
        'H1 bezeichnet Quellenstützung, H2 den Erhalt ausgewählter Referenzbedeutungen und H4 Antwort-F1. '
        'Primär wird V2 (Zeilenexport) mit AS (Originalexport) verglichen. '
        'Die Komponentenvergleiche stehen unmittelbar an den Zeilen. '
        'Die Punkte zeigen Differenzen in Prozentpunkten, die Linien marginale zweiseitige '
        '95%-Bootstrap-Perzentilintervalle. Diese sind keine simultanen Holm-Intervalle. '
        'G2 verwendet den vollständigen festgelegten Quellenbestand. N14 ergänzt je Kontrast die '
        'Quellen mit mindestens einem gültigen Urteil in beiden Armen. Fehlende Positionen innerhalb '
        'einbezogener Quellen behalten ihre ursprüngliche G2-Wertung. N14 ist weder eine zusätzliche '
        'konfirmatorische Hypothese noch eine belegte Zufallsstichprobe aller Quellen. '
        'Die Primärfamilie umfasst drei und die getrennte Komponentenfamilie sechs Hypothesen. '
        'H2, K2, K4 und K6 verwenden die Nichtunterlegenheitsgrenze -5 Prozentpunkte, '
        'die übrigen Tests die Nullgrenze. H1/K1/K3/K6 beruhen auf der kostenbegrenzten '
        'N10-Stichprobe mit nur näherungsweise gleichen Inklusionswahrscheinlichkeiten. '
        'Die Stichproben werden innerhalb jeder Quelle gepoolt und Quellen gleich gewichtet. '
        'H2 verwendet geplante Durchläufe innerhalb gleich gewichteter Quellen. '
        'H4 fehlt. Holm-Korrektur und abschließende Testentscheidungen stehen aus.\n\n'
        '## Caption der Aufteilungen\n\n'
        'Beschreibende H1-Typwerte und H2-Quellfamilienwerte für vier ausdrücklich ausgewählte '
        'Exportansichten, ohne Mittelung über Original- und Zeilenexporte. '
        'KI bezeichnet nur tatsächlich gespeicherte marginale 95%-Intervalle. '
        'S bezeichnet Identifikationsschranken. Fehlende Punktschätzer und Intervalle werden '
        'nicht erfunden. H2-Familien haben keine gespeicherten Konfidenzintervalle. '
        'Der Fehlwertanteil m umfasst fehlende und semantisch unklare Urteile. '
        'Eine markierte Null bei 100 % Fehlwerten ist die vorgegebene G2-Nullwertung, '
        'kein beobachteter vollständiger Bedeutungsverlust. Quellenzahlen sind geplante '
        'Quellenzahlen und keine Typ- oder Referenzpositionsnenner.\n\n'
        'Die numerischen CSVs enthalten ausschließlich ausgewählte gespeicherte Skalare. '
        'Es wurden keine Daten aggregiert, Intervalle neu berechnet, p-Werte korrigiert '
        'oder Entscheidungen aus Intervalllagen abgeleitet.\n', encoding='utf-8', newline='\n')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-real', action='store_true')
    args = parser.parse_args(argv)
    raw = args.analysis.read_bytes()
    report = json.loads(raw)
    output = render(report, args.output, allow_real=args.allow_real)
    need(args.analysis.read_bytes() == raw, 'AB2_INPUT_CHANGED_DURING_RENDER')
    receipt = {'protocol': 'D1-AB2-presentation-only-v1', 'analysis_bytes': len(raw),
               'analysis_sha256': sha256(raw).hexdigest(),
               'synthetic': report['synthetic'], 'main_figure': MAIN_NAME,
               'detail_figure': DETAIL_NAME, 'main_figure_count': 1,
               'forest_rows': len(forest_rows(report)), 'detail_cells': len(detail_rows(report)),
               'measurement_or_inference_recomputed': False,
               'holm_computed': report['holm_computed'],
               'artifacts': [{'file': p.name, 'bytes': p.stat().st_size,
                              'sha256': sha256(p.read_bytes()).hexdigest()}
                             for p in sorted(output.iterdir()) if p.is_file()]}
    (output / 'result.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n',
                                      encoding='utf-8', newline='\n')
    print(json.dumps(receipt, ensure_ascii=True))


if __name__ == '__main__':
    main()
