# Elektronische Begleitmaterialien zur Masterarbeit

„Agentische Knowledge Graph Construction aus semi- und unstrukturierten Daten“
Vladislav Antonov, Masterstudiengang Informatik, Fakultät Informatik und Medien, HTWK Leipzig.
Abgabe: 27. Oktober 2026.

Dieses Repository enthält Code, Vorregistrierung, alle Nachträge und die aggregierten Ergebnisse des
vorregistrierten Vergleichs mit AutoSchemaKG. Die [Chronologie](docs/CHRONOLOGIE.md) dokumentiert
Vorregistrierung, Nachträge und Ergebnisstände.

## Ergebnis in Kürze

Methodisches Gesamturteil **Stufe B** nach Nachtrag 8. Gegenüber AutoSchemaKG, mit demselben Konstruktormodell:

| Endpunkt | V2 minus AutoSchemaKG | 95-%-Intervall | Vorregistriertes Kriterium |
| --- | ---: | --- | --- |
| H1 Quellenstützung | +8,37 Prozentpunkte | [5,48; 11,14] | Überlegenheit bestätigt |
| H2 ausgewählter Bedeutungserhalt | +9,69 Prozentpunkte | [4,23; 15,80] | Nichtunterlegenheit bestätigt |
| H4 MuSiQue-Antwort-F1 | −1,44 Prozentpunkte | [−8,29; 3,91] | nicht bestätigt |

Alle sechs Komponentenkontraste K1–K6 sind bestätigt. Der Prüffilter senkt den Erhalt gegenüber V1 leicht (K4).
Menschliche Gegenprüfungen des Hauptbewerters ergeben κ 0,72 für H1 und κ 0,73 für H2. Einzelheiten und Grenzen
stehen im [D1-Endbericht](Experiments/fair_v2_oct24/D1/final_native_oct26_v1/BERICHT.md).

## Einstieg

| Pfad | Inhalt |
| --- | --- |
| [docs/CHRONOLOGIE.md](docs/CHRONOLOGIE.md) | Zeitfolge von Vorregistrierung, Nachträgen und Ergebnissen mit Original-Commits |
| `Experiments/fair_v2_oct24/A7/` | Eingefrorene Vorregistrierung als Lesefassung |
| `Experiments/fair_v2_oct24/G1/` | Freigaben und Nachträge N2–N17 |
| `protocols/analysis_contract.public.json` | Exportierter Auswertungsvertrag mit Populationen, Seeds und Nachtragsbindungen |
| `Experiments/fair_v2_oct24/D1/` | Statistikcode und synthetische Tests, finale Auswertung in `final_native_oct26_v1/` |
| `Experiments/fair_v2_oct24/C1/`, `C6/`, `C7/`, `H12/` | Abschlüsse von Prüffilter und QA, Autorenprüfungen |
| `Experiments/fair_v2_oct24/E1/`, `T1/`, `X1/`, `K2/`, `X2/` | Reader-Robustheit, Transfer, Strukturdiagnostik, Aufwand, Schemabeschreibung |
| `EF1/`, `RB1/`, `X3/`, `QA1/` | Nachträgliche Analysen nach Nachtrag 17 und H4-Diagnose |
| `S13/`, `H15/`, `H16/` | Weitere Autorenprüfungen, nur Aggregate |
| `Experiments/fair_comparison_oct23_v1/`, `Tools/experiments/` | Konstruktions- und Prüffiltercode |
| `docs/nachweisindex-*.json` | Nachweisindizes, ein Verweis bedeutet nicht, dass das Original beiliegt |

## CPU-Nachvollzug ohne Modellaufrufe

Vorausgesetzt werden Python 3.13, NumPy 2.4.4, SciPy 1.17.1 und Matplotlib 3.10.8
(`Tools/release/submission_requirements.txt`). Keine GPU, keine Modell-API.

```powershell
python -B -X utf8 Tools/release/submission_cpu.py --output SYNTHETIC_DEMO_NEU
```

Der Adapter führt den D1-Auswertungscode auf **synthetischen Daten** mit dem öffentlichen Vertrag aus. Er belegt den
Rechenweg, keinen empirischen Befund. Die empirischen Zahlen stehen in den Ergebnisberichten. Ihre Neuberechnung
benötigt die nicht veröffentlichten Einzelurteile.

## Forschungsdaten

Die Ergebnisberichte enthalten aggregierte Werte. Die zugrunde liegenden Einzelurteile,
Quelltexte, Graphen, Referenzantworten und Modellantworten werden beim Autor aufbewahrt
und können für einen empirischen Nachvollzug angefragt werden.

## Rechte

Es wird keine neue pauschale Lizenz erteilt. Herkunft, Fremdlizenzen und Grenzen stehen in
`Tools/release/SUBMISSION_RECHTE.md`, die Lizenz des AutoSchemaKG-Referenzcodes in `licenses/`.
