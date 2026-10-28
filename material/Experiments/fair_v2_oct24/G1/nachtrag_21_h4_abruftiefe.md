# N21: explorative Abruftiefe für den H4-Graphkontext

Festgelegt am 27.10.2026 nach dem abgeschlossenen H4-Lauf und der Diagnose
QA1, vor der Berechnung der tieferen Q2-Kontexte und vor jedem Q2-Aufruf.
H4-Antwortwerte und die geringe lexikalische Goldabdeckung bei Top 30 sind
bekannt. Dies ist eine nachträgliche Sensitivitätsanalyse, keine ursprüngliche
Vorregistrierung. H4, sein ursprünglicher Top-30-Kontrast, seine Testfamilie
und sämtliche Primärergebnisse bleiben unverändert.

## Einzige geänderte Bedingung

Die identischen acht endgültigen Graphansichten AS_ORIGINAL, AS_ROW,
AS_G_ORIGINAL, AS_G_ROW, V1_ORIGINAL, V1_ROW, V2_ORIGINAL und V2_ROW werden
für dieselben festen 60 MuSiQue-Fragen bei 60 und 100 statt 30 Kanten
abgerufen. Graphdateien, vollständige Aussagen, deren Reihenfolge bei
Gleichstand und der ausschließliche Graphpfad bleiben gleich. Keine neue
Konstruktion, Schemaänderung, Quellenpassage oder antwortgesteuerte Suche.

Encoder bleibt sentence-transformers/all-MiniLM-L6-v2, Revision
1110a243fdf4706b3f48f1d95db1a4f5529b4d41, CPU, float32, normalisiert.
Absteigende Skalarprodukte und aufsteigende Vorkommenskennung bei Gleichstand
entsprechen C6. Vor einer Serie müssen für alle 480 Frage-Graph-Paare die
neu berechneten ersten 30 Kanten und Modellanfragen exakt den gespeicherten
C6-Kontexten entsprechen. Bei Abweichungen kein stiller Ersatz und kein
Modellstart mit abweichender Rangliste.

Antwortmodell bleibt qwen.qwen3-235b-a22b-2507 am bisherigen AWS-Mantle-Endpunkt
eu-north-1, Temperatur 0, höchstens 256 Ausgabetokens, n=1, kein Streaming.
Prompts, Ausgabeparser und offizielle MuSiQue-Alias-F1-/EM-Auswertung bleiben
unverändert. Kein zusätzliches top_p, kein Antwortnachbearbeiten. Eine
unveränderliche providerseitige Gewichtsrevision ist historisch nicht belegt.
Die neuen Tiefen werden gemeinsam nach Frage, dann Graphansicht, dann Tiefe
60/100 abgearbeitet. Höchstens vier unabhängige Anfragen gleichzeitig.

## Vergleich und Endpunkte

Top 30 verwendet unverändert die 480 vorhandenen C6-Antworten. Es werden
höchstens 960 neue natürliche Antworten erzeugt. Die bestehenden Leer- und
Goldkontrollen bleiben historische Referenzen und werden nicht wiederholt.
Eine einzelne synthetische Zugangsprobe mit denselben Parametern ist erlaubt
und im Q2-Aufwand enthalten. Alle Graphkontexte werden vor Zugriff der
Q2-Auswertung auf Goldantworten und Stützabsatzkennungen eingefroren.

Für jede der acht Ansichten und jede Tiefe: Antwort-Token-F1 und normalisierte
Exact Match mit festem Nenner 60, beobachtete und fehlende Antworten sowie
Differenzen gegen die gespeicherte Tiefe 30. Technisch fehlende Antworten
bleiben unbekannt, mit Identifikationsgrenzen statt künstlichen Nullwerten.
Zusätzlich werden gewonnene und verlorene EM-Treffer paarweise beschrieben.
Keine neuen Hypothesentests, p-Werte oder Auswahl eines neuen H4-Endpunkts.

Goldabdeckung folgt unverändert dem nachträglichen QA1-Oberflächenproxy:
normalisierte vollständige Gold-/Alias-Tokenfolge innerhalb einer einzelnen
abgerufenen Aussage mit Herkunft aus einem zugehörigen Stützabsatz.
Breitere Treffer ohne Herkunftsbedingung werden separat ausgewiesen.
Fragetext zählt nicht als Graphbeleg. Top-30-Abdeckung muss QA1 reproduzieren.
Lexikalische Verfügbarkeit beweist weder vollständige Mehrschrittstützung
noch tatsächliche Modellnutzung oder semantischen Quellenrecall.

## Aufwand, Fehler und Abschluss

Harter zusätzlicher Q2-Deckel: 15 USD AWS einschließlich Zugangsprobe,
Fehlversuchen und konservativer Reserven für unbekannten Verbrauch.
Vor dem ersten Aufruf wird der gesamte geplante Lauf konservativ reserviert.
Tokens, physische HTTP-Beobachtungen, Laufzeit und Listenpreiskosten werden
gesondert berichtet. Listenpreise sind keine Rechnungsbestätigung und keine
Gesamtkonstruktionskosten. Unbekannte Größen bleiben unbekannt.

Je logischer Antwort genau ein Versuch, keine automatischen Wiederholungen,
kein Anbieter-/Modellwechsel. Fehler und unbekannte Abschlüsse werden
archiviert. Bei einem solchen Abschluss stoppt die Aufnahme neuer Anfragen,
bereits laufende Anfragen werden nur noch beendet und gesichert. Kein
Neusenden verbrauchter Kennungen. Kosten- oder Kontextgrenzenverletzung,
veränderte Eingaben und Archivierungsfehler stoppen ebenfalls die Serie.

Der Bericht enthält alle acht Ansichten und beide neuen Tiefen unabhängig
von der Ergebnisrichtung, einschließlich Mehrkosten und Gegenbefunden.
Berichtsziel 27.10. bis 15:30, Annahmefrist 16:30 Ortszeit gemäß aktueller
README. Unfertige Ergebnisse werden nicht als abgeschlossener Befund zum
Einbau empfohlen. Rohfragen, Goldwerte, Graphkontexte und Einzelantworten
bleiben privat. Öffentlich sind nur geprüfter Code, Hashbindungen und Aggregate.
