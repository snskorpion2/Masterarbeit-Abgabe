# Nachtrag 8 zur Vorregistrierung: Gesamturteil, Komponentenfamilie und Effizienz (25.10.2026)


**Nummerierung und Veröffentlichung:** Der zeitlich frühere Nachtrag 7 ist
`nachtrag_7_guard_ungueltige_antwort.md` zur ungültigen Guard-Antwort auf MuSiQue.
Der Inhalt des vorliegenden Gesamt- und Komponentenurteils wurde erstmals unter der
alten Nummer 7 mit Commit `3de7fce495c38124096c25418bedd7a8d0cf9d97` am
25.10.2026 veröffentlicht. Zur eindeutigen Trennung wird er nun vor
der aggregierten Auswertung als Nachtrag 8 geführt. Die Kriterien und der
nachstehende Vorab-Prüfvermerk bleiben dabei unverändert.

**Erklärte Datensicht des Erstentwurfs:** Der unter der alten Nummer 7 veröffentlichte
Entwurf bezeichnete die Festlegung als prospektiv vor der Auswertung natürlicher
C2-/C3-Urteilsverteilungen, C6-Antworten oder C7-Labels sowie vor deren Einsicht durch
die Koordination bzw. den Autor. Er nannte technische Zählungen, Kosten und die explorative
Strukturdiagnostik X1 ohne Urteile als bekannte Grundlagen. Dies ist die erklärte
damalige Sicht mit den nachstehenden Grenzen, keine aktuelle Blindheitsbestätigung.
Endpunkte, Nenner, Tests, Seeds und die primäre Holm-Familie aus G2 bleiben
**unverändert**. Dieser Nachtrag legt fest, (a) wie aus den primären
Tests ein Gesamturteil formuliert wird, (b) welche Komponentenkontraste als eigene, sekundäre
Testfamilie inferenziell geprüft werden, und (c) welche Effizienzmaße beschreibend berichtet werden.
Damit ist die spätere Formulierung im Manuskript vor Sicht der Ergebnisse gebunden.

**Vorabprüfung der Erstveröffentlichung am 25.10.2026:** Die Verantwortlichen für D1, C4, C6 und C7 sowie
die aktuelle C1-Untergruppe bestätigten aus ihrem bisherigen Vorgehen, dass sie keine aktuellen
natürlichen C2-/C3-Urteilsverteilungen, C6-Antworten oder C7-Labels ausgewertet haben.
Die bisherige D1-Ausführung verwendete ausschließlich synthetische Eingaben. Main hat technische
Zählungen, Kosten und Qualifikationskontrollen gelesen, aber keine natürliche Urteilsverteilung
berechnet. Die Aussagen betreffen die jeweils verantworteten Arbeitsbereiche, keine lückenlose
Rekonstruktion aller historischen Projektzugriffe.

Eine vollständige Ergebnisblindheit des Teams ist ausdrücklich **nicht** gegeben: Ein C2-/C3-Helfer
hatte nach einem technischen Stopp eine unprojizierte Abschlussdatei gelesen. Dabei wurden einzelne
natürliche C2-Urteilscodes und Begründungen sichtbar. Die gelesene Datei enthielt beide Achsen,
sichtbar gewordene C3-Inhalte sind nicht belegt. Nach seiner Tätigkeitsauskunft wurde keine natürliche
C2-/C3-Urteilsverteilung ausgewertet. Die Festlegung erfolgt vor der aggregierten natürlichen
Auswertung, nicht unter der Behauptung vollständiger Teamblindheit. Die obige Angabe zur Sicht von
Koordination und Autor ist die im Entscheidungsentwurf erklärte Sicht, keine unabhängig rekonstruierte
Zugriffshistorie dieser Beteiligten. Dieser Prüfvermerk ändert keine nachstehenden Kriterien.

**Stand der Umnummerierung und erneuten Veröffentlichung:** Nach der weitergeleiteten
Nutzerauskunft läuft inzwischen die menschliche Annotation für C7. Deshalb wird für
diesen Stand keine vollständige Ergebnisblindheit des Autors oder des Teams behauptet.
Die laufende Annotation ist von ihrer Zusammenführung mit den Modellurteilen und der
aggregierten Auswertung zu unterscheiden. Nach Tätigkeitsauskunft der zuständigen
Auswertung werden bisher ausschließlich synthetische Eingaben verwendet. Die
Veröffentlichung dieser Präzisierung erfolgt vor der dort gemeldeten aggregierten
natürlichen Auswertung. Der Publikationsverantwortliche hat dafür keine natürlichen
C2-/C3-Urteilsverteilungen, C6-Antworten oder C7-Labels geöffnet. Diese bereichsbezogenen
Angaben sind keine lückenlose Prüfung fremder Zugriffe. Die nachfolgenden Kriterien
werden durch diese Präzisierung nicht geändert.

## 1. Gesamturteil zur Pipeline (Primärkontrast V2, zeilengenau, gegen AutoSchemaKG, Originalexport)

Notation: ✓ = Holm-bestätigt nach G2 (H1, F1-H4: einseitig > 0, H2: Nichtunterlegenheit mit Grenze −5
Prozentpunkten). Das Urteil wird genau einer Stufe zugeordnet, geprüft in dieser Reihenfolge:

| Stufe | Bedingung | Vorgesehene Formulierung |
| --- | --- | --- |
| A | H1 ✓, H2 ✓, H4 ✓ | „V2 übertrifft AutoSchemaKG im untersuchten Versuchsraum auf allen drei primären Achsen.“ |
| B | H1 ✓, H2 ✓, H4 nicht ✓, obere 95-%-Grenze der F1-Differenz ≥ 0 | „V2 erhöht die Quellenstützung bei nicht unterlegenem Bedeutungserhalt. Ein QA-Vorteil ist nicht nachgewiesen.“ |
| C | H1 ✓, H2 ✓, obere 95-%-Grenze der F1-Differenz < 0 | „Höhere Quellenstützung bei erhaltenem Bedeutungsumfang, jedoch mit messbarem QA-Nachteil.“ |
| D | H1 ✓, H2 nicht ✓ | „Höhere Quellenstützung, Nichtunterlegenheit im Bedeutungserhalt nicht belegt (Zielkonflikt).“ Keine Überlegenheitsaussage. |
| E | H1 nicht ✓, H4 ✓ | „QA-Vorteil ohne nachgewiesenen Gewinn an Quellenstützung.“ |
| F | H1 nicht ✓, H4 nicht ✓ | „Kein Überlegenheitsnachweis im untersuchten Versuchsraum.“ |

**Herabstufung wegen Bewerterabhängigkeit** (gilt zusätzlich und wird ausdrücklich genannt): Ist Cohen-κ
zwischen Sol und der menschlichen Stichprobe (C7) kleiner als 0,40, oder zeigt Grok (C4) auf seiner
Stichprobe für den H1-Kontrast V2 gegen AS ein entgegengesetztes Vorzeichen des Punktschätzers, wird jede
Aussage zu H1 als „bewerterabhängig“ qualifiziert. Fehlt C4 oder C7, wird das als fehlende Gegenprüfung
genannt, nicht als Bestätigung.

Jede Formulierung wird auf den Versuchsraum begrenzt: insgesamt 24 Quellen, davon 20 neue Quellen
aus zwei Quellfamilien und vier versiegelte Primärquellen, Konstruktor DeepSeek-v3.2,
Prüffilter Kimi-K2.5, Bewerter Sol, 60 MuSiQue-Fragen. Die Klarstellung des Gesamtzählers
ändert weder die eingefrorene Quellenauswahl noch die Kriterien.

## 2. Sekundäre Komponentenfamilie (eigene Holm-Familie, m = 6)

Gleicher gepaarter Cluster-Bootstrap, gleiche Ziehungsmatrix und Seeds wie G2, einseitig, α = 0,05,
Holm nur innerhalb dieser Familie. Die primäre Familie wird davon nicht berührt. Der Export ist für H1 und
H2 irrelevant, denn beide messen Inventare.

| Kennung | Kontrast | Endpunkt | Hypothese |
| --- | --- | --- | --- |
| K1 | AS+G gegen AS | H1 Quellenstützung | Überlegenheit (> 0) |
| K2 | AS+G gegen AS | H2 Bedeutungserhalt | Nichtunterlegenheit (> −0,05) |
| K3 | V2 gegen V1 | H1 Quellenstützung | Überlegenheit (> 0) |
| K4 | V2 gegen V1 | H2 Bedeutungserhalt | Nichtunterlegenheit (> −0,05) |
| K5 | V1 gegen AS | H2 Bedeutungserhalt | Überlegenheit (> 0) |
| K6 | V1 gegen AS | H1 Quellenstützung | Nichtunterlegenheit (> −0,05) |

**Komponentenurteile:**
- **Prüffilter:** „verbessert die Quellenstützung bei erhaltenem Bedeutungsumfang“ für die jeweilige
  Basis, wenn K1 und K2 (Basis AS) bzw. K3 und K4 (Basis V1) bestätigt sind. Ist nur K1/K3 bestätigt, wird
  das als Zielkonflikt berichtet.
- **Extraktionserweiterung (SCOPE und gemeinsamer Ergänzungspass, nur gemeinsam beurteilbar):**
  „erhöht den Bedeutungserhalt ohne relevante Präzisionseinbuße“, wenn K5 und K6 bestätigt sind.
- **Export:** nur beschreibend über H3 (N2, A6/C5). Kein Test.
- **Schemainduktion:** Sie ist in beiden Armen das unveränderte Original-AS-Verfahren. Es gibt keinen
  Komponentenkontrast und **keine Aussage** über Schemaverbesserung.
- **H4-Komponentenkontraste** (AS+G gegen AS, V2 gegen V1, V1 gegen AS bei F1) nur beschreibend mit 95-%-KI.

## 3. Beschreibende Effizienzmaße (kein Test)

Je Arm und Population, aus K2-Ledgern und H1-Zählern:
- bekannte Listenpreiskosten bzw. Tokens je **quellengestützter** Aussage (Konstruktion plus
  gegebenenfalls Prüffilter, ohne gemeinsame Qualifikations- und Bewertungsaufwände),
- quellengestützte Aussagen je 1.000 Konstruktionstokens.

Unbekannte Kosten bleiben unbekannt und machen den betroffenen Wert unvollständig. Es wird keine
Effizienzüberlegenheit behauptet, wenn Kosten fehlen.

## 4. Darstellung

Eine Effektabbildung (Forest-Plot) zeigt alle primären und alle sechs Komponentenkontraste mit 95-%-KI,
Nichtunterlegenheitsgrenzen und gekennzeichneten Holm-Ergebnissen beider Familien getrennt. Die
Typaufteilung von H1 (EE/EV/VV) bleibt sekundär und beschreibend mit KI.
