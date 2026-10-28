# H15: verblindete Autorenprüfung des Bedeutungserhalts

H15 setzt den vor der Ziehung einzeln veröffentlichten
[Nachtrag 15](../Experiments/fair_v2_oct24/G1/nachtrag_15_menschliche_pruefung_h2.md)
um. Der Veröffentlichungsbeleg steht in [publication.json](publication.json).

## Ergebnis vom 26.10.2026

Der direkte Export mit 30 bestätigten Autorenlabels wurde einmal nach N15
ausgewertet. Autor und Sol stimmen in 27 von 30 Fällen überein.
κ beträgt 0,750 für drei Klassen und 0,7337 binär. Die binäre
N15-Schwelle für „H2 bewerterabhängig“ wird nicht ausgelöst, das
95-%-Fallbootstrapintervall [0,3750; 1,0000] ist jedoch breit.
Unter Autorenlabels sind bei AS 11/15 und bei V2 12/15 Bedeutungen vollständig
erhalten. Die gepaarte Differenz von +6,7 Prozentpunkten ist beschreibend.
Methode, Matrizen und Grenzen stehen im [Ergebnisbericht](BERICHT.md).

## Durchführung

Die eigenständige Datei `H15-Annotation-30.html` liegt außerhalb des Repositorys
im Downloads-Verzeichnis des Autors. Sie wird dort manuell in einem aktuellen
Browser geöffnet. Jede der 30 Positionen zeigt die gesamte Referenzbedeutung
einschließlich aller geforderten Aspekte, den vollständigen Quelltext und das
vollständige ursprünglich von C3 bewertete aktive Inventar. Ein Suchfeld filtert
die Anzeige. Es ändert den gespeicherten Bestand nicht. Mit Zurücksetzen werden
alle Einträge wieder angezeigt.

Die vier Auswahlmöglichkeiten sind „vollständig enthalten“, „teilweise
enthalten“, „nicht enthalten“ und „unklar“. Es gibt keine Vorauswahl. Kommentare
sind möglich. Arm, Durchlauf, Sol-Urteil und Paarzuordnung stehen weder sichtbar
noch versteckt in den Clientdaten. Vollständige native Werte und ihre Reihenfolge
bleiben erhalten. Nur technische Fall- und Belegkennungen sind neutral ersetzt.
Inhaltliche Unterschiede können Rückschlüsse zulassen.

Der Browser speichert Eingaben lokal an dieses konkrete Paket gebunden. Zusätzlich
können Zwischenstände direkt als JSON exportiert und wieder importiert werden.
Am Ende wird der vollständige Originalexport mit dem Exportknopf heruntergeladen.
Der Autor teilt dessen Dateipfad mit. Die Datei wird ohne Umschreiben von Labels,
Kommentaren und Zeitstempeln privat bytegleich übernommen. Das Herkunftsfeld
`human_ui_input` stammt aus dem Werkzeug. Es ersetzt nicht die Zuordnung der
Datei zum Autor.

## Feste Stichprobe und Eingabebindung

Die Ziehung verwendet einmalig `PCG64(2026102615)` nach N15. Aus dem Rahmen der
17 Quellen mit gültigen AS- und V2-Urteilen werden 15 eindeutige Bedeutungen
proportional nach Wikipedia und Factbook geschichtet gezogen. Eine Bedeutung
wird höchstens einmal gewählt. Für jedes Paar wird ein gemeinsamer gültiger
Durchlauf gewählt, anschließend werden alle 30 Fälle gemeinsam permutiert.
Die Sol-Klasse ist kein Auswahlkriterium. Technische Fehlwerte werden nicht als
negative Erhaltung ausgegeben. Es gibt keine Nachziehung.

Die Auswahl bindet den eingefrorenen G2-Quellenbestand und den tatsächlichen
C3-Endexport aus `C2/n10_finalization_v2/actual_end_oct25.json`. Der Originalfall
wird über den im C3-Urteil gebundenen Job und dessen gepinntes Originalsegment
mit der ursprünglichen vollständigen Anfrage abgeglichen. Eine übereinstimmende
Fallkennung allein genügt nicht. Quelldateien, Referenzen, Inventare, Originalfälle,
Auswahlschlüssel und Einzelexporte bleiben im privaten Paket außerhalb des
Repositorys. Öffentlich werden Code, Methode, Hashes und Aggregate geführt.

## Auswertung nach dem direkten Export

`run.py` akzeptiert erst 30 gültige, paketgebundene Autorenlabels für die
Auswertung. Ein unvollständiger Export wird gesichert, liefert aber weder κ noch
Erhaltsquoten. Die Auswertung läuft einmal ohne Modellaufrufe:

```powershell
Experiments\.venv\Scripts\python.exe -X utf8 -B -m H15.run `
  --preparation-receipt <privates-Paket>\preparation-complete.private.json `
  --author-export <direkter-Originalexport.json> --author-confirmed
```

Das ungewichtete Drei-Klassen-κ schließt Paare mit unklarem Urteil auf einer
Seite aus. Das binäre κ vergleicht vollständig gegen den Rest einschließlich
unklar. Der originale Sol-Code `not_assessable` bleibt erhalten und wird nur im
Vergleich als unklar abgebildet. Beide Konfusionsmatrizen werden ausgegeben.
Beide κ verwenden dieselben 10.000 Fallbootstrap-Ziehungen mit
`PCG64(2026102616)`. Undefinierte Ziehungen bleiben undefiniert. Der vorgegebene
Fallbootstrap korrigiert keine Paar-, Quellen- oder Konstruktionsabhängigkeit.

Die Autorenquoten verwenden je Arm den festen Nenner 15. Die gepaarte Differenz
V2 minus AS ist beschreibend, ohne Test und ohne Prävalenzbehauptung. Binäres
κ kleiner 0,40 kennzeichnet H2 sekundär als „bewerterabhängig“. Undefiniertes κ
erlaubt keine Schwellenentscheidung. H15 ändert weder native D1-Auswertungen
noch Holm-Familien oder Gesamturteil. Diese kleine Zusatzprüfung ist keine
allgemeine Bewerterqualifikation.

## Technische Prüfung und Nachweise

Die CPU-Tests verwenden ausschließlich synthetische Daten:

```powershell
Experiments\.venv\Scripts\python.exe -X utf8 -B -m pytest H15 -q
node H15/test_ui.mjs
```

Die JavaScript-Prüfung führt die tatsächlich ausgelieferte UI-Logik in einer
synthetischen Node-Umgebung aus. Eine reale Browseransicht ist damit nicht
bestätigt. Der Browserzugriff auf lokale Datei-URLs wurde von der
Sicherheitsrichtlinie abgewiesen. Diese Sperre wurde nicht umgangen.
Die Datei wird dem Autor zum manuellen Öffnen bereitgestellt.

[result.json](result.json) enthält den öffentlichen tatsächlichen Stand,
[verification.json](verification.json) die technische Prüfung des vorbereiteten
Pakets und [author-verification.json](author-verification.json) den Abschluss
der einmaligen Auswertung des direkten Autorenexports.
