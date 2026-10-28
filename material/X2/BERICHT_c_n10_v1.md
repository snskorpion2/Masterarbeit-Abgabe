# X2c: beschreibende Schemaverankerung unter N10

Der C2-Endexport ist abgeschlossen, aber nicht alle ursprünglichen Aussagen sind bewertet. Nicht gezogene Träger und technische Fehlversuche bleiben getrennt. Sie bestätigen keine Zuordnung.

Die Auswertung umfasst unverändert 24 Quellen, 68 Quelle-Durchlauf-Paare und
272 semantische Zellen. Der ursprüngliche Definitionscommit und der gesonderte
N10-Anschluss wurden vor dieser Ergebnissicht veröffentlicht. Die vorhandene
einmalige C2-Endprüfung ist bestanden. Diese Auswertung startet keinen neuen
Prüfer und keine Modellanfrage.

Die eingefrorene All-Träger-Regel und sämtliche Zuordnungsnenner bleiben unverändert. Es erfolgt keine Hochrechnung der Konjunktionen. Die Intervalle beschreiben die beobachtbar verifizierte Verankerung, nicht die wahre Typkorrektheit des Schemas.

| Elementart | Arm | Verifiziert verankert (Anteil 0–1) | Beschreibendes 95-%-Quellenclusterintervall |
|---|---|---:|---|
| all | AS | 0.5731 | [0.5526, 0.5927] |
| all | AS+G | 0.6131 | [0.5946, 0.6310] |
| all | V1 | 0.6107 | [0.5885, 0.6305] |
| all | V2 | 0.6323 | [0.6098, 0.6522] |
| node | AS | 0.5249 | [0.4990, 0.5497] |
| node | AS+G | 0.5734 | [0.5494, 0.5962] |
| node | V1 | 0.5670 | [0.5445, 0.5885] |
| node | V2 | 0.5920 | [0.5695, 0.6130] |
| relation | AS | 0.6246 | [0.6082, 0.6410] |
| relation | AS+G | 0.6552 | [0.6399, 0.6706] |
| relation | V1 | 0.6547 | [0.6309, 0.6756] |
| relation | V2 | 0.6732 | [0.6489, 0.6942] |

Quellenmittel nach geplanten Durchlaufmitteln. 10.000 Quellenclusterziehungen, PCG64, Seed 2026102407. Keine p-Werte, keine Holm-Korrektur und kein Überlegenheitstest. Alle Zuordnungszähler und die getrennte Trägerabdeckung stehen in result_c_n10_v1.json.

## Beurteilungsabdeckung und Aussagegrenze

Von den 8.682 ursprünglichen Aussagen gehören 6.396 zum gezogenen Präfix.
Darunter haben 6.210 ein gültiges C2-Urteil und 186 einen ausgewählten
Fehlwert einschließlich administrativer Ausschlüsse. Weitere 2.286 Aussagen
wurden nicht gezogen. Das sind Aussagenzahlen, keine Konzeptzuordnungen oder
zusätzlichen unabhängigen Quellen. Ein nicht verifizierter Träger macht die
Zuordnung nicht nachgewiesen falsch. In den gefilterten Zellen werden nur
die bereits vorhandenen Urteile der verbliebenen Teilmenge verwendet.

Die höheren verifizierten Anteile nach dem Prüffilter sind eine beschreibende
Beobachtung unter dieser Trägerabdeckung. Das Entfernen von Aussagen kann die
Quote bereits durch Selektion erhöhen. Verschiedene Trägermengen und die
All-Träger-Regel beeinflussen sie zusätzlich. Daraus folgt weder ein
Überlegenheitsnachweis noch die richtige Typisierung einzelner Konzepte.

Die Grundtabelle stammt unverändert aus dem vorab veröffentlichten Skript.
Die Erläuterungen zu Abdeckung und Grenzen wurden danach redaktionell ergänzt.
