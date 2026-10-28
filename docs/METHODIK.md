# Wie wurde verglichen?

[Einstieg](../README.md) · [Ergebnisse](ERGEBNISSE.md) · [Reproduktion](REPRODUKTION.md) · [Kennungen](KENNUNGEN.md)

## Bedingungen und Begriffe

| Anzeigename | Technische Kennung | Rolle |
| --- | --- | --- |
| AutoSchemaKG | AS | Referenzverfahren |
| AutoSchemaKG mit Prüffilter | AS+G | Kontrolle der Filterwirkung auf dem Referenzverfahren |
| Eigener Ansatz | V1 | Eigene Konstruktion vor dem Prüffilter |
| Eigener Ansatz mit Prüffilter | V2 | Eigene Konstruktion einschließlich Prüffilter |

Quellenstützung, ausgewählter Bedeutungserhalt, Schemabeschreibung und Antwortqualität
werden als getrennte Endpunkte ausgewertet. Ihre Populationen, Regeln und Kontraste stehen
in der Vorregistrierung und im öffentlichen Auswertungsvertrag.

## Festlegungen und Zeitfolge

| Gegenstand | Zugang |
| --- | --- |
| Eingefrorene Vorregistrierung | [Lesefassung](../material/Experiments/fair_v2_oct24/A7/preregistration_v2_frozen.md), [JSON](../material/Experiments/fair_v2_oct24/A7/preregistration_v2_frozen.json) |
| Freigaben und Nachträge | [Dokumentenbestand](../material/Experiments/fair_v2_oct24/G1/) |
| Populationen, Seeds und Auswertungsregeln | [Öffentlicher Auswertungsvertrag](../material/protocols/analysis_contract.public.json) |
| Zeitpunkt relativ zu Ergebnissen und Vorläufen | [Chronologie mit Original-Commits](../material/docs/CHRONOLOGIE.md) |
| Herkunft bereinigter öffentlicher Fassungen | [Dokumentierte Ableitungen](../material/TRANSFORMATIONS.json) |

Die Nachträge legen ihre jeweilige Datensicht offen. Insbesondere wurden Teile der menschlichen
Gegenprüfung und spätere ergänzende Analysen nach Kenntnis von Vorlaufwerten festgelegt.

## Code nach Aufgabe

| Aufgabe | Quellcode |
| --- | --- |
| Graphkonstruktion und Extraktionsergänzung | [Konstruktionsprogramme](../material/Experiments/fair_comparison_oct23_v1/) |
| Quellengebundene Prüfung vollständiger Aussagen | [Prüffilter](../material/Tools/experiments/whole_relation_guard_oct24_v1/) |
| Statistische Auswertung, Komponenten und Sensitivitäten | [Auswertungscode](../material/Experiments/fair_v2_oct24/D1/) |
| Bindung an den öffentlichen Vertrag und künstliche Eingaben | [CPU-Demo](../material/Tools/release/submission_cpu.py) |

Die [Reproduktionsanleitung](REPRODUKTION.md) nennt den unterstützten öffentlichen Einstieg
und trennt ihn von Programmen, deren natürliche Eingaben privat aufbewahrt werden.

## Historische Kennungen und Pfade

Das [Kennungsverzeichnis](KENNUNGEN.md) nennt die verständlichen Namen der Programme,
Analysen und Nachträge. In eingefrorenen Belegen bleiben ihre technischen Kennungen erhalten.
Ein ursprünglicher relativer Pfad wird im heutigen Repository durch `material/` ergänzt.
Die dateigenaue Zuordnung mit Herkunftsbindung steht im [Umzugsnachweis](STRUKTUR.json).
