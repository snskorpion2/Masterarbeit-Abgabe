"""Static LaTeX tables and vector PDF figures for the frozen D1 analysis.

No source files, model outputs, credentials or provider clients are opened.
Matplotlib is imported only when render() is explicitly called. During the
synthetic preparation every table and figure carries an unambiguous banner.
Rendering empirical inputs later requires explicit allow_real=True.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import math
from numbers import Integral, Real
from pathlib import Path
import re


SYNTHETIC_BANNER = 'SYNTHETISCH - KEINE EMPIRISCHEN ERGEBNISSE'
CELLS = ('AS_ORIGINAL', 'AS_ROW', 'AS_G_ORIGINAL', 'AS_G_ROW',
         'V1_ORIGINAL', 'V1_ROW', 'V2_ORIGINAL', 'V2_ROW')
CELL_LABELS = ('AS / Original', 'AS / Zeilen', 'AS+G / Original', 'AS+G / Zeilen',
               'V1 / Original', 'V1 / Zeilen', 'V2 / Original', 'V2 / Zeilen')
PRIMARY_NAMES = {'H1': 'H1 Quellenstützung', 'H2': 'H2 Bedeutungserhalt', 'H4': 'H4 Antwort-F1'}
ENDPOINT_NAMES = {'H1': 'Quellenstützung H1', 'H2': 'Ausgewählter Bedeutungserhalt H2',
    'H3_direct_content_fraction': 'H3 Inhaltsauffindbarkeit',
    'H3_occurrence_capacity': 'H3 Projektionskapazität', 'F1': 'MuSiQue Antwort-F1', 'EM': 'MuSiQue Exact Match'}
BLUE, ORANGE, GRAY = '#245b83', '#b45f06', '#666666'


def _need(value, code):
    if not value:
        raise ValueError(code)


def _finite(value):
    return not isinstance(value, bool) and isinstance(value, (Real, Decimal)) and math.isfinite(value)


def _number(value, decimals=3):
    return format(value, '.' + str(decimals) + 'f').replace('.', ',') if _finite(value) else 'n. b.'


def _count(value):
    return str(value) if not isinstance(value, bool) and isinstance(value, Integral) and value >= 0 else 'unbekannt'


def _money(value):
    if type(value) is str:
        try:
            value = Decimal(value)
        except InvalidOperation:
            return 'n. b.'
    return _number(value, 6) if _finite(value) and value >= 0 else 'n. b.'


def _tex(value):
    """Escape data text without permitting an input to inject LaTeX syntax."""
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
        '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}', '\n': ' '}
    return ''.join(replacements.get(char, char) for char in str(value))


def _interval(value):
    if value is None:
        return None
    if type(value) is dict:
        value = [value.get('lower'), value.get('upper')]
    _need(type(value) in (list, tuple) and len(value) == 2, 'D1_RENDER_INTERVAL_PAIR_REQUIRED')
    if value[0] is None and value[1] is None:
        return None
    _need(all(_finite(v) for v in value) and value[0] <= value[1], 'D1_RENDER_VALID_INTERVAL_REQUIRED')
    return value


def _banner(report):
    return SYNTHETIC_BANNER if report['synthetic'] else 'D1 - EMPIRISCHE AUSWERTUNG'


def _write_table(output, filename, title, headers, rows, note, banner):
    path = output / filename
    _need(all(len(row) == len(headers) for row in rows), 'D1_RENDER_TABLE_ARITY')
    alignment = 'l' + 'r' * (len(headers) - 1)
    lines = [r'\begin{table}[htbp]', r'\centering', r'\small', r'\setlength{\tabcolsep}{4pt}',
        r'\caption{' + _tex(banner + '. ' + title) + '}',
        r'\begin{tabular}{' + alignment + '}', r'\toprule',
        ' & '.join(_tex(h) for h in headers) + r' \\', r'\midrule']
    lines.extend(' & '.join(_tex(value) for value in row) + r' \\' for row in rows)
    if not rows:
        lines.append(r'\multicolumn{' + str(len(headers)) + r'}{l}{Keine Einträge vorhanden.} \\')
    lines.extend([r'\bottomrule', r'\end{tabular}', r'\par\medskip',
        r'\begin{minipage}{\linewidth}\raggedright ' + _tex(note) + r'\par\end{minipage}', r'\end{table}', ''])
    path.write_text('\n'.join(lines), encoding='utf8')
    return path


def _longtable_source(title, headers, rows, note, banner, alignment=None):
    """Paginated comparison rows with an explicit banner on every page."""
    _need(all(len(row) == len(headers) for row in rows), 'D1_RENDER_TABLE_ARITY')
    alignment = alignment or (r'p{.12\linewidth}p{.29\linewidth}p{.29\linewidth}r'
                              if len(headers) == 4 else r'p{.13\linewidth}p{.78\linewidth}')
    header = ' & '.join(_tex(h) for h in headers) + r' \\'
    lines = [r'\begingroup', r'\small', r'\setlength{\tabcolsep}{4pt}',
        r'\begin{longtable}{' + alignment + '}',
        r'\caption{' + _tex(banner + '. ' + title) + r'} \\',
        r'\toprule', header, r'\midrule', r'\endfirsthead',
        r'\caption[]{' + _tex(banner + '. ' + title + ' (Fortsetzung).') + r'} \\',
        r'\toprule', header, r'\midrule', r'\endhead', r'\midrule',
        r'\multicolumn{' + str(len(headers)) + r'}{r}{Fortsetzung auf der nächsten Seite.} \\',
        r'\endfoot', r'\bottomrule', r'\endlastfoot']
    lines.extend(' & '.join(_tex(value) for value in row) + r' \\' for row in rows)
    if not rows:
        lines.append(r'\multicolumn{' + str(len(headers)) + r'}{l}{Keine Einträge vorhanden.} \\')
    lines.extend([r'\end{longtable}', r'\noindent\raggedright ' + _tex(note) + r'\par', r'\endgroup', ''])
    return '\n'.join(lines)


def _write_longtable(output, filename, title, headers, rows, note, banner, alignment=None):
    path = output / filename
    path.write_text(_longtable_source(title, headers, rows, note, banner, alignment), encoding='utf8')
    return path


def _n10_note(report):
    value = report.get('N10_H1_sampling')
    if not value:
        return ''
    return (' N10: H1 nutzt ' + _count(value['selected_groups']) + '/' + _count(value['population_groups']) +
            ' kostenbegrenzt gezogene Originalgruppen. Inklusion ist nur näherungsweise gleich. '
            'Gepoolte Anteile je Quelle, gleiche Quellengewichte und gemeinsamer zweistufiger '
            'Quellen-/Gruppenbootstrap für H1/K1/K3/K6. Nicht gezogene Aussagen sind keine Fehlwerte.')


def _primary_table(report, output, banner):
    from .n14_render import end_status, note as n14_note
    rows = []
    for hypothesis in ('H1', 'H2', 'H4'):
        result = report.get('primary', {}).get(hypothesis, {})
        interval = _interval(result.get('ci95'))
        state = ('nicht testbar' if not result.get('testable') else
                 'verworfen' if result.get('reject') else 'nicht verworfen')
        final = end_status(report, hypothesis, result)
        if final:
            state = 'G2-H0 ' + state + '; ' + final
        rows.append([hypothesis, _number(result.get('point_difference')),
            ('[' + _number(interval[0]) + ', ' + _number(interval[1]) + ']') if interval else 'n. b.',
            _number(result.get('raw_p'), 5), _number(result.get('adjusted_p'), 5), state])
    return _write_table(output, 'primary.tex', 'Primärvergleich V2_ROW minus AS_ORIGINAL.',
        ['Endpunkt', 'Differenz', '95%-KI', 'p roh', 'p Holm', 'Teststatus'], rows,
        'Marginale zweiseitige Perzentilintervalle sind keine simultanen Holm-Intervalle. '
        'Holm umfasst genau H1, H2 und F1-H4. Nicht testbare Hypothesen behalten einen '
        'konservativen Korrekturslot 1, ihr roher p-Wert bleibt unbekannt. H2 verwendet den Nullrand -0,05.'
        + _n10_note(report) + n14_note(report), banner)


def _cell_tables(report, output, banner):
    paths = []
    for endpoint in ENDPOINT_NAMES:
        selected = {row['cell']: row for row in report.get('cells', []) if row['endpoint'] == endpoint}
        rows = []
        for cell in CELLS:
            row = selected.get(cell, {})
            rows.append([cell, _number(row.get('estimate')), _number(row.get('lower')),
                _number(row.get('upper')), _number(row.get('missing_rate')),
                _number(row.get('technical_missing_rate')), _count(row.get('denominator'))])
        name = {'H3_direct_content_fraction': 'h3_content', 'H3_occurrence_capacity': 'h3_capacity'}.get(endpoint, endpoint.lower())
        note = ('Schranken sind Identifikationsschranken, keine Konfidenzintervalle. '
                'Unbekannte Werte sind nicht null. Geplante Durchläufe werden je Quelle gemittelt, Quellen gleich gewichtet. '
                'N gesamt ist die Summe der nativen Nenner, nicht der Nenner eines gepoolten Schätzers.')
        if endpoint == 'H3_direct_content_fraction':
            note += ' A6 direct_content_fraction nutzt den Nenner nativer Objekte.'
        elif endpoint == 'H3_occurrence_capacity':
            note += (' A6 occurrence_capacity nutzt den eigenen Nenner von Projektionskanten, bei EV '
                     'Teilnehmerkanten. Kein identifiziertes ganzes aussagenbezogenes C/N.')
        elif endpoint in ('F1', 'EM'):
            note = ('Alle festen QA-Fragen bleiben im Nenner. Fehlende Antworten bleiben unbekannt '
                    'und erhalten Schranken [0,1]. Eine beobachtete leere Antwort ist davon getrennt. '
                    'N gesamt summiert native Nenner und ist kein Nenner eines gepoolten Schätzers.')
        elif endpoint == 'H1' and report.get('N10_H1_sampling'):
            note = ('H1 poolt gezogene Vorkommen über Durchläufe innerhalb jeder Quelle und gewichtet Quellen gleich. '
                    'N gesamt zählt nur gezogene Vorkommen. Keine Quelle wird bei leerer Stichprobenzelle weggelassen. '
                    'Nicht schätzbare Werte behalten [0,1] als Sensitivität.' + _n10_note(report))
        paths.append(_write_table(output, 'cells_' + name + '.tex', ENDPOINT_NAMES[endpoint] + ' in acht Zellen.',
            ['Zelle', 'Schätzer', 'Untergr.', 'Obergr.', 'Fehlwert', 'techn. fehlt', 'N gesamt'], rows, note, banner))
    return paths


def _primary_bounds_table(report, output, banner):
    rows=[]
    for endpoint in ('H1','H2','H4'):
        interval=_interval(report.get('primary',{}).get(endpoint,{}).get('identification_sensitivity95'))
        rows.append([endpoint,_number(interval[0] if interval else None),_number(interval[1] if interval else None)])
    return _write_table(output,'primary_bounds.tex','Primärkontrast: Identifikationssensitivität.',
        ['Endpunkt','Sens.-Untergr.','Sens.-Obergr.'],rows,
        'Quantilgrenzen aus den Identifikationsschranken des gepaarten Bootstrap. Diese Grenzen '
        'ersetzen kein marginales 95%-Konfidenzintervall und sind keine simultanen Holm-Intervalle. '
        'Die einzige primäre Testfamilie bleibt H1, H2 und F1-H4.',banner)


def _sensitivity_table(report, output, banner):
    values=report.get('sensitivities',{})
    rows=[]
    for endpoint in ('H1','H2'):
        row=values.get(endpoint+'_Wilcoxon',{})
        rows.append([endpoint+' Wilcoxon',_count(row.get('source_count')),
            _number(row.get('statistic_W_plus')),_count(row.get('nonzero_sources')),
            _number(row.get('raw_p'),5)])
    path=_write_table(output,'sensitivities.tex','Wilcoxon-Sensitivität auf Quellenebene.',
        ['Sensitivität','Quellen N','W+','N ungleich 0','p roh'],rows,
        'Einseitige Sensitivitätsanalysen, keine zusätzliche Holm-Familie und kein Ersatz der '
        'Primäranalyse. H2 bleibt auf seinen vorab festgelegten Nullrand verschoben. '
        'Ein nicht bestimmbarer roher p-Wert bleibt n. b.',banner)
    row=values.get('EM_McNemar',{})
    extra=_longtable_source('McNemar-Sensitivität für Exact Match.',
        ['W','L','N gepaart','p roh'],
        [[_count(row.get('W')),_count(row.get('L')),_count(row.get('paired_count')),_number(row.get('raw_p'),5)]],
        'W und L zählen diskordante Antwortpaare. Nur tatsächlich gepaarte beobachtete Antworten '
        'tragen bei. Gemeinsame Absätze verletzen die Arbeitsannahme unabhängiger Fragenpaare. '
        'Deshalb nur Sensitivität, ohne zusätzlichen Holm-Slot.',banner,r'rrrr')
    with path.open('a',encoding='utf8') as handle:
        handle.write('\n'+extra)
    return path


def _missingness_table(report, output, banner):
    text=[]
    for endpoint in ('H1','H2'):
        selected={row['cell']:row for row in report.get('cells',[]) if row['endpoint']==endpoint}
        rows=[]
        for cell in CELLS:
            row=selected.get(cell,{})
            rows.append([cell,_number(row.get('missing_rate')),_number(row.get('pooled_missing_rate')),
                _number(row.get('semantic_unclear_rate')),_number(row.get('technical_missing_rate')),
                _count(row.get('undefined_denominators'))])
        note = ('m Quelle verwendet geplante Durchlaufmittel und gleiche Quellengewichte. m gepoolt '
                'ist nur eine getrennte deskriptive Fehlwertquote, kein gepoolter Qualitätsschätzer. '
                'Semantisch unklare Urteile und technische Fehlwerte bleiben getrennt. Undefinierte '
                'native Nenner werden gezählt und niemals als Nullnenner ersetzt. Mehr als 10 % '
                'Fehlwerte begrenzen die Interpretation.')
        if endpoint == 'H1' and report.get('N10_H1_sampling'):
            note = ('N10: Fehlwertquoten beziehen sich nur auf den gezogenen Präfix. Nicht gezogene '
                    'Vorkommen sind keine technischen Fehlwerte. Quellen bleiben gleich gewichtet. '
                    'Leere Stichprobenzellen werden als nicht schätzbar gezählt.' + _n10_note(report))
        text.append(_longtable_source(endpoint+': Fehlwerte und undefinierte Nenner.',
            ['Zelle','m Quelle','m gepoolt','semant.','techn.','N undef.'],rows,
            note,banner,r'p{.26\linewidth}rrrrr'))
    path=output/'missingness.tex';path.write_text('\n'.join(text),encoding='utf8')
    return path


def _distinct_tables(report, output, banner):
    value=report.get('distinct_supported',{})
    by_cell=value.get('by_cell',{})
    rows=[];statuses=[]
    source_rows=value.get('exact_only',[])
    for cell in CELLS:
        row=by_cell.get(cell,{})
        rows.append([cell,*[_number(row.get(name)) for name in (
            'exact_supported_observed_count','exact_supported_distinct_count',
            'semantic_supported_observed_count','semantic_supported_distinct_count')]])
        selected=[entry for entry in source_rows if entry.get('cell')==cell]
        status=[]
        for field in ('complete_support_membership','exact_count_complete','semantic_review_complete'):
            known=[entry[field] for entry in selected if type(entry.get(field)) is bool]
            status.append(str(sum(known))+'/'+str(len(selected)) if selected and len(known)==len(selected) else 'unbekannt')
        statuses.append([cell,*status,_count(row.get('planned_sources'))])
    note=('Geplante Durchläufe je Quelle gemittelt, anschließend Quellen gleich gewichtet. '
          'Deshalb sind dies mittlere Anzahlen. Exakt verschiedene Formen und semantisch geprüfte '
          'Verschiedenheit bleiben getrennt. Gezählt wird nur die beobachtete ausgewählte Stützung, '
          'nicht die vollständige Faktenmenge der Quelle. Unvollständiger Prüfstatus steht gesondert.')
    path=_write_table(output,'distinct_supported.tex','Verschiedene gestützte Aussagen: deskriptive Anzahlen.',
        ['Zelle','exakt beob.','exakt versch.','sem. beob.','sem. versch.'],rows,note,banner)
    with path.open('a',encoding='utf8') as handle:
        handle.write('\n'+_longtable_source('Verschiedene Aussagen: Vollständigkeitsstatus.',
            ['Zelle','Stützung voll.','Exakt voll.','Semantik voll.','Quellen geplant'],statuses,
            'Statusangaben zählen vollständig geprüfte Quell-Durchlauf-Zellen / vorliegende '
            'Quell-Durchlauf-Zellen. Nicht vorliegende Statusfelder bleiben unbekannt. '
            'Eine vorhandene Anzahl ist bei unvollständiger Prüfung kein vollständiger Faktenzähler. '
            'Keine unkontrollierte transitive Zusammenführung und kein Quellen-Recall.',banner,
            r'p{.25\linewidth}rrrr'))
    return [path]


def _strata_table(report, output, banner):
    groups=defaultdict(list)
    for row in report.get('strata',[]):
        groups[row.get('endpoint','unbekannt')].append(row)
    text=[]
    for endpoint,entries in groups.items():
        rows=[[str(row.get('dimension',''))+': '+str(row.get('level','')),row.get('cell',''),
            _number(row.get('estimate')),_number(row.get('lower')),_number(row.get('upper')),
            _number(row.get('missing_rate')),_count(row.get('source_count'))] for row in entries]
        text.append(_longtable_source(endpoint+': vorab festgelegte Schichten.',
            ['Schicht','Zelle','Schätzer','Untergr.','Obergr.','m','Quellen'],rows,
            'Sekundäre deskriptive Schichtdarstellung. Schranken sind keine Konfidenzintervalle. '
            'Keine Auswahl günstiger Untergruppen und keine zusätzliche primäre Testfamilie.',banner,
            r'p{.20\linewidth}p{.22\linewidth}rrrrr'))
    if not text:
        text.append(_longtable_source('Schichten.',['Endpunkt','Status'],
            [['alle','keine Schichtdaten vorhanden']], 'Keine Schichtwerte erfunden.',banner))
    path=output/'strata.tex';path.write_text('\n'.join(text),encoding='utf8')
    return path


def _h1_type_intervals(report, output, banner):
    rows = []
    for row in report.get('strata', []):
        if row.get('dimension') != 'category' or row.get('endpoint') != 'H1':
            continue
        interval = _interval(row.get('ci95'))
        rows.append([row['level'], row['cell'], _count(row.get('source_count')),
            _number(row.get('estimate')),
            '[' + _number(interval[0]) + ', ' + _number(interval[1]) + ']' if interval else 'n. b.'])
    scope = ('Marginale 95%-Intervalle aus demselben zweistufigen Quellen-/Originalgruppenbootstrap wie H1. '
             if report.get('N10_H1_sampling') else
             'Marginale 95%-Quellenbootstrapintervalle aus derselben Ziehungsmatrix wie die Hauptanalyse. ')
    return _write_longtable(output, 'h1_type_intervals.tex', 'H1 nach Aussagenart, rein beschreibend.',
        ['Art', 'Zelle', 'Quellen', 'Schätzer', '95%-KI'], rows,
        scope +
        'Keine zusätzliche Testfamilie und keine Auswahl vollständiger Teilmengen. '
        'Ein fehlender oder leerer geplanter Typnenner bleibt nicht bestimmbar.' + _n10_note(report), banner,
        r'p{.08\linewidth}p{.28\linewidth}rrp{.22\linewidth}')


def _n10_sampling_table(report, output, banner):
    """Display the declared selection distributions, not a new quality test."""
    sample = report['N10_H1_sampling']
    sensitivity = report['sensitivities']['H1_G2_draw_first_aggregation']['cells']
    cells = {row['cell']: row for row in report['cells'] if row['endpoint'] == 'H1'}
    rows = [[cell, _number(cells[cell]['estimate']), _number(sensitivity[cell]['estimate'])]
            for cell in CELLS]
    text = [_longtable_source('N10: H1-Schätzer und getrennte G2-Aggregationssensitivität.',
        ['Zelle', 'N10 gepoolt je Quelle', 'G2 erst Durchläufe'], rows,
        'Dieselben gezogenen Aussagen und festen Quellengewichte. Die G2-Spalte ist eine '
        'beschreibende Aggregationssensitivität, kein weiterer Primärtest. Nicht bestimmbare '
        'Werte bleiben n. b. Keine Auswahl vollständiger Quellen.' + _n10_note(report), banner,
        r'p{.35\linewidth}rr')]
    rows = [[dimension + ': ' + str(row['level']), _count(row['population_count']),
             _count(row['selected_count']), _number(row['sampling_fraction'])]
            for dimension, values in sample['selection_distributions'].items() for row in values]
    text.append(_longtable_source('N10: beschreibende Verteilung von Population und gezogenem Präfix.',
        ['Merkmal', 'Population N', 'Gezogen n', 'Anteil n/N'], rows,
        'Nur ursprüngliche Elternvorkommen, keine Doppelzählung über Export- oder Filterzellen. '
        'Fehlversuche bleiben im Präfix. Diese Verteilungen begründen weder exakt gleiche '
        'Inklusionswahrscheinlichkeiten noch einen Qualitätsvorteil.', banner,
        r'p{.45\linewidth}rrr'))
    path = output / 'n10_sampling.tex'
    path.write_text('\n'.join(text), encoding='utf8')
    return path


def _construction_table(report, output, banner):
    data=report.get('construction_diagnostics',{}).get('N5_joint',{})
    variant=data.get('V1',{})
    rows=[['AS','n. a.','n. a.','n. a.',data.get('AS',{}).get('status','not_applicable')],
        ['V1',_count(variant.get('completed_joint_responses')),_count(variant.get('rejected_joint_responses')),
         _number(variant.get('rejection_rate')),variant.get('status','not_provided')]]
    return _write_table(output,'construction_diagnostics.tex','N5: technischer Ergänzungspass.',
        ['Arm','abgeschlossen','abgelehnt','Ablehnquote','Status'],rows,
        'AS besitzt keinen gemeinsamen Ergänzungspass, daher nicht anwendbar statt null. '
        'Fehlende V1-Belege bleiben unbekannt. Auch abgelehnte Antworten verursachen Aufwand. '
        'N5 ist eine prospektive B4-Änderung und keine ursprüngliche G2-Bestätigungsanalyse. '
        'Guardablehnungen sind keine externen Bewertungsfehlwerte.',banner)


def _h3_counts_table(report, output, banner):
    originals=report.get('H3_original_measurements',[])
    rows=[]
    for cell in CELLS:
        selected=[row for row in originals if row.get('cell')==cell]
        counts=[]
        for category,names in (('content',('direct_content_found','native_objects')),
                               ('capacity',('retained_occurrences','expected_occurrences'))):
            records=[]
            for row in selected:
                section=(row.get('categories',{}).get('ALL',{}) if category=='content'
                         else row.get('projected_occurrence_capacity',{}))
                records.append([section.get(name) for name in names])
            complete=bool(records) and all(row.get('status')=='complete' for row in selected)
            for column in range(2):
                values=[record[column] for record in records]
                valid=[value for value in values if not isinstance(value,bool) and isinstance(value,Integral) and value>=0]
                if not valid:
                    counts.append('unbekannt')
                else:
                    counts.append(str(sum(valid))+(' (Teil)' if len(valid)!=len(values) or not complete else ''))
        rows.append([cell,*counts])
    return _write_table(output,'h3_absolute_counts.tex','H3: Summen der ursprünglichen A6-Zähler.',
        ['Zelle','Gefunden ges.','Nativ ges.','Erhalten ges.','Erwartet ges.'],rows,
        'Ausschließlich absolute Summen vorhandener Originalmessungen über Quellen und Durchläufe. '
        'Teil kennzeichnet eine unvollständige technische Summe. Inhaltsauffindbarkeit verwendet native '
        'Objekte, Projektionskapazität verwendet Projektions-/EV-Teilnehmerkanten. Diese Summen definieren '
        'keinen gepoolten Qualitätsschätzer und kein ganzes aussagenbezogenes C/N. '
        'Rollen- und Einschränkungsrekonstruktion folgt daraus nicht.',banner)


def _ablation_table(report, output, banner):
    groups=defaultdict(list)
    for row in report.get('ablations', []):
        groups[row.get('endpoint','unbekannt')].append(row)
    text=[]
    for endpoint, entries in groups.items():
        rows=[];bounds=[]
        for row in entries:
            ci=_interval(row.get('ci95'))
            sensitivity=_interval(row.get('identification_sensitivity95'))
            rows.append([row.get('control',''),row.get('treatment',''),_number(row.get('point_difference')),
                '['+_number(ci[0])+', '+_number(ci[1])+']' if ci else 'n. b.'])
            bounds.append([row.get('control',''),row.get('treatment',''),
                _number(sensitivity[0] if sensitivity else None),_number(sensitivity[1] if sensitivity else None)])
        note=('Sekundäre deskriptive Kontraste. Marginale 95%-Perzentilintervalle sind keine '
              'simultanen Holm-Intervalle. Kein zusätzlicher Primärtest und kein isolierter kausaler Effekt.')
        alignment=r'p{.28\linewidth}p{.28\linewidth}rr'
        text.append(_longtable_source(endpoint+': vorab festgelegte Zellkontraste.',
            ['Kontrolle','Variante','Differenz','95%-KI'],rows,note,banner,alignment))
        text.append(_longtable_source(endpoint+': Identifikationssensitivität der Kontraste.',
            ['Kontrolle','Variante','Sens.-Untergr.','Sens.-Obergr.'],bounds,
            'Quantilgrenzen der Identifikationsschranken bleiben vom marginalen Konfidenzintervall '
            'getrennt. Keine zusätzliche Testfamilie oder Auswahl günstiger Kontraste.',banner,alignment))
    if not text:
        text.append(_longtable_source('Vorab festgelegte Zellkontraste.',
            ['Endpunkt','Kontrolle','Variante','Differenz'],[], 'Keine Kontraste vorhanden.',banner))
    path=output/'ablations.tex';path.write_text('\n'.join(text),encoding='utf8')
    return path


def _effort_tables(report, output, banner):
    effort = report.get('effort', [])
    groups = defaultdict(list)
    for row in effort:
        groups[(row.get('population'), row.get('pricing_scenario'), str(row.get('currency') or 'unbekannt'))].append(row)
    paths = []
    for (population, scenario, currency), entries in sorted(groups.items(), key=lambda item: tuple(str(v) for v in item[0])):
        scope = ('Population: ' + str(population or 'nicht zugeordnet') + '. Preisszenario: '
                 + str(scenario or 'nicht angegeben') + '. Währung: ' + currency + '.')
        plain_suffix = re.sub(r'[^A-Za-z0-9]+', '_', currency).strip('_').lower() or 'unknown'
        if population is None and scenario is None:
            suffix = plain_suffix
        else:
            signature = '|'.join(str(v) for v in (population, scenario, currency))
            slug = re.sub(r'[^A-Za-z0-9]+', '_', str(population or 'shared') + '_' + str(scenario or 'unknown')).strip('_')[:55]
            suffix = slug.lower() + '_' + plain_suffix + '_' + sha256(signature.encode('utf8')).hexdigest()[:8]
        calls = [[row.get('package', ''), row.get('arm') or 'shared/unallocated',
            _count(row.get('calls_known')), _count(row.get('calls_unknown')),
            _count(row.get('usage_missing'))] for row in entries]
        paths.append(_write_table(output, 'effort_calls_' + suffix + '.tex', 'Aufruf- und Belegstatus. ' + scope,
            ['Paket', 'Arm', 'Calls bekannt', 'Belege unklar', 'Usage fehlt'], calls,
            'Gemeinsamer oder nicht zugeordneter Aufwand bleibt shared/unallocated. Keine willkürliche '
            'Aufteilung auf V2 oder abhängige Zellen. Szenarien werden nicht addiert. '
            'Reasoning wird nicht nochmals zu Ausgabetokens addiert. Belege unklar zählt Datensätze '
            'mit unbekanntem call_count, nicht die Anzahl unbekannter Aufrufe. Usage fehlt zählt '
            'Datensätze ohne vollständige native Usage.', banner))
        tokens=[[row.get('package',''),row.get('arm') or 'shared/unallocated',
            _count(row.get('prompt_tokens_known')),_count(row.get('output_tokens_known'))] for row in entries]
        paths.append(_write_table(output,'effort_tokens_'+suffix+'.tex','Native Tokenzähler. '+scope,
            ['Paket','Arm','Eingabe','Ausgabe'],tokens,
            'Native Zähler je ausgewiesenem Aufwandspaket. Unvollständige Usage ist kein '
            'Gesamttokenwert. Reasoning wird nicht nochmals zu Ausgabetokens addiert. '
            'Gemeinsamer Aufwand bleibt unzugeordnet; Szenarien und Währungen werden nicht addiert.',banner))
        wires = [[row.get('package', ''), row.get('arm') or 'shared/unallocated',
            _count(row.get('physical_POSTs_known')), _count(row.get('physical_POSTs_unknown_records'))]
            for row in entries]
        paths.append(_write_table(output, 'effort_wire_' + suffix + '.tex', 'Physische Aufrufbelege. ' + scope,
            ['Paket', 'Arm', 'POST bekannt', 'Beleg unbekannt'], wires,
            'Callback-Einträge sind keine unabhängige physische Paketmessung. Fehlende Paketbelege '
            'bleiben unbekannt und werden nicht in null Aufrufe umgedeutet.', banner))
        rows = []
        for row in entries:
            value = _money(row.get('cost_known'))
            if not row.get('cost_complete') and value != 'n. b.':
                value += ' (Teil)'
            rows.append([row.get('package', ''), row.get('arm') or 'shared/unallocated', value,
                _money(row.get('reserved_or_held_cost_known')),
                'vollständig' if row.get('cost_complete') else 'unvollständig',
                'belegt' if row.get('invoice_verified') else 'nicht belegt'])
        paths.append(_write_table(output, 'effort_costs_' + suffix + '.tex', 'Bekannte Kosten. ' + scope,
            ['Paket', 'Arm', currency, 'Reserve/Hold', 'Kostenstand', 'Rechnung'], rows,
            'Keine Währungs- oder Szenariomischung. Reserven/Holds stehen getrennt und werden nicht '
            'nochmals zu bereits enthaltenem Verbrauch addiert. Unvollständige Komponenten sind kein Gesamtpreis. '
            'Listenpreise oder bedingte Szenariowerte sind keine bestätigte Rechnung. '
            'Unbekannte Kosten werden nicht als null ausgegeben.', banner))
    if not groups:
        paths.append(_write_table(output, 'effort_costs.tex', 'Kostenstatus.',
            ['Status'], [['keine Kostenmessung vorhanden']], 'Unbekannte Kosten sind nicht null.', banner))
    return paths


def _agreement_tables(report, output, banner):
    data = report.get('agreement', {})
    rows = []
    paths = []
    labels = ('supported', 'not_supported', 'unclear')
    variants = [('human', 'Mensch', data.get('human')), ('grok', 'Grok gesamt', data.get('grok'))]
    if data.get('grok') is not None:
        for panel, label in (('random_core', 'Grok Zufallsanteil'), ('augmentation_only', 'Grok angereicherte Entfernungen')):
            if panel in data['grok'].get('panels', {}):
                variants.append(('grok_' + panel, label, data['grok']['panels'][panel]))
    for name, label, result in variants:
        if result is None:
            rows.append([label, 'nicht vorhanden', 'n. b.', 'n. b.'])
            continue
        rows.append([label,
            _count(result.get('n_pairs', result.get('N_pair'))), _number(result.get('agreement', result.get('p_o'))),
            _number(result.get('kappa'))])
        matrix = result.get('table3x3', result.get('confusion_matrix', result.get('table')))
        if matrix is not None:
            _need(type(matrix) is list and len(matrix) == 3 and all(len(r) == 3 for r in matrix),
                  'D1_RENDER_3X3_AGREEMENT_REQUIRED')
            table_rows = [[label, *[_count(v) for v in values]] for label, values in zip(labels, matrix)]
            paths.append(_write_table(output, 'agreement_' + name + '_matrix.tex',
                label + ' gegen Hauptbewerter: Paarzählung.',
                ['Zeile / Spalte', *labels], table_rows,
                'Zeilen: C2, Spalten: '+label+'. N_left bezeichnet C2, N_right die jeweilige Annotation. '
                'Nominale Klassen. Unklar ist eine gültige Klasse, technische Fehlwerte sind keine '
                'Unklar-Klasse. Es zählt nur der tatsächliche gepaarte Nenner.', banner))
    paths.insert(0, _write_table(output, 'agreement.tex', 'Bewerterübereinstimmung.',
        ['Vergleich', 'Paare', 'Übereinst.', 'Cohen-kappa'], rows,
        'Ungewichtetes nominales Cohen-kappa über drei Klassen. Bei keinem Paar oder p_e=1 '
        'bleibt kappa undefiniert. Keine Akzeptanzschwelle und keine automatische Labeländerung. '
        'Ein menschlicher Autor ist keine Zweitmenschenannotation. Groks Zufallsanteil und '
        'angereicherte Entfernungen bleiben getrennt, der angereicherte Anteil ist keine Prävalenzstichprobe.', banner))
    return paths


def _weighted_human_table(report, output, banner):
    value = (report.get('agreement', {}).get('human') or {}).get('weighted_prevalence')
    if value is None:
        return []
    if type(value) is dict:
        entries = value.get('arms', value.get('rows', []))
        if type(entries) is dict:
            entries = [{'arm': arm, **row} for arm, row in entries.items()]
    else:
        entries = value
    _need(type(entries) is list and all(type(row) is dict for row in entries),
          'D1_RENDER_WEIGHTED_PREVALENCE_ROWS_REQUIRED')
    rows = [[row.get('arm', row.get('stratum', '')), _number(row.get('estimate')),
        _number(row.get('lower')), _number(row.get('upper')),
        _number(row.get('conservative_verified_supported_fraction')),
        _count(row.get('population_count', row.get('population',row.get('N')))),
        _count(row.get('sample_count', row.get('sample',row.get('n'))))] for row in entries]
    note=('Designgewichtete Schätzer mit Stratumgewichten N_h/n_h, kein populationsvollständiger '
          'Goldwert. Ungeklärte, technisch fehlende und nicht beprobte Anteile können den Punktwert '
          'unidentifiziert lassen. Der konservativ verifizierte Anteil steht getrennt. '
          'Schranken sind Identifikationsschranken des gewichteten Schätzers und keine Stichproben-Konfidenzintervalle.')
    path=_write_table(output, 'human_weighted_prevalence.tex', 'Gewichtete menschliche Quellenstützung.',
        ['Arm', 'Schätzer', 'Untergr.', 'Obergr.', 'verifiziert', 'Population', 'Stichprobe'], rows,note,banner)
    sources=[]
    for entry in entries:
        arm=str(entry.get('arm',entry.get('stratum','')))
        strata=entry.get('strata',[])
        if not strata:
            continue
        samples=[[row.get('category',''),_count(row.get('population_count')),
            _count(row.get('sample_count')),_count(row.get('provided_rows')),
            _count(row.get('unprovided_selected_rows'))] for row in strata]
        sources.append(_longtable_source(arm+': menschliche Schichtstichprobe.',
            ['Schicht','Population','gezogen','vorhanden','fehlt'],samples,
            'Fehlt zählt gezogene, aber nicht bereitgestellte Urteile. Nicht beprobte '
            'Populationsteile verschwinden nicht aus dem gewichteten Nenner.',banner,r'p{.30\linewidth}rrrr'))
        labels=[[row.get('category',''),_count(row.get('supported_count')),
            _count(row.get('not_supported_count')),_count(row.get('unclear_count')),
            _count(row.get('technical_missing_count'))] for row in strata]
        sources.append(_longtable_source(arm+': menschliche Schichturteile.',
            ['Schicht','gestützt','nicht gestützt','unklar','techn. fehlt'],labels,
            'Ungewichtete beobachtete Anzahlen der jeweiligen Stichprobenschicht. '
            'Semantisch unklar und technisch fehlend werden getrennt ausgewiesen.',banner,r'p{.30\linewidth}rrrr'))
        bounds=[[row.get('category',''),_number(row.get('weight')),_number(row.get('estimate')),
            _number(row.get('lower')),_number(row.get('upper'))] for row in strata]
        sources.append(_longtable_source(arm+': menschliche Schichtgewichte und Schranken.',
            ['Schicht','N_h/n_h','Schätzer','Untergr.','Obergr.'],bounds,note,banner,r'p{.30\linewidth}rrrr'))
    with path.open('a',encoding='utf8') as handle:
        handle.write('\n'+'\n'.join(sources))
    return [path]


def _qa_control_table(report, output, banner):
    fixed = report.get('metadata', {}).get('QA_questions', 60)
    _need(type(fixed) is int and fixed == 60, 'D1_RENDER_QA_CONTROL_FIXED_Q60_REQUIRED')
    rows = []
    for control in report.get('QA_controls', []):
        observed, provided = control.get('observed'), control.get('provided')
        _need(control.get('planned', fixed) == fixed and type(observed) is int
              and type(provided) is int and 0 <= observed <= provided <= fixed,
              'D1_RENDER_QA_CONTROL_DENOMINATOR_DRIFT')
        point = control.get('F1') if observed == provided == fixed else None
        rows.append([control.get('mode', ''), str(fixed), str(provided), str(observed),
            _number(point), _number(control.get('lower')), _number(control.get('upper'))])
    return _write_table(output, 'qa_controls.tex', 'Sekundäre QA-Kontextkontrollen mit festem Nenner 60.',
        ['Kontext', 'geplant', 'vorhanden', 'beobachtet', 'F1', 'Untergr.', 'Obergr.'], rows,
        'Pro Kontext bleiben alle 60 vorab festgelegten Fragen im Nenner. Fehlende Antworten '
        'sind unbekannt. Ein Mittel nur über abgeschlossene Antworten ersetzt keinen vollständigen '
        'Punktwert. Leer-/Goldkontrollen sind kein Ersatz für den graphbasierten H4-Endpunkt. '
        'Der nach N6 nicht durchgeführte sekundäre Passagenweg liefert keine Messung.', banner)


def _amendment_table(report, output, banner):
    rows = [[row.get('identifier', ''), row.get('note', '')] for row in report.get('amendments', [])]
    return _write_longtable(output, 'amendments.tex', 'Gebundene Nachträge N2 bis N6.',
        ['Nachtrag', 'Geltung und Grenze'], rows,
        'Nachträge bleiben getrennt vom ursprünglichen G2-Vertrag. N5 ist nach Sicht eines '
        'Konstruktionsfehlers beschlossen. N6 dokumentiert einen nicht durchgeführten sekundären '
        'Passagenendpunkt. Die synthetische Ausführung schafft keine empirische Bestätigung.', banner)


def _decorate(figure, title, note, banner):
    figure.text(.5, .985, banner, ha='center', va='top', fontsize=11, fontweight='bold', color='#8a2633')
    figure.suptitle(title, fontsize=13, y=.925)
    figure.text(.5, .025, note, ha='center', va='bottom', fontsize=9, color='#333333', linespacing=1.45)


def _save(plt, figure, path, title, banner):
    try:
        figure.savefig(path, format='pdf', facecolor='white',
            metadata={'Title': title, 'Subject': banner, 'Creator': 'D1 frozen-analysis renderer'})
    finally:
        plt.close(figure)
    return path


def _primary_figure(report, output, plt, banner):
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    values = []
    for y, name in enumerate(('H1', 'H2', 'H4')):
        row = report.get('primary', {}).get(name, {})
        point, interval = row.get('point_difference'), _interval(row.get('ci95'))
        boundary = row.get('null_boundary', -.05 if name == 'H2' else 0)
        if _finite(boundary):
            ax.vlines(boundary * 100, y-.22, y+.22, color=ORANGE, linestyles='--', linewidth=1.7)
            values.append(boundary * 100)
        if interval:
            ax.hlines(y, interval[0]*100, interval[1]*100, color=BLUE, linewidth=1.8)
            ax.plot([interval[0]*100, interval[1]*100], [y, y], '|', color=BLUE, markersize=9)
            values.extend(v*100 for v in interval)
        if _finite(point):
            ax.plot(point*100, y, 'o', color=BLUE, markersize=6)
            values.append(point*100)
        else:
            ax.text(.99, y, 'nicht bestimmbar', transform=ax.get_yaxis_transform(), ha='right', va='center', color=GRAY)
        if not row.get('testable'):
            ax.text(.99, y+.20, 'kein Primärtest', transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=9, color=GRAY)
    ax.axvline(0, color='#888888', linewidth=.8, zorder=0)
    lower, upper = min([0, *values]), max([0, *values])
    padding = max(1.5, (upper-lower)*.12)
    ax.set_xlim(lower-padding, upper+padding)
    ax.set_yticks(range(3), [PRIMARY_NAMES[k] for k in ('H1','H2','H4')])
    ax.set_ylim(2.55, -.50)
    ax.set_xlabel('Differenz V2_ROW minus AS_ORIGINAL in Prozentpunkten')
    ax.grid(axis='x', color='#dddddd', linewidth=.6)
    ax.spines[['top','right']].set_visible(False)
    fig.subplots_adjust(left=.24, right=.94, top=.79, bottom=.27)
    _decorate(fig, 'Primärkontrast und marginale Unsicherheit',
        'Punkte: Schätzer. Linien: zweiseitige 95%-Bootstrapintervalle, keine simultanen Holm-Intervalle.\n'
        'Orange Striche: jeweiliger Nullrand (H2: -5 Prozentpunkte). H3 hat keinen Primärtest.' +
        ('\nH1: N10-Näherung mit kostenbegrenztem Präfix und zweistufigem Quellen-/Gruppenbootstrap.'
         if report.get('N10_H1_sampling') else ''), banner)
    return _save(plt, fig, output/'primary_contrasts.pdf', 'Primärkontrast', banner)


def _ratio_panel(ax, rows, title, xlabel):
    selected = {row['cell']: row for row in rows}
    _need(len(selected) == len(rows), 'D1_RENDER_DUPLICATE_ENDPOINT_CELL')
    for y, cell in enumerate(CELLS):
        row = selected.get(cell, {})
        interval = _interval([row.get('lower'), row.get('upper')])
        point = row.get('estimate')
        if interval:
            _need(0 <= interval[0] <= interval[1] <= 1, 'D1_RENDER_RATIO_BOUNDS_OUTSIDE_UNIT')
            ax.hlines(y, *interval, color=GRAY, linewidth=2.1)
            ax.plot(interval, [y,y], '|', color=GRAY, markersize=7)
        if _finite(point):
            _need(0 <= point <= 1, 'D1_RENDER_RATIO_OUTSIDE_UNIT')
            ax.plot(point, y, 'o', color=BLUE, markersize=5)
        elif interval:
            ax.text(.98, y-.16, 'unvollständig', ha='right', va='bottom', fontsize=9, color=GRAY)
        else:
            ax.text(.03, y, 'nicht bestimmbar', ha='left', va='center', fontsize=9, color=GRAY)
    # Keep markers/caps at the legal score endpoints fully visible.
    ax.set_xlim(-.02,1.02)
    ax.set_xticks([0,.2,.4,.6,.8,1])
    ax.set_ylim(7.65,-.65)
    ax.set_yticks(range(8), CELL_LABELS)
    ax.set_title(title, fontsize=11, pad=10)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.grid(axis='x', color='#dddddd', linewidth=.6)
    ax.spines[['top','right']].set_visible(False)


def _cell_figure(report, output, plt, banner):
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 6))
    for ax, endpoint, title in zip(axes, ('H1','H2'), ('H1 Quellenstützung','H2 Ausgewählter Bedeutungserhalt')):
        _ratio_panel(ax, [r for r in report.get('cells', []) if r['endpoint'] == endpoint], title, 'Anteil [0,1]')
    fig.subplots_adjust(left=.15, right=.97, wspace=.52, top=.78, bottom=.20)
    _decorate(fig, 'Acht Zellen: konservative Scores und Identifikationsschranken',
        'Punkte: konservative Schätzer. Graue Linien: Identifikationsschranken, keine Konfidenzintervalle.\n'
        + ('H1: N10-Anteile über gezogene Vorkommen je Quelle gepoolt, Inklusion nur näherungsweise gleich.\n'
           'H2: Durchläufe je Quelle gemittelt. Alle Quellen gleich gewichtet, keine Fehlwertauswahl.'
           if report.get('N10_H1_sampling') else
           'Durchläufe je Quelle gemittelt, Quellen gleich gewichtet. Fehlende native Nenner bleiben unbestimmt.'), banner)
    return _save(plt, fig, output/'h1_h2_cells.pdf', 'H1 und H2: acht Zellen', banner)


def _h3_figure(report, output, plt, banner):
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 6.2))
    for ax, endpoint, title, xlabel in zip(axes,
        ('H3_direct_content_fraction','H3_occurrence_capacity'),
        ('Inhaltsauffindbarkeit','Projektionskapazität'),
        ('direct_content_fraction\nNenner: native Objekte',
         'occurrence_capacity\nNenner: Projektions-/EV-Teilnehmerkanten')):
        _ratio_panel(ax, [r for r in report.get('cells', []) if r['endpoint'] == endpoint], title, xlabel)
    fig.subplots_adjust(left=.15, right=.97, wspace=.52, top=.78, bottom=.23)
    _decorate(fig, 'H3: zwei getrennte A6-Kennzahlen',
        'Verschiedene Nenner bleiben getrennt. Kein identifiziertes ganzes aussagenbezogenes C/N.\n'
        'EV-Teilnehmerprojektionen belegen keine vollständige Wiederherstellung von Rollen und Einschränkungen.', banner)
    return _save(plt, fig, output/'h3_separate_denominators.pdf', 'H3: getrennte Nenner', banner)


def _qa_figure(report, output, plt, banner):
    fig, ax = plt.subplots(figsize=(10.5, 6))
    _ratio_panel(ax, [r for r in report.get('cells', []) if r['endpoint'] == 'F1'],
        'Offizielles Antwort-F1 auf dem festen Fragenbestand', 'Fragegemitteltes F1 [0,1]')
    fig.subplots_adjust(left=.23, right=.94, top=.78, bottom=.21)
    _decorate(fig, 'MuSiQue: acht Graphzellen',
        'Schranken über alle festen Fragen. Fehlende Antworten bleiben unbekannt, nicht leer oder falsch.\n'
        'Punktwerte nur bei definiertem Endpunkt. EM und zusätzliche Kontextwege sind sekundär.', banner)
    return _save(plt, fig, output/'qa_f1_cells.pdf', 'MuSiQue F1: acht Zellen', banner)


def render(report, output_dir, *, allow_real=False):
    """Return absolute table/PDF paths. Default scope permits synthetic data only.

    This function does not compute an estimand, alter a score, select a test or
    load any input file. Real-data delivery is a later explicit owner action.
    """
    _need(type(report) is dict and type(report.get('synthetic')) is bool, 'D1_RENDER_SYNTHETIC_FLAG_REQUIRED')
    _need(report['synthetic'] or allow_real is True, 'D1_RENDER_REAL_INPUTS_REQUIRE_EXPLICIT_ENABLE')
    seen = set()
    for row in report.get('cells', []):
        key = row['endpoint'], row['cell']
        _need(key[0] in ENDPOINT_NAMES and key[1] in CELLS and key not in seen,
              'D1_RENDER_UNKNOWN_OR_DUPLICATE_ENDPOINT_CELL')
        _need(row.get('defined') is not False or row.get('estimate') is None,
              'D1_RENDER_UNDEFINED_ENDPOINT_CANNOT_HAVE_POINT_SCORE')
        seen.add(key)
    output = Path(output_dir).absolute()
    output.mkdir(parents=True, exist_ok=True)
    banner = _banner(report)
    paths = [_primary_table(report, output, banner), _primary_bounds_table(report, output, banner),
        _sensitivity_table(report, output, banner), *_cell_tables(report, output, banner),
        _missingness_table(report, output, banner), _h3_counts_table(report, output, banner),
        *_distinct_tables(report, output, banner), _strata_table(report, output, banner),
        _construction_table(report, output, banner), _ablation_table(report, output, banner), *_effort_tables(report, output, banner),
        *_agreement_tables(report, output, banner), *_weighted_human_table(report, output, banner),
        _qa_control_table(report, output, banner), _amendment_table(report, output, banner)]
    # Lazy import keeps code development and import-time discovery lightweight.
    import matplotlib
    matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt
    with plt.rc_context({'font.family':'DejaVu Sans', 'font.size':10, 'axes.labelsize':10,
                        'xtick.labelsize':9, 'ytick.labelsize':9, 'pdf.fonttype':42,
                        'ps.fonttype':42, 'axes.unicode_minus':False}):
        for creator in (_primary_figure, _cell_figure, _h3_figure, _qa_figure):
            paths.append(creator(report, output, plt, banner))
    if 'components' in report:
        from .n8_render import render_n8
        paths.extend(Path(p) for p in render_n8(report, output, banner=banner, allow_real=allow_real))
        paths.append(_h1_type_intervals(report, output, banner))
    if report.get('N10_H1_sampling'):
        paths.append(_n10_sampling_table(report, output, banner))
    if report.get('N14_H2_missingness'):
        from .n14_render import render_n14
        paths.extend(render_n14(report, output, banner=banner, allow_real=allow_real))
    wrapper = output/'tables.tex'
    tables = [p for p in paths if p.suffix == '.tex']
    wrapper.write_text('\n'.join([r'\documentclass[a4paper,12pt]{article}',
        r'\usepackage[T1]{fontenc}', r'\usepackage[utf8]{inputenc}',
        r'\usepackage[a4paper,margin=20mm]{geometry}', r'\usepackage{booktabs,longtable}',
        r'\begin{document}', r'\section*{' + _tex(banner) + '}',
        *[r'\input{' + p.name + '}\n' + r'\clearpage' for p in tables], r'\end{document}', '']), encoding='utf8')
    paths.append(wrapper)
    return [str(path) for path in paths]
