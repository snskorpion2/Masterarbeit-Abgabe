# T1 – explorativer Transfer auf Qwen3-235B

Abgeschlossen ist die beauftragte Konstruktion, Filteranwendung und beschreibende Strukturmessung. Eine Quellenstützungs- oder Bedeutungserhaltsbewertung mit Sol oder Grok wurde nicht gestartet. Die Strukturzahlen und Filterentfernungen belegen für sich keinen Qualitätsgewinn und keine Modellübertragung der Hauptbefunde.

## Bedingung und Ablauf

Nachtrag 9 wurde vor dem ersten T1-Modellaufruf als einziger Pfad mit Commit `16640bbbf88500cbf0a14f9f1963b1924a759cb3` veröffentlicht. Der lokale gemeinsame Git-Stand und Index blieben dabei unverändert. Der Remote-Bytevergleich ist in `publication.json` dokumentiert.

20 Frischquellen aus A4, zwölf Wikipedia- und acht Factbook-Quellen, ein Durchlauf je AS-/V1-Arm. Konstruktor und originale Schemainduktion verwenden `qwen.qwen3-235b-a22b-2507` über Mantle, Temperatur 0,7, Ausgabegrenze 8.192 Tokens. Die vorhandenen B3-Prompts, Parser, Segmentierung und sonstigen Modellparameter werden durch die T1-Modellanbindung wiederverwendet. Die vier versiegelten Quellen und B2-Referenzinhalte sind nicht Teil dieses Laufs.

Native Konstruktion und Schemainduktion: 40/40 Elternbestände. Strukturmessung: 80/80 Inventare über AS, AS+G, V1 und V2. Alle exportierten Vergleichszellen verwenden die zeilengenaue Darstellung.

Der Prüffilter verwendet unverändert Kimi-K2.5, Temperatur 0, Ausgabegrenze 16.384 und höchstens zehn EE-/VV-Aussagen je Gruppe mit vollständigem Quellkontext und Inventar. EV bleibt unverändert und ist für den Prüffilter nicht anwendbar. Eine ungültige vollständig empfangene Gruppenantwort führt zur unveränderten Übernahme des ganzen Quellkontexts als ungeprüft. Netz-/Timeout-/unbekannte Versuche folgen der markierten Einmalgrenze aus Nachtrag 2. Vollständige vertragsungültige Joint-Antworten folgen Nachtrag 5 ohne neue Generierung.

Joint-Fallbacks nach Nachtrag 5: **0/20 V1-Konstruktionen**. Prüffilter-Elternbestände mit ausschließlich strukturell gültigen Gruppen: **40/40**. Vollständige Prüffilterbeurteilung einschließlich Zitatbindung: **6/40**. Ein konservativ beibehaltener ungeprüfter Bestand zählt nicht als erfolgreich geprüft.

## Strukturgrößen und Entfernungsraten

Die vollständigen Tabellen mit Zählern und Nennern stehen in [STRUKTURBERICHT.md](STRUKTURBERICHT.md), die maschinenlesbaren Werte in [structure_metrics.json](structure_metrics.json). Die X1-Definitionen bleiben unverändert. Facettenraten beziehen sich auf den ursprünglichen Bestand der jeweiligen Aussageart. Zusätzlich wird die Facettenverteilung unter entfernten Aussagen ausgegeben. Mehrere auslösende Facetten pro Aussage sind möglich. Relation und Richtung bilden die vorhandene gemeinsame Facette. Ungeprüfte Zitat-, Struktur- und sonstige Fälle bleiben getrennt.

## Aufwand

| Modell | reservierte einzelne Versuche | gemeldete Eingabetokens | gemeldete Ausgabetokens | ohne vollständige Usage |
|---|---:|---:|---:|---:|
| qwen.qwen3-235b-a22b-2507 | 7413 | 2812261 | 259965 | 0 |
| moonshotai.kimi-k2.5 | 243 | 2694783 | 933553 | 0 |

Gemeinsamer T1-Deckel: **20 USD AWS**. Bekannter Standard-Listenpreisaufwand: **6.14850118 USD**. Zusätzliche Reserve für unbekannte/offene Kosten: **0 USD**. Anbieterrechnung und verifizierter Rabatt bleiben unbekannt. Die Zugangsprobe zählt zum selben Deckel. Die Hauptbestände und die C1-Kostenverwaltung werden nicht zurückgesetzt oder verändert.

Listenpreise pro Million Tokens: Qwen 0,22 USD Eingabe / 0,88 USD Ausgabe aus der bereits gepinnten regionalen B1-Preisgrundlage, Kimi 0,72 / 3,60 USD aus der unveränderten C1-/A3d-Grundlage. Alle Eingabetokens werden konservativ zum Standardpreis angesetzt, ohne Cache-Rabatt. Reservierungen und bestätigte physische POSTs sind unterschiedliche Größen. Fehlende Usage wird nicht zu Null ergänzt.

## Grenzen und Nachweise

Dies ist eine explorative Bedingung mit einem Durchlauf je Arm. Es gibt hier keine H1-/H2-Schätzer, keine Bootstrapintervalle, keine Holm-Korrektur und keine Qualitätsrangfolge. Eine spätere Sol-Bewertung benötigt die gesonderte Entscheidung nach Abschluss von C2/C3. Nicht explizit gesetzte Modellvoreinstellungen und die genaue Gewichtsrevision werden nicht als kontrolliert behauptet.

Die Rohantworten, Quellenbindungen, ursprünglichen Inventare, Schemaartefakte und Prüffilterbelege liegen im eigenen privaten T1-Paket. Die öffentlichen lokalen Ergebnisdateien enthalten die zugehörigen Pfad-/Hashbindungen. Technische Anpassungen vor dem ersten Quell-HTTP-Aufruf sind in `technical-repairs.json` mit erhaltenen Originalbelegen getrennt dokumentiert. Die betroffenen ursprünglichen SDK-Unbekannt-Platzhalter werden nicht umgeschrieben.

Belege: `publication.json`, `access-probe.json`, `construction-result.json`, `result.json`, `structure_metrics.json`, `cpu-final.xml` und die darin referenzierten privaten T1-Laufartefakte.
