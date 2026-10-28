# Menschliche Transferstichprobe nach Nachtrag 16

Stand 26.10.2026, vor Ziehung und vor menschlicher Bewertung. Maßgeblich ist
[Nachtrag 16](../Experiments/fair_v2_oct24/G1/nachtrag_16_transfer_menschlich.md).
Die Hauptbedingung und ihre dort genannte Differenz von +8,4 Prozentpunkten
sind bekannt. Der Kimi-Prüffilter wurde in T1 bereits als Konstruktionsschritt
angewandt. Eine zusätzliche menschliche oder externe Quellenbewertung von T1
liegt bei der Festlegung nicht vor.

## Bestand und Ziehung

Aus den vollständigen aktiven zeilengenauen T1-Inventaren der 20 Frischquellen
werden 30 ursprüngliche Aussagevorkommen aus AS und 30 aus V2 gezogen. T1
verwendet Qwen3-235B und einen Durchlauf. V2 ist der gefilterte V1-Bestand.
Der Eingabebestand wird an die bereits abgeschlossene T1-Übergabe und deren
ursprüngliche Quellen gebunden. Technisch ungeprüft beibehaltene Aussagen
bleiben in der Population. Es gibt keine Auswahl anhand von Prüffilterurteilen,
externen Bewertungen oder menschlichen Urteilen. Identische Texte verschiedener
Vorkommen werden nicht dedupliziert.

Je Arm werden zehn EE-, zehn EV- und zehn VV-Vorkommen gezogen. Nur bei weniger
als zehn VV werden die verfügbaren VV vollständig gezogen und die fehlenden
Positionen proportional zu den ursprünglichen EE-/EV-Populationszahlen verteilt.
Die ganzzahlige Zuteilung verwendet größte Reste mit EE vor EV bei Gleichstand.
Ein Kapazitätsüberhang geht an den anderen Typ. Fehlen zehn EE, zehn EV oder
insgesamt 30 Vorkommen in einem Arm, stoppt die Vorbereitung.

Alle Pools werden nach unveränderlicher Vorkommenskennung sortiert. Python
`random.Random(2026102616)` zieht ohne Zurücklegen in der Reihenfolge AS, V2
und darin EE, EV, VV. Derselbe Zufallsstrom mischt anschließend die 60 Positionen.
Python-Version, Populationsgrößen, Quoten und Einschlusswahrscheinlichkeiten
werden dokumentiert. Die Ziehung erfolgt genau einmal nach der separaten
Veröffentlichung von Nachtrag 16.

## Verblindete Autorenannotation

Die unveränderte C7-Oberfläche zeigt ganze ursprüngliche JSON-Aussagen mit allen
Feldern und den vollständigen gebundenen Quelltexten. Die öffentlichen Felder
enthalten ausschließlich opake Kennungen, Aussagen und Quellen. Arm, Typ,
Prüffilterstatus und private Vorkommenskennungen fehlen. Ein neues privates Salz
erzeugt eine neue Paketkennung. Der Browserspeicher ist an Paketkennung und
Paketdigest gebunden. Die Quellen und Formulierungen können Hinweise auf ihre
Herkunft geben. Metadatenverblindung garantiert keine inhaltliche Unkenntlichkeit.

Der Autor wählt jeweils „Gestützt“, „Nicht gestützt“ oder „Unklar“. Alle 60
Positionen beginnen ohne Urteil. Die Annotation ist eine Autorenannotation,
kein unabhängiger menschlicher Goldstandard. Das technische C7-Feld
`cohort=confirmation` bezeichnet hier lediglich natürliche Daten im bestehenden
Austauschformat. H16 bleibt wissenschaftlich explorativ.

## Festgelegte Auswertung nach dem Export

Der unveränderte menschliche JSON-Export wird mit seinen Originalbytes außerhalb
des Repositorys gesichert und zurückgelesen, bevor der private Schlüssel geöffnet
wird. Nur ein explizit als Autorenannotation bestätigter, paketgebundener Export
mit `annotation_origin=human_ui_input` wird ausgewertet. Erst bei 60 gültigen
Urteilen werden Raten, Differenz, Intervall und Vorzeichen berechnet.
Unbeantwortete Positionen verhindern diese Berechnung und werden nicht als null
gestützte Aussagen ergänzt. „Unklar“ ist dagegen eine gültige Antwort im Nenner.

Die primäre Rate ist die Zahl gestützter Urteile geteilt durch 30 je Arm. Die
Differenz lautet V2 minus AS. Berichtet werden die ungewichteten Raten der
geschichteten Stichprobe. Sie schätzen nicht ohne Weiteres die natürlichen
Typmischungen der gesamten Arme. Die Typaufteilung bleibt beschreibend.

Vor Labelsicht festgelegte technische Konkretisierung des Aussagen-Bootstraps:
10.000 Ziehungen mit Zurücklegen, separat je Arm über dessen 30 ganze Aussagen.
Originalkennungen werden vor der Auswertung sortiert. NumPy PCG64 verwendet
den separaten Seed 2026102617. Das zweiseitige 95-%-Perzentilintervall der
Differenz verwendet lineare Quantile. Es wird weder über Quellencluster noch
unter Erhaltung der Typquoten resampelt. Gemeinsame Quellen und die kleine
Stichprobe begrenzen die Interpretation dieses Aussagenintervalls.

Das Vorzeichen des Punktschätzers wird mit der in Nachtrag 16 bekannten positiven
Richtung der Hauptbedingung verglichen. Null wird gesondert als null berichtet.
Eine gleiche Richtung ist keine Bestätigung gleicher Effektgröße oder allgemeiner
Modellübertragung. Es gibt keinen Signifikanztest, keine Holm-Korrektur und keinen
Eingang in das Gesamturteil. Ergebnisse und Einzelurteile werden nicht vorweggenommen.

## Verwendung

Vorbereitung aus dem Repository-Stamm: `python -m H16.prepare`.
Der Autor öffnet die erzeugte Datei `Downloads/H16-Autorenannotation-60.html`
und exportiert nach Abschluss alle Urteile als JSON. Der Auswerter erhält die
expliziten Paket-, Schlüssel- und Exportpfade über `python -m H16.evaluate --help`.
Quellen, Auswahlzuordnung und Einzelurteile bleiben außerhalb von Git.
