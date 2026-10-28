# D1: finale vorregistrierte Auswertung

Der native D1-Runner hat den gebundenen Endstand von C1/C2/C3/C5/C6 und die aktuellen C7-Autorenpaare verarbeitet.
600/600 C6-Antworten sind gültig. Die ursprünglichen Eingänge und die vollständige Auswertung bleiben unverändert privat erhalten.

**Methodisches Gesamturteil nach N8: Stufe B, keine Notenstufe.** V2 erhöht die Quellenstützung bei nicht unterlegenem ausgewähltem Bedeutungserhalt.
**Ein QA-Vorteil ist nicht nachgewiesen.** Keine allgemeine Überlegenheit über sämtliche KGC-Verfahren, Quellen oder Modelle.

## Primärkontrast V2_ROW minus AS_ORIGINAL

| Endpunkt | Differenz (Prozentpunkte) | Marginales 95-%-KI | p Holm | Vorregistriertes Kriterium |
| --- | ---: | --- | ---: | --- |
| H1 | 8,37 | [5,48; 11,14] | 0,00029997 | Höhere Quellenstützung: bestätigt |
| H2 | 9,69 | [4,23; 15,80] | 0,00029997 | Nichtunterlegenheit am Rand −5 Prozentpunkte: bestätigt |
| H4 | -1,44 | [-8,29; 3,91] | 0,693431 | Höherer MuSiQue-Antwort-F1: nicht bestätigt |

H2 bezeichnet ausgewählte Referenzbedeutungen, keinen Quellenrecall. Das bestandene Primärkriterium ist Nichtunterlegenheit, kein Gleichheits- oder allgemeiner Überlegenheitsnachweis.
H4 hat einen negativen Punktschätzer, sein Intervall umfasst jedoch null. Weder Gleichwertigkeit noch ein gesicherter QA-Schaden wird daraus abgeleitet.

## Getrennte H2-Analysen nach N14

| Analyse | Quellen | Differenz (Prozentpunkte) | Marginales 95-%-KI | p Holm | Nichtunterlegenheit |
| --- | ---: | ---: | --- | ---: | --- |
| G2 | 24 | 9,69 | [4,23; 15,80] | 0,00029997 | bestätigt |
| N14 | 17 | 13,67 | [6,47; 20,94] | 0,00029997 | bestätigt |

Beide nach N14 erforderlichen Analysen bestehen. Die 17 Quellen der Zusatzanalyse sind keine nachgewiesene Zufallsstichprobe aller 24 Quellen.

## Quellenzahlen und VV, ausschließlich beschreibend

| Endpunkt/Umfang | V2 höher | Gleich | V2 niedriger | Vergleichbare Quellen |
| --- | ---: | ---: | ---: | ---: |
| H1 | 21 | 0 | 3 | 24/24 |
| H2 | 14 | 8 | 2 | 24/24 |
| H2_N14_eligible | 14 | 1 | 2 | 17/17 |

Die acht H2-Gleichstände der G2-Analyse schließen sieben Quellen ohne gültige C3-Urteile ein. Deren konservative Nullwerte sind keine beobachtete positive Qualitätsbestätigung.

| H1-VV | Mittel über schätzbare Quellen (%) | Schätzbares n / geplantes N |
| --- | ---: | ---: |
| V1_ROW | 59,89 | 23/24 |
| V2_ROW | 72,73 | 23/24 |

Diese VV-Mittel ergänzen die Primäraggregation rein beschreibend. Zusätzliche Tests oder Intervalle werden nicht ausgewiesen.

## Sensitivitäten, Schranken und Einschränkungen

- N10-G2-Aggregation erst Durchläufe, dann Quellen: H1-Kontrast 8,18 Prozentpunkte. Gepaarte N10-Hauptanalyse und diese Aggregationssensitivität bleiben getrennt.
- Wilcoxon: H1 p=9,999e-05, H2 p=9,999e-05. Vorregistrierte Sensitivität, kein zusätzlicher Primärtest.
- Punkt-Identifikationsschranken, Bootstrap-Sensitivitätsgrenzen und marginale Konfidenzintervalle werden getrennt in [requested_outputs.md](requested_outputs/requested_outputs.md) ausgewiesen. Insbesondere sind die G2-H2-Schranken wegen fehlender Urteile breit.
- N8 verwendet ausschließlich das gebundene binäre Autoren-κ aus C7: 0,72327 auf 110 gültigen Paaren. Der Rand 0,40 wird nicht unterschritten. Dreiklassiges κ bleibt beschreibend. Kein Modell-Zweitbewerter wurde ergänzt; fehlendes C4 ist keine Bestätigung der Bewerterunabhängigkeit.
- K2 ist wegen historischem Teilstand und bekannter Quittungsidentitätskollision nicht im Primärlauf. Effizienz und Kostenüberlegenheit bleiben nicht berechenbar, keinesfalls null.
- N10 beruht auf einem kostenbegrenzt gezogenen Präfix mit nur näherungsweise gleicher Inklusion. C3-Fehlwerte behalten feste Nenner und symmetrische G2-Behandlung.
- H12/S13 sowie spätere N15/N16/X3-Begleitprüfungen erweitern die eingefrorene Primär- oder Komponentenfamilie nicht.

## Elektronische Belege

[analysis.public.json](analysis.public.json) enthält ausschließlich ausgewählte Aggregate. Rohdiagnostik, Einzelurteile, Quellen- und Antworttexte bleiben außerhalb dieser Lieferung.
Die erzeugten LaTeX-Tabellen und fünf PDF-Diagramme sind numerische Begleitmaterialien.
Der Ergebnisbeleg bindet die vollständige private Originalrechnung und die öffentlichen Lieferbytes getrennt. Kein Modellaufruf und keine neue Annotation.
