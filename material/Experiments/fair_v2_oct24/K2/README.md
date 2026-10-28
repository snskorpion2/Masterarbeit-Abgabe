# K2: endgültiger Aufwandsstand für EF1

Stand **26.10.2026**, CPU-Auswertung vorhandener Originalbelege. `aufwand.csv`
enthält 70 disjunkte Aufwandsgruppen mit 33 Feldern. Der zugehörige LaTeX-Tabellenentwurf
gehört nicht zum öffentlichen Paket. Der datierte [Abschluss](ABSCHLUSS_EF1.md) und
`verification.json` beschreiben den aktuellen Stand, die frühere Beschreibung
vom 25.10. war ein Zwischenstand vor dem Abschluss von C1/C2/C3 und C6.

Die Tabelle erfasst 38.106 verschiedene Anfragepositionen. C1-MuSiQue,
T1 und C6 sind ergänzt. C2/C3 folgen dem abschließenden N10-Snapshot.
Alle 4.673 Produktions-Prüffilteraufrufe haben eine eindeutige ursprüngliche
Quelle und einen Durchlauf. Der aggregierte Nachweis steht in
`source_assignment.json`, die vollständigen Zuordnungen bleiben privat.
Leere Belegmengen unterschiedlicher Gruppen haben verschiedene Gruppenhashes.

Aufrufe sind dokumentierte Originalanfragen beziehungsweise Versuche.
Physische POSTs bleiben davon getrennt und bei fehlender Messung unbekannt.
34 historisch unbekannte Ausführungen bleiben erhalten. Fehlende Usage und
Kosten sind nicht null. Die B2-Tokenzählung ist eine nichtgenerative API-Stufe.
Technisch geschlossene Ausführung bedeutet keine vollständig gültige Bewertung.

Gemeinsame Konstruktion wird physisch einmal gebucht: AS wird von AS+G,
V1 von V2 wiederverwendet. Die jeweiligen zusätzlichen Prüffilterkosten gehören
zu AS+G und V2. Für Kosten einer logischen Variante muss deren Konstruktionsbasis
hinzugenommen werden. Gemeinsame Bewertungen und Qualifikationen werden nicht
anteilig auf Arme verteilt. T1 bleibt eine eigene Transferbedingung. Die
600 C6-Readeraufrufe und eine gesonderte Zugangsprobe sind Forschungsaufwand.

Bekannte Listenwerte gelten unter den archivierten Preisszenarien und sind
keine Rechnungen. EUR und USD werden nicht umgerechnet. Reserven und Holds
werden nicht als weitere Kosten addiert. Historische unbekannte Extraktion
versiegelter Quellen bleibt eine Lücke. Die N17-Bilanz verwendet nur Quellen
mit vollständig bekannten Kosten und wird im separaten EF1-Paket berechnet.

HTTP-Einzelaufrufzeiten sind für alle Produktions-Prüffilteraufrufe und die
600 C6-Readeraufrufe erfasst. Ihre Summe ist keine Stufen- oder Gesamtwandzeit.
Nicht gemessene Wandzeiten bleiben unbekannt. Konstruktor-Einzelzeiten wurden
im aktuellen Export nicht aus dem zusätzlichen Receipt-Massenscan übernommen.

`provenance.json` bindet die normalisierten Eingaben, Gruppen und das private
Originalanfragearray über `native_D1_input_pin`. Umfangreiche originale
Receipt-Pfadlisten stehen ausschließlich im dort gebundenen privaten Sidecar,
öffentlich bleiben Hashes und Anzahlen. Die CSV wird mit dem gebündelten
Artifact Tool zellengenau rückgelesen. Keine Ausführungsledger oder
Originalantworten werden verändert und keine Modelle aufgerufen.

## Aktualisieren

Bereits gebundene normalisierte Eingaben erneut exportieren:

```powershell
python -X utf8 Experiments\fair_v2_oct24\K2\update.py
```

`--refresh` liest neue lokale Snapshots in einem frischen privaten Ordner.
Das fordert keine Modelle an. Der vollständige Konstruktor-Receipt-Scan kann
auf Windows zeitaufwendig sein. Für den aktuellen EF1-Stand wurde stattdessen
der bereits geschlossene B3/B4-Normalisierungsbeleg bytegleich übernommen,
nachdem sämtliche seiner Originaleingabepins erneut bestätigt waren.
Neue Ledger oder Tarifbedingungen benötigen eine ausdrückliche
Quellenzuordnung und dürfen nicht mit alten Preisbedingungen vermischt werden.
