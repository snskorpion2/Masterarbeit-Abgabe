# H12: eingefrorene Vorbereitung nach N12

[N12](../G1/nachtrag_12_menschliche_pruefung_prueffilter.md) wurde allein unter
`51fff895734d2056bc1cad1f383a955a03efa79d` veröffentlicht. Die präzisierte
Chronologie und der ursprüngliche Statuswortlaut stehen in `publication.json`.
X2c war bereits ausgewertet. Diese Veröffentlichung erfolgte vor der C7-
Auswertung in diesem Chat sowie vor H12-Ziehung und H12-Annotation.

Die tatsächliche Stichprobe ist einmalig mit Seed `2026102512` eingefroren.
Grundlage sind alle 24 Konfirmationsquellen, 68 gepaarte Quell-Durchläufe,
136 AS-/V1-Eltern und 550 tatsächliche Prüffilterentfernungen. Aus jeder Basis
werden 30 Entfernungen gezogen. Ihre EE-/VV-Quoten folgen proportional den
ursprünglichen Entfernungszahlen, gerundet mit größtem Rest; Gleichstände
verwenden EE vor VV. Hinzu kommen je 15 behaltene EE-/VV-Aussagen mit gültigem
Prüffilterurteil, ohne zusätzliche Typquote. Ungeprüfte bleiben ausgeschlossen.

Jeder UID-sortierte ursprüngliche Pool wird permutiert. C7-IDs werden beim Scan
übersprungen und durch die nächste zulässige Position ersetzt. Abschließend
werden die 90 Fälle mit demselben Zufallsstrom durchmischt. Die ursprünglichen
C7-150 werden unverändert ausgeschlossen. Bei Kapazitätsmangel würde die
Vorbereitung stoppen, ohne Quoten zu verkleinern oder Strata umzuschichten.
Die vier versiegelten Primärquellen werden als `sealed4_primary` geführt und
weder ausgeschlossen noch als Wikipedia oder Factbook umklassifiziert.

Alle Aussagen bleiben vollständige native JSON-Werte, alle Quellen vollständig.
Die HTML-Datei verwendet unverändert das C7-Werkzeug. Nur opake IDs, Aussagen
und Quellen stehen im Autorenpaket. Arme, Filterentscheidung, Filtergrund,
Facetten, C2-Urteile und ursprüngliche IDs bleiben im getrennten privaten
Schlüssel. Stil und Inhalt können trotzdem Hinweise auf die Herkunft geben.
Die Metadatenverblindung ist keine Zugriffskontrolle auf dem Rechner.

Ein Hash-Anschluss wurde nach dem Einfrieren der Auswahl korrigiert:
`graph_contract.digest` verwendet ASCII-JSON mit `ensure_ascii=True`, das
C7-Werkzeug UTF-8 mit `ensure_ascii=False`. Bei Unicode unterscheiden sich die
Hashes desselben unveränderten Wertes. Beide Definitionen werden jetzt getrennt
geprüft und dokumentiert. Die gespeicherte erste Auswahl blieb identisch,
es erfolgte keine Neuziehung oder Normalisierung der Aussagen.

## Festlegung der späteren Auswertung vor H12-Labelsicht

Erst nach einem paketgebundenen Export mit 90 gültigen Autorenlabels werden
Punktschätzer, Fisher-Test und Konfidenzintervalle berechnet. Ein fehlendes Label
wird nicht zu null oder zu „nicht gestützt“. Der Originalexport wird vorher
privat unverändert gesichert. Eine Datei beweist keine authentifizierte
Urheberschaft. Die Autorenannotation ist kein unabhängiger externer Goldstandard.

Primär gilt „nicht gestützt“ als Erfolg, „gestützt“ und „unklar“ als kein Erfolg.
Die 2×2-Tabelle enthält zeilenweise entfernte und behaltene Aussagen, spaltenweise
Erfolg und sonstiges Label. Fisher wird einseitig mit `alternative='greater'`
bei Alpha 0,05 berechnet. Eine Sensitivität zählt zusätzlich „unklar“ als Erfolg.
Die Richtung folgt der [SciPy-Definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html).

Die Differenz lautet Entfernungsanteil minus Kontrollanteil. Für das marginale
95-%-Intervall werden 10.000 Aussagen-Bootstraps mit PCG64 und getrenntem
CI-Seed `2026102513` in den vier festen Arm-/Entscheidungsstrata 30/15/30/15
gezogen. Innerhalb jedes Stratum werden Original-IDs vorher sortiert. Primär
und Unklar-Sensitivität verwenden dieselben Ziehungen. Quellen- und
Konstruktionsabhängigkeiten sind dadurch nicht korrigiert. Fisher-Test und
Intervall beruhen auf einer Arbeitsannahme unabhängiger Aussagen und begründen
keine allgemeine Populations- oder Kausalbehauptung.

Entfernungspräzision wird je Basis, EE/VV, Quellfamilie und auslösender Facette
beschrieben. Eine Aussage mit mehreren Facetten erscheint in mehreren
Facettenzeilen, im Gesamtzähler jedoch genau einmal. Übereinstimmung mit Sol
verwendet ausschließlich gültige Paare. N10-Nichtziehung und technische
Fehlwerte bleiben getrennt. Keine neuen G2-/N8-Holm-Slots und kein Ersatz der
primären Sol-Bewertung.

Öffentlich werden nur Code, Methode und Aggregate gespeichert. Autoren-HTML,
Schlüssel, einzelne Aussagen, Kommentare und Labels liegen außerhalb des Repos.
Aktuelle Aufgaben stehen ausschließlich in der Root-README.
