"""Render only QA1's public aggregate result into the requested manuscript handoff."""
from pathlib import Path
from hashlib import sha256
import json

HERE = Path(__file__).resolve().parent


def pct(value):
    return f'{100 * value:.2f}'.replace('.', ',')


def nr_rate(value):
    if value['not_measurable']:
        return f"{value['hits']}/{value['questions']} (unb. {value['not_measurable']})"
    return f"{value['hits']}/{value['questions']} ({pct(value['rate'])}\\,\\%)"


def main():
    raw = (HERE / 'result.json').read_bytes()
    result = json.loads(raw)
    m = result['metrics']
    cells = result['primary_table_cells']
    coverage, removals = m['context_coverage'], m['guard_removals']
    h4 = m['H4_interval_precision']
    if any(v[name]['not_measurable'] for v in coverage.values() for name in [
            'gold_or_alias_in_actual_context', 'gold_or_alias_within_one_statement',
            'gold_or_alias_in_support_paragraph_statement']):
        raise ValueError('Manuscript wording requires complete measurable coverage')
    if any(v['gold_or_alias_in_actual_context']['hits'] != v['gold_or_alias_within_one_statement']['hits'] for v in coverage.values()):
        raise ValueError('Report must distinguish observed cross-statement-only hits')
    supported_count = coverage['AS_ORIGINAL']['gold_or_alias_in_support_paragraph_statement']['hits']
    if supported_count != coverage['V2_ROW']['gold_or_alias_in_support_paragraph_statement']['hits']:
        raise ValueError('Shared-support wording is not applicable')
    if m['raw_supporting_paragraph_answer_coverage_control']['hits'] != 60:
        raise ValueError('Gold-support control wording requires actual full coverage')
    sentence = (
        r'Die nachträgliche lexikalische Diagnose findet die Goldantwort oder einen vorhandenen Alias bei AS in '
        + f"{coverage['AS_ORIGINAL']['gold_or_alias_in_actual_context']['hits']}/60 und bei V2 in {coverage['V2_ROW']['gold_or_alias_in_actual_context']['hits']}/60 Top-30-Graphkontexten, "
        + f'wobei jeweils {supported_count}/60 Fragen einen solchen Treffer innerhalb einer Aussage aus einem zugehörigen Stützabsatz aufweisen '
        + r'(Tabelle~\ref{tab:qa1-h4-diagnose}).' + '\n'
        + r'Bei 60 Fragen in 39 Absatzblöcken beträgt die halbe Breite des marginalen H4-95-\%-Intervalls '
        + f"\\({h4['half_width_percentage_points']:.2f}\\)".replace('.', '{,}')
        + r' Prozentpunkte, und die nachträgliche Diagnose trennt Konstruktions-, Such- und Antwortmodellfehler nicht kausal.' + '\n'
    )
    table = [
        r'% QA1: generated solely from public aggregates; no case IDs or answers.',
        r'\begin{table}[htbp]', r'\centering',
        r'\caption{Nachträgliche, beschreibende Diagnose der graphbasierten Antwortgüte auf 60 festen MuSiQue-Fragen.}',
        r'\label{tab:qa1-h4-diagnose}',
        r'\begin{tabularx}{\textwidth}{@{}Xrrrr@{}}', r'\toprule',
        r'Lexikalische Abdeckung & AS orig. & AS+G orig. & V1 zeileng. & V2 zeileng. \\', r'\midrule',
    ]
    for label, metric in [
        ('Gold/Alias im Top-30-Kontext', 'gold_or_alias_in_actual_context'),
        ('Innerhalb einer Aussage aus einem Stützabsatz', 'gold_or_alias_in_support_paragraph_statement')]:
        table.append(label + ' & ' + ' & '.join(nr_rate(coverage[cell][metric]) for cell in cells) + r' \\')
    table += [r'\midrule',
        r'Explizite Guard-Entfernungen & Fragen/60 & Paare & Versch. Vork. & \\',
        r'\multicolumn{5}{@{}l@{}}{Gold-/Aliastreffer innerhalb nativer Aussagen aus zugehörigen Stützabsätzen:} \\']
    for arm, label in [('AS', r'AS $\rightarrow$ AS+G'), ('V1', r'V1 $\rightarrow$ V2')]:
        row = removals[arm]
        table.append(label + ' & ' + f"{row['questions_with_support_answer_bearing_removal']['hits']}/60 & {row['support_answer_bearing_removed_statement_question_pairs']} & {row['unique_support_answer_bearing_removed_occurrences']} & " + r' \\')
    table += [r'\midrule',
        r'EM-Paare & Beide richtig & Nur V2 & Nur Vergleich & Beide falsch \\']
    for key, label in [('V2_ROW_minus_AS_ORIGINAL', 'V2 gegen AS'), ('V2_ROW_minus_V1_ROW', 'V2 gegen V1')]:
        row = m['EM_discordance'][key]
        table.append(label + ' & ' + ' & '.join(str(row[k]) for k in ['both_correct', 'treatment_only', 'control_only', 'both_incorrect']) + r' \\')
    table += [r'\midrule',
        r'\multicolumn{5}{@{}l@{}}{H4: V2 zeilengenau minus AS original, Antwort-Token-\(F_1\)} \\',
        r'\multicolumn{5}{@{}l@{}}{Differenz $-1{,}44$ Prozentpunkte; marginales 95-\%-KI $[-8{,}29;3{,}91]$} \\',
        r'\multicolumn{5}{@{}l@{}}{Halbe Intervallbreite: $6{,}10$ Prozentpunkte; 60 Fragen, 39 Absatzblöcke} \\',
        r'\bottomrule', r'\end{tabularx}',
        r'\par\smallskip', r'\begin{minipage}{\textwidth}',
        r'\textit{Einordnung:} Ganze Tokenfolgen nach offizieller MuSiQue-Normalisierung, ohne Fragetext und ohne neue Aliasse. '
        r'Die Rohstützabsätze enthalten für alle 60 Fragen einen lexikalischen Treffer. '
        r'Eine Absatzzuordnung oder ein Treffer beweist keine vollständige Mehrschrittbegründung. '
        r'Bei identischen sichtbaren Aussagen genügt mindestens eine passende native Herkunft. '
        r'Paare zählen Aussage--Frage-Kombinationen, verschiedene Vorkommen die ursprünglichen nativen Identitäten. '
        r'Die Löschzahlen beziehen sich auf den gesamten nativen Bestand, nicht nur auf ausgewählte Top-30-Aussagen. '
        r'Sie zeigen keinen kausalen Antwortverlust. '
        r'Die halbe Breite ist $(U-L)/2$ des vorhandenen asymmetrischen, marginalen Perzentilintervalls. '
        r'Keine neue Bootstraprechnung, Power, minimale erkennbare Wirkung oder zusätzliche Hypothesenprüfung.',
        r'\end{minipage}', r'\end{table}', ''
    ]
    report = f'''# QA1: nachträgliche H4-Diagnose

Reine CPU-Auswertung des gebundenen C6-Endstands und der bereits versiegelten
Goldantworten auf 60 festen Fragen. Kein neuer Modellaufruf, keine neue
H4-/Holm-Rechnung oder C6-Endprüfung. Die methodische Gesamtstufe bleibt B.

| Diagnose | AS original | AS+G original | V1 zeilengenau | V2 zeilengenau |
| --- | ---: | ---: | ---: | ---: |
'''
    for label, metric in [('Gold/Alias im Top-30-Kontext', 'gold_or_alias_in_actual_context'),
                          ('Aussage aus zugehörigem Stützabsatz mit Gold/Alias', 'gold_or_alias_in_support_paragraph_statement')]:
        report += '| ' + label + ' | ' + ' | '.join(f"{coverage[cell][metric]['hits']}/60 ({pct(coverage[cell][metric]['rate'])} %)" for cell in cells) + ' |\n'
    report += '''
Die Rohstützabsätze enthalten auf 60/60 Fragen einen Gold-/Aliastreffer.
Zwischen Aussagegrenzen entstehen im tatsächlich beobachteten Bestand keine
zusätzlichen Treffer. Sämtliche lexikalischen Diagnosen sind messbar, es gibt
keine Frage ohne nichtleer normalisierbaren Alias. Alle acht Exportzellen
stehen vollständig in `result.json`.

| Guard-Entfernungen mit lexikalischem Treffer aus dem zugehörigen Stützabsatz | Fragen | Aussage-Frage-Paare | Verschiedene native Vorkommen |
| --- | ---: | ---: | ---: |
'''
    for arm, label in [('AS', 'AS → AS+G'), ('V1', 'V1 → V2')]:
        row = removals[arm]
        report += f"| {label} | {row['questions_with_support_answer_bearing_removal']['hits']}/60 | {row['support_answer_bearing_removed_statement_question_pairs']} | {row['unique_support_answer_bearing_removed_occurrences']} |\n"
    report += '''
Die expliziten Entfernungen stammen aus dem vollständigen nativen Bestand.
Sie bedeuten weder, dass die Aussage zuvor im Top-30-Kontext stand, noch dass
die Antwort anschließend nicht mehr vorhanden war. Die breitere Zählung ohne
Stützabsatzbedingung ist ebenfalls in `result.json` enthalten. Wegen zufällig
gleichlautender Antworten in anderen Quellen ist sie weniger spezifisch.

| EM-Vergleich | Beide richtig | Nur V2 richtig | Nur Vergleich richtig | Beide falsch |
| --- | ---: | ---: | ---: | ---: |
'''
    for key, label in [('V2_ROW_minus_AS_ORIGINAL', 'V2 zeilengenau gegen AS original'), ('V2_ROW_minus_V1_ROW', 'V2 zeilengenau gegen V1 zeilengenau')]:
        row = m['EM_discordance'][key]
        report += f"| {label} | " + ' | '.join(str(row[k]) for k in ['both_correct', 'treatment_only', 'control_only', 'both_incorrect']) + ' |\n'
    report += f'''
Der offizielle Antwort-F1-Kontrast von H4 bleibt −1,4412 Prozentpunkte mit
marginalem 95-%-Intervall [−8,2856; +3,9108]. Die halbe Breite beträgt
**{h4['half_width_percentage_points']:.10f} Prozentpunkte**. Sie ist nicht
symmetrisch um den Punktschätzer und keine Power- oder MDE-Schätzung.
Die vorhandene Auswertung verwendet 10.000 gepaarte Absatzblock-Bootstraps
bei 60 Fragen aus 39 überlappungsgebundenen Blöcken. Es gibt keinen neuen Test.

Die Diagnose zeigt begrenzte wörtliche Antwortabdeckung in den abgerufenen
Graphkontexten und einen kleinen Austausch einzelner EM-Treffer. Sie trennt
Konstruktions-, Such-, Mehrschrittbegründungs- und Readerfehler nicht kausal.
Lexikalische Verfügbarkeit ist kein semantischer Quellenrecall und keine
nachgewiesene tatsächliche Nutzung durch das Antwortmodell.

`METHODIK.md` bindet die operationalen Definitionen als nachträgliche Analyse.
`chapter6-snippet.tex` enthält genau zwei Ergebnissätze,
`appendix-table.tex` genau eine Anhangtabelle. Beide sind eine Übergabe an den
zuständigen D2-Agenten. Keine parallele Änderung des Thesis-Projekts oder
zusätzlicher Gesamtbau durch QA1. Fragekennungen, Antworten, Aliasse,
Einzelzuordnungen und vollständige Quellpins bleiben privat außerhalb von Git.
'''
    outputs = {'chapter6-snippet.tex': sentence,
               'appendix-table.tex': '\n'.join(table), 'BERICHT.md': report}
    for name, text in outputs.items():
        path = HERE / name
        if path.exists() and path.read_text(encoding='utf-8') != text:
            raise ValueError('Refusing to overwrite a different manuscript handoff')
        path.write_text(text, encoding='utf-8', newline='\n')
    (HERE / 'render-receipt.json').write_text(json.dumps({
        'input_result_sha256': sha256(raw).hexdigest(),
        'renderer_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'outputs': {name: {'bytes': (HERE / name).stat().st_size,
                           'sha256': sha256((HERE / name).read_bytes()).hexdigest()} for name in outputs},
        'exactly_two_chapter6_sentences': True, 'exactly_one_appendix_table': True,
        'thesis_sources_modified': False, 'new_full_builds': 0}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'rendered': list(outputs), 'natural_case_data_used': False}))


if __name__ == '__main__':
    main()
