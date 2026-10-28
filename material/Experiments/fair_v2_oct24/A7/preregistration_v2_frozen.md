# Vorregistrierung V2 – eingefrorener G2-Vertrag

Zeitpunkt UTC: **2026-10-24T19:08:35.371395+00:00**. Europe/Berlin: **2026-10-24T21:08:35.371395+02:00**.
Die verbindliche maschinenlesbare Fassung steht in `preregistration_v2_frozen.json`.
Beide Dateien bilden einen Vertrag. Gültig für Folgebewertungen erst nach Veröffentlichung
des eigenen Zwei-Dateien-Commits `Friere Vorregistrierung V2 ein`. Dessen Hash ist der Nachweis.
Die A7-Entwürfe bleiben unverändert. Nachträgliche Änderungen benötigen einen getrennten
datierten Nachtrag und eine Erklärung, ob betroffene Ergebnisse bereits bekannt waren.

## Zusammenfassung für das Manuskript (höchstens eine Seite)

Der vorab festgelegte Vergleich prüft V2 gegen AutoSchemaKG unter demselben Konstruktormodell DeepSeek-v3.2. V2 kombiniert Original-EE, eingegrenzte EV-/VV-Anweisungen und einen gemeinsamen Ergänzungspass mit der ursprünglichen Schemainduktion, einer Quellenprüfung ganzer EE-/VV-Aussagen und einem zeilengenauen Export. EV bleibt durch die Quellenprüfung unverändert. Der Kimi-K2.5-Guard entfernt ganze Aussagen, ohne sie umzuschreiben oder neue Fakten einzufügen. Seine Entwicklung und bekannte Teilverluste werden offengelegt.

Vier Bestände – AS, AS mit Guard, V1 und V2 – werden jeweils mit Originalexport und zeilengenauem Export untersucht. Primär ist V2 mit zeilengenauem Export gegen AS mit Originalexport. Für Quellenstützung und ausgewählten Bedeutungserhalt dienen vier versiegelte Quellen mit je zwei Konstruktionen und 20 neue Quellen mit je drei Konstruktionen pro Ausgangsarm. Die neuen Quellen umfassen zwölf Wikipedia-Texte und acht Factbook-Auszüge. Die 200 vorab gebundenen Referenzbedeutungen messen ausgewählten Erhalt, keinen vollständigen Quellenrecall. Main12 bleibt Entwicklungsmaterial, weil V2 nach Sicht der V1-Ergebnisse gewählt wurde.

H1 prüft den Anteil vollständig quellengestützter ganzer Ausgabevorkommen. H2 prüft vollständig erhaltene Referenzbedeutungen mit fünf Prozentpunkten Nichtunterlegenheitsgrenze. Unklare und technisch fehlende Urteile erhalten in beiden Armen den numerischen Primärwert null. Ihre ursprünglichen Zustände bleiben erhalten, Fehlwertquoten und Identifikationsschranken werden gesondert berichtet. Mehr als zehn Prozent Fehlwerte eines Arms werden als Einschränkung genannt. Alle vier Bestände werden für H2 direkt bewertet.

H4 prüft auf verbindlich 60 MuSiQue-Fragen graphbasierte Antworten, primär mit offiziellem F1, sekundär mit Exact Match. Beide Arme konstruieren hier Instanzgraphen ohne Schemainduktion. Derselbe Qwen-Reader erhält ausschließlich die 30 höchstbewerteten Graphkanten. Die Auswahl von 60 Fragen ist eine ausdrückliche Nutzerentscheidung nach technisch unvollständigem Kostenpilot. Sie wird nicht als abgeschlossene Kostenhochrechnung ausgegeben.

Die Auswertung mittelt zuerst Wiederholungen je Quelle und gewichtet Quellen gleich. Gepaarte Cluster-Bootstraps verwenden 10.000 Ziehungen, Wilcoxon dient der Quellen-Sensitivität und McNemar der sekundären EM-Prüfung. Holm korrigiert ausschließlich H1, H2 und H4. H3-Exportdeckung und verschiedene gestützte Aussagen sind sekundär und beschreibend. Sol bewertet primär, Grok kontrolliert eine feste Stichprobe. Eine verblindete menschliche Stichprobe von 150 Aussagen prüft die Übereinstimmung mittels Cohen-κ. Ergebnisse begründen höchstens Aussagen für die untersuchten Texte, das Konstruktormodell und die gebundenen Bedingungen.

## Festgelegter Versuchsraum

Der Primärkontrast lautet **V2_ROW minus AS_ORIGINAL**. Die acht Zellen sind:

| Bestand | Originalexport | Zeilengenauer Export |
| --- | --- | --- |
| AutoSchemaKG | AS_ORIGINAL | AS_ROW |
| AutoSchemaKG mit Guard | AS_G_ORIGINAL | AS_G_ROW |
| V1 | V1_ORIGINAL | V1_ROW |
| V1 mit Guard = V2 | V2_ORIGINAL | V2_ROW |

Die Quellenbasis umfasst 24 Quellen und 68 gepaarte Quelle-Durchlauf-Einheiten,
also 136 eigenständige AS-/V1-Konstruktionen. Gefilterte und Exportzellen sind abhängige
Ableitungen. Durchläufe werden zunächst innerhalb jeder Quelle gemittelt, dann werden
die 24 Quellen gleich gewichtet. Wiederholungen und Ausgabemengen vergrößern nicht
die Zahl unabhängiger Quellen. Quellenfamilie, Kohorte und EE/EV/VV werden getrennt berichtet.
Ein Konstruktormodell und mehrere Bewerterfamilien beweisen keinen Konstruktortransfer.

### Pipeline und Eingriff

AS verwendet unveränderte Original-EE-/EV-/VV-Prompts, Parser und Schemainduktion.
V1 verwendet Original-EE, SCOPE für EV/VV und genau einen gemeinsamen Ergänzungspass,
danach dieselbe ursprüngliche AS-Schemainduktion. V2 wendet anschließend ausschließlich
`c1_guard.make_facet_guard(completion, max_statements=10)` an, danach A8-Teilmenge
und zeilengenauen Export. `guard()` und `make_guard()` sind nicht der gewählte Einstieg.
Der Guard prüft EE/VV, EV bleibt Kontext und unverändert. Keine Ergänzung, Umschreibung,
Identitätsfusion, neue Schemainduktion oder gezielte Domänen-/Relationswortliste.
Jede Guardgruppe sieht dieselbe vollständige Quelle und den vollständigen ursprünglichen Bestand.
Der Callback verwendet Kimi-K2.5, T0, 16.384 Ausgabetokens, 300 Sekunden und keine
Wiederholung oder Zitatreparatur. Technisches Scheitern ist kein positiver Quellenbefund.

Die Entwicklung A3/A3b/A3c und die bekannten natürlichen Gegenbefunde/Teilverluste
bleiben sichtbar. A3d prüft ein bekanntes Entwicklungsgate, keine neue natürliche
Bestätigungsstichprobe. Guard und unabhängige Quellenbewerter gehören unterschiedlichen
Familien an. A8 erlaubt strukturelle Projektion, ausdrücklich keine allgemeine exakte
Offline-Ableitung von H2. Nur `active_cell(...)` darf C3 und den aktiven Verbrauchern
übergeben werden. Private Wiederherstellungscontainer sind keine Bewertungs- oder Readerinputs.

## Hypothesen, Zähler und Nenner

Für Quelle s, geplanten Durchlauf d und Zelle c bezeichnen S vollständig gestützte
Vorkommen, F aufgelöst nicht gestützte und M unklare/technisch fehlende Urteile.
N=S+F+M umfasst alle vorhandenen ganzen Vorkommen, einschließlich Duplikaten.

| Endpunkt | Zähler | Nenner und Primärscore | Status |
| --- | --- | --- | --- |
| H1 | S: unabhängig als vollständig gestützt bewertete ganze Vorkommen | alle N behaltenen EE/EV/VV-Vorkommen, S/N | primär, Differenz >0 |
| H2 | K: vollständig bestätigte Referenzbedeutungen | alle vorab fixierten R_s, K/R_s | primär, Differenz >−0,05 |
| H3 | C: A6-konform direkt repräsentierte native Vorkommen | alle vor Export behaltenen N, C/N | ausschließlich sekundär beschreibend |
| H4 | Summe des offiziellen maximalen Alias-F1 je Frage | alle Q=60 fixierten Fragen | F1 primär, EM sekundär |

H1/H2 werten unklare und technisch fehlende **Urteile** in beiden Armen numerisch als
null. Das bedeutet nicht, dass ihre Aussage in der Welt falsch wäre. Rohcodes bleiben
erhalten. H1 vergibt nur für `supported` eins, H2 nur für `retained` eins. Gemischte
ganze Aussagen und teilweise erhaltene Bedeutungen erhalten null, ihre richtigen Teile
und Verluste werden separat ausgewiesen. Die genaue unveränderte Rohcodetabelle und
ihre Abbildung stehen unter `evaluators.shared` der JSON-Fassung.

Pro Arm werden M/N beziehungsweise M/R sowie die Quellverteilung berichtet. Eine Quote
über 10 Prozent wird ausdrücklich als Einschränkung genannt. Die Sensitivitätsintervalle
sind [S/N,(S+M)/N] und [K/R,(K+M)/R]. Die Differenzgrenzen
Δ_L=L_V2−U_AS und Δ_U=U_V2−L_AS dienen ausschließlich der Sensitivität.
**Δ_L ist kein Primärschätzer und kein Primärtest.**

Ein leerer oder unbekannter nativer Nenner wird weder null noch 100 Prozent.
Ohne definierten Nenner ist der vollständige geplante H1-Vergleich nicht testbar,
statt die Quelle still zu streichen. H2 behält feste Referenznenner und numerisch
konservative Primärwerte, auch wenn das Inventar fehlt. Unvollständigkeit bleibt im
Rohstatus sichtbar. Ein gelöschter Einzelzeuge beweist keinen vollständigen Verlust.
**C3 bewertet AS, AS+G, V1 und V2 direkt**, verblindet und gemischt, anhand des vollständigen
jeweiligen aktiven Inventars und der unveränderten Quelle/Referenzpflicht.

H3 misst nur A6-konforme technische Kantenpflichten. Bei EV handelt es sich um operative
Teilnehmerprojektionen, nicht um belegte Wiederherstellung des vollständigen nativen
EV-Inhalts oder seiner Rollen und Einschränkungen. Kein H3-Primärtest, kein Holm-Slot.

## MuSiQue und Reader

**60 Fragen sind verbindlich festgelegt.** Die 60er-Menge ist das bereits vorbereitete
Präfix derselben 100er-Ziehung, Seed 20261024, Hopquoten 31/19/10. Sie umfasst 1.120
deduplizierte Korpusabsätze. Die direkte Nutzerentscheidung ersetzt den noch offenen
Kostenentscheid. B4 ist technisch unvollständig, mit einem unbekannten Aufruf.
Teilkosten gelten nicht als abgeschlossener 100-Chunk-Forecast. Kein Wiederholen des
unbekannten Aufrufs und kein vollständiger Gesamtgraph werden daraus behauptet.

Auf MuSiQue wird pro AS/V1 genau ein Instanzbestand ohne Schema konstruiert, identischer
Korpus für beide Arme. Fragen, Antworten, Aliase, Supportflags und Zerlegungen bleiben
vom Konstruktor und vom Graphindex getrennt. Der Reader erhält Frage und ausschließlich
die tatsächlichen Graphkanten. Alle acht Graphzellen bleiben fest, der Primärkontrast
bleibt V2_ROW gegen AS_ORIGINAL. Gleicher Reader, Encoder und Abruf in allen Zellen.

Der prospektiv festgelegte Readervertrag unter `reader_contract` enthält den vollständigen
neuen Systemtext und dessen UTF-8-Hash, die Benutzervorlage, Qwen235/T0/256/300s/Retry0
und den lokal vorhandenen MiniLM-Snapshot samt Dateihashes. Top-k=30, normalisiertes
Skalarprodukt, vollständige Suche und deterministische Bindung gleicher Scores an
Kantenvorkommens-IDs. Keine Rekonstruktion verlorener Fakten aus nativen Rohbeständen.
Dies ist eine **vorab festgelegte Readeraufgabe**, keine Behauptung eines bereits
fertigen oder qualifizierten C6-Runners. Vor dessen erstem Aufruf müssen tatsächlicher
Code und technische Kontrollen den Vertrag nachweislich umsetzen. Der Original-AS-Prompt
mit erlaubtem Weltwissen wird nicht still als dieser Reader ausgegeben.

Der offizielle MuSiQue-Normalisierer mit Maximum über Aliase liefert ungerundete
Einzelfragenwerte. Ein vollständig beobachtetes leeres/abstinent antwortendes Ergebnis
erhält seinen offiziellen Score. Fehlende oder abgeschnittene Antworten bleiben unbekannt.
Bei fehlenden gepaarten QA-Werten ist der primäre vollständige F1-Punktvergleich nicht
schätzbar, p=null, keine Ablehnung. Vollständige Q=60-Schranken werden berichtet.
EM, Original-HippoRAG2-Passagenweg sowie einmalige Leer- und Goldabsatzkontrollen bleiben
sekundär, getrennt und unter demselben Readerdeckel. Keine nachträgliche günstige Zellauswahl.

G2 hat ausschließlich Frage-IDs und Paragraphen-ID-Zuordnungen positiv projiziert.
Die eingefrorene 60er-Liste und die 39 Komponenten geteilter Absätze stehen in der JSON-Fassung,
kanonischer Metadatenhash `a2cfff4f89368c7fa9fd7ee54427ca574dcad920e19b676dfade640f4f283720`.
Die größte Komponente enthält 13 Fragen. Das sind Abhängigkeitsblöcke, keine neuen
Konstruktionen und keine Qualitätsergebnisse. Es gibt keinen MuSiQue-Konstruktionsstabilitätsnachweis
aus einem Durchlauf je Ausgangsarm.

## Tests und Entscheidung

Alle primären Tests sind einseitig bei α=0,05. Der gepaarte Cluster-Bootstrap verwendet
10.000 Ziehungen, NumPy PCG64, Seed 2026102407. Für H1/H2 werden 24 Quellen mit
Zurücklegen gezogen und jeweils alle geplanten Durchläufe beibehalten. Für H4 werden
die eingefrorenen Absatz-Überlappungskomponenten mit Zurücklegen gezogen, alle Fragen
eines Blocks bleiben zusammen. Der QA-Schätzer ist die Fragewertsumme geteilt durch
die Zahl gezogener Fragen, nicht der ungewichtete Mittelwert von Blockmitteln.

Mit Punktschätzer Δ_hat, Bootstrapwert Δ*_b und Nullrand δ0 gilt
T_b0=δ0+(Δ*_b−Δ_hat), p=(1+Anzahl[T_b0≥Δ_hat])/10001.
δ0=0 für H1/F1-H4, δ0=−0,05 für H2. Die primären H1/H2-Statistiken sind die
symmetrisch konservativen Punktscores, nicht die einseitige Identifikationsgrenze.
Marginale zweiseitige 95-Prozent-Perzentilintervalle verwenden lineare Quantile
0,025 und 0,975. Sie sind keine simultanen Holm-Intervalle.

Wilcoxon ist eine festgelegte Sensitivität über Quellenmittel, kein separater Test
pro Quelle und kein Test über alle Vorkommen. H2 verschiebt Differenzen um +0,05.
Alternative greater, Pratt-Nullbehandlung, Rangwerte auf zwölf Dezimalstellen,
10.000 feste Vorzeichenpermutationen mit Seed 2026102408. Alle Nullen ergeben p=1.
Die Lageinterpretation benötigt symmetrische Differenzen. Kein günstigerer Test wird ausgewählt.

McNemar betrifft nur sekundäres EM: W=AS falsch/V2 richtig, L=AS richtig/V2 falsch,
einseitig P[Binomial(W+L,0,5)≥W], bei W+L=0 p=1. Nur vollständig beobachtete Paare
mit genanntem Nenner. Wegen geteilter Absätze gilt die Binomial-Exaktheit nicht ohne
Unabhängigkeitsannahme, daher nur Sensitivität und kein H4-Holm-Eingang.

**Holm umfasst H1, H2 und F1-H4, m=3.** Sortierte p-Werte werden mit
min(1,max_(k≤i)((3−k+1)p_(k))) adjustiert. Nicht testbare Hypothesen behalten
raw_p=null und für die Korrektur einen konservativen Slot 1. Weniger als zwei
unabhängige Blöcke, undefinierte Nenner oder degenerierte Bootstrapverteilungen
begründen keinen inferenziellen Erfolg. Zweimalige Unabhängigkeit ist nur eine
technische Mindestbedingung, keine ausreichende Power.

H1 benötigt positive Differenz und Holm-Ablehnung. H2 benötigt Holm-Ablehnung am
Rand −0,05, nicht bloß fehlende Signifikanz am Rand null. Für H4 werden beobachtete
Nichtabnahme und inferenzieller F1-Zuwachs getrennt berichtet. Ein Gleichstand oder
p>0,05 beweist keine Gleichwertigkeit. Ablationen, EE/EV/VV-Schichten, Kohorten,
Zweitbewerter, H3 und verschiedene gestützte Aussagen bilden keine weiteren Primärfamilien.

## Sekundär: verschiedene gestützte Aussagen

Pro Quelle und Durchlauf werden unabhängig gestützte ganze Aussagen zunächst exakt
normalisiert: kanonisches JSON des semantischen nativen Inhalts, Schlüssel sortiert,
Unicode NFC. Großschreibung, Zahlen, Zeichen, Listenreihenfolge und Einschränkungen
bleiben erhalten. Nur technische Vorkommens-/Provenienzkennungen werden nicht verglichen.
Keine Domänenlisten oder semantisch vermutete Aliasfusion.

Bedeutungsgleiche Paare dürfen zusätzlich nach verblindeter Bewerterprüfung zusammengeführt
werden, wenn beide Richtungen dieselben Rollen, Beziehungen und Einschränkungen tragen.
Eine zusätzliche belegte Präzisierung ist keine Gleichheit. Für widersprüchliche/fehlende
Paare ist die Partition deterministisch: kanonische UTF-8-Werte lexikographisch sortieren,
jedes Element der ersten vorhandenen Gruppe nur bei bestätigter Gleichheit zu allen
Mitgliedern zuweisen, andernfalls neue Gruppe. Keine unkontrollierte transitive Fusion.
Ungeklärte Paare bleiben getrennt. Paar-IDs, Abdeckung und nicht geprüfte Paare ausweisen.

Gezählt werden Gruppen mit mindestens einem gestützten behaltenen Vorkommen in der Zelle,
je Quelle/Durchlauf, dann dieselbe Quellenaggregation. Exakt-only-Zahl und semantische
Zusammenführungen getrennt berichten. Diese zusätzliche Paaraufgabe ist nicht durch das
B1-Stützungsgate qualifiziert. Vorgeschlagene Zusammenführungen müssen menschlich geprüft
sein, bevor eine semantisch deduplizierte Zählung als abgeschlossen berichtet wird.
Unvollständige Prüfung bleibt unvollständig, keine Behauptung vollständiger Quellenfakten.
Die vollständigen geplanten H1-/H2-Bewertungen haben vor sekundären semantischen
Dedup-Paaraufrufen Vorrang innerhalb derselben Bewerterdeckel.

## Bewerter, menschliche Validierung und Kosten

Hauptbewerter: Sol/Foundry, Temperatur- und Reasoningfeld ausgelassen wie in B1,
8.192 max_completion_tokens. Zweitbewerter: Grok4.7/Foundry, T0, Reasoning ausgelassen,
8.192 max_tokens. Timeout300s, Retry0, Sechsergruppen. Der identische qualifizierte
Main12-Systemtext für H1/H2 hat 1.778 UTF-8-Bytes und SHA-256
`c94afc22feba85bef5e3703d91f32d881061fef7104dda4629d69dee13d80724`.
H2 fügt vollständige feste Pflicht und aktiven Carrier mit originalen Zeugen-IDs hinzu.
Rohcode- und Formatvalidierung werden nicht durch die neuen Primärscores ersetzt.
Die effektive Sol-Standardtemperatur bleibt unbekannt. B1 ist eine begrenzte Kontrolle,
kein unabhängiger menschlicher Goldstandard.

Grok erhält eine feste 15-Prozent-Stichprobe der ursprünglichen AS/V1-C2-Vorkommen,
geschichtet Arm×EE/EV/VV, ceil(0,15N_h), Seed2026102410. Zusätzlich alle vom Guard
entfernten Aussagen beider Elternarme aus den so vertretenen Stichprobenquellen.
Nach Vorkommens-ID vereinigen, keine Doppelbewertung. Zufallsanteil und angereicherte
Entfernungen getrennt berichten. Die Ergänzung ist keine Prävalenzstichprobe.

Die menschliche Stichprobe umfasst 150 ursprüngliche AS/V1-Aussagen, Ziel25 je
Arm×Typ, Seed2026102409. Ohne Zurücklegen, vor Labelsicht. Defizite werden in fester
Reihenfolge AS-EE,AS-EV,AS-VV,V1-EE,V1-EV,V1-VV auf verfügbare Strata verteilt.
Bei Gesamtbestand<150 alle verwenden und Mangel nennen, niemals duplizieren.
Arm, Guard und KI-Urteil bleiben bis Versiegelung der menschlichen Datei verborgen.
Ein menschlicher Autor wird mit C2 verglichen, keine behauptete Zweitmenschenannotation.
Nominales Cohen-κ über supported/not_supported/unclear, technische Fehlwerte gesondert.
κ=(p_o−p_e)/(1−p_e), mit 3×3-Tabelle und tatsächlichem Paar-Nenner. Bei keinem Paar
oder p_e=1 bleibt κ undefiniert. Keine erfundene Akzeptanzschwelle und keine automatische
Umschreibung der C2-Primärlabels. Populationspräzision je Arm verwendet Stratumgewichte
N_h/n_h; die ungewichtete geschichtete Stichprobe ist nicht die Gesamtprävalenz.

Verbindlich gelten G1-Einzeldeckel: B3 20USD, B4 25USD, Guard24 20USD,
GuardMuSiQue 40USD mit Kostenprüfung nach200Chunks, Reader5USD. Eine spätere strengere
Einzelfreigabe begrenzt zusätzlich. Hauptbewerter25EUR, Zweitbewerter12EUR mit
Portalprüfung nachetwa50Anfragen, Vertex-Referenzen separat1EUR.
Zusätzlich bleiben AWS160USD und Foundry30EUR global begrenzt. Einzelmaxima dürfen
nicht additiv als neue Gesamtfreigabe ausgegeben werden. Keine Währungsvermischung.
G2 selbst benötigt null Modell-/Encoderaufrufe.

Bei unbekannter Ausführung/Usage keine Wiederholung zur Kostenklärung. Bekannte
Kosten und begrenzte offene Verpflichtungen bilanzieren, unbekannt bleibt unbekannt.
Parameter-/Quellen-/ID-Drift, Leakage, Abschneiden oder unerklärte Modellwechsel stoppen
die betroffene Folgearbeit. Kein ergebnisabhängiger Frühsieg, kein Ersetzen ungünstiger
Quellen/Urteile/Nenner. Ergebnisstopp27.10.2026,20:00Europe/Berlin(+01:00), danach
nur bereits begonnene sichere Aufrufe abschließen und fehlende Werte erhalten.

## Prüfung vor Inhaltsbewertung

Die zuständigen Bereiche A2, A3c/A3d, B1/B2, B3, B4, C1, C7 und dieser G2-Chat
bestätigten ausdrücklich, in ihrem jeweiligen fair_v2-Bereich keine C2/C3/C4-Bewertungen
oder C6-Readeraufrufe gestartet zu haben. Zuständigkeiten, Zeitpunkte und Grenzen stehen
unter `pre_evaluation_check`. Fehlende Paketverzeichnisse allein wurden nicht als
Nichtstartbeweis gewertet. Es handelt sich um zeit- und bereichsgebundene Prüfung,
keine globale Netzwerkinventur oder zukünftige Garantie. Konstruktionsläufe und
quellengebundene Referenzerstellung sind davon getrennt. Keine Konstruktionsinhalte
der Konfirmationsquellen wurden durch G2 geöffnet oder bewertet.

## Verbindliche Pfad- und SHA-256-Bindungen

Die folgenden Tabellen und der vollständige JSON-Baum binden tatsächliche Bytes,
keine bloß geplanten Artefakte. Private Quellen/Referenzen/Gold wurden nur gehasht.
Die Frage-/Clusterliste enthält ausschließlich Kennungen. Private Dateien und
Zugangsdaten werden nicht in diesen Commit übernommen.

| Bindung | Pfad | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| provenance/drafts/0 | `Experiments/fair_v2_oct24/A7/preregistration_v2.md` | 32656 | `cb8b6da33276b403d9f683169ca255b354e11ff7521a8b72001e2ab460483554` |
| provenance/drafts/1 | `Experiments/fair_v2_oct24/A7/preregistration_v2.json` | 37777 | `23e14f350924a35e71d597b219390ce54e661460077cd33136955201f56593e0` |
| provenance/handoff | `withheld-artifact/cae9e70b3e8aa499592e` | 33428 | `2ee14174c3c163f09f693deedab4874b69bb44f24afed55dda4c1dc27ba5b38f` |
| provenance/role_decisions/0 | `Experiments/fair_v2_oct24/G1/freigabe_teil1.md` | 1945 | `c583169cd1ba2131325f82070b5145d6cab54fd92d96a6aef584c22efd5d930e` |
| provenance/role_decisions/1 | `Experiments/fair_v2_oct24/G1/freigabe_teil2.md` | 2021 | `211b6f0b070a808442e8c49be1819bf72b0df213bb4fa81b5b67a3334b357fba` |
| code_bindings/0 | `Experiments/fair_comparison_oct23_v1/baseline.py` | 33152 | `2af3e01d685e6bf3ee85403e0429ef06ed8b67ad55b27cafce2c3bdaddee30d6` |
| code_bindings/1 | `Experiments/fair_comparison_oct23_v1/candidate_adapter.py` | 13805 | `27456bb820c826855f37f23e8b35a0ccebc46dfe2bc2bcb0efb689272dbac000` |
| code_bindings/2 | `Experiments/fair_comparison_oct23_v1/scope_prefix.py` | 5725 | `1cbe34cd4f61a83e7289c013d29126b9916c3e37cb85738345fcd213e643206e` |
| code_bindings/3 | `Experiments/fair_comparison_oct23_v1/joint_supplement.py` | 12235 | `d7ba246e3775a83ea6446b7a523b5f4d630423ee175473c8cc6a675574749ddf` |
| code_bindings/4 | `Experiments/fair_comparison_oct23_v1/baseline_precollection.py` | 15468 | `cce9fdc04d7550dde16aace54cfe6e46f06a5e66b4d9bd353ea3092e0d192d10` |
| code_bindings/5 | `Experiments/fair_comparison_oct23_v1/baseline_precollection_worker.py` | 21275 | `9cb4bfc1eaee5720d643a732cb2569c7f1271c7bb0b1e845ad18d2dfd8146c19` |
| code_bindings/6 | `Experiments/fair_comparison_oct23_v1/candidate_precollection_worker.py` | 21636 | `17b7a0ed83813031e34924af13ce5b95c898095b1cd0d275676287e3c2646e7e` |
| code_bindings/7 | `Tools/experiments/whole_relation_guard_oct24_v1/guard.py` | 10316 | `95b1de9a8680ffd6b99c21c515f820837639d85b17b46596c6fc02fbfe832b23` |
| code_bindings/8 | `Tools/experiments/as_parallel_export_oct20_v1/export_control.py` | 7760 | `cacb2e11bcaaa18f9aa3ffa5a016845fe3dc54adb0b74c1e1966782287f67e88` |
| code_bindings/9 | `Tools/ReferenceRepos/benchmark_autoschemakg_original/atlas_rag/kg_construction/concept_generation.py` | 11549 | `41029f07e197de1330a3228c22bbf870fdc835925206002c2c0d5b28ccab8586` |
| code_bindings/10 | `Tools/ReferenceRepos/benchmark_autoschemakg_original/atlas_rag/kg_construction/triple_extraction.py` | 29840 | `71a9a3475adeaa2262e66cd002cae20053788fd807bdca0039aa7ac19770acdf` |
| code_bindings/11 | `Tools/ReferenceRepos/benchmark_autoschemakg_original/atlas_rag/kg_construction/concept_to_csv.py` | 5934 | `59dcd8a71a4f73d888b834cf48d2ae967afbb9ad811a1b994444a2c35dd44a5f` |
| code_bindings/12 | `Tools/ReferenceRepos/benchmark_autoschemakg_original/atlas_rag/kg_construction/utils/csv_processing/csv_to_graphml.py` | 12645 | `b88c0f52d9d623b12b16dcdf23ab735bcfb4df4c12a9d8efe14ba2c932b3ddf9` |
| code_bindings/13 | `Tools/ReferenceRepos/benchmark_autoschemakg_original/atlas_rag/llm_generator/prompt/triple_extraction_prompt.py` | 17455 | `7d8ea6f6795fa4d85be7ba1e14c0cde231a4119e31953aae7716076c0eaf3d0a` |
| code_bindings/14 | `Tools/ReferenceRepos/benchmark_autoschemakg_original/atlas_rag/llm_generator/generation_config.py` | 14989 | `408c318cdf8a02ad2b18da0fef4c7f9a84bb32088ad012b3dde584021a60a734` |
| code_bindings/15 | `Tools/ReferenceRepos/benchmark_autoschemakg_original/atlas_rag/kg_construction/triple_config.py` | 1258 | `f60ee33093728e5de20cef58ed98c7424d38e684522840145f4c83e1d026d941` |
| code_bindings/16 | `Tools/ReferenceRepos/benchmark_autoschemakg_original/atlas_rag/llm_generator/format/validate_json_schema.py` | 3650 | `6540487518748bf12af13ec2215832fdc660dedba2a0a212227c2589cd5e1c9c` |
| code_bindings/17 | `Tools/experiments/whole_relation_guard_oct24_v1/c1_guard.py` | 11889 | `34209741945a11b2dcbb7ece20dc9596a27fa65b42f00837af339b901ceef185` |
| code_bindings/18 | `Experiments/fair_v2_oct24/A8/project_subset.py` | 20122 | `08c1ea17489c52d415ced1e336976be2cc921e9ed19737cd76c0185c0cc740fe` |
| code_bindings/19 | `Tools/experiments/h3_export_loss_oct24_v1/measure_h3.py` | 27769 | `42d938d14f479fc8b0337b8167bf59c3af32d08e01270bf702e62955f64c8083` |
| code_bindings/20 | `Tools/experiments/whole_relation_guard_oct24_v1/a3c_core.py` | 7856 | `122d3c0ea5d784f83b67a382cb7d339e13c6faf6f94b8cb1cf4c9930e4cb2577` |
| code_bindings/21 | `Tools/experiments/whole_relation_guard_oct24_v1/a3c_runtime.py` | 18611 | `05863de020c24e50cee0d44bd93b8f4699818b23e543edd8b6b582536b7b6e79` |
| code_bindings/22 | `Tools/experiments/b1_evaluator_qualification_oct24_v1/foundry_adapter.py` | 11707 | `61a7912d792eaf68fe221d89afa4fdadae47ebe3965998f292275f34597e7996` |
| code_bindings/23 | `Tools/experiments/b1_evaluator_qualification_oct24_v1/cohort.py` | 8036 | `6d5f8fd78831474ec859d3b4f7b0102d77180eb4e75c6341188ff2fd6fa4601b` |
| code_bindings/24 | `Tools/experiments/whole_relation_guard_oct24_v1/gemini_condition_v1.py` | 11083 | `c79dbaecc1f2a3260f4124a0855b00d501e11eddead3503b0f650d38b993979e` |
| code_bindings/25 | `Experiments/fair_comparison_oct23_v1/candidate_selection_v1.json` | 5473 | `d11637c1bb5a90ae42d3360b15cb1b9a444a2ff7da400cc37e4a21c350e1b119` |
| code_bindings/26 | `Experiments/fair_comparison_oct23_v1/batch_review.py` | 20501 | `41a69d0e39c43994ede0064916df32ff148223862050e3a0e2d3de1eae1e78ed` |
| code_bindings/27 | `Tools/abschluss/e01_api_review_controls_v1.py` | 17119 | `d80243721779b10a3e5a02ad1a888e85831cf84d6abc4c8d4781d8ea4572a683` |
| code_bindings/28 | `Tools/abschluss/e01_review_control_readback_v1.py` | 22603 | `b5240cee4710be8cf1f7ce03913e6e685754a6420f7ebb089fa6688920910d13` |
| code_bindings/29 | `Tools/abschluss/e01_review_profile_v2.json` | 7714 | `3d2cbba0090198b20cbb462e254f3ddcac65cbef8d14675db547d43e4783c6dc` |
| code_bindings/30 | `Experiments/fair_comparison_oct23_v1/gemini_compact_id_transport.py` | 6960 | `476e4518eea05e7ecefaededa8b631edbade0c35475f4d4efccef9f3eb9daeed` |
| code_bindings/31 | `Tools/experiments/b1_evaluator_qualification_oct24_v1/runtime.py` | 13478 | `f5c4171bd65bda8a26de1ec5f969fb6d9cb306b3eb72605facddcefc2ab412bc` |
| code_bindings/32 | `Experiments/fair_v2_oct24/A8/audit_confirmation.py` | 12664 | `3d9ffa93df465df5242d79b18ea1dd5a226d033d1831a01a16506e6c85b81a67` |
| code_bindings/33 | `Tools/experiments/independent_repair_transfer_oct23_v1/controller.py` | 15429 | `2d501557c007efc902c9a184b8f470b01a99f500003834652f0ba5d86126cbf8` |
| code_bindings/34 | `Tools/experiments/fair_qa_oct23_v1/runner.py` | 30950 | `f93aa0d303b48334292d9c0630d965b6b2c2b6a222cbd326b51a5da24e6ad6f5` |
| bindings/A4/manifest | `Experiments/data/confirmation_a4_oct24_v1/sources_manifest.json` | 70039 | `e712666d8ee1dcbf35173b7ae804c6a734fffee97c4ebfefc893e70b5ded894d` |
| bindings/A4/selection_rule | `Experiments/data/confirmation_a4_oct24_v1/selection_rule.json` | 9061 | `29cd2958a0aa86e7474b305ad676b183dd78bfca26acca4f931cafaff55466d4` |
| bindings/A4/implementation_manifest | `Experiments/data/confirmation_a4_oct24_v1/selection_implementation.json` | 3325 | `c3c09678f2363d7ca80662ec98cc33154831e611e773c6a70088773f61606595` |
| bindings/A4/sources/0/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W01.txt` | 3504 | `8435e9f32d34cdd2c5edfa574448457ef246fb564c327698e886bf52da02d5b7` |
| bindings/A4/sources/1/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W02.txt` | 3734 | `0df31594c4f556e2413f8e7f858c1ccd5a24a8d47f2b3e60d252f9e158a46660` |
| bindings/A4/sources/2/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W03.txt` | 1904 | `311982536b36a16ffa129689b0cbf11e59636f4c11e3d59dd0e6260a7dc9cd6e` |
| bindings/A4/sources/3/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W04.txt` | 3836 | `f270bdceb7e95af8be154a77ab0be4a0113a825cc907dea6fd9330c380dc1720` |
| bindings/A4/sources/4/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W05.txt` | 3802 | `0a3f1a16cea24f5d7638fe91ade407a5e05f030b743a6633ba6f8e47634be805` |
| bindings/A4/sources/5/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W06.txt` | 3062 | `d336a63adbf66f397918c481767da221bf299f8b5cc092e47f682b9c728ac921` |
| bindings/A4/sources/6/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W07.txt` | 1869 | `02418c1f519f52ad38542d7fcb5eb5694f361c89facabc16079462842ba1db66` |
| bindings/A4/sources/7/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W08.txt` | 1770 | `cb10886494a4bacb0b1cdd2f9023888aad7ba7e9080593b56a8d6261d475cc94` |
| bindings/A4/sources/8/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W09.txt` | 3359 | `d2fc4d13ceea0baa0d7ad10f819ef13e091dd91d3a05371fa9318b122715606c` |
| bindings/A4/sources/9/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W10.txt` | 3544 | `c79470d0023a1d5c75cc3833ec1e6b93d66c53de3d67c0aea245dfd6a1da3c18` |
| bindings/A4/sources/10/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W11.txt` | 3301 | `9be849da83242ef7709ebd4152e1f3e17979e008abde8ad36be306f4e613dd5c` |
| bindings/A4/sources/11/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-W12.txt` | 3113 | `83b22a73cd83ea70a44d0fdeb8008e6599b03c443bb2e2b0e35586d7f236841e` |
| bindings/A4/sources/12/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-F01.txt` | 3992 | `b13bbc3ce03599a52d3ad33255af48278bcd780afa52eb4b3c859a02644977e2` |
| bindings/A4/sources/13/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-F02.txt` | 3996 | `6b93f47b011db8c2ecff25cb42b20c6b967d7c63ab2588dbf29e852a08053eba` |
| bindings/A4/sources/14/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-F03.txt` | 3983 | `816d767191e8555797f6ea5999a1b5e3b201669ac3b11ef67a2679b355fc2d66` |
| bindings/A4/sources/15/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-F04.txt` | 3994 | `3d8b76ed92c4b2171baf62e784e026189f76d8449dde57aa563476f14d82ef3c` |
| bindings/A4/sources/16/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-F05.txt` | 4000 | `d7445d82ed3fca31251f68883f1686a7af3bd36828eec269720ce11440f25f1d` |
| bindings/A4/sources/17/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-F06.txt` | 3992 | `c46e01eeda5f9d97e292c457d467baa9825f784bef3d2bebcdd2d71f89b3e9a0` |
| bindings/A4/sources/18/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-F07.txt` | 3995 | `53f3786e8be73e37c5fe4db97dd17221cd32c123a80e335b68a9240811df9369` |
| bindings/A4/sources/19/input | `Experiments/data/confirmation_a4_oct24_v1/sources/A4-F08.txt` | 3986 | `fcaf46519ef66f56d4961c27f7af39f6ae79954838309801142c322551e1d34f` |
| bindings/sealed4/source_only_manifest | `withheld-artifact/1701e3c37a38836131b8` | 1576 | `5c4324daa3f5bf62ad2690f0c4edda5542a2d7e61000d69771354a9a26829bed` |
| bindings/sealed4/reference_freeze | `withheld-artifact/4553c2491fcf903fdfc9` | 11897 | `9d178482fbf00ab0b7a5bb8ad97c579084861335fec0d72d79b35ff5a1825e3b` |
| bindings/sealed4/sources/0/input | `withheld-artifact/ff5809a63968783ad6a2` | 4977 | `9cb0a98ad5c19458d0e48d925c00cbc6532baaa736b5c817e0351080045d80af` |
| bindings/sealed4/sources/0/reference_inventory | `withheld-artifact/08cedf09b08c27a5ef29` | 17185 | `11424a5862062a11bc6b067eb155b1b51382054ad755010c631b923d85d118c8` |
| bindings/sealed4/sources/1/input | `withheld-artifact/351fb6fbd6d512f0b66f` | 1694 | `f5e3b15bce8608d659fa3b39c57d51fac5b6384f0bf4ef6ef9a5d09ae2c50da1` |
| bindings/sealed4/sources/1/reference_inventory | `withheld-artifact/23f0e1b5932d41a83803` | 15703 | `e105462048fa294c52e65337e44585cdc64c60db2c10b294f211e0577e833847` |
| bindings/sealed4/sources/2/input | `withheld-artifact/06f55bbc62ca215756dd` | 4611 | `9315e29366dc435f5d1be73e890a3831ad3c7e90fdea1ba5c2a3fe148f568bad` |
| bindings/sealed4/sources/2/reference_inventory | `withheld-artifact/a5b624febd195ee4c6e8` | 35465 | `714c977f587b2877ac6b3608d416455cb6ae3e7b4db7e60335b6926c4167793b` |
| bindings/sealed4/sources/3/input | `withheld-artifact/eca769ca8bf32281c0a0` | 2137 | `b67dea2fd79dad52b9de7c7c233031fd59d751152b005e87f79a4d1ee81b1676` |
| bindings/sealed4/sources/3/reference_inventory | `withheld-artifact/6d9f6cf539a4e61a2f5a` | 22612 | `3386f46d44401b20a8aa182332ea84874a578d76a0b85fc82edf316b1ed453fe` |
| bindings/B2/manifest | `Experiments/results/b2_reference_generation_oct24_v1/manifest.json` | 6594 | `c68712bf7fe20e2715e7d23dbba0e267c5d8e250d04e874ef1c071a1d24af02e` |
| bindings/B2/bundle | `withheld-artifact/94c339808e78e315f6c7` | 240339 | `fa0943662c343c4f5740fb9a2bc94440450f836b619baa67bb1c1d331937a051` |
| bindings/B2/index | `withheld-artifact/361686a9afe99aadc8c4` | 6342 | `ed54b516c6d2c101140ffcaa0a4618207cbf4f1a145b31a7f603708e1ffcd605` |
| bindings/A5/manifest | `Experiments/fair_v2_oct24/A5/manifest.json` | 20254 | `f77a4d9ddb082ecdb5dec1ac5bea07d4438a3d78d75f0f4296ec85710933e617` |
| bindings/A5/sampling_rule | `withheld-artifact/b638b7c91cc3994cdfb5` | 1895 | `e5ca546b2db60178fc005d26706821f43e53b733d760e2c0100da3fd6ae1fe66` |
| bindings/A5/official_source | `withheld-artifact/de51d477fdbbff26ebf3` | 30439728 | `15fa63794d18a94ce12411aca6e2327e65b6e83b0b1490efab3f1962e48abf3b` |
| bindings/A5/official_evaluator | `withheld-artifact/e72637e8b86e99700bfe` | 4606 | `f5fe66ae61dbea5172cba9d428d9924a5811f3457edc945fc1d81369c30e74b7` |
| bindings/A5/gold | `withheld-artifact/f9504aa36d1356dd4a6e` | 1535880 | `627c2f3dde28618ed2bfb49c2b259f91421f865ea2caf80b21eea5f3761b13bc` |
| bindings/A5/variants/100/corpus | `withheld-artifact/fa4c776615b689f0231e` | 1106438 | `784b86365a1406f55c138cdfb23edff1b7662552e5ffbca7dbaf981a132967ce` |
| bindings/A5/variants/100/questions | `withheld-artifact/a9b468bf79c314d79835` | 164487 | `b496b5a5292373ae5187f46e3adb2311e72c6c69599bb3606a64b2ade35ba480` |
| bindings/A5/variants/60/corpus | `withheld-artifact/7d43b9a52e9f79ba1a59` | 723577 | `ee935e226a26c5aafa4d1351d585b2fb9a8c4bda249ef8bea207b9d29ae6323c` |
| bindings/A5/variants/60/questions | `withheld-artifact/13f290fc02253a4fc125` | 98717 | `ba9337d190f03046bc8821a8ca2cdb70e76f540be8c8788242a9998a8a5e2c2c` |
| bindings/A5/B4_technical_stop | `withheld-artifact/0514cfa76a9fed0f829e` | 142167 | `55227deeded57d44bb768a60668afea333b7b89877169c2725fc82b669fc27e1` |
| bindings/A5/B4_original_terminal | `withheld-artifact/8c4c56ae937b5d6655a0` | 1045 | `51e75fb15eba141c7fb765919ed0b7429377442f69e04a98b861d3bbd30eb8af` |
| bindings/A8/result | `Experiments/fair_v2_oct24/A8/result.json` | 742496 | `e203cc5fc8758b6551f7f6961cc60a8d7db1abdc9002cde2bc9247cc8bd54a1c` |
| bindings/Guard/admission | `Experiments/fair_v2_oct24/A3d/admission.json` | 11305 | `d8e38fddc73d111e0bb3403de8825f6f66a50a7da869d24e2541c9de14e17147` |
| evaluators/shared/B1_result | `Experiments/results/b1_evaluator_qualification_oct24_v1/result.json` | 41082 | `bf20a2a96e5e005ccaa5bd5ae69604c779c2d55e60aeb9ea06849c4b10a01df7` |
| evaluators/shared/B1_manifest | `withheld-artifact/08a9b8620800e6ebf90d` | 2158657 | `d6875902d28a86ad6a7079daaa57ad66702f41d8dbd991842051d99a4b2b365e` |
| reader_contract/retrieval/files/0 | `withheld-artifact/8de692d65ca14403d6d2` | 1229 | `98ccb431c012ebfe976280fbd45aea4cec7409935868ccecf3954370f96732a1` |
| reader_contract/retrieval/files/1 | `withheld-artifact/359f3c2d883283199b25` | 190 | `4be450dde3b0273bb9787637cfbd28fe04a7ba6ab9d36ac48e92b11e350ffc23` |
| reader_contract/retrieval/files/2 | `withheld-artifact/58a88d84c853c30839f6` | 612 | `953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41` |
| reader_contract/retrieval/files/3 | `withheld-artifact/f26486ca60a5afad375a` | 116 | `061ca9d39661d6c6d6de5ba27f79a1cd5770ea247f8d46412a68a498dc5ac9f3` |
| reader_contract/retrieval/files/4 | `withheld-artifact/0d4117bea6a04a44dcff` | 39265 | `32edcb108fc2516b920734a862ae0692bcae1c5d45d5f8d972cb0d53434a4c54` |
| reader_contract/retrieval/files/5 | `withheld-artifact/50838584715d232095e3` | 90868376 | `53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db` |
| reader_contract/retrieval/files/6 | `withheld-artifact/4c5be15237468de5a42a` | 349 | `84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf` |
| reader_contract/retrieval/files/7 | `withheld-artifact/55d3286aa659bf380a31` | 90405214 | `6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452` |
| reader_contract/retrieval/files/8 | `withheld-artifact/73f20c2ba289f56a8774` | 90360328 | `1391c6fc20b5530250bc15cbe1f47578ffeca55ab0551d335cc668b6299a88ec` |
| reader_contract/retrieval/files/9 | `withheld-artifact/9b7a50e98f1068d72080` | 90326566 | `1de3905029190b398c7d300b530e320cf4b5e7d3dfb9af1429ebd73fd9a16faf` |
| reader_contract/retrieval/files/10 | `withheld-artifact/698e51166bb984553f31` | 90326497 | `a44f671e364dddbac31f203f07b91be6b0a35e51936e5ebfab65b6d9538b83ff` |
| reader_contract/retrieval/files/11 | `withheld-artifact/c7dd9d053af1ad4e1cc2` | 45212349 | `1667d7f3ba669048b13a96ee3a44456d5e42c8f44588ae8b603430e16160c485` |
| reader_contract/retrieval/files/12 | `withheld-artifact/99f34c057405a936240f` | 23026053 | `4278337fd0ff3c68bfb6291042cad8ab363e1d9fbc43dcb499fe91c871902474` |
| reader_contract/retrieval/files/13 | `withheld-artifact/086c09f49dc94c035640` | 23026053 | `4278337fd0ff3c68bfb6291042cad8ab363e1d9fbc43dcb499fe91c871902474` |
| reader_contract/retrieval/files/14 | `withheld-artifact/4e21fb98609c572a23cc` | 23026053 | `4278337fd0ff3c68bfb6291042cad8ab363e1d9fbc43dcb499fe91c871902474` |
| reader_contract/retrieval/files/15 | `withheld-artifact/091173a7acd07fec31d5` | 23046789 | `b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21` |
| reader_contract/retrieval/files/16 | `withheld-artifact/0d66e394fb96e3366ca7` | 90265744 | `8b86cab4722e2aefab310cf96d4d5a9eb3b187f7d9670a082afc55c7fa0d392a` |
| reader_contract/retrieval/files/17 | `withheld-artifact/a95a398ecf824195959d` | 211315 | `f87dd1482b2a745f8c699b81ddd9cbcad666a193be4693abcea44b7ac8c67c1e` |
| reader_contract/retrieval/files/18 | `withheld-artifact/5d584eeeb45a9e426f3a` | 22933664 | `c92ea4af3c6bc7b4a0f3b3d61b147c850f4dbdd7c9e7beee0c0c70dc12da289b` |
| reader_contract/retrieval/files/19 | `withheld-artifact/77df9145bd6140e6abdf` | 368006 | `a19425e3f56f7736f752923f0a0b5a8d61c7878017f02e1fc9086615391105dd` |
| reader_contract/retrieval/files/20 | `withheld-artifact/581fe8171f187e4a5618` | 90888945 | `c3a85f238711653950f6a79ece63eb0ea93d76f6a6284be04019c53733baf256` |
| reader_contract/retrieval/files/21 | `withheld-artifact/95da209c9b92fb283781` | 10502 | `dcd602d2fd35c203a247304a06fec6654a12f7941b739f9221a064fe8dc3b7f0` |
| reader_contract/retrieval/files/22 | `withheld-artifact/e8df14aada9a74d2b28b` | 90887379 | `2d98d96d278348988f2744e6445b8bc16d921c3f6e17c667362f3cb353007aea` |
| reader_contract/retrieval/files/23 | `withheld-artifact/b00b93355cd5f0bb6f7e` | 53 | `fc1993fde0a95c24ec6c022539d41cf6e2f7c9721e5415d6fb6897472a9cd4b7` |
| reader_contract/retrieval/files/24 | `withheld-artifact/aed53a4604bb0a8a164e` | 112 | `303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3` |
| reader_contract/retrieval/files/25 | `withheld-artifact/2020197a4828bf33de8f` | 91005696 | `24c06a7429b843d46e40c6b167122053921bf94dce2e5550ea5c07fabc597646` |
| reader_contract/retrieval/files/26 | `withheld-artifact/9271b102eccc32bd8d2c` | 466247 | `be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037` |
| reader_contract/retrieval/files/27 | `withheld-artifact/0e46676d6024449ce8c6` | 350 | `acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b` |
| reader_contract/retrieval/files/28 | `withheld-artifact/56be3069af9ad6660d45` | 13156 | `f9b98b9d203d728cbf93ccdbae84131ab926541b56196f11d1385fed0b4d1a07` |
| reader_contract/retrieval/files/29 | `withheld-artifact/bf9f1170f254716590cc` | 231508 | `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3` |

### Kanonische Teilbaum-Hashes

Die JSON-Kanonisierung ist UTF-8, ensure_ascii=false, sort_keys=true, separators=(comma,colon).

- `code_bindings`: `f40a089c3df204b0803cfff5fff4d45a39a7facc86f978657e985806404d25b6`
- `bindings`: `eee3fe79740d00d19604c5cdb631f0272d4088c2df01093976c2f10d372971ba`
- `evaluators`: `04ce6679a2e0b2a135d3a56067c508dcf21c5ae8e73912e09881c7dce8c42be3`
- `reader_contract`: `b5761ba09764572e3b45259ff86a7f1259554e87f2e488dbf2d3c907476eea8b`
- `analysis`: `50300236d34daac86461c2d7b3293fe9b4bf5ab246d9cd1bc7251bcb4c497eae`
