# Begleitmaterialien zur Masterarbeit

**Agentische Knowledge Graph Construction aus semi- und unstrukturierten Daten**

Vladislav Antonov · M. Sc. Informatik · HTWK Leipzig · 2026

Dieses Repository enthält Materialien zum Vergleich des eigenen Ansatzes mit AutoSchemaKG:
Ergebnisberichte, Versuchsverträge, Auswertungscode und ausgewählte Konstruktionsprogramme.

## Hier beginnen

| Ich möchte … | Einstieg |
| --- | --- |
| die Ergebnisse und ihre Einordnung lesen | [Ergebnisübersicht](docs/ERGEBNISSE.md) |
| Versuchsaufbau, Vorregistrierung und Nachträge nachvollziehen | [Methodik und Zeitfolge](docs/METHODIK.md) |
| die synthetische Auswertung selbst ausführen | [Reproduktion](docs/REPRODUKTION.md) |
| eine interne Kennung oder einen alten Pfad zuordnen | [Kennungsverzeichnis](docs/KENNUNGEN.md) |
| direkt zum Statistikcode | [Auswertung](material/Experiments/fair_v2_oct24/D1/) |
| direkt zum Konstruktions- und Prüffiltercode | [Konstruktion](material/Experiments/fair_comparison_oct23_v1/), [Prüffilter](material/Tools/experiments/whole_relation_guard_oct24_v1/) |

## Was zeigt der Vergleich?

Mit demselben Konstruktormodell erreicht der **eigene Ansatz mit Prüffilter**
gegenüber AutoSchemaKG eine höhere Quellenstützung. Der ausgewählte Bedeutungserhalt
erfüllt die vorregistrierte Nichtunterlegenheitsgrenze. Für die MuSiQue-Antwortqualität
wird das vorregistrierte Kriterium nicht bestätigt.

Die [Ergebnisübersicht](docs/ERGEBNISSE.md) nennt Schätzer, Unsicherheit und die zugehörigen Berichte.

## Synthetische Auswertung

Für die CPU-Demo werden die in `requirements.txt` festgelegten Paketversionen benötigt:

```sh
python -m pip install -r requirements.txt
python -B -X utf8 reproduzieren.py demo --output ../masterarbeit-demo
```

Die Demo führt den Auswertungscode auf künstlichen Daten aus. Voraussetzungen, Ausgaben
und die Datenbasis der empirischen Ergebnisse beschreibt die [Reproduktionsanleitung](docs/REPRODUKTION.md).

## Aufbau und Lieferumfang

`docs/` führt nach Fragestellungen durch den Bestand. `material/` enthält die Programme
und Belege in ihrer bisherigen relativen Ordnung. Dadurch bleiben eingefrorene Dateibindungen,
Python-Imports und historische Pfadangaben nachvollziehbar. Alte Pfade beginnen jetzt mit `material/`.
Das [Pfadabbild](docs/STRUKTUR.json) dokumentiert den Umzug dateigenau.

Die Arbeit als PDF und ihre LaTeX-Quellen werden getrennt geführt.
Den Stand der PDF-Prüfsumme führt die [Chronologie](material/docs/CHRONOLOGIE.md).

## Herkunft und Rechte

Es gilt die dokumentierte [Rechtesituation](material/Tools/release/SUBMISSION_RECHTE.md).
Die [AutoSchemaKG-Lizenz](material/licenses/AutoSchemaKG-LICENSE.txt) liegt bei.
Für das Gesamtpaket wird keine zusätzliche pauschale Lizenz erteilt.
