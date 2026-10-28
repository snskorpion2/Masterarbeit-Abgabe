# C6: öffentliche Aggregate des einmaligen Abschlusses

Deskriptiver Vergleich auf dem festen 60er-Bestand mit gleichem Reader und lokaler Top-30-Suche. Die zehn Zellaggregate wurden unverändert aus der gebundenen bestandenen Endprüfung übernommen. Es erfolgten keine neue Auswertung, Neuberechnung, Endprüfung oder Modellaufrufe.

Eingefrorene Konfiguration: Reader `qwen.qwen3-235b-a22b-2507`, Temperatur 0, höchstens 256 Ausgabetokens, eine Antwort ohne Streaming. Lokaler Encoder `sentence-transformers/all-MiniLM-L6-v2`, Top-30-Graphkontext. Der vorab festgelegte H4-Kontrast ist V2_ROW minus AS_ORIGINAL. Seine inferenzstatistische Auswertung erfolgt getrennt in D1 und wird hier weder ersetzt noch vorweggenommen.

F1 ist der offizielle MuSiQue-Antwort-Token-F1, keine Tripel-F1. EM ist die exakte Übereinstimmung der normalisierten Antwort. Unter- und Obergrenzen begrenzen fehlende Antworten bei festem Nenner 60. Sie sind keine Konfidenzintervalle. Es gibt hier keine Signifikanz- oder allgemeine Überlegenheitsbehauptung.

| Zelle | Beobachtet / 60 | Fehlend | F1-Punktschätzer | EM-Punktschätzer | F1-Grenzen | EM-Grenzen |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| AS_ORIGINAL | 60 / 60 | 0 | 15.22 % | 11.67 % | 15.22 % bis 15.22 % | 11.67 % bis 11.67 % |
| AS_ROW | 60 / 60 | 0 | 15.13 % | 11.67 % | 15.13 % bis 15.13 % | 11.67 % bis 11.67 % |
| AS_G_ORIGINAL | 60 / 60 | 0 | 15.31 % | 11.67 % | 15.31 % bis 15.31 % | 11.67 % bis 11.67 % |
| AS_G_ROW | 60 / 60 | 0 | 15.13 % | 11.67 % | 15.13 % bis 15.13 % | 11.67 % bis 11.67 % |
| V1_ORIGINAL | 60 / 60 | 0 | 16.49 % | 13.33 % | 16.49 % bis 16.49 % | 13.33 % bis 13.33 % |
| V1_ROW | 60 / 60 | 0 | 16.53 % | 13.33 % | 16.53 % bis 16.53 % | 13.33 % bis 13.33 % |
| V2_ORIGINAL | 60 / 60 | 0 | 14.33 % | 11.67 % | 14.33 % bis 14.33 % | 11.67 % bis 11.67 % |
| V2_ROW | 60 / 60 | 0 | 13.78 % | 11.67 % | 13.78 % bis 13.78 % | 11.67 % bis 11.67 % |
| EMPTY_CONTROL | 60 / 60 | 0 | 1.67 % | 1.67 % | 1.67 % bis 1.67 % | 1.67 % bis 1.67 % |
| GOLD_PARAGRAPH_CONTROL | 60 / 60 | 0 | 46.35 % | 36.67 % | 46.35 % bis 46.35 % | 36.67 % bis 36.67 % |

Unabhängige Prüfung: 2 technische Versuche, 1 abgeschlossene Endprüfung. Der erste Versuch scheiterte technisch an der Pfaddarstellung. Genau ein ausdrücklich genehmigter CPU-Folgeversuch korrigierte ausschließlich deren kanonische Darstellung. Dateibytes und SHA256 des ursprünglichen Ergebnisses blieben unverändert. Originalfehlerbelege für Prüf- und Abschlussfehler sowie der erste Prüfauftrag blieben erhalten und sind über SHA256 gebunden. Keine neuen Modellaufrufe und keine neue Reader-Auswertung.

Leer- und Goldkontrollen wurden je einmal pro Frage ausgeführt. Sie sind keine Graphqualitätswerte. Es gab keine Quellenpassagen im Graphindex und keinen sekundären Passagenweg nach N6.

N5 bleibt eine nach dem ursprünglichen Einfrieren beschlossene Konstruktionsabweichung. Nicht auswertbare Guard-Fälle blieben ungeprüft im Graphen. EE/VV-Ausfälle und grundsätzlich ungeprüfte EV-Aussagen sind keine bestätigte Qualität. Diese Übernahme bewertet oder quantifiziert sie nicht neu. Es wurde keine Schemainduktion untersucht.

## Bekannte Aufwände und offene Größen

| Größe | USD |
| --- | ---: |
| Bekannte Reader-Listenpreiskosten | 0.15451260 |
| Davon bekannte Eingabekosten | 0.15258716 |
| Davon bekannte Ausgabekosten | 0.00192544 |
| Bekannte Zugangsprobe | 0.00002706 |
| Ungelöste Reservierung, keine bekannten Istkosten | 0.00000000 |
| Gebundene Gesamtexposition einschließlich Reserve und Probe | 0.15453966 |

Dies sind Reader- und Probenaufwände, keine vollständigen Pipelinekosten. Rechnungsbetrag und reine providerinterne Modellzeit sind unbekannt. Die maschinenlesbaren Belege erhalten diese Werte als null.

| Zeitgröße | Erfasst | Fehlend | Summe erfasster Sekunden |
| --- | ---: | ---: | ---: |
| HTTP-Einzelaufrufzeiten | 600 | 0 | 522.424 |
| Workerzeiten einschließlich lokaler Prüfung und Archivierung | 600 | 0 | 6900.883 |

HTTP-Zeiten enthalten Netz- und Serverwartezeit. Workerzeiten enthalten zusätzlich lokale Prüf- und Archivarbeit. Die Summen paralleler Einzelaufrufe sind weder gesamte Lauf-Wallzeit noch reine Modellzeit. Provider-Tokenzähler, technische Anzahlen und Anfragegrenzen aus HTTP-Archiven stehen in result.json. Physische POSTs sind nicht unabhängig attestiert.

Frage-IDs, Antworten, Gold, Quelltexte, Einzelannotationen, private Pfade und Einzelmetrikwerte werden nicht veröffentlicht.
