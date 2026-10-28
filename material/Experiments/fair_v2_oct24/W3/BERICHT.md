# W3: nachträgliche H4-Nachweisgrenze

**Die bedingt geschätzte Nachweisgrenze beträgt 7,46 Prozentpunkte im Alias-F1
und 7,89 Prozentpunkte im Exact Match.** Verwendet wurden die 60 vollständigen
Paare `V2_ROW` gegen `AS_ORIGINAL` und die 39 ursprünglichen
Absatzüberlappungsblöcke. Die Rechnung ist nachträglich und setzt eine reine
Lageverschiebung bei unveränderter empirischer Fehlerform und Streuung voraus.
Sie ergänzt keine Hypothese und ersetzt keine primäre H4-/Holm-Entscheidung.

| Größe | Alias-F1, Prozentpunkte | EM, Prozentpunkte | Fragen | Blöcke |
| --- | ---: | ---: | ---: | ---: |
| Nachweisgrenze bei 80 % geschätzter Teststärke | 7,46 | 7,89 | 60 | 39 |

Die nominale Schwelle beträgt einseitig α = 0,05 vor Holm. Beide Kennzahlen
verwenden dieselben 10.000 PCG64-Blockziehungen mit Seed `2026102407` und
fragengewichtete Mittel. Bei F1 beträgt die bedingte Entdeckungsrate am
gewählten Rasterpunkt 80,00 %, bei EM 80,11 %. Die unmittelbaren Vorgänger
7,45 beziehungsweise 7,88 Prozentpunkte erreichen nur 79,95 beziehungsweise
79,90 %. Die kleinsten Rasterpunkte sind damit auf dem festgelegten Raster
von 0,01 Prozentpunkten bestimmt. Diese Rasterauflösung ist keine Garantie
entsprechender statistischer Genauigkeit.

Die Rechnung hält die zentrierte Bootstrap-Fehlerverteilung fest und
verschiebt sie um einen hypothetischen positiven mittleren Vorteil. Sie
ist keine verschachtelte wiederholte Neukalibrierung und keine
verteilungsfreie Powergarantie für eine zukünftige Studie. Für binäre
EM-Antworten wird kein konkreter realisierbarer Änderungsprozess modelliert.
EM ist ausschließlich eine zusätzliche beschreibende Blockbootstrap-Angabe,
keine Powerrechnung des ursprünglichen McNemar-Verfahrens. Der Nullshift
in `result.json` dient nur der Kalibrierung des angesetzten Nullmodells.

Der ursprüngliche F1-Kontrast von −1,44 Prozentpunkten, sein marginales
95-%-Intervall und sein ursprünglicher p-Wert wurden mit der unveränderten
D1-Funktion reproduziert. Der F1-/EM-Ausgangsbestand, die Primärfamilie und
das Gesamturteil werden nicht geändert. Aus der Nachweisgrenze folgt weder
Gleichwertigkeit noch eine nachträgliche Erklärung des H4-Negativbefunds.

## Ein Satz und eine Tabellenzeile für INT1/A.13

`anhang-satz.tex` enthält genau einen Satz. `anhang-zeile.tex` enthält genau
eine Zeile für fünf Spalten: Größe, Alias-F1 in Prozentpunkten, EM in
Prozentpunkten, Fragen, Blöcke. Die Annahme und die Einordnung als
nachträgliche Sensitivität müssen bei der Übernahme sichtbar bleiben.
INT1 übernimmt die Integration. Keine Thesisdatei wurde durch W3 geändert.

## Festlegung und Nachweise

Die Methodik wurde vor der Powerrechnung, aber nach Kenntnis der finalen
Hauptergebnisse festgelegt. Maßgeblich sind `METHODIK.md` mit SHA-256
`3f3a6219824132fa47aa3d89bd9590a36e0382f512ad6914ed5c107fe26d7183`
und der lokale Einzelpfadcommit von N19
`20a762b544be492b7eec1da4f28b55b7b4c96413`.
Die Rechnung endete am 27.10.2026 um 08:53:57 UTC.
N19 wurde anschließend ausschließlich für W1 präzisiert
(`1740f63ba5aecc25266280e082c910bb1206482f`). Sein W3-Abschnitt blieb
bytegleich. Die tatsächlich verwendete ältere Fassung ist getrennt
archiviert. Die ursprüngliche Bindung wurde nicht rückwirkend ausgetauscht,
es gab deswegen keine neue empirische Powerrechnung.

`result.json` enthält nur Aggregate und logische Hashbindungen. Einzelwerte,
Fragekennungen, Antworten, die Bootstrap-Fehlerarrays und absolute
Privatpfade werden nicht mitgeliefert. Die unabhängige numerische Prüfung
verwendete ausschließlich die gespeicherten Fehlerarrays. Direkte
Tailzählungen und eine eigene Rangrechnung bestätigten beide Übergänge.
16 synthetische Kontrollen prüfen Tailrichtung, +1-Korrektur, Gleichstände,
Rasterkleinstheit, ungültige Werte, Fragezuordnung, die beschränkte
Scoreauswahl und die unveränderte N19-Hashprüfung. Ein zuvor fehlschlagender
zusätzlicher Schreibtest sichert identische UTF-8-/LF-JSON-Bytes unter Windows
und in Git. Die öffentliche JSON-Lieferdatei unterscheidet sich von der
ursprünglich gespeicherten privaten Ausgabe ausschließlich durch CRLF-zu-LF-
Zeilenenden. Alle JSON-Werte und die privaten Originalbytes bleiben erhalten.
Die lokale `.gitattributes` verhindert weitere automatische
Zeilenendumwandlungen dieser W3-Lieferdateien beim Klonen oder Auschecken.

Für eine erneute Rechnung sind die privaten Originalscores und die originale
N19-Fassung aus Commit `20a762b...` erforderlich. Der Eingabeleser prüft
deren ursprüngliche SHA-256-Bindungen und die Originaldateien erneut nach
der Rechnung. Der explizite Parameter `--n19-snapshot` erlaubt die archivierte
N19-Datei, ohne die seitdem ergänzte gemeinsame G1-Datei zurückzusetzen. Er
kann keine anderen Eingaben umleiten. Ein neuer privater Ausgabeordner
außerhalb des Quellrepositorys ist zwingend:

```text
python -B -X utf8 -m Experiments.fair_v2_oct24.W3.run --allow-final-scores --n19-snapshot ORIGINAL_N19_DATEI --private-output NEUER_PRIVATER_ORDNER
```

Rechenphase ohne Python-Importe: 0,1494 Sekunden Wandzeit und 0,0625 Sekunden
gemessene Prozess-CPU-Zeit. Neue Modell-, Encoder- und Bewertungsaufrufe:
jeweils 0. Kein zusätzlicher Modell-API-Verbrauch. Lokale Stromkosten sind
nicht gemessen. Öffentliche Veröffentlichung und Manuskriptbau sind nicht
Teil dieses W3-Abschlusses.
