# RB1 – Robustheit und Typzerlegung nach N17 §2

Reine CPU-Nachrechnung der final gebundenen D1-Eingänge. Keine Modellaufrufe, keine neue Annotation, keine Änderung an Primärtests, Holm oder N8-Gesamtstufe. N17 wurde nach Kenntnis des D1-Vorlaufs festgelegt. Die folgenden Zahlen sind nachträgliche beschreibende Sensitivitäten.

**Der typstandardisierte Vorsprung ist deutlich kleiner.** Auf den gemeinsam schätzbaren 23 Quellen sinkt V2−AS von 8,27 auf 5,41 Prozentpunkte mit AS-Typgewichten und auf 4,09 mit gepoolten Gewichten. Das sind keine standardisierten 24-Quellen-Ergebnisse: RGCONF04 enthält in V1 und V2 gar keine VV-Aussagen. Nach N17 bleiben deshalb die drei davon betroffenen Standardkontraste über alle 24 Quellen unbestimmt.

## Typstandardisierung und rechnerischer Mischungsrest

Ganze native Vorkommensbestände über alle 68 geplanten Quelle-Durchlauf-Einheiten bestimmen die Gewichte. Die Typgüten sind die gleichgewichteten D1-Quellenmittel. Original-/ROW-Exportansichten werden nicht doppelt gezählt. Die gemeinsamen Gewichte entstehen aus der Summe der beiden Bestände, nicht ihrer Schnittmenge. Der Rest ist die unstandardisierte minus standardisierte Differenz derselben Quellen. Er umfasst auch Unterschiede der Quellen-/Typaggregation und ist kein kausal erklärter Gewinnanteil.

| Vergleich | Quellen | Roh (PP) | AS-standardisiert | Pool-standardisiert | Rest AS (PP) | Rest Pool (PP) |
|---|---:|---:|---:|---:|---:|---:|
| V2−AS (N17) | 24 | 8,37 | u. | u. | u. | u. |
| V2−AS (Zusatzsensitivität) | 23 | 8,27 | 5,41 | 4,09 | 2,85 | 4,17 |
| V1−AS (N17) | 24 | 5,33 | u. | u. | u. | u. |
| V1−AS (Zusatzsensitivität) | 23 | 5,10 | 2,23 | 1,80 | 2,86 | 3,29 |
| AS+G−AS (N17) | 24 | 5,95 | 3,97 | 3,54 | 1,97 | 2,40 |
| V2−V1 (N17) | 24 | 3,04 | u. | u. | u. | u. |
| V2−V1 (Zusatzsensitivität) | 23 | 3,17 | 3,18 | 2,07 | -0,01 | 1,10 |

Vollständiger AS-Bestand: EE: 1533 (42,48 %), EV: 1372 (38,02 %), VV: 704 (19,51 %); insgesamt 3609 Vorkommen. In der 23er-Sensitivität werden sowohl Gewichte als auch Rohkontraste innerhalb genau dieser Quellen neu berechnet. Ihre Auswahl nach Typschätzbarkeit ist keine Zufallsstichprobe.

## Weglassen einzelner Quellen und Vertragsgruppen

Alle Angaben sind Prozentpunkte. Die Spannen sind keine Konfidenzintervalle. „sealed4“ bezeichnet die vier versiegelten Quellen als Vertragskohorte, keine gemeinsame Textgattung. N14 schließt Quellen nach technischer Urteilsverfügbarkeit kontrastspezifisch ein. Das Weglassen bereits ausgeschlossener Quellen ist kein weiterer Robustheitsfall.

| Maß / Kontrast | n | Voll | Quelle weg: Spanne | Einflussreichste Quelle | Gruppe weg: Spanne |
|---|---:|---:|---|---|---|
| H1 V2−AS | 24 | 8,37 | 7,98 bis 8,78 | A4-F05 (Änderung 0,41 PP) | 7,90 bis 8,84 |
| H1 V1−AS | 24 | 5,33 | 4,87 bis 5,79 | RGCONF03 (Änderung -0,46 PP) | 4,53 bis 6,68 |
| H1 AS+G−AS | 24 | 5,95 | 5,68 bis 6,21 | A4-W08 (Änderung -0,27 PP) | 4,55 bis 6,99 |
| H1 V2−V1 | 24 | 3,04 | 2,73 bis 3,17 | A4-W05 (Änderung -0,31 PP) | 2,16 bis 3,38 |
| H2 G2 V2−AS | 24 | 9,69 | 8,22 bis 10,69 | A4-F03 (Änderung -1,46 PP) | 3,99 bis 14,05 |
| H2 G2 V1−AS | 24 | 11,28 | 9,89 bis 12,06 | A4-F03 (Änderung -1,39 PP) | 5,58 bis 15,13 |
| H2 G2 AS+G−AS | 24 | 0,44 | 0,17 bis 0,64 | A4-F04 (Änderung -0,27 PP) | -0,02 bis 0,90 |
| H2 G2 V2−V1 | 24 | -1,60 | -1,83 bis -1,23 | A4-F05 (Änderung 0,37 PP) | -1,92 bis -1,08 |
| H2 N14 V2−AS | 17 | 13,67 | 11,82 bis 15,36 | A4-F03 (Änderung -1,85 PP) | 7,10 bis 21,07 |
| H2 N14 V1−AS | 17 | 15,93 | 14,22 bis 17,34 | A4-F03 (Änderung -1,71 PP) | 9,92 bis 22,69 |
| H2 N14 AS+G−AS | 17 | 0,62 | 0,24 bis 0,91 | A4-F04 (Änderung -0,38 PP) | -0,04 bis 1,35 |
| H2 N14 V2−V1 | 17 | -2,25 | -2,63 bis -1,77 | A4-F05 (Änderung 0,48 PP) | -2,82 bis -1,62 |

Für V2−AS bleibt die Richtung in allen definierten Weglassfällen positiv. Der H2-G2-Abstand sinkt ohne die acht Factbook-Quellen jedoch auf 3,99 PP; in N14 beträgt er dann 7,10 PP auf neun verbleibenden Quellen. Diese Schwankung und die nicht zufällige N14-Abdeckung begrenzen Aussagen über andere Quellenfamilien. Die übrigen Komponenten werden vollständig berichtet, auch bei negativen Kontrasten oder Richtungswechseln.

## Konstruktionen getrennt

Durchlauf 1 und 2 umfassen je 24 Quellen. Durchlauf 3 umfasst die 20 neuen Quellen. N14 verwendet die ursprüngliche kontrastspezifische Quellenmenge auch in der Durchlaufzerlegung. Ein in diesem Durchlauf fehlendes Urteil bleibt nach G2 fehlend. Die Hauptwerte behalten sämtliche 68 geplanten Einheiten und sind keine einfache Mittelung der drei Durchlaufkontraste.

| Maß, V2−AS | Durchlauf 1 | Durchlauf 2 | Durchlauf 3 |
|---|---:|---:|---:|
| H1 | 10,46 (n=24) | 7,31 (n=24) | 6,27 (n=20) |
| H2 G2 | 14,73 (n=24) | 7,82 (n=24) | 7,81 (n=20) |
| H2 N14 | 20,79 (n=17) | 11,04 (n=17) | 9,19 (n=17) |

Alle vier Kontraste mit Zellmitteln und Quellenzahlen stehen in durchlaeufe.csv und result.json.

## Relative Senkung des konservativ nicht vollständig gestützten Anteils

Berechnet wird 1 − (1 − H1_c)/(1 − H1_AS) aus den aggregierten H1-Werten, nicht aus dem Mittel einzelner Quellenquotienten. Es handelt sich um das Komplement des konservativen H1-Schätzers: Unklare und gezogene technisch fehlende Urteile zählen dazu. Die Kennzahl ist deshalb keine unabhängig bestätigte sachliche Fehlerquote.

| Gegenüber AS | Nicht gestützt AS (%) | Nicht gestützt Variante (%) | Relative Senkung (%) | 95-%-KI (%) |
|---|---:|---:|---:|---|
| V2 | 18,17 | 9,80 | 46,05 | [31,72; 58,52] |
| V1 | 18,17 | 12,84 | 29,33 | [13,15; 43,86] |
| AS+G | 18,17 | 12,22 | 32,74 | [25,30; 40,51] |

Die Intervalle transformieren dieselben 10.000 gepaarten zweistufigen N10-Replikate (Seed 2026102407; lineare 2,5-/97,5-%-Quantile). Alle Verhältnisse sind endlich; kein Replikat wurde entfernt. Die Intervalle sind marginal, nicht Holm-korrigiert. Die näherungsweise N10-Inklusion und mögliche kostenabhängige Auswahl bleiben bestehen.

## Lieferung und Nachrechnung

- anhang-tabelle.tex: eine kompakte Tabelle mit Typzerlegung, Weglassspannen, Durchläufen und relativer Senkung.
- kapitel6-zwei-saetze.tex: zwei Sätze zur Einbindung ins Manuskript.
- result.json, weglassungen.csv und durchlaeufe.csv: vollständige ausgewählte Aggregate.
- PROTOKOLL.md: Definitionen und nachträgliche Auswahlgrenzen.
- USAGE.md: Reproduktion, Eingangsbindungen und private Dateien.

Der gebundene D1-Hauptkontrast und sein H1-Intervall wurden reproduziert. Alle 24 strikten Typ-Zellwerte einschließlich der undefinierten VV-Werte stimmen mit D1 überein. Die primären H2-G2-/N14-Punkte stimmen ebenfalls überein. Es wurden keine neuen p-Werte berechnet. Semantische Wahrheit, Bewertungsunabhängigkeit, Kostenüberlegenheit und QA-Gewinn werden dadurch nicht neu nachgewiesen.
