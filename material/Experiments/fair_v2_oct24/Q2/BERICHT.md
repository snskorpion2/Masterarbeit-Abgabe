# Q2: Explorative Sensitivität der Abruftiefe

Die Auswertung vergleicht dieselben acht Graphansichten und dieselben 60 Fragen bei 30, 60 und 100 abgerufenen Kanten. Laufstatus: **complete**. 960 von 960 geplanten neuen Antwortpositionen wurden bearbeitet. Die 480 vorhandenen Top-30-Antworten wurden unverändert wiederverwendet.

Bei Tiefe 60 liegt der Antwort-F1 in 4 der acht Ansichten über, in 3 darunter und in 1 auf dem gespeicherten Top-30-Wert. Für 0 Ansichten fehlt ein vollständiger Punktschätzer. Die beobachteten Differenzen reichen von -3,38 bis +6,25 Prozentpunkten.

Bei Tiefe 100 liegt der Antwort-F1 in 8 der acht Ansichten über, in 0 darunter und in 0 auf dem gespeicherten Top-30-Wert. Für 0 Ansichten fehlt ein vollständiger Punktschätzer. Die beobachteten Differenzen reichen von +1,01 bis +4,37 Prozentpunkten.

Diese Richtungszählung bezieht sich auf acht Ansichten derselben Graphkonstruktionen. Sie ist keine Zahl unabhängiger Bestätigungen und kein allgemeiner Überlegenheitsnachweis.

## Unveränderte Bedingungen und Messgrenzen

Antwortmodell `qwen.qwen3-235b-a22b-2507`, Temperatur 0, maximal 256 Ausgabetokens, eine nicht gestreamte Antwort und der bisherige AWS-Mantle-Endpunkt in `eu-north-1`. Encoder `sentence-transformers/all-MiniLM-L6-v2`, Revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, CPU, float32 und normalisierte Vektoren. Die ersten 30 Kanten und Anfragen wurden für alle 480 Frage-Graph-Paare exakt gegen die gespeicherten Kontexte geprüft. Prompts, Parser und offizielle MuSiQue-Alias-F1- und EM-Auswertung bleiben unverändert.

F1 ist Antwort-Token-F1, EM die exakte normalisierte Antwort. Alle Werte haben den festen Nenner 60. Bei fehlenden Antworten steht kein Punktschätzer, sondern eine Identifikationsgrenze. Diese Grenzen sind keine Konfidenzintervalle. Es gibt keine neuen Hypothesentests und keine Änderung von H4 oder seiner Testfamilie.

Die Goldabdeckung zählt die unveränderte QA1-Definition: Eine vollständige normalisierte Gold- oder Alias-Tokenfolge muss innerhalb einer einzelnen abgerufenen Aussage aus einem zugehörigen Stützabsatz vorkommen. Fragetext zählt nicht mit. Dieses Oberflächenmaß beweist weder vollständige Mehrschrittstützung, semantischen Quellenrecall noch tatsächliche Nutzung durch das Antwortmodell. Die Top-30-Abdeckung reproduziert QA1 für alle acht Ansichten.

## Qualität und Aufwand je Ansicht und Tiefe

Die letzte Spalte enthält die bekannten Listenpreiskosten der jeweiligen Readerantworten. Die Top-30-Kosten sind historischer Aufwand und wurden für Q2 nicht erneut verursacht.

| Ansicht | Kanten | Antwort-F1 | EM | Goldfolge aus Stützabsatz | Fehlend | Readerkosten USD |
| --- | --- | --- | --- | --- | --- | --- |
| AS_ORIGINAL | 30 | 15,22 % | 11,67 % | 20/60 (33,33 %) | 0 | 0,01789678 |
| AS_ORIGINAL | 60 | 19,39 % | 15,00 % | 26/60 (43,33 %) | 0 | 0,03346486 |
| AS_ORIGINAL | 100 | 16,23 % | 11,67 % | 34/60 (56,67 %) | 0 | 0,05392662 |
| AS_ROW | 30 | 15,13 % | 11,67 % | 20/60 (33,33 %) | 0 | 0,01781868 |
| AS_ROW | 60 | 21,39 % | 13,33 % | 26/60 (43,33 %) | 0 | 0,03342614 |
| AS_ROW | 100 | 16,23 % | 11,67 % | 34/60 (56,67 %) | 0 | 0,05391034 |
| AS_G_ORIGINAL | 30 | 15,31 % | 11,67 % | 20/60 (33,33 %) | 0 | 0,01757514 |
| AS_G_ORIGINAL | 60 | 15,13 % | 11,67 % | 25/60 (41,67 %) | 0 | 0,03279210 |
| AS_G_ORIGINAL | 100 | 19,24 % | 15,00 % | 29/60 (48,33 %) | 0 | 0,05286138 |
| AS_G_ROW | 30 | 15,13 % | 11,67 % | 20/60 (33,33 %) | 0 | 0,01754544 |
| AS_G_ROW | 60 | 15,13 % | 11,67 % | 25/60 (41,67 %) | 0 | 0,03275800 |
| AS_G_ROW | 100 | 19,18 % | 15,00 % | 29/60 (48,33 %) | 0 | 0,05278570 |
| V1_ORIGINAL | 30 | 16,49 % | 13,33 % | 22/60 (36,67 %) | 0 | 0,01903176 |
| V1_ORIGINAL | 60 | 14,87 % | 11,67 % | 24/60 (40,00 %) | 0 | 0,03609980 |
| V1_ORIGINAL | 100 | 19,72 % | 13,33 % | 34/60 (56,67 %) | 0 | 0,05823906 |
| V1_ROW | 30 | 16,53 % | 13,33 % | 21/60 (35,00 %) | 0 | 0,01900140 |
| V1_ROW | 60 | 17,58 % | 11,67 % | 24/60 (40,00 %) | 0 | 0,03603292 |
| V1_ROW | 100 | 19,56 % | 13,33 % | 34/60 (56,67 %) | 0 | 0,05836402 |
| V2_ORIGINAL | 30 | 14,33 % | 11,67 % | 20/60 (33,33 %) | 0 | 0,01889954 |
| V2_ORIGINAL | 60 | 10,94 % | 6,67 % | 22/60 (36,67 %) | 0 | 0,03565320 |
| V2_ORIGINAL | 100 | 17,83 % | 13,33 % | 33/60 (55,00 %) | 0 | 0,05744420 |
| V2_ROW | 30 | 13,78 % | 11,67 % | 20/60 (33,33 %) | 0 | 0,01882100 |
| V2_ROW | 60 | 15,21 % | 11,67 % | 22/60 (36,67 %) | 0 | 0,03555970 |
| V2_ROW | 100 | 18,15 % | 13,33 % | 33/60 (55,00 %) | 0 | 0,05751372 |

## Veränderungen gegenüber gespeicherten 30 Kanten

Positive Differenzen bedeuten höhere Punktwerte. Gewonnene und verlorene EM-Treffer werden getrennt gezählt. Jede Zeile vergleicht dieselben 60 Fragen, keine neue Quellenstichprobe.

| Ansicht | Kanten | Delta F1 in PP | Delta EM in PP | EM gewonnen | EM verloren | Paar fehlt |
| --- | --- | --- | --- | --- | --- | --- |
| AS_ORIGINAL | 60 | +4,17 | +3,33 | 2 | 0 | 0 |
| AS_ORIGINAL | 100 | +1,01 | +0,00 | 1 | 1 | 0 |
| AS_ROW | 60 | +6,25 | +1,67 | 2 | 1 | 0 |
| AS_ROW | 100 | +1,10 | +0,00 | 1 | 1 | 0 |
| AS_G_ORIGINAL | 60 | -0,18 | +0,00 | 1 | 1 | 0 |
| AS_G_ORIGINAL | 100 | +3,93 | +3,33 | 2 | 0 | 0 |
| AS_G_ROW | 60 | +0,00 | +0,00 | 1 | 1 | 0 |
| AS_G_ROW | 100 | +4,04 | +3,33 | 2 | 0 | 0 |
| V1_ORIGINAL | 60 | -1,62 | -1,67 | 0 | 1 | 0 |
| V1_ORIGINAL | 100 | +3,24 | +0,00 | 1 | 1 | 0 |
| V1_ROW | 60 | +1,05 | -1,67 | 1 | 2 | 0 |
| V1_ROW | 100 | +3,02 | +0,00 | 1 | 1 | 0 |
| V2_ORIGINAL | 60 | -3,38 | -5,00 | 0 | 3 | 0 |
| V2_ORIGINAL | 100 | +3,51 | +1,67 | 3 | 2 | 0 |
| V2_ROW | 60 | +1,43 | +0,00 | 2 | 2 | 0 |
| V2_ROW | 100 | +4,37 | +1,67 | 3 | 2 | 0 |

## V2 zeilengenau gegen AS original bei gleicher Tiefe

Dieser zusätzliche Vergleich ist rein beschreibend. Die Differenz lautet jeweils V2_ROW minus AS_ORIGINAL und ersetzt den ursprünglichen H4-Kontrast nicht.

| Kanten | Delta F1 in PP | Delta EM in PP | Nur V2 EM richtig | Nur AS EM richtig | Paar fehlt |
| --- | --- | --- | --- | --- | --- |
| 30 | -1,44 | +0,00 | 2 | 2 | 0 |
| 60 | -4,18 | -3,33 | 1 | 3 | 0 |
| 100 | +1,92 | +1,67 | 3 | 2 | 0 |

## Gemeinsame Bewertung von Qualität und Aufwand

Die Tiefe wirkt nicht monoton auf die Antwortqualität. Mehr Goldoberflächen im Kontext führen nicht in jeder Ansicht und Tiefe zu höheren F1- oder EM-Werten. Gerade 60 Kanten verschlechtern einige Varianten gegenüber 30.

V2 zeilengenau erreicht bei 100 Kanten 18,15 % F1 und 13,33 % EM für bekannte Readerkosten von 0,05751372 USD. AutoSchemaKG original erreicht bereits bei 60 Kanten 19,39 % F1 und 15,00 % EM für 0,03346486 USD. Damit ist der Vorteil von V2 bei gleicher Tiefe 100 kein allgemeiner Qualitäts- oder Effizienzvorsprung gegenüber einer passend gewählten AutoSchemaKG-Konfiguration. Auch diese Gegenüberstellung beruht auf denselben Entwicklungsfragen und ist rein beschreibend.

Für V2 ist die höhere Tiefe ein Qualitätsgewinn mit mehr Readeraufwand gegenüber dem eigenen Top-30-Ausgangsstand. Die wesentlich höhere lexikalische Abdeckung geht nur mit einem kleinen Nettozuwachs exakter Antworten einher. Weitere Abdeckungsgewinne dürfen daher nicht automatisch als entsprechend große Gewinne der Antwortqualität ausgegeben werden.

## Zusätzlicher Q2-Aufwand

Die Kosten betreffen ausschließlich neue Readeraufrufe und die synthetische Zugangsprobe. Historische Konstruktion, Prüffilter und andere Versuche werden Q2 nicht zugerechnet. Bekannte Teilsummen mit unbekanntem Verbrauch sind kein vollständiger Istbetrag.

| Kanten | Neue archivierte Abschlüsse | Bekannte Zusatzkosten USD | Kosten unbekannt | Bekannte Eingabetokens | Bekannte Ausgabetokens |
| --- | --- | --- | --- | --- | --- |
| 30 | 0 | 0,00000000 | 0 | 0 | 0 |
| 60 | 480 | 0,27578672 | 0 | 1246572 | 1751 |
| 100 | 480 | 0,44504504 | 0 | 2014372 | 2140 |

**Neue natürliche Antworten:** bekannte Kosten 0,72083176 USD, 0 Abschlüsse mit unbekannten Kosten und 0 mit unbekannter Ausführung. 960 HTTP-Antworten sind beobachtet. Physische POSTs sind nicht unabhängig attestiert.

**Synthetische Zugangsprobe:** bekannte Kosten 0,00002706 USD, 0 Abschlüsse mit unbekannten Kosten und 0 mit unbekannter Ausführung. 1 HTTP-Antworten sind beobachtet. Physische POSTs sind nicht unabhängig attestiert.

Bekannte Gesamtkosten einschließlich Probe: 0,72085882 USD. Gebundene Gesamtexposition einschließlich Probe und ungelöster Reserven: 0,72085882 USD. Vorabreservierung für den vollständigen Lauf: 5,27741456 USD. Harter Deckel: 15,00000000 USD.

Lokale Vorbereitung: 2416,411 Sekunden. Wallzeit des neuen Readerlaufs einschließlich Probe: 293,939 Sekunden. Summe der erfassten Workerzeiten neuer natürlicher Antworten: 1128,998 Sekunden, Summe erfasster HTTP-Zeiten: 1094,873 Sekunden. Die lokale Vorbereitung umfasst die erneute Einbettung zur Reproduktion der alten Ranglisten und wird für Tiefe 60 und 100 gemeinsam genutzt. Sie ist experimenteller Reproduktionsaufwand, kein isoliert gemessener Zeitmehraufwand einer größeren Abruftiefe gegenüber Tiefe 30. Vier parallele Anfragen bedeuten, dass diese Summen keine Laufwallzeit und keine reine Modellzeit sind. Die alten Workerzeiten enthalten andere lokale Prüf- und Archivierungsarbeit und erlauben keinen unmittelbaren Geschwindigkeitsvergleich.

Bei technischen Dispatchfehlern können archivierte Abschlüsse unter der Zahl bearbeiteter Positionen liegen. Deren offene Reserven sind in der gebundenen Gesamtexposition enthalten. Rechnungsbetrag und reine providerinterne Modellzeit bleiben unbekannt.

Listenpreise laut regionaler Prüfung vom 2026-10-27: 0.22 USD je Million Eingabetokens und 0.88 USD je Million Ausgabetokens für Standard in eu-north-1. [Offizielle Preisseite](https://aws.amazon.com/bedrock/pricing/), regionale Datensätze und Hashbindungen in `price-verification.json`. Listenpreise sind keine bestätigte Rechnung.

## Reichweite und Nachweise

Je Tiefe liegt eine Realisierung vor. Temperatur 0 macht die Serie nicht zu einem Nachweis von Wiederholungsstabilität. Top 30 stammt aus dem früheren C6-Lauf, 60 und 100 aus dem neuen Lauf. Modellkennung und Parameter sind gebunden, eine unveränderliche providerseitige Gewichtsrevision ist nicht belegt. Die bekannten 60 Fragen sind Entwicklungsdaten für diese nachträgliche Wahl der Abruftiefen, keine neue ungenutzte Bestätigung.

Mehr Kanten verändern neben möglicher Goldverfügbarkeit auch Umfang und Ablenkung im Kontext. Der Vergleich trennt diese Wirkungen nicht kausal. Ein Antworttreffer beweist für sich keine quellenrichtige vollständige Mehrschrittbegründung. Die Tabellen zeigen sämtliche Ansichten und Tiefen unabhängig von der Richtung ihrer Punktwerte.

Öffentlicher Ergebnis-SHA256: `e3bbefb25074699a8d00639d210debd1d3cb2328b1fbb69e6fd6eed2e819722b`.  
Abdeckungs-SHA256: `96cb46af7a1bc83f85209516bfbd360c02a2181e59664ccd162f37e4d1133eec`.  
new_run: `9992feeb1342bcf42b3f8236e4a599e10ac86bd4bb10bfbcebf211cd11cb6ca8` (230562 Bytes).  
sealed_preparation: `718401c01916ff4bde4e58ea5ac47122dd290f26957a7bc893c3351c8c11d58e` (635022 Bytes).  
original_C6_result: `8131c58097903692195cf6405ac925d79bb5602b8862fdb488b507148fac773a` (665180 Bytes).  
coverage: `96cb46af7a1bc83f85209516bfbd360c02a2181e59664ccd162f37e4d1133eec` (18226 Bytes).  
N21: `4290e9599d76f7718862fe5a805c00c27adc1699da4fa835e96d71421d49a861` (4802 Bytes).  

Rohfragen, Goldantworten, Aliasse, Graphtexte, Einzelantworten und private Pfade werden nicht in diesem Bericht veröffentlicht.

## Neutraler Einbauvorschlag

Eine nachträgliche Sensitivitätsanalyse auf denselben 60 Fragen erhöhte bei unveränderten Graphen und unverändertem Antwortmodell die Abruftiefe von 30 auf 100 Kanten: Für V2 im zeilengenauen Export stieg der Antwort-F1 von 13,78 % auf 18,15 %, EM von 11,67 % auf 13,33 % und die Gold-/Aliasabdeckung aus Stützabsatzaussagen von 20 auf 33 von 60 Kontexten. Der explorative Einzellauf ändert H4 nicht und belegt keinen Vorsprung der Gesamtpipeline, da AutoSchemaKG mit 60 Kanten bereits 19,39 % Antwort-F1 und 15,00 % EM bei geringeren Readerkosten erreichte.
