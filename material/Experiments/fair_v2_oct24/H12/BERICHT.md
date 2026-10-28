# H12: Autorenprüfung der Prüffilter-Entscheidungen

Die direkt vom Autor bestätigte Annotation wurde unverändert privat übernommen.
Alle 90 Labels sind vollständig, paketgebunden und als `human_ui_input` gekennzeichnet.
Es wurde keine Aussage neu gezogen oder neu bewertet. Der vor Labelsicht festgelegte N12-Auswerter blieb unverändert.

## Primär: nicht gestützt

Unklare Urteile zählen konservativ als nicht „nicht gestützt“.

| Gruppe | Nicht gestützt / N | Anteil |
| --- | ---: | ---: |
| Entfernt | 39/60 | 65,00 % |
| Behaltene Kontrolle | 1/30 | 3,33 % |

Differenz entfernt minus behalten: **61,67 Prozentpunkte**. 95-%-KI [48,33 Prozentpunkte; 75,00 Prozentpunkte], einseitiger Fisher-p = **4,07086e-09**.

Der nominale einseitige Test bestätigt in dieser Stichprobe eine Anreicherung nicht gestützter Aussagen unter den Entfernungen.

Der Prüffilter entfernte zugleich **16/60 vom Autor gestützte Aussagen (26,67 %)**,
weitere fünf Entfernungen sind unklar. Unter den behaltenen Kontrollen sind
25/30 gestützt und vier unklar. Damit ist die Anreicherung ein Mechanismusbeleg,
aber keine fehlerfreie Löschentscheidung oder alleiniger Nachweis eines Nettonutzens.

## Sensitivität: unklar ebenfalls als nicht gestützt

| Gruppe | Nicht gestützt oder unklar / N | Anteil |
| --- | ---: | ---: |
| Entfernt | 44/60 | 73,33 % |
| Behaltene Kontrolle | 5/30 | 16,67 % |

Differenz entfernt minus behalten: **56,67 Prozentpunkte**. 95-%-KI [38,33 Prozentpunkte; 73,33 Prozentpunkte], einseitiger Fisher-p = **3,12965e-07**.

## Beschreibende Entfernungspräzision

Präzision bedeutet hier den Anteil der entfernten Aussagen, die der Autor als nicht gestützt beurteilt.
Alle Konfidenzintervalle oben betreffen ausschließlich den Gesamtunterschied, nicht die folgenden kleinen Teilgruppen.

| Dimension | Gruppe | Nicht gestützt / N entfernt | Präzision |
| --- | --- | ---: | ---: |
| Arm | AS | 19/30 | 63,33 % |
| Arm | V1 | 20/30 | 66,67 % |
| Typ | EE | 5/16 | 31,25 % |
| Typ | VV | 34/44 | 77,27 % |
| Quellfamilie | factbook | 10/15 | 66,67 % |
| Quellfamilie | sealed4_primary | 3/5 | 60,00 % |
| Quellfamilie | wikipedia | 26/40 | 65,00 % |
| Auslösende Facette | head | 1/1 | 100,00 % |
| Auslösende Facette | qualifications | 14/24 | 58,33 % |
| Auslösende Facette | relation_and_direction | 39/57 | 68,42 % |
| Auslösende Facette | tail | 0/1 | 0,00 % |

Facetten können überlappen. Ihre Nenner werden nicht addiert. Im Gesamtzähler zählt jede der 60 Entfernungen einmal.

Der Typunterschied ist ein relevanter beschreibender Gegenbefund: Bei EE sind
nur 5/16 Entfernungen als nicht gestützt bestätigt, während sieben gestützt und
vier unklar sind. Bei VV sind 34/44 nicht gestützt, neun gestützt und eine unklar.
Diese kleinen Teilgruppen erhalten keinen nachträglichen Überlegenheitstest.

## Übereinstimmung mit Sol im C2-Präfix

Von 90 Fällen sind 75 gültige Paare, 13 nicht gezogen und 2 technische Fehlwerte. Nicht gezogene oder technisch fehlende Sol-Urteile wurden nicht als unklar umgedeutet.

Dreiklassiges Cohen-κ: 0,688797. Binär konservativ: 0,68663; binär mit unklar als nicht gestützt: 0,862082.

## Reichweite und Übergabe

Sekundäre Mechanismusprüfung nach N12, keine zusätzlichen Holm-Slots in G2/N8 und kein Ersatz der primären Bewertung.
Das 95-%-KI verwendet 10.000 feste PCG64-Aussagen-Bootstraps in AS/V1 × entfernt/behalten mit Seed 2026102513.
Quellen- und Konstruktionsabhängigkeiten sind nicht korrigiert. Kleine geschichtete Autorenstichprobe, keine Populationsprävalenz,
keine unabhängige externe Goldannotation und keine allgemeine kausale oder globale Überlegenheitsbehauptung.
Autorschaft beruht auf der direkten Nutzerbestätigung, nicht auf einer Authentifizierung durch die Exportdatei.

Öffentlich stehen ausschließlich Aggregate und Hashbindungen in [result.json](result.json).
Originalexport, Zuordnung, Kommentare und einzelne Labels bleiben privat. Die Datei ist als eigenes H12-Aggregat D1-lesbar.
Eine bereits erfolgte Einbindung in den D1-Endlauf wird nicht behauptet. Keine Modellaufrufe.
