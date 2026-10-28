# T1 – beschreibende Strukturdiagnostik

Explorative Transferbedingung nach Nachtrag 9. Unveränderte X1-Definitionen, keine Qualitätsbewertung, keine Sol-/Grok-Bewertung und kein inferenzstatistischer Test.

Population: 20 A4-Frischquellen, 80/80 verfügbare Inventare. Nur zeilengenauer Export. Fehlende Zellen bleiben fehlend. Summenzähler und Anteile beziehen sich ausdrücklich auf die beobachteten Inventare.

## Strukturgrößen

| Familie | Arm | Inventare beob./geplant | Pronomen n/N (%) | Mittlere Entitätslänge | EV-Satznähe n/N (%) | Leere EV-Listen n/N (%) |
|---|---|---:|---:|---:|---:|---:|
| wikipedia | AS | 12/12 | 0/952 (0,0) | 2.81 | 192/357 (53,8) | 0/357 (0,0) |
| wikipedia | AS+G | 12/12 | 0/941 (0,0) | 2.79 | 192/357 (53,8) | 0/357 (0,0) |
| wikipedia | V1 | 12/12 | 0/1111 (0,0) | 2.63 | 206/387 (53,2) | 0/387 (0,0) |
| wikipedia | V2 | 12/12 | 0/1101 (0,0) | 2.62 | 206/387 (53,2) | 0/387 (0,0) |
| factbook | AS | 8/8 | 1/816 (0,1) | 2.55 | 11/320 (3,4) | 0/320 (0,0) |
| factbook | AS+G | 8/8 | 1/809 (0,1) | 2.54 | 11/320 (3,4) | 0/320 (0,0) |
| factbook | V1 | 8/8 | 1/829 (0,1) | 2.56 | 16/392 (4,1) | 0/392 (0,0) |
| factbook | V2 | 8/8 | 1/820 (0,1) | 2.55 | 16/392 (4,1) | 0/392 (0,0) |

Entitäten: je Quellinventar eindeutige NFKC-/Leerraum-normalisierte EE-Endpunkte und EV-Teilnehmer. Pronomen: unveränderte englische X1-Wortliste, keine Erkennung realer Entitäten. Länge: Leerraumtokens. EV-Satznähe: unveränderte regelbasierte Segmentierung und Zeichenähnlichkeit mindestens 0,9, keine semantische Metrik. Leere EV-Listen: vorhandene `Entity == []`; fehlende Felder und andere Datentypen werden nicht als leer gezählt.

## Guard-Entfernungen

| Familie | Übergang | Typ | Eltern beob./geplant | Entfernt n/N (%) | Ungeprüft Zitat/Struktur/sonst | Kopf n/N (%) | Ziel n/N (%) | Relation + Richtung n/N (%) | Einschränkung n/N (%) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| wikipedia | AS→AS+G | EE | 12/12 | 17/381 (4,5) | 37/0/0 | 0/381 (0,0) | 2/381 (0,5) | 12/381 (3,1) | 11/381 (2,9) |
| wikipedia | AS→AS+G | EV | 12/12 | nicht geprüft (N=357) | nicht anwendbar | — | — | — | — |
| wikipedia | AS→AS+G | VV | 12/12 | 97/240 (40,4) | 38/0/0 | 1/240 (0,4) | 4/240 (1,7) | 96/240 (40,0) | 16/240 (6,7) |
| wikipedia | V1→V2 | EE | 12/12 | 24/432 (5,6) | 18/0/0 | 4/432 (0,9) | 11/432 (2,5) | 22/432 (5,1) | 16/432 (3,7) |
| wikipedia | V1→V2 | EV | 12/12 | nicht geprüft (N=387) | nicht anwendbar | — | — | — | — |
| wikipedia | V1→V2 | VV | 12/12 | 86/193 (44,6) | 15/0/0 | 0/193 (0,0) | 4/193 (2,1) | 85/193 (44,0) | 13/193 (6,7) |
| factbook | AS→AS+G | EE | 8/8 | 11/385 (2,9) | 86/0/0 | 0/385 (0,0) | 1/385 (0,3) | 4/385 (1,0) | 9/385 (2,3) |
| factbook | AS→AS+G | EV | 8/8 | nicht geprüft (N=320) | nicht anwendbar | — | — | — | — |
| factbook | AS→AS+G | VV | 8/8 | 46/121 (38,0) | 26/0/0 | 1/121 (0,8) | 6/121 (5,0) | 43/121 (35,5) | 13/121 (10,7) |
| factbook | V1→V2 | EE | 8/8 | 15/429 (3,5) | 124/0/0 | 0/429 (0,0) | 1/429 (0,2) | 6/429 (1,4) | 13/429 (3,0) |
| factbook | V1→V2 | EV | 8/8 | nicht geprüft (N=392) | nicht anwendbar | — | — | — | — |
| factbook | V1→V2 | VV | 8/8 | 29/90 (32,2) | 25/0/0 | 0/90 (0,0) | 5/90 (5,6) | 28/90 (31,1) | 12/90 (13,3) |

Facetten zählen auslösende negative Facetten unter den entfernten Aussagen. Mehrfachzählungen sind möglich. Der Nenner N der Facettenraten in der Tabelle ist der ursprüngliche Bestand des jeweiligen Typs vor dem Filter, einschließlich ungeprüft erhaltener Aussagen (`trigger_facet_share_of_original`). Die JSON-Datei enthält zusätzlich die Ursachenverteilung unter den entfernten Aussagen mit der Anzahl entfernter Aussagen als Nenner (`trigger_facet_share_of_removals`). Beide Anteile werden aus Summenzählern berechnet, nicht als Mittelwert von Quellquoten. Relation und Richtung sind gemeinsam gespeichert und werden nicht nachträglich getrennt. EV ist nicht Gegenstand des Prüffilters. Bei den ungeprüften Fällen bezeichnet Struktur einen belegten Fehler einer vollständig bekannten Antwort. Transport-, Provider-, Abbruch-, Budget- und fehlende Gruppenfälle stehen unter sonst. Maßgeblich ist die letzte gewählte Beobachtung des Quellkontexts, nicht ein durch einen späteren Versuch ersetzter Fehler. Behaltene ungeprüfte Aussagen sind keine bestätigten Aussagen. Gültig beurteilte, aber unbestimmte Aussagen stehen gesondert in der JSON-Datei.

Die beiden gefilterten Ansichten zählen in der Strukturdiagnostik erneut als Inventare, Guard-Anwendung und Aufwand werden je AS-/V1-Elternbestand nur einmal gezählt. Die unverdoppelten und alle Inventare umfassenden Zähler leerer EV-Entitätslisten sind im JSON gesondert ausgewiesen. Es wurden keine Goldreferenzen, versiegelten Quellen oder Bewertungen geöffnet.
