# S13: Autorenannotation der explorativen Schemaprobe

**Ein höherer Anteil passender Typen durch zusätzliche Quellsätze ist im primären
Test nicht nachgewiesen.** Auf allen 60 gepaarten Knoten steigt die mittlere
Präzision von A mit 59,71 % auf B mit 65,62 %. Die Differenz beträgt +5,91
Prozentpunkte, das vorab festgelegte 95-%-Bootstrapintervall reicht von −2,46
bis +14,46 Punkten. Der zweiseitige Wilcoxon-Test ergibt p = 0,175558
(Statistik 518, 51 von null verschiedene Paardifferenzen und neun Paare mit
Präzisionsdifferenz null).
Das belegt weder Gleichwertigkeit noch Unterlegenheit von B.

Die Ergebnisse stehen maschinenlesbar in [result.json](result.json), Schema
`s13-evaluation-v1`. Alle Präzisionsmittel und Differenzen sind knotengewichtet.
Im JSON sind Präzision, `mean_delta` und Intervallgrenzen Anteile.
`mean_delta_percentage_points` gibt die Differenz ausdrücklich in Prozentpunkten an.

| Sekundärer Befund | A: Original-AS | B: zusätzliche Quellsätze |
| --- | ---: | ---: |
| Knoten mit mindestens einem ausdrücklich unpassenden Konzept | 25/60 (41,67 %) | 17/60 (28,33 %) |
| Präferenz des Autors | 20/60 | 36/60 |
| Konzeptanzahl | 279 | 288 |
| Konzepte je Knoten | 4,65 | 4,80 |
| Passende / unpassende / unklare Konzepte | 165 / 50 / 64 | 185 / 23 / 80 |
| Unklare Konzepte, Anteil an allen Konzepten | 22,94 % | 27,78 % |
| Mittlerer Unklaranteil je Knoten | 23,35 % | 26,70 % |

Vier Präferenzen sind „gleich“. Der exakte zweiseitige McNemar-Test ergibt
p = 0,096252. Nur A weist bei 13 Paaren mindestens ein unpassendes Konzept auf,
nur B bei fünf Paaren. Bei zwölf Paaren gilt dies für beide, bei 30 für keinen
Arm. Die vollständige Tabelle mit Zeilen A und Spalten B, jeweils in der
Reihenfolge nein/ja, lautet `[[30, 5], [13, 12]]`. Auch dieser vorab festgelegte
Test weist bei α = 0,05 keinen Unterschied nach. „Unklar“ wird nicht als
ausdrücklich unpassend umcodiert und bleibt im Präzisionsnenner. Der größere
Unklarbestand bei B bleibt als Gegenbefund sichtbar.

| Quellfamilie, beschreibend | Wikipedia | Factbook |
| --- | ---: | ---: |
| Knoten / vertretene Quellen | 36 / 11 | 24 / 7 |
| Mittlere Präzision A → B | 56,74 % → 65,43 % | 64,16 % → 65,90 % |
| Differenz B − A | +8,69 Prozentpunkte | +1,75 Prozentpunkte |
| Präferenz A / B / gleich | 10 / 25 / 1 | 10 / 11 / 3 |
| Konzepte A / B | 162 / 174 | 117 / 114 |
| Konzepte je Knoten A / B | 4,50 / 4,83 | 4,875 / 4,75 |
| Knoten mit unpassendem Konzept A / B | 16/36 / 12/36 | 9/24 / 5/24 |

Die zusätzliche, vorab festgelegte Quellencluster-Sensitivität ergibt ein
95-%-Intervall von +0,99 bis +11,97 Prozentpunkten. Sie zieht die 18 Quellen
familiengeschichtet und übernimmt jeweils alle zugehörigen Knoten. Dieses
positive sekundäre Intervall steht neben dem null einschließenden primären
Knotenintervall. Es ersetzt weder den primären Test noch dessen Ergebnis und
ist keine unabhängige Bestätigung. Die Familienaufteilung ist beschreibend.

Ausgewertet wurde exakt nach
[Nachtrag 13](../Experiments/fair_v2_oct24/G1/nachtrag_13_schemaprobe_kontext.md),
vor Ziehung und B-Erzeugung veröffentlicht unter
`0e709cf4d5638e0f307bedac6360aaf33940944f`:
10.000 gepaarte, familiengeschichtete Bootstrapziehungen mit PCG64-Seed
2026102514, lineare Perzentile, ungerundete Präzisionsanteile. Der Wilcoxon-Test
verwendet auf zwölf Nachkommastellen gerundete Differenzen, verwirft
Nulldifferenzen und verwendet mittlere Ränge ohne Kontinuitätskorrektur.
Die Vorzeichenpermutation umfasst 100.000 Monte-Carlo-Ziehungen mit PCG64-Seed 2026102515.
McNemar ist der exakte zweiseitige Binomialtest. Explorativ, ohne Holm.

Die unveränderte Autorenannotation mit 60 Einträgen wurde privat byteidentisch
gesichert und ihr SHA-256 vor dem ersten Lesen der Armzuordnung geprüft:
`68e41a579cf9cd02ba6e73255704d30c49166809f034d6affa71cb404516b91f`.
Paket, vollständige Konzepte und Urteile sowie die private Armzuordnung stimmen
mit den vorab gebundenen Beständen überein. Die gespeicherten A-Listen wurden
nicht neu erzeugt. Kein Urteil wurde ergänzt oder geändert, kein Modell
aufgerufen. Einzelurteile, Kommentare, Quelltexte und Zuordnungsdatei bleiben
privat. Alle 83 synthetischen CPU-Tests bestanden. Die öffentliche Ausgabe wurde
vor der Entblindung auf Aggregate begrenzt, die statistischen Funktionen blieben
nach geprüftem Syntaxbaumvergleich unverändert.

Die Auswahl umfasst 60 Knoten aus dem vorab begrenzten Rahmen von 759 exakt
quellspannengebundenen unter 851 originalen AS-Knoten. 92 Knoten ohne exakte
Nennung wurden bereits vor der Ziehung ausgeschlossen. Mehrere Knoten gehören
derselben Quelle an. Es gibt einen Autorenbewerter, einen Generierungsdurchlauf
und frühere gemischte Entwicklungsbefunde. Die ursprüngliche AS-Aufgabe erlaubt
Typen und verwandte Konzepte, während diese Annotation die engere Eigenschaft
„passender Typ im Kontext“ bewertet. Der Befund betrifft ausschließlich diese
explorative Schemastufenprobe. Er bestätigt keine Verbesserung der eingefrorenen
V2-Pipeline, keinen allgemeinen Vorsprung gegenüber AutoSchemaKG, keine
Schemaabdeckung, keinen funktionalen Schemanutzen und keinen Effizienzvorteil.
Die historischen Ausführungsbelege bleiben unter [Vorbereitung](preparation.json),
[Generierungsstand](status.json) und [Bindungsprüfung](verification.json) erhalten.
