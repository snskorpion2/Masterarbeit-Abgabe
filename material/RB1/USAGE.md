# RB1 nachrechnen

Die Rechnung gehört ausschließlich zu N17 §2. Sie verändert keine bestehenden D1-Dateien, Primärtests oder Holm-Familien. Der Bericht, die eine Anhangstabelle und die zwei Sätze werden separat geliefert, ohne Einbindung in das Manuskript.

## Eingänge

- Verbindlicher D1-Endbeleg: Experiments/fair_v2_oct24/D1/final_native_oct26_v1/result.json.
- Ursprüngliche private D1-Analyse: SHA-256 c45634ee7fda25c288491ae530387e752a3933592b3f244972c92df0d87c0fe2.
- Privates finales D1-Eingangsmanifest: SHA-256 1a495e8da34acfe4726fc45d44f62002cb4c23413c5355247471abb5dbf9ad11. Der lokal vorhandene Zeiger steht in .private-temp/d1-final-oct26/prepared-input-manifest-pin.private.json.
- RB1 liest die gepinnten Originale mit dem bestehenden D1-Loader und projiziert nur H1/H2-Felder. Quellen-, Antwort- und Aussageinhalte werden nicht öffentlich ausgegeben. Originale und alte Ergebnisse bleiben erhalten.
- Die einheitliche zweistufige N10-Matrix wird reproduziert und gegen den Endbeleg geprüft: e88daf8592fbf987e03cf9fc51642e462db9e142f788046dac0b3b8936235b76. Keine unabhängigen Armziehungen und kein neuer Seed.

## CPU-Ablauf

Vom Repository-Stamm mit der vorhandenen Python-Umgebung:

~~~powershell
.\Experiments\.venv\Scripts\python.exe -X utf8 -B -m RB1.prepare --manifest <lokaler-privater-D1-Manifestpfad> --private-output <neuer-privater-RB1-Ordner>
.\Experiments\.venv\Scripts\python.exe -X utf8 -B -m RB1.run --bundle <neuer-privater-RB1-Ordner>/bundle.private.json --original-analysis <gepinntes-privates-D1-Original>/analysis.json --output <neuer-Ergebnispfad>.json --private-output <neuer-privater-RB1-Ordner>
~~~

Die Platzhalter sind vor dem Aufruf durch vorhandene lokale Pfade zu ersetzen. Der Originaleingang darf nicht durch synthetische Daten ersetzt werden. Der private Ordner wird durch prepare angelegt. prepare überschreibt vorhandene Eingänge nicht.

Der mitgelieferte Renderer verwendet RB1/result.json. Er schreibt ausschließlich eigene RB1-Lieferdateien:

~~~powershell
.\Experiments\.venv\Scripts\python.exe -X utf8 -B -m RB1.render
~~~

Die synthetischen Solltests betreffen fehlende Typwerte, Gewichte aus vollständigen Beständen, Exportdoppelzählung, relative Senkung mit undefinierten Replikaten, ursprüngliche H2-Fehlwerte, feste N14-Quellenauswahl, Quellen-/Familienwegfall und den dritten Durchlauf:

~~~powershell
.\Experiments\.venv\Scripts\python.exe -X utf8 -B -m pytest -q -p no:cacheprovider RB1/test_analysis.py RB1/test_robustness.py
~~~

## Nachweisumfang

verification.json bindet Eingangs-, Ergebnis-, Code- und Tabellenbytes sowie die synthetischen Tests. Die strikten D1-H1-Zell- und Typwerte, der gepaarte Bootstrap und die primären H2-G2-/N14-Punktschätzer wurden gegen das unveränderte D1-Original verglichen. Die private Eingangsprojektion wurde nochmals wertgleich und mit der ursprünglichen Windows-Zeilenendendarstellung bytegleich hergestellt. Ein erster Vergleich gegen eine nur im Speicher LF-serialisierte Darstellung war wegen dieser Zeilenenden nicht bytegleich, die JSON-Inhalte waren identisch. Dieser technische Vergleich hat weder die Statistik noch die Eingänge geändert.

Die Vorschau anhang-vorschau.pdf enthält genau eine Tabelle auf einer Seite mit den bestehenden Schrift-, Rand- und Tabellenparametern. Die endgültige Gesamtseitenzahl ergibt sich erst nach der Einbindung ins Manuskript. Die Vorschau verwendet die eigenständige Nummer A.1, die spätere Nummer vergibt das Manuskript.

Die numerischen Replikate bleiben privat. Öffentlich stehen marginale Intervalle und vollständige gewünschte Kontrast-/Weglassaggregate, keine Einzelurteile oder Antworttexte. CPU-Arbeit erzeugt keine Modellaufrufe. Die vorhandenen N10-Auswahlgrenzen, die nicht zufällige N14-Abdeckung und die Modellabhängigkeit der H1-/H2-Urteile bleiben bestehen.
