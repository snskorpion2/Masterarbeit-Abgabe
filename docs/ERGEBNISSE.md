# Welche Ergebnisse liegen vor?

[Einstieg](../README.md) · [Methodik](METHODIK.md) · [Reproduktion](REPRODUKTION.md) · [Kennungen](KENNUNGEN.md)

## Vorregistrierter Vergleich

Die Tabelle vergleicht den **eigenen Ansatz mit Prüffilter** (technische Kennung V2)
mit AutoSchemaKG bei demselben Konstruktormodell. Differenzen sind in Prozentpunkten angegeben.

| Fragestellung | Endpunkt | Differenz | 95-%-Intervall | Vorregistriertes Urteil |
| --- | --- | ---: | --- | --- |
| Sind die Aussagen besser durch ihre Quellen gestützt? | H1: Quellenstützung | +8,37 | [5,48; 11,14] | Überlegenheit bestätigt |
| Bleiben ausgewählte Bedeutungen erhalten? | H2: ausgewählter Bedeutungserhalt | +9,69 | [4,23; 15,80] | Nichtunterlegenheit bestätigt |
| Verbessern sich Antworten aus dem Graphkontext? | H4: MuSiQue-Antwort-F1 | −1,44 | [−8,29; 3,91] | Kriterium nicht bestätigt |

Das methodische Gesamturteil lautet **Stufe B** nach dem Nachtrag zum Gesamt- und Komponentenurteil.
Die sechs Komponentenkontraste K1–K6 sind bestätigt. Der Prüffilter senkt den Bedeutungserhalt
gegenüber dem eigenen Ansatz ohne Prüffilter leicht. Bei den menschlichen Gegenprüfungen
des Hauptbewerters beträgt Cohen-κ für H1 0,72 und für H2 0,73.

Der [Endbericht](../material/Experiments/fair_v2_oct24/D1/final_native_oct26_v1/BERICHT.md)
enthält Definitionen, Nenner, Fehlwerte, Sensitivitäten und Komponentenbefunde.
Die [maschinelle Ergebnisausgabe](../material/Experiments/fair_v2_oct24/D1/final_native_oct26_v1/result.json)
und die [Tabellen und Abbildungen](../material/Experiments/fair_v2_oct24/D1/final_native_oct26_v1/)
liegen daneben.

## Ergänzende Fragen

Die folgenden Analysen haben eigene Populationen und Festlegungszeitpunkte.
Ihr Status und ihre Bedingungen stehen jeweils im verlinkten Bericht und in der [Chronologie](../material/docs/CHRONOLOGIE.md).

| Frage | Bericht oder Ergebnis |
| --- | --- |
| Wie verteilen sich Qualität und tatsächlicher Aufwand? | [Aufwand und Qualität](../material/EF1/BERICHT.md) |
| Wie robust sind die Schlussfolgerungen? | [Robustheitsanalyse](../material/RB1/) |
| Was verändert die Filterprojektion bei Ereignisbeziehungen? | [Ereignisbeziehungen](../material/X3/tabelle.md) und [Protokoll](../material/X3/PROTOKOLL.md) |
| Wo fehlen Antwortbelege im abgerufenen Graphkontext? | [Diagnose des QA-Kontexts](../material/QA1/) |
| Wie wirkt ein anderes Lesermodell? | [Reader-Robustheit](../material/Experiments/fair_v2_oct24/E1/BERICHT.md) |
| Übertragen sich die Befunde auf ein zweites Konstruktormodell? | [Modelltransfer](../material/Experiments/fair_v2_oct24/T1/) |
| Welche Struktureffekte zeigen die Graphansichten? | [Strukturdiagnostik](../material/Experiments/fair_v2_oct24/X1/) |
| Welche Unterschiede zeigen die Schemaausgaben? | [Beschreibende Schemaverankerung](../material/X2/BERICHT_c_n10_v1.md) |
| Welche Aufwandsmessungen liegen vor? | [Aufwandsdokumentation](../material/Experiments/fair_v2_oct24/K2/README.md) |
| Wie wurden automatische Urteile menschlich geprüft? | [Quellenstützung](../material/Experiments/fair_v2_oct24/C7/BERICHT.md), [Bedeutungserhalt](../material/H15/), [Modelltransfer](../material/H16/) |

## Ergebnisse lesen und nachrechnen

Die Berichte enthalten aggregierte empirische Ergebnisse. Der öffentliche CPU-Einstieg führt
denselben Auswertungsweg mit synthetischen Eingaben aus. Eine erneute Berechnung der empirischen
Zahlen benötigt die privat aufbewahrten Einzelurteile.

Die [Nachweisindizes](../material/docs/) erschließen weitere Originalbelege.
Ob eine genannte Datei öffentlich beiliegt, zeigt der aktuelle Lieferbaum mit seinem [Manifest](../MANIFEST.json).
