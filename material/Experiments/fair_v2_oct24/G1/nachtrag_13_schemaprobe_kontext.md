# Nachtrag 13: explorative Schemaprobe „kontextgebundene Konzeptinduktion“ (25.10.2026)

**Status:** explorative Komponentenprobe für die Schemastufe. **Keine Änderung an V2**, denn die Pipeline bleibt
eingefroren. Festgelegt bevor Ausgaben der neuen Variante existieren. Gilt nur, wenn der Autor die Annotation
durchführt.

**Begründung:** Die Original-Entitätsaufgabe von AutoSchemaKG enthält bereits graphischen Nachbarschaftskontext.
Sie erhält jedoch nicht zusätzlich die hier ausgewählten Originalquellsätze. Mehrdeutige Namen können zu unpassenden
Konzepten führen. Frühere kleine Entwicklungsproben mit Kontextzugabe waren
gemischt (fünf Fälle). Diese Probe prüft die Frage auf einer zufälligen, größeren Stichprobe mit menschlichem Urteil.

## Bedingung

- **Stichprobe:** 60 Entitätsknoten, zufällig gezogen (Seed 2026102513) aus den AS-Inventaren der 20 Frischquellen,
  Durchlauf 1, geschichtet 36 Wikipedia und 24 Factbook.
- **Arm A:** die vorhandenen Original-Konzepte von AutoSchemaKG aus B3, unverändert.
- **Arm B:** dieselbe Original-Konzeptaufgabe mit identischem Modell und identischen Parametern (DeepSeek-v3.2, T 0,7),
  ergänzt nur um die Quellsätze, in denen die Entität vorkommt. Vorhandene Implementierung
  `Experiments/fair_comparison_oct23_v1/schema_context_s2.py` wiederverwenden, ein Lauf, kein Auswählen.
- **Annotation:** je Knoten beide Konzeptlisten nebeneinander, in zufälliger Reihenfolge und ohne Armkennung, mit dem
  Quellsatz. Je Konzept: „passender Typ im Kontext“, „unpassend“ oder „unklar“. Zusätzlich je Knoten eine Präferenz
  (links, rechts, gleich).

## Auswertung

- **Primär für diese Probe:** Präzision je Knoten (Anteil passender Konzepte), gepaart B gegen A, Wilcoxon-Vorzeichen-Rang-Test
  zweiseitig, α = 0,05, mittlere Differenz mit Bootstrap-KI (Seed 2026102514).
- **Sekundär:** Anteil der Knoten mit mindestens einem unpassenden Konzept (McNemar), Präferenzverteilung, Konzepte je
  Knoten, Aufteilung nach Quellfamilie.
- Explorativ, ohne Holm. Ein positiver Befund wird als Hinweis auf eine Verbesserungsmöglichkeit der Schemastufe
  berichtet, nicht als Eigenschaft von V2.

## Prospektive Ausführungspräzisierung S13

Diese Präzisierung und alle unten genannten Regeln werden zusammen mit N13 als
**genau ein Dateipfad** auf einem Remotecommit veröffentlicht, bevor die 60 Knoten
gezogen werden und bevor Arm B erzeugt wird. Vorhandene A-Artefakte sind bereits
vor dieser Festlegung vorhanden. Keine vollständige Verblindung gegenüber A oder
unabhängige Bestätigung einer vorab unbekannten Methode wird behauptet.

### Einheit, Quellenbezug und Auswahl

- Einheit ist ein originaler AS-Entitätsknoten, gebunden durch Quelle, Durchlauf 1
  und unveränderte originale GraphML-Knoten-ID. Keine nachträgliche Namensnormalisierung,
  keine zusätzlichen Vorkommensduplikate aus verschiedenen Relationszeilen.
- Die 20 Frischquellen sind die zwölf Wikipedia- und acht Factbook-Quellen von B3.
  Die vorhandenen AS-Konzeptanfragen ergeben 851 Entitätsknoten, davon 606 aus
  Wikipedia und 245 aus Factbook. Fehlende oder mehrdeutige Bindungen von
  Graphknoten, tatsächlicher Originalanfrage, Originalantwort und Quelltext sind
  technische Fehler und lösen keine stille Ersatzwahl aus.
- Für die verlangte Annotation mit Originalquellsätzen ist die vorab festgelegte
  Auswahlpopulation auf **759 quellenspannengebundene Knoten** beschränkt:
  543 Wikipedia und 216 Factbook. Das unveränderte Entitätslabel muss im Originaltext
  exakt, einschließlich Groß-/Kleinschreibung und mit Unicode-Wortgrenzen vorkommen.
  92 weitere Knoten (63 Wikipedia, 29 Factbook) besitzen diese Bindung nicht.
  Sie werden vor der Ziehung separat gezählt, nicht nach Sicht von B ersetzt.
  Weder Konzeptqualität, Konzeptzahl noch gewünschte Typen sind Auswahlkriterien.
- Innerhalb der beiden Familien werden 36 beziehungsweise 24 Knoten ohne Zurücklegen
  nach aufsteigendem SHA-256-Rang des kanonischen JSON
  `["S13-sample-v1",2026102513,family,source_id,original_node_id]` gewählt.
  Gleichstand wird durch `(source_id,original_node_id)` aufgelöst. Der vollständige
  vorab gebundene Populationsindex und seine Prüfsumme bleiben im privaten Nachweis.
  Es gibt keine Nachziehung. Die Aussage gilt für diesen begrenzten Auswahlrahmen,
  insbesondere nicht für paraphrasierte oder unaufgelöst referenzierte Knoten.
- Factbook-Kontext sind die nichtleeren originalen Feldzeilen mit der Nennung.
  Wikipedia-Kontext sind deterministische Abschnitte an Satzschlusszeichen
  `. ! ? 。 ！ ？` mit nachfolgenden Schlusszeichen/Leerraum und harten Zeilenumbrüchen.
  Liegt eine Grenze innerhalb der exakten Entitätsnennung, werden die berührten
  Abschnitte zu einem unveränderten Quellspan verbunden. Alle passenden Spans
  bleiben in Quellreihenfolge erhalten. Keine Längenkürzung, Aliaserfindung oder
  Koreferenzauflösung. Die Abschnitte sind eine technische Satznäherung, kein
  sprachwissenschaftlich annotierter Satzstandard.

### Einmalige Generierung und Verblindung

- A übernimmt die tatsächlich gespeicherte ursprüngliche Konzeptantwort und den
  ursprünglichen Komma-/Strip-/Kleinschreibungsparser. Doppelte oder leere
  Parser-Einträge werden nicht still entfernt. A wird nicht neu generiert.
- B verwendet `schema_context_s2.build_entity_sentence_request`. Die beiden
  ursprünglichen System-/Nutzernachrichten einschließlich des ursprünglichen
  Nachbarschaftskontexts bleiben byteinhaltlich unverändert. Dazwischen steht genau
  eine zusätzliche Nutzernachricht mit ausschließlich den oben gebundenen Quellsätzen
  als Daten. Der historische S2-Fünfslotauftrag mit ganzer Quelle, nativer Aussage
  und Rollenobjekt ist eine andere Bedingung und wird nicht für S13 ausgeführt.
- Tatsächliche explizite Parameter müssen in A und B übereinstimmen:
  `model=deepseek.v3.2`, `temperature=0.7`, `max_tokens=8192`, `stream=false`.
  Kein zusätzliches Sampling-, Reasoning-, Top-p-, Cache- oder Tariffeld.
  Endpunkt ist der bestehende AWS-Mantle-Zugang in `eu-north-1`, HTTP-Grenze 300 s.
  Effektive ausgelassene Dienststandards und geladene Gewichtsrevision bleiben
  unbekannt. Keine Übertragung einer Prüferzulassung auf diesen Konstruktor.
- Höchstens ein physischer POST je ausgewähltem Knoten und kein Wiederholen,
  Reparieren oder Auswählen einer zweiten Antwort. Vorhandene Antworten und
  Fehlversuche bleiben erhalten. Bei unbestätigtem Abschluss bleibt die Position
  fehlend. Ein Ausführungsfehler ist kein Qualitätsurteil.
- Die Zusatzgenerierung bleibt unter einem USD Listenpreisansatz. Verwendete
  Tokenpreise werden mit Datum/Quelle gebunden. Vor jedem POST muss der bekannte
  bisherige Aufwand plus konservative Eingabe-/maximale Ausgaberücklage unter
  dem Deckel bleiben. Unbekannte Usage behält die volle Rücklage. Kein Replay und
  kein anderer Anbieter oder Tarif zur Umgehung des Deckels. Ein Rechnungsbetrag
  wird nur bei vorhandenem Rechnungsbeleg behauptet.
- Die Annotationsreihenfolge ist ein eigener SHA-256-Rang mit Kennung
  `S13-order-v1` und demselben Seed. Links/rechts wird innerhalb jeder Quellfamilie
  nach dem getrennten Rang `S13-side-v1` ausgeglichen zufällig zugeordnet:
  18/18 Wikipedia und 12/12 Factbook. Konzeptreihenfolgen bleiben unverändert.
  Neutrale Fall-/Konzeptkennungen enthalten keine Armkennung. Die Zuordnung bleibt
  außerhalb der Annotations-HTML und ihres Exports.
- Die Seite zeigt Entität, Quellsätze und beide Listen, je Konzept die drei
  genannten Labels und pro Knoten links/rechts/gleich. Keine vorausgewählten
  Urteile. Ein passender Begriff muss einen im bereitgestellten Kontext
  zutreffenden Typ des Zielobjekts bezeichnen. Zutreffende breite Typen sowie
  kontextgebundene Berufs-/Funktionsrollen sind zulässig, bloße Themen oder
  lose assoziierte Gegenstände nicht. Bei nicht entscheidbarem Quellenkontext
  wird „unklar“ gewählt. Kein externes Nachschlagen. Die ursprüngliche AS-Aufgabe
  erlaubt auch verwandte Konzepte: Diese Typenprüfung misst daher bewusst eine
  engere Eigenschaft als vollständige Erfüllung des Originalauftrags.
- Teilstände sind exportierbar, aber keine fertige Auswertung. Endauswertung
  erfolgt erst nach dem tatsächlichen Export des Autors und vollständiger
  Bindung von Paket, Konzepttexten, neutralen Kennungen und privater Armzuordnung.
  Die HTML enthält weder bekannte Qualitätslabels noch Methodennamen. Unterschiedliche
  Listeneigenschaften können die Bedingung trotzdem erratbar machen.

### Festgelegte Auswertungsdetails

- Pro Knoten/Arm ist die Präzision `passend / Anzahl aller ursprünglichen
  Konzepteinträge`. „Unklar“ bleibt im Nenner und wird zusätzlich separat berichtet.
  Keine gewichtete Zusammenlegung aller Konzepte als primärer Schätzer.
  Leere Listen ohne Nenner, fehlende B-Antworten, fehlende Konzepturteile oder
  fehlende Präferenz sperren den endgültigen gepaarten Score. Sie erhalten weder
  künstliche null noch eins. Fehlende Generierung wird mit Ursache dokumentiert.
- Primärer Unterschied ist B minus A, nodegewichtet. Der zweiseitige
  Wilcoxon-Vorzeichen-Rang-Test verwendet auf zwölf Nachkommastellen gerundete
  Paardifferenzen, entfernt Nulldifferenzen (`zero_method=wilcox`), mittlere
  Ränge bei Bindungen und keine Kontinuitätskorrektur. Die Vorzeichenpermutation
  verwendet 100.000 Ziehungen, PCG64-Seed 2026102515, exakt falls der Raum kleiner
  ist. Bei ausschließlich Nulldifferenzen gilt ausdrücklich Statistik 0 und p=1.
  SciPy-/NumPy-Version und tatsächlich verwendeter Modus werden berichtet.
- Mittlere Differenz und 95%-Perzentilintervall verwenden die ungerundeten
  ursprünglichen Präzisionsanteile, 10.000 gepaarte Bootstrapziehungen,
  PCG64-Seed 2026102514, getrennte Ziehung in Wikipedia/Factbook mit den festen
  Familiengrößen 36/24, Quantile 2,5/97,5 mit linearer Interpolation.
- Mehrere Knoten derselben Quelle sind abhängig. Der primäre Knotentest ist
  deshalb bedingt explorativ. Zusätzlich wird ein ausdrücklich sekundäres
  quellenweises, familiengeschichtetes Clusterintervall berichtet: gezogene
  Quellen bringen jeweils alle zugehörigen Knoten mit, der Schätzer bleibt
  der Mittelwert aller gezogenen Knoten. Die Knotenzahl je Bootstrapziehung
  kann variieren. Keine größere unabhängige Quellenzahl daraus ableiten.
- McNemar ist der exakte zweiseitige Binomialtest der ungleichen Knotenpaare
  „mindestens ein unpassendes Konzept“, ohne Kontinuitätskorrektur. Gibt es
  keine ungleichen Paare, ist p=1. Präferenzen werden erst mit der privaten
  Links-/Rechtszuordnung als A/B/gleich ausgezählt. Konzeptzahl, Unklaranteil,
  Familien- und Quellenumfänge bleiben sichtbar. Keine Holm-Korrektur für diese
  explorative Probe, keine Bestätigung der eingefrorenen V2-Pipeline,
  kein Nachweis von Schemaabdeckung, funktionalem Schemanutzen oder Transfer.

### Reproduktion

Ausführung und Annotationswerkzeug liegen unter `S13/`. Der feste Vergleich
verwendet den ursprünglichen AutoSchemaKG-Komma-Parser und die Originalvorlagen
aus `Tools/ReferenceRepos/benchmark_autoschemakg_original/atlas_rag/`.
Der Veröffentlichungsnachweis, Code-/Eingabebindungen, Ziehung, einzelne
Aufrufbelege und neutrale Annotationspaketbindung werden vor dem jeweiligen
nachgelagerten Schritt unveränderlich gespeichert. Inhalte, Antwortbytes und
Armzuordnung bleiben lokal privat. Keine Schlüssel oder privaten Speicherpfade
werden in die öffentliche Vorregistrierung aufgenommen.

Vor der Ziehung gebundene Methodencodebytes (SHA-256):

- `S13/discovery.py`:
  `52f12e561d35c808cd36975b5594a45d75fbdfcceeefceabc74b21b89d3e44ff`
- `Experiments/fair_comparison_oct23_v1/schema_context_s2.py`:
  `40073c7015ef2de62c86a0cb4a1c0e6b2a3310e1d4af7bfefa012413919407f3`

Der AWS-Listenpreisansatz am 25.10.2026 beträgt für DeepSeek-v3.2 in Stockholm
0,74 USD je Million Eingabe- und 2,22 USD je Million Ausgabetokens
([AWS-Preistabelle](https://aws.amazon.com/bedrock/pricing/)). Die konservative
Aufrufrücklage verwendet UTF-8-Bytes des vollständigen serialisierten Requests
plus 512 als Eingabetokenoberansatz und die unveränderte Ausgabegrenze 8.192.
Das ist eine Planungsrücklage, keine tatsächliche Tokenmessung oder Rechnung.
Keine ausgewiesenen Cacheersparnisse werden vorab angerechnet.
