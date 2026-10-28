# X3: nachträglich, explorativ - Prüffilter nur für VV

Diese hypothesenbildende Analyse wurde am 26.10.2026 nach Kenntnis der
H12-Autorenprüfung beauftragt. Der Auslöser ist deren unterschiedliche
Entfernungspräzision für VV und EE. Die Analyse ist nicht vorregistriert und
bestätigt keine neue Pipelinevariante. V2, die ursprünglichen Testfamilien und
das Gesamturteil bleiben unverändert.

## Ableitung

Grundlage sind ausschließlich die ursprünglichen AS-/V1-Inventare der
24 Konfirmationsquellen mit 68 geplanten Quellen-Durchlauf-Paaren und die
bereits gespeicherten C1-Entscheidungen. Main12 und MuSiQue gehören nicht
zu dieser Ableitung. Aus jedem ungefilterten Elternbestand werden genau die
bereits entfernten Vorkommens-IDs des Typs VV entfernt. Ursprüngliche
EE-Entfernungen werden dadurch zurückgenommen, sämtliche EE und EV bleiben
unverändert. Neue Facettenurteile werden nicht erzeugt.

Die bestehenden `project_subset`-/C1-Projektionsfunktionen materialisieren
Original- und Zeilenexport derselben abgeleiteten Mitgliedschaft. Die
beiden Exportansichten bilden keine zusätzlichen Verfahren. Neue öffentliche
Bezeichnungen sind ausschließlich AS+G(VV) und V1+G(VV). Vorhandene AS+G-/V2-
Ergebnisse und ihre Mitgliedschaftsnachweise werden nicht überschrieben.

## H1 und Unsicherheit

Alle verbleibenden Vorkommen erben unverändert ihr C2-Urteil und ihren
Auswahlstatus. H1 wird auf dem gesamten abgeleiteten Inventar gemessen,
nicht ausschließlich auf dessen VV-Anteil. Der N10-Präfix einschließlich
Fehlversuchen, die originalen globalen Sechsergruppen und die Quellenreihenfolge
bleiben erhalten. Nicht gezogene Positionen bleiben nicht gezogen.

Die vorhandene D1-N10-Schätzung poolt gezogene Vorkommen über geplante
Durchläufe innerhalb jeder Quelle und gewichtet anschließend alle Quellen
gleich. Der gemeinsame zweistufige Quellen-/Originalgruppenbootstrap verwendet
10.000 Replikationen mit PCG64 und Seed 2026102407. Derselbe Matrixgegenstand
wird für alle Ausgangs-, Vollfilter- und VV-only-Zellen verwendet. Die
vorhandene D1a-Matrixbindung dient als technische Reproduktionsreferenz.

Ausgegeben werden Punktschätzer und marginale zweiseitige 95%-Perzentilintervalle
für H1 sowie beschreibende gepaarte Differenzen zu den jeweiligen Ausgangs-
und Vollfilterbeständen. Es werden keine p-Werte, Nullhypothesentests,
Nichtunterlegenheitsentscheidungen, Holm-Korrekturen oder Gesamtstufen berechnet.
Leere Nenner und nicht bestimmbare Replikate bleiben nicht bestimmbar. Die
N10-Näherung identifiziert keine exakt gleichen Inklusionswahrscheinlichkeiten.

## Entfernungen und vorhandene Autorenurteile

Entfernungen werden je Ausgangsarm gegen alle ursprünglichen nativen
Aussagevorkommen und zusätzlich gegen dessen ursprüngliche VV-Vorkommen
ausgewiesen. Zurückgenommene EE-Entfernungen werden gesondert gezählt.

Die feste 90er-H12-Stichprobe wird ohne Neuziehung über globale Original-IDs
mit der neuen Mitgliedschaft verbunden. Autorenlabels und Ursprungsexport
bleiben unverändert. Berichtet werden nur Aggregate der weiterhin entfernten
VV, der zurückgenommenen EE-Entfernungen und der unveränderten Kontrollen.
Diese gezielt geschichtete Stichprobe liefert keine Populationsprävalenz
oder unabhängige Bestätigung der nachträglich gewählten Filterregel.

## Grenze und Ausgaben

H2 ist für AS+G(VV) und V1+G(VV) **nicht bewertet und wird nicht geschätzt**.
EE-Erhalt und VV-Entfernung allein belegen keinen Bedeutungserhalt oder
Qualitätsvorsprung. Es gibt keine Modell-, Referenz- oder weiteren
Bewertungsaufrufe. Alle Ergebnisdarstellungen tragen den Vermerk
**„nachträglich, explorativ“**.

Öffentliche Ausgaben sind `X3/result.json` und eine kurze Tabelle für
Diskussion beziehungsweise Ausblick. Private Aussagen, Autoren-Einzelfälle,
Quelltexte und abgeleitete native Bestände verbleiben in der privaten
Evidenzablage. Die ursprünglichen Eingänge bleiben bytegleich erhalten.
