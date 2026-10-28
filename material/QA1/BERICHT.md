# QA1: nachträgliche H4-Diagnose

Reine CPU-Auswertung des gebundenen C6-Endstands und der bereits versiegelten
Goldantworten auf 60 festen Fragen. Kein neuer Modellaufruf, keine neue
H4-/Holm-Rechnung oder C6-Endprüfung. Die methodische Gesamtstufe bleibt B.

| Diagnose | AS original | AS+G original | V1 zeilengenau | V2 zeilengenau |
| --- | ---: | ---: | ---: | ---: |
| Gold/Alias im Top-30-Kontext | 23/60 (38,33 %) | 23/60 (38,33 %) | 25/60 (41,67 %) | 25/60 (41,67 %) |
| Aussage aus zugehörigem Stützabsatz mit Gold/Alias | 20/60 (33,33 %) | 20/60 (33,33 %) | 21/60 (35,00 %) | 20/60 (33,33 %) |

Die Rohstützabsätze enthalten auf 60/60 Fragen einen Gold-/Aliastreffer.
Zwischen Aussagegrenzen entstehen im tatsächlich beobachteten Bestand keine
zusätzlichen Treffer. Sämtliche lexikalischen Diagnosen sind messbar, es gibt
keine Frage ohne nichtleer normalisierbaren Alias. Alle acht Exportzellen
stehen vollständig in `result.json`.

| Guard-Entfernungen mit lexikalischem Treffer aus dem zugehörigen Stützabsatz | Fragen | Aussage-Frage-Paare | Verschiedene native Vorkommen |
| --- | ---: | ---: | ---: |
| AS → AS+G | 22/60 | 44 | 37 |
| V1 → V2 | 17/60 | 20 | 19 |

Die expliziten Entfernungen stammen aus dem vollständigen nativen Bestand.
Sie bedeuten weder, dass die Aussage zuvor im Top-30-Kontext stand, noch dass
die Antwort anschließend nicht mehr vorhanden war. Die breitere Zählung ohne
Stützabsatzbedingung ist ebenfalls in `result.json` enthalten. Wegen zufällig
gleichlautender Antworten in anderen Quellen ist sie weniger spezifisch.

| EM-Vergleich | Beide richtig | Nur V2 richtig | Nur Vergleich richtig | Beide falsch |
| --- | ---: | ---: | ---: | ---: |
| V2 zeilengenau gegen AS original | 5 | 2 | 2 | 51 |
| V2 zeilengenau gegen V1 zeilengenau | 7 | 0 | 1 | 52 |

Der offizielle Antwort-F1-Kontrast von H4 bleibt −1,4412 Prozentpunkte mit
marginalem 95-%-Intervall [−8,2856; +3,9108]. Die halbe Breite beträgt
**6.0982162554 Prozentpunkte**. Sie ist nicht
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
`appendix-table.tex` genau eine Anhangtabelle. Die beiden LaTeX-Dateien wurden separat für die Einbindung ins Manuskript bereitgestellt. Fragekennungen, Antworten, Aliasse,
Einzelzuordnungen und vollständige Quellpins bleiben privat außerhalb von Git.
