# X3: Prüffilter nur für VV – nachträglich, explorativ

[Ergebnis](result.json) · [kurze Tabelle](tabelle.md) ·
[Analyseprotokoll](PROTOKOLL.md)

Die Analyse wurde nach Kenntnis der unterschiedlichen VV-/EE-Präzision aus
[H12](../Experiments/fair_v2_oct24/H12/result.json) beauftragt. Sie ist
hypothesenbildend. Sie ändert weder V2 noch die vorregistrierten Tests oder
das Gesamturteil. H2 der neuen Zellen ist nicht bewertet und wird nicht geschätzt.

Nachträglich, explorativ erreicht AS+G(VV) einen H1-Punktwert von 87,0 % bei
236/3.609 entfernten Aussagen (6,5 %). V1+G(VV) erreicht 89,4 % bei
166/5.073 Entfernungen (3,3 %). Gegenüber AS beziehungsweise V1 sind die
Punktdifferenzen +5,2 beziehungsweise +2,3 Prozentpunkte. Gegenüber den jeweiligen
Vollfiltern liegen beide VV-Varianten rund 0,8 Prozentpunkte niedriger.
Die Intervalle stehen in der Tabelle und in der Ergebnisdatei.

In der festen H12-Stichprobe werden 16 EE-Entfernungen zurückgenommen:
7 Aussagen sind nach Autorenurteil gestützt, 5 nicht gestützt und 4 unklar.
Von den weiterhin entfernten 44 VV-Aussagen sind 34 nicht gestützt,
9 gestützt und 1 unklar. Dieser nachträglich, explorativ beschriebene Trade-off
liefert keinen unabhängigen Nachweis für die neue Filterauswahl.

## Verfahren

`projection.py` leitet aus den 136 ungefilterten AS-/V1-Elterninventaren der
24 H1-Konfirmationsquellen die beiden VV-Varianten ab. Hierzu werden ausschließlich
die vorhandenen VV-Entfernungen über die vorhandene C1-/A8-Funktion `project_subset`
angewandt. Zuvor entfernte EE sowie sämtliche EV bleiben erhalten. Beide
Exportansichten werden erzeugt und an ihre unveränderten nativen Werte gebunden.
Ursprünglich nicht durch den Prüffilter beurteilte Einträge erhalten kein neues Urteil.

`run.py` liest ausschließlich die explizit gebundenen Eingänge. `analysis.py`
vererbt C2-Rohcodes, Auswahlinformationen, Fehlwerte und Werte über die globalen
Vorkommens-IDs. Es verwendet die vorhandenen D1-/N10-Helfer für H1 auf dem
**gesamten verbleibenden Inventar**. Der gemeinsame Quellen-/Originalgruppenbootstrap
hat 10.000 Replikationen und Seed 2026102407. Die vier vorhandenen H1-Punktwerte
und der Bootstrapmatrix-Hash werden gegen den unveränderten D1a-Stand abgeglichen.
Die Intervalle sind marginale Perzentilintervalle. Es werden keine Tests, p-Werte,
Multiplizitätskorrekturen oder Nichtunterlegenheitsentscheidungen berechnet.

`author.py` kreuzt die unveränderte feste 90er-H12-Stichprobe mit den abgeleiteten
Mitgliedschaften. Die Einzelurteile bleiben privat. Die Aggregate sind keine
Prävalenzschätzung und keine unabhängige Bestätigung der nachträglichen Auswahl.
`report.py` stellt die gelieferten Aggregate dar, ohne eine Schätzung neu zu berechnen.

## Reproduktion und Messgrenzen

Die vollständige Reproduktion benötigt die gebundenen privaten Originalarchive,
C1-Entscheidungen, C2-Exporte und H12-Ursprungsannotation. Der öffentliche Ergebnisstand
enthält die jeweiligen Bytezahlen und SHA-256-Werte. Private Pfade und einzelne
Aussagen verbleiben im Ausführungsnachweis der privaten Evidenzablage.

Der einmalige Aufruf von `X3.projection.run_projection(output_dir)` liefert den
Pin der vollständigen neuen Mitgliedschaft. Dieser wird als eigenes JSON mit
`path`, `bytes`, `sha256` an den Auswerter übergeben:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m X3.run --membership-pin <Pin-Datei> --h12-handoff <originale-private-H12-Übergabe> --private-output <neues-privates-Ausgabeverzeichnis>
```

Der Auswerter überschreibt kein vorhandenes Ergebnis und prüft die Eingänge
vor und nach der Berechnung. `X3.report.write_tables(result, output_dir)` erzeugt
die Markdown- und LaTeX-Tabelle aus genau diesem Ergebnis. Softwaretests auf
synthetischen Eingaben laufen mit `python -m pytest X3 -q -p no:cacheprovider`.
Diese Softwaretests sind keine statistischen Tests der natürlichen X3-Ergebnisse.

N10 verwendet ein kostenbedingt gestopptes C2-Präfix. Gleiche
Einschlusswahrscheinlichkeiten sind nicht nachgewiesen. Nicht ausgewählte
Vorkommen werden weder als Fehlurteile noch als technische Ausfälle behandelt.
Technische Fehlwerte bleiben separat ausgewiesen. Der konservative N10-Punktwert
zählt für sie keinen Erfolg; die Identifikationsschranken werden getrennt ausgegeben.
Entfernungsanteile beziehen sich dagegen auf sämtliche ursprünglichen nativen
Vorkommen und sind entsprechend von der H1-Stichprobe zu unterscheiden.

Es wurden keine neuen Modelle, Referenzen oder externen Qualitätsbewertungen
angefordert. Die Analyse erlaubt keine Aussage zur Schemaqualität der neuen
Zellen und keinen bestätigten Gesamtvorsprung.
