# C3: technische Fehlwertmetadaten

Nur technische Statusauswertung nach der vorhandenen bestandenen einmaligen C3-Endprüfung. Keine neuen Modellaufrufe oder Audits. Gültig bedeutet auswertbar, nicht inhaltlich erhalten.

## Fester Endbestand

| Einheit | Geplant | Gültig | Fehlend | Nie gestartet (Budget) | Begonnen, nicht gültig |
|---|---:|---:|---:|---:|---:|
| Anfragegruppen | 414 | 322 | 92 | 87 | 5 |
| Urteilspositionen | 2336 | 1824 | 512 | 484 | 28 |

## Nach Arm: Urteilspositionen

| Arm | Geplant | Gültig | Fehlend | Nie gestartet (Budget) | Begonnen, nicht gültig |
|---|---:|---:|---:|---:|---:|---:|
| AS | 584 | 454 | 130 | 121 | 9 |
| AS+G | 584 | 459 | 125 | 121 | 4 |
| V1 | 584 | 458 | 126 | 121 | 5 |
| V2 | 584 | 453 | 131 | 121 | 10 |

## Unbekannte Abschlüsse

Unbekannter Abschluss (true): 5 Gruppen / 28 Urteilspositionen. Nicht spezifizierter Abschlussstatus (null): 0 Gruppen / 0 Positionen. Diese Zustände werden nicht in bekannte erfolglose Modellantworten oder null Kosten umgedeutet. Die gespeicherten Ausführungsstatus sind technische Kennungen, keine semantischen Fehlerdiagnosen.

## Je Quelle: fehlend / geplant

| Quelle | AS | AS+G | V1 | V2 | Nie gestartet, gesamt | Begonnen fehlend, gesamt |
|---|---:|---:|---:|---:|---:|---:|
| A4-F01 | 0/27 | 0/27 | 0/27 | 0/27 | 0 | 0 |
| A4-F02 | 2/33 | 0/33 | 2/33 | 2/33 | 0 | 6 |
| A4-F03 | 0/30 | 1/30 | 1/30 | 2/30 | 0 | 4 |
| A4-F04 | 0/30 | 0/30 | 0/30 | 0/30 | 0 | 0 |
| A4-F05 | 2/30 | 1/30 | 0/30 | 3/30 | 0 | 6 |
| A4-F06 | 0/30 | 0/30 | 0/30 | 0/30 | 0 | 0 |
| A4-F07 | 0/24 | 0/24 | 0/24 | 0/24 | 0 | 0 |
| A4-F08 | 0/24 | 0/24 | 0/24 | 0/24 | 0 | 0 |
| A4-W01 | 2/27 | 1/27 | 2/27 | 1/27 | 0 | 6 |
| A4-W02 | 0/27 | 0/27 | 0/27 | 0/27 | 0 | 0 |
| A4-W03 | 3/30 | 1/30 | 0/30 | 2/30 | 0 | 6 |
| A4-W04 | 0/27 | 0/27 | 0/27 | 0/27 | 0 | 0 |
| A4-W05 | 0/24 | 0/24 | 0/24 | 0/24 | 0 | 0 |
| A4-W06 | 0/24 | 0/24 | 0/24 | 0/24 | 0 | 0 |
| A4-W07 | 0/30 | 0/30 | 0/30 | 0/30 | 0 | 0 |
| A4-W08 | 0/30 | 0/30 | 0/30 | 0/30 | 0 | 0 |
| A4-W09 | 8/24 | 8/24 | 8/24 | 8/24 | 32 | 0 |
| A4-W10 | 27/27 | 27/27 | 27/27 | 27/27 | 108 | 0 |
| A4-W11 | 24/24 | 24/24 | 24/24 | 24/24 | 96 | 0 |
| A4-W12 | 30/30 | 30/30 | 30/30 | 30/30 | 120 | 0 |
| RGCONF01 | 8/8 | 8/8 | 8/8 | 8/8 | 32 | 0 |
| RGCONF02 | 8/8 | 8/8 | 8/8 | 8/8 | 32 | 0 |
| RGCONF03 | 8/8 | 8/8 | 8/8 | 8/8 | 32 | 0 |
| RGCONF04 | 8/8 | 8/8 | 8/8 | 8/8 | 32 | 0 |

Gruppenzähler nach Arm überlappen bei gemischten Anfragen und dürfen nicht addiert werden. Urteilspositionen gehören jeweils genau einem Arm und sind additiv. Wiederholte lokale batch_id werden ausschließlich zusammen mit dem Segment-SHA identifiziert.

Originale Ausführungsstatus, unbekannte Abschlüsse (true/null getrennt), die Aufschlüsselung nach Quelle, Durchlauf und Arm sowie die einzelnen fehlenden Fall-IDs stehen in result.json. Ein Budgetfehlwert bedeutet weder faktischen Nichterhalt noch eine semantisch unklare Antwort. Die vorregistrierten Nenner und H2-Regeln bleiben unverändert.

## Konzentration der Fehlwerte

17/24 Quellen und 50/68 geplante Quelle-Durchlauf-Paare haben mindestens ein gültiges Urteil. Quellen ohne gültiges Urteil: A4-W10, A4-W11, A4-W12, RGCONF01, RGCONF02, RGCONF03, RGCONF04.

Gepoolte Fehlwertquote: 21.92 %. Gleichgewichtetes Mittel der quellenweisen Fallfehlwertquoten: 31.53 %. Das sind verschiedene Gewichtungen derselben technischen Lücken, keine Qualitätswerte.

Die Budgetlücken liegen in der gespeicherten Ausführungsreihenfolge und werden nicht als zufällige Quellenstichprobe ausgegeben. Vollständig fehlende Quellen und Durchläufe bleiben im festen H2-Nenner. Der G2-Fehlwertvertrag und seine Schranken bleiben für D1 maßgeblich. Ein bestandener technischer Abschluss ersetzt weder diese Lücken noch eine vollständige Inhaltsmessung.
