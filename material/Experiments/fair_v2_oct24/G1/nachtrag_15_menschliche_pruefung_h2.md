# Nachtrag 15: menschliche Prüfung der Erhaltsurteile (H2) (26.10.2026)

**Status:** sekundäre Validierung des Hauptbewerters für H2, kein Eingang in Holm-Familien oder Gesamturteil.
**Chronologie:** festgelegt nach dem D1-Vorlauf (H1/H2-Punktschätzer sind bekannt), aber vor jeder Sicht auf einzelne
C3-Urteile durch den Autor. Der Autor bleibt verblindet gegenüber Arm und Sol-Urteil. Diese Chronologie wird im Bericht
offengelegt.

## Stichprobe (Seed 2026102615)

- 15 Referenzbedeutungen, zufällig aus allen Referenzpositionen der 17 Quellen gezogen, die in **beiden** Zellen AS
  und V2 ein gültiges C3-Urteil haben, geschichtet nach Quellfamilie (Wikipedia, Factbook) proportional.
- Je Bedeutung zwei Prüffälle: dieselbe Referenzbedeutung gegenüber dem AS-Inventar und gegenüber dem V2-Inventar.
  Zusammen 30 Fälle in zufälliger Reihenfolge, ohne Armkennung.
- Annotation: Referenzbedeutung, Quelltext und das vollständige Inventar mit Suchfeld. Labels wie in C3:
  „vollständig enthalten“, „teilweise enthalten“, „nicht enthalten“, optional „unklar“, mit Kommentar.

## Auswertung

- Cohen-κ Autor gegen Sol (drei Klassen und binär „vollständig“ gegen Rest), Konfusionsmatrix, Bootstrap-KI über Fälle.
- Beschreibend: Erhaltsquote je Arm unter Autorenlabels auf den 15 Bedeutungen und gepaarte Differenz V2 − AS, ohne
  Test. Ausdrücklich keine Prävalenzschätzung.
- Analog zu N8: Ist κ binär kleiner als 0,40, wird H2 als „bewerterabhängig“ qualifiziert.

## Prospektive Ausführungspräzisierung vor Veröffentlichung und Ziehung

Die folgenden Regeln präzisieren die technische Durchführung desselben Auftrags.
Sie werden zusammen mit diesem Nachtrag als genau ein Pfad veröffentlicht,
bevor die H15-Stichprobe gezogen oder dem Autor gezeigt wird. Es gibt keine
neuen Modellaufrufe und keine Änderung vorhandener C3-Urteile oder Referenzen.

### Bedeutungseinheit, gemeinsamer Durchlauf und Schichtung

- Die 17 Quellen sind die Quellen des vorhandenen N14-Vergleichs AS gegen V2
  mit mindestens einem gültigen C3-Urteil in beiden Armen. Gültige unklare
  Urteile gelten dabei als gültig, technische Fehlwerte nicht. Die Quellen
  werden nicht anhand ihrer Erhaltsquote gewählt.
- Eine Bedeutung ist durch `(source_id, obligation_id)` bestimmt. Sie wird
  höchstens einmal gezogen, auch wenn dieselbe Referenz in mehreren
  Konstruktionsdurchläufen geprüft wurde. Zur Auswahl stehen nur Bedeutungen,
  für die mindestens ein gemeinsamer Durchlauf gültige C3-Urteile für AS und
  V2 enthält. Beide menschlichen Fälle verwenden genau diesen Durchlauf.
- Die Quoten für Wikipedia und Factbook folgen der Zahl solcher eindeutigen
  zulässigen Bedeutungen je Familie. Von 15 Plätzen werden zunächst die
  abgerundeten proportionalen Anteile vergeben, Restplätze nach größtem Rest.
  Bei Gleichstand gilt die lexikographische Familienreihenfolge.
- Verwendet wird `numpy.random.Generator(PCG64(2026102615))`. Familien,
  Bedeutungen und zulässige Durchläufe werden vor jedem Zufallszugriff
  lexikographisch sortiert. Je Familie wird die Bedeutungsliste einmal
  permutiert und ihr Quotenpräfix gewählt. Danach wird je gewählter Bedeutung
  ein zulässiger gemeinsamer Durchlauf gleichverteilt gewählt. Zuletzt werden
  die 30 AS-/V2-Fälle gemeinsam permutiert.
- Die tatsächliche Sol-Klasse ist kein Auswahlkriterium. Fehlende Kapazität,
  widersprüchliche Bindungen oder ein anderer Quellenrahmen führen zum Stopp,
  nicht zu Nachziehung, geänderten Quoten oder einer anderen Saat.

### Verblindeter Inhalt und direkter Autorenexport

Die Seite zeigt je Fall die unveränderte Referenzbedeutung, den vollständigen
Quelltext und das vollständige tatsächlich von C3 bewertete aktive Inventar.
Die Suche verändert nur die Anzeige, nicht den gespeicherten Bestand. Ganze
native Werte einschließlich Duplikaten bleiben erhalten. Arm, Durchlauf,
Sol-Urteil und Zuordnung der beiden Fälle zur selben gezogenen Bedeutung
liegen ausschließlich im getrennten privaten Schlüssel. Auch versteckte
Clientdaten enthalten diese Metadaten nicht. Inhaltliche Unterschiede können
trotzdem Rückschlüsse erlauben, es wird keine technische Geheimhaltung auf
dem gemeinsam genutzten Rechner behauptet.
Technische Fall- und Belegkennungen werden neutral neu vergeben, ihre
Originalzuordnung bleibt privat. Aussagenwerte und ihre Reihenfolge werden
dadurch nicht geändert.

Es gibt keine vorausgewählten Labels. Die deutschen Anzeigen lauten
„vollständig enthalten“, „teilweise enthalten“, „nicht enthalten“ und
„unklar“. Die ersten drei entsprechen `retained`, `partially_retained` und
`not_retained`, das letzte `undetermined`. Die C3-Klasse `not_assessable`
bleibt im Originalschlüssel erhalten und wird nur für die Vergleichsabbildung
ebenfalls als unklar behandelt.

Das Werkzeug exportiert selbst die Fallkennungen, Labels, Kommentare und
Zeitstempel mit Paketbindung und `annotation_origin: human_ui_input`.
Der direkte Originalexport wird vor der Auswertung privat bytegleich
gesichert. Er wird nicht mit Modellurteilen ergänzt oder inhaltlich
umgeschrieben. Eine unvollständige oder fremd gebundene Datei gibt keine
H15-Kennzahlen frei. Quellen, Inventare, Schlüssel und Einzelurteile bleiben
privat, öffentliche Dateien enthalten nur Code, Methode und Aggregate.

### Feste Auswertungsabbildung und Unsicherheit

- Erst 30 gültige Autorenlabels und eine ausdrückliche Zuordnung des Exports
  zum Autor geben die Auswertung frei. Fehlende Labels werden weder als null
  noch als „nicht enthalten“ gewertet.
- Das ungewichtete Drei-Klassen-κ verwendet nur Paare, in denen beide Urteile
  eine der drei eindeutigen Klassen besitzen. Wegen unklarer Urteile
  ausgeschlossene Paare und deren ursprüngliche Codes werden getrennt
  ausgewiesen. Binär gilt vollständig gegen alle übrigen gültigen Klassen,
  einschließlich unklar. Beide Konfusionsmatrizen werden berichtet.
- Für beide κ-Werte werden dieselben 10.000 Fallbootstrap-Ziehungen aus den
  30 Fällen verwendet, `PCG64`, CI-Seed `2026102616`, lineare 2,5-/97,5-%-
  Quantile. Die Drei-Klassen-Abbildung wird innerhalb jeder Ziehung angewandt.
  Undefinierte κ-Ziehungen werden nicht zu null gemacht. Ihre Zahl und die
  Zahl definierter Ziehungen werden berichtet, bei weniger als zwei
  definierten Ziehungen bleibt das Intervall unbekannt.
- Dieser vorgegebene Aussagenbootstrap korrigiert weder die Paarung derselben
  Bedeutung noch Quellen- oder Konstruktionsabhängigkeit. Das Intervall ist
  kein Quellenclusterintervall und keine allgemeine Bewerterqualifikation.
- Die beschreibende Autorenquote je Arm zählt nur vollständig enthaltene
  Bedeutungen im festen Nenner 15. Teilweise, nicht enthalten und unklar sind
  keine vollständige Erhaltung und werden zusätzlich getrennt gezählt.
  Die Differenz V2 minus AS wird über dieselben 15 Bedeutungspaare gebildet,
  ohne Test oder Populationsprävalenzbehauptung.
- Die Schwelle κ binär < 0,40 liefert die sekundäre Kennzeichnung
  „H2 bewerterabhängig“. Ein undefiniertes κ erlaubt keine Schwellenentscheidung.
  Ein höheres κ beweist keine allgemeine Richtigkeit. Weder Punktwerte noch
  Schwellenkennzeichnung verändern die nativen H1-/H2-/H4-Auswertungen,
  Holm-Familien oder Gesamtstufe.
