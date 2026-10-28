"""Aggregate-only X3 tables: nachträglich, explorativ.

Rendering uses the supplied result without recomputing an estimator, interval,
sample, test or judgment. No individual source or annotation rows are emitted.
"""
import math
from pathlib import Path


CLASSIFICATION = 'nachträglich, explorativ'
ORDER = ('AS', 'AS+G', 'AS+G(VV)', 'V1', 'V2', 'V1+G(VV)')
VARIANTS = frozenset(('AS+G(VV)', 'V1+G(VV)'))


def _number(value, *, signed=False):
    if value is None:
        return 'nicht schätzbar'
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('X3_FINITE_DISPLAY_NUMBER_REQUIRED')
    # Avoid a visually misleading negative zero after rounding.
    percent = value * 100
    if abs(percent) < 0.05:
        percent = 0.0
    return format(percent, '+.1f' if signed else '.1f').replace('.', ',')


def _interval(interval, *, signed=False):
    if interval is None or interval.get('lower') is None or interval.get('upper') is None:
        return 'KI nicht schätzbar'
    return '[' + _number(interval['lower'], signed=signed) + '; ' + _number(interval['upper'], signed=signed) + ']'


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError('X3_NONNEGATIVE_INTEGER_COUNT_REQUIRED')
    return str(value)


def _validated(result):
    if result.get('classification') != CLASSIFICATION:
        raise ValueError('X3_EXPLORATORY_CLASSIFICATION_REQUIRED')
    rows = []
    for name in ORDER:
        row = result['cells'][name]
        if row.get('classification') != CLASSIFICATION:
            raise ValueError('X3_CELL_EXPLORATORY_CLASSIFICATION_REQUIRED')
        if name in VARIANTS:
            h2 = row.get('H2', {})
            if (h2.get('status') != 'nicht bewertet; nicht geschätzt'
                    or h2.get('estimate') is not None or h2.get('ci95') is not None):
                raise ValueError('X3_H2_MUST_REMAIN_UNASSESSED_AND_UNESTIMATED')
        removal = row['removals']
        removed = (_count(removal['removed_occurrences']) + '/'
                   + _count(removal['original_native_occurrences']) + ' ('
                   + _number(removal['removed_share_of_all_original_occurrences']) + ')')
        h1 = row['H1']
        score = _number(h1['estimate']) + ' ' + _interval(h1['ci95'])
        contrast = row['difference_from_original_parent']
        delta = ('Referenz' if contrast is None else
                 _number(contrast['point_difference'], signed=True) + ' '
                 + _interval(contrast['ci95'], signed=True))
        rows.append((name, removed, score, delta))
    return rows


def _author_notes(result):
    sample = result['H12_fixed_sample']
    if sample.get('classification') != CLASSIFICATION:
        raise ValueError('X3_AUTHOR_EXPLORATORY_CLASSIFICATION_REQUIRED')
    notes = []
    for group, description in (('vv_still_removed', 'VV weiterhin entfernt'),
                               ('ee_removal_reversed', 'EE wiederhergestellt')):
        detail = []
        for arm in ('AS', 'V1', 'overall'):
            row = sample['intersections'][group]['by_arm'][arm]
            values = [row[field] for field in ('supported_count', 'not_supported_count',
                                               'unclear_count', 'missing_count')]
            if sum(int(_count(v)) for v in values) != int(_count(row['N'])):
                raise ValueError('X3_AUTHOR_COUNT_SUM_DIFFERS')
            detail.append(('gesamt' if arm == 'overall' else arm) + ': '
                          + '/'.join(_count(v) for v in values)
                          + ' (n=' + _count(row['N']) + ')')
        notes.append(description + ' — ' + '; '.join(detail) + '.')
    return notes


def _notes(result):
    scope = result['scope']
    return [
        'Nachträglich, explorativ. H1 betrifft das gesamte erhaltene Inventar, einschließlich EE und EV; '
        'VV kennzeichnet nur den angewandten Prüffilter. Entfernung: n/N der ursprünglichen Aussagen (%).',
        'H1 und Differenzen: ' + _count(scope['sources']) + ' gleich gewichtete Quellen, '
        + _count(scope['source_draw_pairs']) + ' Quelle-Durchlauf-Paare; '
        'C2-Urteile nach N10 geerbt. Marginale 95-%-Bootstrapintervalle wie D1, '
        'Differenzen jeweils gegenüber AS bzw. V1. Kostenbedingt gestopptes C2-Präfix; '
        'gleiche Einschlusswahrscheinlichkeiten sind nicht nachgewiesen.',
        'H2 ist für AS+G(VV) und V1+G(VV) nicht bewertet und wird nicht geschätzt. '
        'V2 bleibt unverändert; kein Eingang dieser Analyse in Haupttests oder Gesamturteil.',
        'H12-Autorenurteile (feste Stichprobe, keine Prävalenzschätzung): Reihenfolge '
        'gestützt/nicht gestützt/unklar/fehlend. '
        + ' '.join(_author_notes(result)),
    ]


def render_markdown(result):
    rows = _validated(result)
    lines = ['**X3: Prüffilter nur für VV — nachträglich, explorativ**', '',
             '| Zelle | Entfernt n/N (%) | H1 (%) [95-%-KI] | Δ zur Ausgangszelle (Pp.) [95-%-KI] |',
             '|:--|--:|--:|--:|']
    for name, removed, h1, delta in rows:
        cell = '**' + name + '**' if name in VARIANTS else name
        lines.append('| ' + ' | '.join((cell, removed, h1, delta)) + ' |')
    lines.extend(['', *[note + '\n' for note in _notes(result)]])
    return '\n'.join(lines).rstrip() + '\n'


def _tex(text):
    mapping = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
               '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
               '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
               '—': '---', 'Δ': r'$\Delta$'}
    return ''.join(mapping.get(char, char) for char in text)


def render_latex(result):
    rows = _validated(result)
    lines = [
        '% X3: nachträglich, explorativ; generated from aggregate result.json.',
        r'\begin{table}[htbp]', r'\centering',
        r'\caption{Prüffilter nur für VV: nachträglich, explorativ.}',
        r'\label{tab:x3-vv-explorativ}',
        r'\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrr@{}}',
        r'\hline',
        r'Zelle & \shortstack{Entfernt\\n/N (\%)} & \shortstack{H1 (\%)\\{[95-\%-KI]}} & \shortstack{$\Delta$ (Pp.)\\{[95-\%-KI]}} \\',
        r'\hline',
    ]
    for name, removed, h1, delta in rows:
        name = r'\textbf{' + _tex(name) + '}' if name in VARIANTS else _tex(name)
        lines.append(' & '.join((name, _tex(removed), _tex(h1), _tex(delta))) + r' \\')
    lines.extend([r'\hline', r'\end{tabular*}', r'\par\medskip',
                  r'\begin{minipage}{\linewidth}'])
    for note in _notes(result):
        lines.append(_tex(note) + r'\par')
    lines.extend([r'\end{minipage}', r'\end{table}', ''])
    return '\n'.join(lines)


def write_tables(result, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for filename, contents in (('tabelle.md', render_markdown(result)),
                               ('tabelle.tex', render_latex(result))):
        path = output_dir / filename
        with path.open('w', encoding='utf8', newline='\n') as handle:
            handle.write(contents)
        artifacts[filename] = path
    return artifacts
