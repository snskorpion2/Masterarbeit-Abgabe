# C7: Abgleich der gebundenen Autorenannotation mit Sol

Die Autorenannotation enthält 150 gültige Labels.
Das Exportfeld `annotation_origin` lautet `human_ui_input`.
Es wurde auf Anweisung des Autors berichtigt. Labels, Kommentare und sämtliche
anderen Felder sind gegenüber der ursprünglichen Rechenfassung unverändert.
Die Kennzahlen bleiben unverändert.

## Bindung und Reihenfolge

Ursprünglicher Autorenexport für die Berechnung: SHA-256
`e298973f7bcca4746d2f7704c618b93724d60d2fe977a3cb3e4e60e9785ab88b`.
Aktueller Autorenexport nach Berichtigung ausschließlich von `annotation_origin`:
SHA-256 `291c623a42611f16124adbf80298b60430f8501cded62ee01a3fc9b2677f335c`.
Die ursprünglichen Bytes bleiben privat erhalten. Der Korrekturbeleg ist in
[result.json](result.json) gebunden. Eine neue Bewertung oder Berechnung erfolgte nicht.
Der unveränderte private C7-Schlüssel bindet dieselben 150 Vorkommen.
Nach ausdrücklicher Übergabe der Orchestrierung wurde der C2-Endexport mit SHA-256
`1dc354b2c480936f205975e65eb926109e09f4f16ab4d9ae6e566e295bc3fafb`
verwendet. Einzelurteile, Kommentare und die aufgedeckte Zuordnung bleiben privat.
Die Zuordnung prüft zellgebundene Vorkommens-ID, vollständigen Aussagewert,
Quellzuordnung und die identischen Original-/Zeilenansichten. Alte leere
Sol-Labels aus dem Stichprobenschlüssel werden nicht als Endurteile verwendet.

N12 wurde zuvor als einzelner Pfad veröffentlicht
(`51fff895734d2056bc1cad1f383a955a03efa79d`). Danach wurde H12 einmalig
gezogen und ohne Überschneidung mit C7 eingefroren. Erst anschließend erfolgte
dieser C7-Abgleich. Die frühere C7-Schlüsselsicht für den H12-Ausschluss war
auf IDs beschränkt. Allgemeine Ergebnisblindheit wird nicht behauptet.
[N12-Chronologie](../H12/publication.json), [H12-Bericht](../H12/BERICHT.md).

## Übereinstimmung

Von 150 Fällen haben 110 ein gültiges Sol-Urteil. 37 wurden im N10-Präfix nicht
gezogen, drei haben einen technischen Fehlwert. Diese 40 Fälle werden weder als
„unklar“ noch als Übereinstimmung gezählt. Beide Arme liefern je 55 gültige Paare.

| Maß | Schätzwert | 95-%-Bootstrap-KI |
| --- | ---: | ---: |
| Cohen-κ, drei Klassen | 0,7250 | [0,5212, 0,8871] |
| Cohen-κ, gestützt gegen nicht gestützt + unklar | 0,7233 | [0,5156, 0,8866] |
| Exakte Übereinstimmung | 102/110 = 92,73 % | nicht berechnet |

Konfusionsmatrix der drei Klassen. Zeilen: Autorenannotation,
Spalten: Sol. Reihenfolge jeweils gestützt / nicht gestützt / unklar.

| | Sol gestützt | Sol nicht gestützt | Sol unklar |
| --- | ---: | ---: | ---: |
| Autorenannotation gestützt | 89 | 7 | 0 |
| Autorenannotation nicht gestützt | 0 | 13 | 0 |
| Autorenannotation unklar | 1 | 0 | 0 |

Binär ergibt sich `[[89, 7], [1, 13]]`. Beide κ-Intervalle verwenden dieselben
10.000 Aussagen-Ziehungen mit G2-Seed 2026102407 und PCG64. Kein κ der
Gesamtstichproben-Ziehungen ist undefiniert. Es wird über gültige Aussagenpaare
resampelt, nicht über Quellen oder Konstruktionen. Alle 23 vertretenen Quellen
liefern mehrere Aussagen. Die Intervalle korrigieren deren Abhängigkeit nicht.

## Armwerte und Entfernungen

Die feste Stichprobe enthält je 25 EE-, EV- und VV-Fälle pro Arm. Die Werte sind
ungewichtete Beschreibungen dieser kleinen geschichteten Stichprobe, keine
Prävalenzschätzung der Grundgesamtheit. „Unklar“ zählt im primären Nenner mit.

| Arm | Gestützt | Nicht gestützt | Unklar | Gestützt / alle | 95-%-KI |
| --- | ---: | ---: | ---: | ---: | ---: |
| AS | 65 | 10 | 0 | 65/75 = 86,67 % | [78,67 %, 93,33 %] |
| V1 | 69 | 5 | 1 | 69/75 = 92,00 % | [85,33 %, 97,33 %] |

V1 minus AS: **+5,33 Prozentpunkte**, 95-%-KI **[−4,00, +14,67] Prozentpunkte**.
Das Intervall umfasst null. Ein Vorteil wird daraus nicht bestätigt.
Der Bootstrap erhält die sechs festen Arm-/Typ-Nenner, wiederum mit 10.000
Ziehungen und G2-Seed. Populationsgrößen dienen nur als Metadaten. Es werden keine
Hochrechnungsgewichte verwendet. Bedingt auf gestützt/nicht gestützt wären es
bei V1 69/74, dies ersetzt den primären Wert 69/75 nicht.

Unter den 150 Fällen wurden 13 vom Prüffilter entfernt. In AS beurteilt die
Autorenannotation drei von zehn als gestützt und sieben als nicht gestützt.
In V1 sind zwei von drei gestützt und einer nicht gestützt. Insgesamt sind somit
**fünf der 13 Entfernungen laut Autorenannotation gestützt**. Dies ist ein sichtbarer
Gegenbefund auf der kleinen C7-Teilmenge, keine Schätzung der gesamten
Entfernungspräzision. Die gezielte H12-Stichprobe steht dafür noch aus.

## Kommentare

40 Kommentare sind nicht leer, davon AS 22 und V1 18. Nach Typ sind es EE 13,
EV sechs und VV 21. Nach Quellgruppe sind es Wikipedia 22, Factbook elf und
separate versiegelte Primärquellen sieben.

Der Export enthält keine strukturierten Kategorien. Die vier vorab implementierten
engen Wortmuster für „Pronomen“, „kein Ereignis“, „leere Entitätsliste“ sowie
„Anapher/wörtliche Kopie“ haben jeweils null ausdrückliche Treffer, in allen
Arm-, Typ- und Quellgruppen. Alle 40 Kommentare bleiben dabei unzugeordnet.
Das sind ausschließlich lexikalische Zählungen. Sie belegen weder die Abwesenheit
dieser Probleme noch deren semantische Häufigkeit. Eine neue inhaltliche Annotation
wurde nicht vorgenommen. Für solche Kategorienhäufigkeiten müssten die Kommentare
explizit entsprechend kodiert werden.

## N8 und D1

Nach der direkten C7-Vorgabe wird der **binäre** κ-Punktschätzer mit 0,40
verglichen. 0,7233 liegt darüber. Der rechnerische Schwellenfall für eine
Herabstufung tritt an dieser Autorenannotation nicht ein. N8 bleibt unverändert.
Die kleine Autorenstichprobe und der Aussagen-Bootstrap begrenzen die Aussage.
Die ausgefallene modellbasierte Zweitbewertung wird durch dieses Ergebnis
nicht ersetzt.

[result.json](result.json) enthält nur Aggregate und Herkunftsmetadaten. Ein privater
D1-Datenträger enthält die unveränderten drei Klassen und führt
`annotation_origin: "human_ui_input"` sowie die ausdrückliche Autorenbestätigung.
Der C7-Eingang, der aktive D1-Datenträger und die öffentliche Ergebnisdatei
verwenden dieselbe korrigierte Fassung. Das bisherige D1
verwendet für seine interne Schwelle dreiklassiges κ. Diese Schnittstellenabweichung
ist gemeldet. Ein synthetisches Gegenbeispiel ergibt dreiklassiges κ = 0 und
binäres κ = 1. In C7 selbst unterscheiden sich die Schwellenentscheidungen nicht.
Keine stillschweigende Umetikettierung und keine natürliche D1-Gesamtauswertung.

Keine Modellaufrufe, keine erneute Quellenannotation und keine neuen Labels.
Die aktuellen CPU-Prüfungen, Datei-Bindungen und der Veröffentlichungsschutz
sind in [verification.json](verification.json) dokumentiert. Der ursprüngliche
Prüfbeleg bleibt darin als historischer Nachweis gebunden. Die Korrektur vom
25.10.2026 berichtigt die Bezeichnung und das Exportfeld `annotation_origin`.
Der ursprüngliche Recheneingang bleibt erhalten, die aktuelle Datei erhält
einen eigenen Hash. Keine Labels, Kommentare oder Kennzahlen wurden geändert.

Die Exportfunktion des Annotationswerkzeugs schreibt `human_ui_input`
([annotate.html](../../../Tools/experiments/c7_human_annotation_oct24_v1/annotate.html)).
71 synthetische CPU-Tests für C7 und 13 Verhaltensprüfungen des tatsächlichen
Oberflächencodes bestanden. Der korrigierte C7-Code ordnet die Datei anhand der
gebundenen Autorenbestätigung als Autorenannotation ein. Exportmarker und
Kommentarpräfixe erzeugen keine Herkunfts- oder Unabhängigkeitsbehauptung.
Ein bereits abgeschlossener Lauf wird vor jedem privaten Dateizugriff gestoppt.
