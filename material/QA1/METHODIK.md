# QA1: nachträgliche, beschreibende H4-Diagnose

Direkter Auftrag vom 26.10.2026. Der H4-Endbefund ist bereits bekannt. Diese
Diagnose ist nicht vorregistriert und verändert weder H4 noch Holm-Familien,
Gesamtstufe, Retrieval, Readerantworten oder die versiegelten Referenzen.
Es gibt keine neuen Modellaufrufe, Encoderläufe, Referenzantworten,
Signifikanztests, Bootstrapziehungen oder zweite C6-Endprüfung.

Einheit sind die 60 fest gebundenen Fragen. Die acht vorhandenen Graphzellen
werden getrennt ausgegeben. Die kompakte Anhangtabelle verwendet AS original,
AS+G original, V1 zeilengenau und V2 zeilengenau. Damit bleibt der H4-Kontrast
V2 zeilengenau gegen AS original erhalten und der Vergleich V2/V1 hält die
Exportansicht fest. Fragen aus gemeinsamen Absatzblöcken sind keine zusätzlich
unabhängigen Beobachtungen.

1. **Lexikalische Abdeckung:** Die vorhandene Goldantwort und ausschließlich
   ihre vorhandenen Aliasse werden mit dem unveränderten offiziellen
   MuSiQue-Normalisierer bearbeitet. Ein Treffer ist eine nichtleere,
   zusammenhängende ganze Tokenfolge im tatsächlich gespeicherten Top-30-
   Graphkontext, ohne den Fragetext. Der Nenner bleibt 60. Zusätzlich wird
   ausgewiesen, ob die Folge innerhalb einer einzelnen Aussage vorkommt,
   um zufällige Verkettung über Aussagegrenzen sichtbar zu halten.
2. **Antworttragende Aussage aus einem Stützabsatz:** derselbe lexikalische
   Test innerhalb einer einzelnen ausgewählten Aussage mit gebundener
   Originalherkunft in einem der für diese Frage als `is_supporting`
   markierten MuSiQue-Absätze. Die Herkunft wird aus den unveränderten nativen
   Vorkommen und der tatsächlich sichtbaren Exportaussage verbunden.
   Verlorene oder mehrdeutige Herkunft bleibt kenntlich. Die Markierung eines
   Absatzes beurteilt keine aus ihm extrahierte Aussage semantisch.
3. **Entfernte Antwortvorkommen:** ausdrücklich protokollierte native
   Guard-Löschungen aus AS zu AS+G bzw. V1 zu V2. Der lexikalische Test wird
   auf die vollständigen ursprünglichen nativen EE-/VV-Werte angewandt.
   Fragen mit mindestens einem Treffer, Aussage-Frage-Paare und verschiedene
   native Vorkommen werden getrennt gezählt. Die strengere Untermenge aus den
   tatsächlichen Stützabsätzen wird zusätzlich ausgewiesen. Das ist keine
   Bilanz kausal verlorener Antworten und kein Vergleich neu berechneter Rankings.
4. **Diskordante EM-Paare:** unveränderte offizielle frageweise EM-Werte aus
   C6, verbunden anhand der tatsächlichen Frageidentität. Für V2 zeilengenau
   gegen AS original sowie V2 zeilengenau gegen V1 zeilengenau werden beide
   richtig, beide falsch und die beiden einseitigen Treffer gezählt.
5. **Beobachtete Präzision:** halbe Breite `(Obergrenze−Untergrenze)/2` des
   vorhandenen marginalen H4-95-%-Intervalls aus D1. Das asymmetrische
   Perzentilintervall wird nicht als symmetrisches Plusminusintervall um den
   Punktschätzer umgedeutet. Keine Power oder minimale erkennbare Wirkung.

Leere normalisierte Antworten ergeben keinen automatischen Treffer. Wenn kein
nichtleerer Alias verbleibt, ist die Frage für diese lexikalische Diagnose
nicht messbar. Unbekannte Herkunft wird nicht als negativer Befund behandelt.
Der tatsächliche Nenner und fehlende Messbarkeit stehen in den Aggregaten.

Wörtliche Antwortabdeckung ist weder semantischer Quellenrecall noch der
Nachweis einer vollständigen Mehrschrittbegründung oder tatsächlicher
Graphnutzung durch den Reader. Gleichlautende Antworten können in einem
anderen Zusammenhang vorkommen. Der Gold-Absatzkontext ist eine eigene
Kontrollbedingung, keine fehlerfreie Antwortobergrenze.

Öffentlich liegen nur aggregierte Zahlen, Methodik, Code, synthetische Tests
und die beiden LaTeX-Übergaben. Fragekennungen, Antworten, Aliasse, Quellen- und
Aussagetexte, individuelle EM-Paare und vollständige Dateipins bleiben im
privaten Evidenzverzeichnis außerhalb des Repositories.
