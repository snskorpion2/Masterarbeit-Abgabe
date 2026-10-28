"""Render RB1 numerical aggregates as the requested LaTeX and report."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LABELS = {'AS_ORIGINAL': 'AS', 'AS_G_ROW': 'AS+G', 'V1_ROW': 'V1', 'V2_ROW': 'V2'}
ENDPOINTS = ('H1', 'H2_G2', 'H2_N14')
ENAMES = {'H1': 'H1', 'H2_G2': 'H2 G2', 'H2_N14': 'H2 N14'}


def num(x, digits=2):
    return 'u.' if x is None else f'{100*x:.{digits}f}'.replace('.', ',')


def rng(obj, tex=False):
    separator = '--' if tex else ' bis '
    return num(obj['minimum']) + separator + num(obj['maximum'])


def pair(obj, tex=False):
    separator = r'$\!-\!$' if tex else '−'
    return LABELS[obj['treatment']] + separator + LABELS[obj['control']]


def render():
    r = json.loads((ROOT/'result.json').read_text(encoding='utf-8'))
    rob = r['robustness']
    table = [
        r'\begin{table}[htbp]',
        r'\centering\small',
        r'\caption[Robustheit und Typstandardisierung nach N17]{Nachträgliche Sensitivitäten nach N17. Kontraste sind Differenzen in Prozentpunkten. Die relative Senkung ist in Prozent angegeben und betrifft den konservativ nicht vollständig gestützt gewerteten Anteil.}',
        r'\label{tab:rb1-robustheit}',
        r'\begin{tabular}{@{}lrrrrr@{}}',
        r'\toprule',
        r'\multicolumn{6}{@{}l}{\textbf{Typstandardisierung von H1}}\\',
        r'Kontrast ($n$) & Roh & Std.\ AS & Std.\ Pool & Rest AS & Rest Pool\\',
        r'\midrule',
    ]
    for d in r['type_decomposition']:
        a = d['N17_full_population']
        table.append(pair(d, True) + f" ({a['source_count']}) & " + ' & '.join([
            num(a['unstandardized']['difference']), num(a['AS_standardized']['difference']),
            num(a['pooled_standardized']['difference']), num(a['AS_standardized']['mix_remainder']),
            num(a['pooled_standardized']['mix_remainder'])]) + r'\\')
    table.append(r'\addlinespace')
    for d in r['type_decomposition']:
        a = d['common_estimable_sensitivity']
        if a is None:
            continue
        table.append(pair(d, True) + f" ({a['source_count']})" + r'$^\ast$ & ' + ' & '.join([
            num(a['unstandardized']['difference']), num(a['AS_standardized']['difference']),
            num(a['pooled_standardized']['difference']), num(a['AS_standardized']['mix_remainder']),
            num(a['pooled_standardized']['mix_remainder'])]) + r'\\')
    table.extend([r'\bottomrule', r'\end{tabular}', r'\par\medskip',
        r'\begin{tabular}{@{}lrrr@{}}', r'\toprule',
        r'\multicolumn{4}{@{}l}{\textbf{V2 gegenüber AS: Weglassanalysen}}\\',
        r'Maß ($n$) & Voll & Eine Quelle weg & Eine Vertragsgruppe weg\\', r'\midrule'])
    for e in ENDPOINTS:
        a = rob['endpoints'][e][0]
        table.append(ENAMES[e] + f" ({a['source_count']}) & {num(a['full']['difference'])} & " +
                     rng(a['leave_one_source_out']['range'], tex=True) + ' & ' +
                     rng(a['leave_one_family_out']['range'], tex=True) + r'\\')
    table.extend([r'\bottomrule', r'\end{tabular}', r'\par\medskip',
        r'\begin{tabular}{@{}lrrr@{}}', r'\toprule',
        r'\multicolumn{4}{@{}l}{\textbf{V2 gegenüber AS: getrennte Konstruktionen}}\\',
        r'Maß & Durchlauf 1 & Durchlauf 2 & Durchlauf 3\\', r'\midrule'])
    for e in ENDPOINTS:
        table.append(ENAMES[e] + ' & ' + ' & '.join(
            num(x['endpoints'][e][0]['full']['difference']) for x in rob['by_draw']) + r'\\')
    table.extend([r'\bottomrule', r'\end{tabular}', r'\par\medskip',
        r'\begin{tabular}{@{}lrr@{}}', r'\toprule',
        r'\multicolumn{3}{@{}l}{\textbf{Relative Senkung des nicht gestützten Anteils}}\\',
        r'Gegenüber AS & Senkung (\%) & Marginales 95-\%-KI (\%)\\', r'\midrule'])
    for a in r['relative_non_supported_reductions']:
        ci = a['ci95']
        table.append(LABELS[a['treatment']] + ' & ' + num(a['relative_reduction']) +
                     ' & [' + num(ci['lower']) + '; ' + num(ci['upper']) + r']\\')
    table.extend([r'\bottomrule', r'\end{tabular}',
        r'\par\smallskip\begin{minipage}{\textwidth}\footnotesize',
        r'u.: unbestimmt, da V1/V2 in RGCONF04 keine VV-Aussagen enthalten. '
        r'AS: Typanteile des vollständigen AS-Bestands. Pool: gepoolte vollständige Bestände beider Kontrastarme. '
        r'Rest: Roh minus standardisiert auf denselben Quellen, keine kausale Erklärung.',
        r'$\ast$: zusätzliche Sensitivität auf gemeinsam schätzbaren Quellen mit dort neu gebildeten Gewichten, '
        r'kein Ersatz des 24-Quellen-Kontrasts. Weglassspannen sind keine Konfidenzintervalle. '
        r'N14 behält 17 Quellen, darunter keine versiegelte Quelle. Deren Weglassen wäre ein Nullschritt. '
        r'Durchlauf 3 umfasst nur die 20 neuen Quellen, N14 weiterhin 17. '
        r'Die relative Senkung enthält unklare und gezogene technisch fehlende Urteile und ist keine bestätigte sachliche Fehlerquote. '
        r'Ihre Intervalle verwenden dieselben 10\,000 gepaarten N10-Ziehungen. Keine neuen Tests oder Holm-Entscheidungen.',
        r'\end{minipage}', r'\end{table}', ''])
    (ROOT/'anhang-tabelle.tex').write_text('\n'.join(table), encoding='utf-8')

    main = (
        r'Auf 23 für alle Typen schätzbaren Quellen sinkt der H1-Abstand V2 gegenüber AutoSchemaKG '
        r'von 8{,}27 auf 5{,}41 Prozentpunkte mit AS-Typgewichten beziehungsweise 4{,}09 mit gemeinsamen '
        r'Bestandsgewichten, während der standardisierte 24-Quellen-Kontrast wegen strukturell fehlender '
        r'VV-Aussagen unbestimmt bleibt. '
        r'Die unstandardisierten V2--AS-Abstände bleiben für H1 und beide H2-Analysen beim Weglassen einzelner '
        r'Quellen oder Vertragsgruppen positiv, ohne dass diese nachträglichen Sensitivitäten einen zusätzlichen '
        r'Primärtest oder Bewerterunabhängigkeit ersetzen (Anhang~\ref{tab:rb1-robustheit}).'
    )
    (ROOT/'kapitel6-zwei-saetze.tex').write_text(main + '\n', encoding='utf-8')

    lines = [
        '# RB1 – Robustheit und Typzerlegung nach N17 §2',
        '',
        'Reine CPU-Nachrechnung der final gebundenen D1-Eingänge. Keine Modellaufrufe, keine neue Annotation, '
        'keine Änderung an Primärtests, Holm oder N8-Gesamtstufe. N17 wurde nach Kenntnis des D1-Vorlaufs '
        'festgelegt. Die folgenden Zahlen sind nachträgliche beschreibende Sensitivitäten.',
        '',
        '**Der typstandardisierte Vorsprung ist deutlich kleiner.** Auf den gemeinsam schätzbaren 23 Quellen '
        'sinkt V2−AS von 8,27 auf 5,41 Prozentpunkte mit AS-Typgewichten und auf 4,09 mit gepoolten Gewichten. '
        'Das sind keine standardisierten 24-Quellen-Ergebnisse: RGCONF04 enthält in V1 und V2 gar keine VV-Aussagen. '
        'Nach N17 bleiben deshalb die drei davon betroffenen Standardkontraste über alle 24 Quellen unbestimmt.',
        '',
        '## Typstandardisierung und rechnerischer Mischungsrest',
        '',
        'Ganze native Vorkommensbestände über alle 68 geplanten Quelle-Durchlauf-Einheiten bestimmen die Gewichte. '
        'Die Typgüten sind die gleichgewichteten D1-Quellenmittel. Original-/ROW-Exportansichten werden nicht doppelt '
        'gezählt. Die gemeinsamen Gewichte entstehen aus der Summe der beiden Bestände, nicht ihrer Schnittmenge. '
        'Der Rest ist die unstandardisierte minus standardisierte Differenz derselben Quellen. Er umfasst auch '
        'Unterschiede der Quellen-/Typaggregation und ist kein kausal erklärter Gewinnanteil.',
        '',
        '| Vergleich | Quellen | Roh (PP) | AS-standardisiert | Pool-standardisiert | Rest AS (PP) | Rest Pool (PP) |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for d in r['type_decomposition']:
        for label, a in [('N17', d['N17_full_population']),
                         ('Zusatzsensitivität', d['common_estimable_sensitivity'])]:
            if a is None:
                continue
            lines.append(f"| {pair(d)} ({label}) | {a['source_count']} | " + ' | '.join([
                num(a['unstandardized']['difference']), num(a['AS_standardized']['difference']),
                num(a['pooled_standardized']['difference']), num(a['AS_standardized']['mix_remainder']),
                num(a['pooled_standardized']['mix_remainder'])]) + ' |')
    weights = r['type_decomposition'][0]['N17_full_population']['AS_inventory_weights']
    lines.extend(['', 'Vollständiger AS-Bestand: ' +
        ', '.join(f"{t}: {weights['counts'][t]} ({num(weights['weights'][t])} %)" for t in ('EE', 'EV', 'VV')) +
        f"; insgesamt {weights['denominator']} Vorkommen. "
        'In der 23er-Sensitivität werden sowohl Gewichte als auch Rohkontraste innerhalb genau dieser Quellen neu berechnet. '
        'Ihre Auswahl nach Typschätzbarkeit ist keine Zufallsstichprobe.',
        '', '## Weglassen einzelner Quellen und Vertragsgruppen',
        '', 'Alle Angaben sind Prozentpunkte. Die Spannen sind keine Konfidenzintervalle. '
        '„sealed4“ bezeichnet die vier versiegelten Quellen als Vertragskohorte, keine gemeinsame Textgattung. '
        'N14 schließt Quellen nach technischer Urteilsverfügbarkeit kontrastspezifisch ein. '
        'Das Weglassen bereits ausgeschlossener Quellen ist kein weiterer Robustheitsfall.',
        '',
        '| Maß / Kontrast | n | Voll | Quelle weg: Spanne | Einflussreichste Quelle | Gruppe weg: Spanne |',
        '|---|---:|---:|---|---|---|'])
    omission_rows = []
    for e in ENDPOINTS:
        for a in rob['endpoints'][e]:
            s = a['leave_one_source_out']
            f = a['leave_one_family_out']
            influence = s['most_influential']
            desc = ('u.' if influence is None else
                    influence['omitted_source_id'] + ' (Änderung ' + num(influence['deviation_from_full']) + ' PP)')
            lines.append(f"| {ENAMES[e]} {pair(a)} | {a['source_count']} | {num(a['full']['difference'])} | " +
                         rng(s['range']) + ' | ' + desc + ' | ' + rng(f['range']) + ' |')
            for level, panel, key in [('source', s, 'omitted_source_id'), ('family', f, 'omitted_family')]:
                for row in panel['rows']:
                    omission_rows.append({'endpoint': e, 'control': a['control'], 'treatment': a['treatment'],
                        'omission_level': level, 'omitted': row[key], 'remaining_sources': row['source_count'],
                        'control_mean': row['control_mean'], 'treatment_mean': row['treatment_mean'],
                        'difference': row['difference'], 'deviation_from_full': row['deviation_from_full']})
    lines.extend(['', 'Für V2−AS bleibt die Richtung in allen definierten Weglassfällen positiv. '
        'Der H2-G2-Abstand sinkt ohne die acht Factbook-Quellen jedoch auf 3,99 PP; in N14 beträgt er dann '
        '7,10 PP auf neun verbleibenden Quellen. Diese Schwankung und die nicht zufällige N14-Abdeckung '
        'begrenzen Aussagen über andere Quellenfamilien. Die übrigen Komponenten werden vollständig berichtet, '
        'auch bei negativen Kontrasten oder Richtungswechseln.',
        '', '## Konstruktionen getrennt',
        '', 'Durchlauf 1 und 2 umfassen je 24 Quellen. Durchlauf 3 umfasst die 20 neuen Quellen. '
        'N14 verwendet die ursprüngliche kontrastspezifische Quellenmenge auch in der Durchlaufzerlegung. '
        'Ein in diesem Durchlauf fehlendes Urteil bleibt nach G2 fehlend. Die Hauptwerte behalten sämtliche '
        '68 geplanten Einheiten und sind keine einfache Mittelung der drei Durchlaufkontraste.',
        '', '| Maß, V2−AS | Durchlauf 1 | Durchlauf 2 | Durchlauf 3 |',
        '|---|---:|---:|---:|'])
    for e in ENDPOINTS:
        lines.append('| ' + ENAMES[e] + ' | ' + ' | '.join(
            f"{num(d['endpoints'][e][0]['full']['difference'])} (n={d['endpoints'][e][0]['source_count']})"
            for d in rob['by_draw']) + ' |')
    draw_rows = []
    for d in rob['by_draw']:
        for e in ENDPOINTS:
            for a in d['endpoints'][e]:
                draw_rows.append({'draw': d['draw'], 'endpoint': e, 'control': a['control'],
                    'treatment': a['treatment'], 'sources': a['source_count'],
                    **{k: a['full'][k] for k in ('control_mean', 'treatment_mean', 'difference')}})
    lines.extend(['', 'Alle vier Kontraste mit Zellmitteln und Quellenzahlen stehen in durchslaeufe.csv und result.json.',
        '', '## Relative Senkung des konservativ nicht vollständig gestützten Anteils',
        '', 'Berechnet wird 1 − (1 − H1_c)/(1 − H1_AS) aus den aggregierten H1-Werten, nicht aus dem Mittel '
        'einzelner Quellenquotienten. Es handelt sich um das Komplement des konservativen H1-Schätzers: '
        'Unklare und gezogene technisch fehlende Urteile zählen dazu. Die Kennzahl ist deshalb keine '
        'unabhängig bestätigte sachliche Fehlerquote.',
        '', '| Gegenüber AS | Nicht gestützt AS (%) | Nicht gestützt Variante (%) | Relative Senkung (%) | 95-%-KI (%) |',
        '|---|---:|---:|---:|---|'])
    for a in r['relative_non_supported_reductions']:
        lines.append('| ' + LABELS[a['treatment']] + ' | ' +
            ' | '.join(num(a[k]) for k in ('control_non_supported_share',
                'treatment_non_supported_share', 'relative_reduction')) +
            ' | [' + num(a['ci95']['lower']) + '; ' + num(a['ci95']['upper']) + '] |')
    lines.extend(['', 'Die Intervalle transformieren dieselben 10.000 gepaarten zweistufigen N10-Replikate '
        '(Seed 2026102407; lineare 2,5-/97,5-%-Quantile). Alle Verhältnisse sind endlich; kein Replikat wurde '
        'entfernt. Die Intervalle sind marginal, nicht Holm-korrigiert. Die näherungsweise N10-Inklusion und '
        'mögliche kostenabhängige Auswahl bleiben bestehen.',
        '', '## Lieferung und Nachrechnung',
        '', '- anhang-tabelle.tex: eine kompakte Tabelle mit Typzerlegung, Weglassspannen, Durchläufen und relativer Senkung.',
        '- kapitel6-zwei-saetze.tex: genau zwei Sätze zur getrennten Integration durch den Manuskript-Owner.',
        '- result.json, weg lassungen.csv und durchslaeufe.csv: vollständige ausgewählte Aggregate.',
        '- PROTOKOLL.md: Definitionen und nachträgliche Auswahlgrenzen.',
        '- USAGE.md: Reproduktion, Eingangsbindungen und private Dateien.',
        '', 'Der gebundene D1-Hauptkontrast und sein H1-Intervall wurden reproduziert. Alle 24 strikten '
        'Typ-Zellwerte einschließlich der undefinierten VV-Werte stimmen mit D1 überein. '
        'Die primären H2-G2-/N14-Punkte stimmen ebenfalls überein. Es wurden keine neuen p-Werte berechnet. '
        'Semantische Wahrheit, Bewertungsunabhängigkeit, Kostenüberlegenheit und QA-Gewinn werden dadurch nicht neu nachgewiesen.',
        ''])
    (ROOT/'BERICHT.md').write_text('\n'.join(lines).replace('durchslaeufe', 'durchlaeufe')
                                .replace('weg lassungen', 'weglassungen'), encoding='utf-8')
    for filename, rows in [('weglassungen.csv', omission_rows), ('durchlaeufe.csv', draw_rows)]:
        with (ROOT/filename).open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == '__main__':
    render()
