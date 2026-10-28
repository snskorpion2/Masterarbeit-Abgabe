# X1: explorative Strukturdiagnostik

Stand: 25.10.2026. Rein beschreibend, nachträglich festgelegt, kein Test und keine Qualitätsbewertung. Keine C2-/C3-Urteile und keine neuen Modellaufrufe.

## Konstruktionsinventare

| Quellgruppe | Inventar | Pronomenformen n/N (%) | Nahezu wörtliche EV n/N (%) | Mittlere Entitätslänge |
|---|---|---:|---:|---:|
| Wikipedia | AS | 25/1836 (1,4) | 517/958 (54,0) | 2,39 |
| Wikipedia | AS+G | 25/1825 (1,4) | 517/958 (54,0) | 2,39 |
| Wikipedia | V1 | 59/2698 (2,2) | 935/1304 (71,7) | 2,76 |
| Wikipedia | V2 | 59/2679 (2,2) | 935/1304 (71,7) | 2,76 |
| Factbook | AS | 3/855 (0,4) | 62/319 (19,4) | 2,27 |
| Factbook | AS+G | 3/840 (0,4) | 62/319 (19,4) | 2,28 |
| Factbook | V1 | 3/1419 (0,2) | 77/636 (12,1) | 2,50 |
| Factbook | V2 | 3/1377 (0,2) | 77/636 (12,1) | 2,52 |
| Primärquellen, Prosa | AS | 4/198 (2,0) | 47/71 (66,2) | 2,55 |
| Primärquellen, Prosa | AS+G | 4/190 (2,1) | 47/71 (66,2) | 2,49 |
| Primärquellen, Prosa | V1 | 5/300 (1,7) | 51/106 (48,1) | 2,49 |
| Primärquellen, Prosa | V2 | 5/298 (1,7) | 51/106 (48,1) | 2,48 |
| Primärquellen, JSON | AS | 0/46 (0,0) | nicht anwendbar (JSON) | 2,00 |
| Primärquellen, JSON | AS+G | 0/46 (0,0) | nicht anwendbar (JSON) | 2,00 |
| Primärquellen, JSON | V1 | 2/124 (1,6) | nicht anwendbar (JSON) | 1,59 |
| Primärquellen, JSON | V2 | 2/123 (1,6) | nicht anwendbar (JSON) | 1,59 |

Einheit: eindeutige Entitätsbezeichnungen innerhalb jedes Quelle-Durchlauf-Inventars, nicht identifizierte reale Entitäten. Die Bezeichnungen werden nach NFKC und Vereinheitlichung der Leerzeichen, aber unter Erhalt der Großschreibung dedupliziert. EE-Kopf/-Ziel und sämtliche EV-Entity-Einträge zählen, Ereignistexte und Konzepte nicht. Der Mittelwert nutzt durch Leerraum getrennte Tokens, keinen Modelltokenizer. Aggregiert wird aus Summenzählern, nicht durch Mittelung von Prozentwerten.

Englische, sprachspezifische Wortlistendiagnose. Exakter Vergleich nach Kleinschreibung und Entfernen äußerer ASCII-Satzzeichen sowie Anführungszeichen. Auch pronominale Possessivformen sind enthalten. Eine Form wie 'that' kann auch anders verwendet sein. Mehrwortausdrücke zählen nicht als Treffer. Liste: `he her hers herself him himself his i it its itself me mine my myself our ours ourselves she that their theirs them themselves these they this those us we you your yours yourself yourselves`.

EV: jedes native EV-Ausgabevorkommen zählt einmal, auch wenn derselbe Ereignistext in mehreren Aussagen steht. Ähnlichkeit ist `difflib.SequenceMatcher(..., autojunk=False).ratio()` auf NFKC-, Leerraum- und kleinschreibungsnormalisierten Zeichenfolgen, mit Schwelle ≥ 0,9 zum ähnlichsten Quellsegment. Formel 2M/(Länge Ereignis + Länge Segment), M ist die Summe der vom Algorithmus gefundenen passenden Zeichenblöcke. Keine semantische Ähnlichkeit und keine Aussage über Abstraktion oder Richtigkeit.

Die Satzsegmentierung ist eine regelbasierte englische Näherung innerhalb nichtleerer Quellzeilen: Satzendezeichen mit folgendem Leerraum trennen, häufige Abkürzungen und Initialen sind geschützt. Nichtleere Überschriften und Factbook-Feldzeilen bleiben Kandidaten. Die vollständigen Regeln stehen in measure.py. Die beiden JSON-Primärquellen enthalten keine vergleichbar definierten Quellsätze und werden für diesen einen Anteil ausdrücklich als nicht anwendbar ausgewiesen. Keine automatische Umetikettierung in Prosa.

## Guard-Entfernungen

| Quellgruppe | Übergang | Typ | Ausgang N | Entfernt n (%) | Kopf | Ziel | Relation + Richtung | Einschränkung |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Wikipedia | AS→AS+G | EE | 840 | 29 (3,5) | 1 | 0 | 26 | 17 |
| Wikipedia | AS→AS+G | VV | 462 | 181 (39,2) | 0 | 6 | 180 | 64 |
| Wikipedia | V1→V2 | EE | 1116 | 34 (3,0) | 1 | 3 | 27 | 18 |
| Wikipedia | V1→V2 | VV | 400 | 127 (31,8) | 4 | 2 | 126 | 48 |
| Factbook | AS→AS+G | EE | 564 | 17 (3,0) | 0 | 0 | 11 | 11 |
| Factbook | AS→AS+G | VV | 192 | 40 (20,8) | 3 | 2 | 39 | 28 |
| Factbook | V1→V2 | EE | 998 | 49 (4,9) | 0 | 8 | 23 | 40 |
| Factbook | V1→V2 | VV | 156 | 32 (20,5) | 1 | 0 | 32 | 22 |
| Primärquellen, Prosa | AS→AS+G | EE | 93 | 13 (14,0) | 3 | 0 | 6 | 9 |
| Primärquellen, Prosa | AS→AS+G | VV | 38 | 11 (28,9) | 0 | 0 | 11 | 9 |
| Primärquellen, Prosa | V1→V2 | EE | 87 | 5 (5,7) | 0 | 0 | 1 | 4 |
| Primärquellen, Prosa | V1→V2 | VV | 35 | 6 (17,1) | 0 | 0 | 6 | 4 |
| Primärquellen, JSON | AS→AS+G | EE | 36 | 0 (0,0) | 0 | 0 | 0 | 0 |
| Primärquellen, JSON | AS→AS+G | VV | 12 | 4 (33,3) | 0 | 1 | 4 | 4 |
| Primärquellen, JSON | V1→V2 | EE | 109 | 1 (0,9) | 0 | 0 | 1 | 1 |
| Primärquellen, JSON | V1→V2 | VV | 7 | 1 (14,3) | 0 | 1 | 1 | 1 |

Die Facettenspalten zählen auslösende negative Facetten unter den entfernten Aussagen. Mehrfachnennungen sind möglich. Prozentverteilungen je Facette und ihre Nenner stehen in result.json. Relation und Richtung wurden gemeinsam gespeichert und lassen sich ohne neue Kodierung nicht trennen. AS und V1 haben selbst keine Guard-Stufe. EV ist von der Guard-Prüfung ausgeschlossen: alle EV-Entfernungen sind strukturell null.

Über alle 24 Quellen: **550 entfernte Aussagen, 810 auslösende negative Facetten, 239 Mehrfachfacettenfälle**. 753 EE-/VV-Aussagen blieben wegen Zitatfehlern ungeprüft erhalten. Behalten heißt nicht bestätigt. Dies sind gespeicherte Guard-Entscheidungen, keine extern bestätigten Fehler.

## Nachtrag (e): leere EV-Entitätslisten

Explorative Ergänzung derselben Ausgaben, keine Qualitätsbewertung. Gezählt wird jedes native EV-Vorkommen mit einer tatsächlich vorhandenen leeren Liste `value.Entity == []`. Nenner sind sämtliche nativen EV-Vorkommen, auch bei den JSON-Primärquellen. Ein fehlendes Feld oder ein anderer Datentyp bricht die Messung ab und zählt nicht als leere Liste.

| Quellgruppe | Inventar | Leere EV-Entitätslisten n/N (%) |
|---|---|---:|
| Wikipedia | AS | 23/958 (2,4) |
| Wikipedia | AS+G | 23/958 (2,4) |
| Wikipedia | V1 | 19/1304 (1,5) |
| Wikipedia | V2 | 19/1304 (1,5) |
| Factbook | AS | 8/319 (2,5) |
| Factbook | AS+G | 8/319 (2,5) |
| Factbook | V1 | 86/636 (13,5) |
| Factbook | V2 | 86/636 (13,5) |
| Primärquellen, Prosa | AS | 0/71 (0,0) |
| Primärquellen, Prosa | AS+G | 0/71 (0,0) |
| Primärquellen, Prosa | V1 | 0/106 (0,0) |
| Primärquellen, Prosa | V2 | 0/106 (0,0) |
| Primärquellen, JSON | AS | 0/24 (0,0) |
| Primärquellen, JSON | AS+G | 0/24 (0,0) |
| Primärquellen, JSON | V1 | 0/119 (0,0) |
| Primärquellen, JSON | V2 | 0/119 (0,0) |

Über alle 272 Inventare: **272/7074 (3,8 %)**. AS/AS+G und V1/V2 zählen als getrennte Inventare. EV bleibt in jedem der 136 Guard-Übergänge unverändert. Ohne diese Wiederzählung durch die Guard-Ansichten sind es in den 136 ursprünglichen AS-/V1-Inventaren 136/3537 (3,8 %).

Quellen und Durchläufe entsprechen (a)–(d): 12 Wikipedia- und 8 Factbook-Quellen mit je drei Durchläufen, zwei Prosa- und zwei JSON-Primärquellen mit je zwei Durchläufen. Die Familienwerte sind Summenzähler über die jeweiligen Quelle-Durchlauf-Inventare. Keine C2-/C3-Urteile, keine neuen Konstruktionen und keine Modellaufrufe.

## Population und Reproduktion

24 Quellen: Wikipedia 12, Factbook 8, andere Primärquellen 4 (NASA/NOAA Prosa, USGS/NWS JSON). Die ersten 20 besitzen je drei, die vier versiegelten Quellen je zwei Konstruktionsdurchläufe. Daher 68 Quelle-Durchlauf-Paare und 272 Inventare. Die zwei Exportformen werden nicht doppelt gezählt. Keine Main12-Entwicklungsausgaben, keine MuSiQue-Ausgaben, keine C2-/C3-Urteile.

Einstieg ist der endgültige technische Index aus C5, ausschließlich für den Zeiger auf die 136 kanonischen Konstruktionspaare. Pro Elternbestand werden die ursprünglichen Konstruktionsdaten, der zugehörige Guard-Grund und das endgültige gefilterte Inventar gelesen. Gefilterte Bestände werden gegen ursprüngliche stabile Record-IDs minus tatsächlich entfernte IDs geprüft. Eingabepins und quellweise Zahlen stehen in result.json, EV-Ähnlichkeiten mit Record-IDs und Segmenthashes in ev_similarity.jsonl. Keine Quelltexte werden kopiert.

Ausführung: `Experiments/.venv/Scripts/python.exe -B -X utf8 Experiments/fair_v2_oct24/X1/measure.py`. Die zugehörigen LaTeX-Fragmente gehören nicht zum öffentlichen Paket.
