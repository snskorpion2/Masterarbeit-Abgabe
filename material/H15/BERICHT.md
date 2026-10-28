# H15: menschliche Zusatzprüfung des Bedeutungserhalts

**Abgeschlossen am 26.10.2026.** Der Autor bewertete alle 30 Fälle im
verblindeten Werkzeug. Sein direkter Originalexport wurde vor dem Öffnen des
privaten Schlüssels bytegleich gesichert und zurückgelesen. Die unveränderte
N15-Auswertung wurde genau einmal ausgeführt. Es gab keine neuen Modellaufrufe.
Die maschinenlesbaren Aggregate stehen in [result.json](result.json), der
technische Abschlussbeleg in [author-verification.json](author-verification.json).

## Anlage und Herkunft

[Nachtrag 15](../Experiments/fair_v2_oct24/G1/nachtrag_15_menschliche_pruefung_h2.md)
wurde als einzelner Pfad vor der Ziehung veröffentlicht
(`21d6d3d1055fd7edfb86de6572e58f2e249fb177`). Die Festlegung erfolgte nach
Kenntnis der aggregierten D1-Vorlaufwerte und vor der Autorenannotation.

Die feste Stichprobe umfasst 15 eindeutige Referenzbedeutungen mit je einem
AS- und einem V2-Inventar aus demselben gültigen Konstruktionsdurchlauf.
Die einmalige, nach Quellfamilie proportionale Ziehung mit Seed 2026102615
ergab sieben Factbook- und acht Wikipedia-Bedeutungen aus elf Quellen.
Der zulässige Rahmen umfasste 17 Quellen und 157 eindeutige Bedeutungen
(76 Factbook, 81 Wikipedia). Die Sol-Klasse war kein Auswahlkriterium.

Die 30 Fälle wurden gemeinsam permutiert. Die Seite zeigte die vollständige
Referenz samt erforderlichen Aspekten, den vollständigen Quelltext und das
tatsächlich von C3 bewertete vollständige Inventar mit Suchfunktion. Arm,
Durchlauf, Sol-Urteil und Paarzuordnung fehlten auch in versteckten Clientdaten.
Inhaltliche Unterschiede konnten Rückschlüsse erlauben. Die Trennung beruhte
auf getrennten Dateien und dem Eingabevertrag, nicht auf technischen
Zugriffsrechten zwischen Agents auf demselben Rechner.

Der direkte Export enthält 30 gültige Autorenlabels, keine fehlenden Labels
und keine unklaren Urteile. Seine Herkunft wurde durch die direkte
Autorenbestätigung und das Werkzeugformat `human_ui_input` gebunden.
Originalexport, Kommentare, Zeitstempel, privater Schlüssel und Einzelurteile
bleiben unverändert privat. Der Export umfasst 5.091 Bytes mit SHA-256
`c73f818c4547ff91eda5017d6c639d8cd8ae392f8c779f0f14c5f53f201f025f`.

## Übereinstimmung zwischen Autor und Sol

In **27 von 30 Fällen (90,0 %)** stimmen Autor und Sol überein. Alle drei
Abweichungen betreffen die Grenze zwischen vollständigem und teilweisem
Erhalt. Zwei Autorenurteile lauten vollständig, während Sol teilweise vergab.
Ein Autorenurteil lautet teilweise, während Sol vollständig vergab.

| Abbildung | Gültige Paare | Cohen-κ | 95-%-Fallbootstrapintervall |
| --- | ---: | ---: | ---: |
| Drei Klassen: vollständig, teilweise, nicht enthalten | 30 | 0,750 | [0,3841; 1,0000] |
| Binär: vollständig gegen übrige gültige Klassen | 30 | 0,7337 | [0,3750; 1,0000] |

Konfusionsmatrix der drei Klassen, Zeilen Autor und Spalten Sol:

| Autor \\ Sol | vollständig | teilweise | nicht enthalten |
| --- | ---: | ---: | ---: |
| vollständig | 21 | 2 | 0 |
| teilweise | 1 | 4 | 0 |
| nicht enthalten | 0 | 0 | 2 |

Die binäre Matrix lautet bei gleicher Orientierung:

| Autor \\ Sol | vollständig | Rest |
| --- | ---: | ---: |
| vollständig | 21 | 2 |
| Rest | 1 | 6 |

Wegen unklarer Urteile wurde kein Paar ausgeschlossen. Sol verwendete auf
diesen Fällen weder `undetermined` noch `not_assessable`.
Beide κ-Werte verwenden dieselben vorgegebenen 10.000 Fallbootstrap-Ziehungen,
PCG64 mit CI-Seed 2026102616 und linearen 2,5-/97,5-%-Quantilen. Alle 10.000
κ-Werte waren für beide Abbildungen definiert.

Nach N15 wird die Kennzeichnung **„H2 bewerterabhängig“ nicht ausgelöst**,
weil das binäre Punkt-κ nicht kleiner als 0,40 ist. Das breite Intervall
reicht jedoch unter 0,40. Die festgelegte Punktregel bedeutet daher keine
statistisch abgesicherte Überschreitung dieser Schwelle.

## Beschreibender Bedeutungserhalt unter Autorenlabels

| Arm | vollständig | teilweise | nicht enthalten | unklar | vollständig / 15 |
| --- | ---: | ---: | ---: | ---: | ---: |
| AS | 11 | 2 | 2 | 0 | 73,3 % |
| V2 | 12 | 3 | 0 | 0 | 80,0 % |

Die gepaarte Differenz V2 minus AS beträgt **+1/15 beziehungsweise
+6,7 Prozentpunkte**. Zehn Bedeutungen sind in beiden Armen vollständig
enthalten, eine nur in AS, zwei nur in V2 und zwei in keinem der beiden Arme.
Diese Werte sind nach N15 beschreibend. Es wurde kein Hypothesentest
ausgeführt und keine Populationsprävalenz geschätzt.

## Reichweite

Die Zusatzprüfung zeigt auf dieser festen Stichprobe eine weitgehende
Übereinstimmung mit Sol. Sie liefert keinen allgemeinen Nachweis der
Richtigkeit des Bewerters. 30 Fälle entsprechen 15 Bedeutungspaaren aus elf
Quellen. Der vorgegebene Fallbootstrap korrigiert weder die Paarung noch
Quellen- oder Konstruktionsabhängigkeit und ist kein Quellenclusterintervall.

H15 verändert weder die nativen D1-Punktwerte noch H2-Nichtunterlegenheitsregeln,
Holm-Familien oder Gesamtstufe. Der beschreibende Unterschied von einer
Bedeutung belegt keinen allgemeinen Konstruktionsvorsprung gegenüber AS.

## Technischer Abschluss

Vor dem Lauf bestanden die bereits vorgesehenen 125 Python- und zehn
JavaScript-Prüfungen auf künstlichen Daten. Die prospektiven H15-Codepins
entsprachen weiterhin dem Zustand der ursprünglichen Ziehung. Die Auswertung
verwendete `H15.run` ohne Änderung. Originalexport und gespeicherte Kopie
wurden vor dem Lauf bytegleich verglichen. Der private Abschlussbeleg und die
öffentlichen Aggregate wurden danach gelesen, ohne die Statistik neu zu berechnen.

Die frühere Browserprüfung durch den Agenten war durch die Sicherheitsrichtlinie
blockiert. Eine automatisierte visuelle Prüfung der Oberfläche liegt daher nicht vor. Der direkte Autorenexport stammt aus dem bereitgestellten Werkzeug.
