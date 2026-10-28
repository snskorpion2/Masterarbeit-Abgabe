# EF1 – Aufwand-Qualitäts-Bilanz

Sekundäre CPU-Auswertung nach N17 §1, Stand 26.10.2026. Einstieg ist
[`BERICHT.md`](BERICHT.md). Die Primäranalyse von D1 wird weder erneut ausgeführt
noch verändert. Keine Modellaufrufe, neuen Hypothesentests oder
Überlegenheitsentscheidungen.

## Ergebnisse

- `result.json`: Punktschätzer, 95-%-Quantilintervalle, Identifikationsschranken
  und gepaarte Verhältnisse zu AS. H1: 20 neue Quellen; H2 zusätzlich dieselben
  17 neuen N14-Quellen mit Urteilen und vollständigen Kosten.
- `source-costs.json`: vollständige Kosten je Quelle/Arm sowie ausdrücklich
  unvollständige historische Kostenuntergrenzen. Alle tatsächlichen Durchläufe
  bleiben erhalten, für neue Quellen drei.
- `stages.json`: disjunkte Belegzählung nach Paket, Stufe, Arm und
  Preisszenario. Anfragedauern und Wandzeit sind getrennt.
- `kosten_qualitaet.png` und `figure-data.json`: zwei Felder
  mit Kosten je Quelle gegen H1 beziehungsweise H2.
- `textbausteine.md` / `.tex`: jeweils ein Absatz für Kapitel 6 und die
  Diskussion. Entwürfe, nicht automatisch ins Manuskript eingebunden.
- `input_inventory.json`, `verification.json`, `cpu-tests.xml`:
  Eingangsnachweise, Abschlussprüfung und synthetische Mechanismuskontrollen.

Die Aufwandsbasis ist das finalisierte K2-Paket unter
`Experiments/fair_v2_oct24/K2/`. Dessen Quelle ist die explizit in
`provenance.json/native_D1_input_pin` gebundene private Einzelaufrufdatei.
Die bereits abgeschlossenen Originalbelege und Rohantworten bleiben privat und
unverändert. Die öffentlichen Aggregate enthalten keine Rohurteile oder
Quelltexte. Eine Reproduktion ohne diese privaten Eingänge ist nicht möglich.

## Reproduktion auf CPU

Aus dem Repository, mit der vorhandenen Experimentumgebung:

```powershell
Experiments/.venv/Scripts/python.exe -B -X utf8 EF1/run.py
Experiments/.venv/Scripts/python.exe -B -X utf8 EF1/plot.py EF1/result.json
Experiments/.venv/Scripts/python.exe -B -X utf8 EF1/render_report.py
Experiments/.venv/Scripts/python.exe -B -X utf8 -m pytest EF1/test_accounting.py EF1/test_metrics.py -q
```

Benötigt werden NumPy, SciPy und Matplotlib, für die Kontrollen pytest. Die
Ausführung prüft den expliziten finalen D1-Eingang und die K2-Dateipins und
schreibt ausschließlich abgeleitete EF1-Ausgaben. Exakte Laufzeitversionen
stehen im Abschlussbeleg. Sie verwendet unverändert die vollständige
24-Quellen-N10-Matrix mit 10.000 Ziehungen und dem G2-Seed. Die vorher festgelegte
kostenbekannte Teilmenge wird innerhalb jeder Ziehung ausgewertet. Damit bleiben
Kosten und Qualität gepaart, auch wenn die Teilmengenanzahl pro Ziehung variiert.

## Aussagegrenze

Listenpreise sind keine Rechnungen. Forschungskosten werden nicht auf die Arme
verteilt. Für die vier versiegelten Quellen fehlen historische Extraktionskosten.
Fehlende Zeiten oder Kosten werden nicht null gesetzt. Für X3 liegt am
gebundenen Stand kein gemessener unabhängiger Lauf vor. AS+G gegen V1 ist ein
beschreibender Kontrast, kein rechenaufwandsgleicher AutoSchemaKG-Versuch und
keine kausale Isolation des Aufwands- oder Architektureffekts.
