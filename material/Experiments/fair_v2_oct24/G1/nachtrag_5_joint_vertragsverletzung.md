# Nachtrag 5 zur Vorregistrierung: vollständige, aber vertragsungültige Joint-Antworten (25.10.2026, präzisierte Fassung)

Prospektiv für die weitere Konstruktion. Anlass ist B4, Batch 0151 / V1-Job 005, Absatzindex 744. Die Antwort
ist HTTP 200 mit `stop` und vollständig, striktes JSON und Schema sind gültig, aber ein neues EE-Objekt hat einen
leeren Tail. Es wurden keine Inhalte zur Qualität gesehen.

**Einordnung:** Der Original-AS-Parser `parse_native(entity_relation)` und der V1-Präfixparser
`classify_native_prefix` akzeptieren einen leeren Tail unverändert. Nur die **zusätzliche
Joint-Nativeprüfung** (`completion_contracts._native_value`) verwirft ihn. Es handelt sich also um eine
**asymmetrische, zusätzliche Validierungsschwelle, die nur den Joint-Pass von V1 betrifft**. Keine
bestehende Regel deckt diesen Fall eindeutig ab. Nachtrag 2 betrifft nur Netzwerkfehler, Timeouts und
unbekannte Abschlüsse. Diese Regel ist deshalb eine **prospektive Ergänzung der Konstruktion**. Sie wurde
nach Sicht dieses einen B4-Ausgabefehlers festgelegt, aber vor jeder H4-Bewertung. Für H4 wird sie als
nachträgliche Konstruktionsänderung gegenüber G2 sichtbar berichtet und nicht als Teil der ursprünglichen
G2-Konfirmation ausgegeben.

## Regel

1. Eine **vollständig empfangene** Joint-Antwort von V1, die den gebundenen Joint- oder Native-Value-Vertrag
   verletzt, wird **als Ganzes abgelehnt**. Es gibt
   - keine Teilübernahme gültiger Objekte,
   - keine Parserlockerung,
   - keine Ergänzung oder Filterung von Objekten,
   - keine Neugenerierung und keinen erneuten Versuch.
2. Die Inventarzelle besteht dann aus dem **unveränderten nativen V1-Präfix ohne Ergänzung** für diesen
   Chunk. Der Chunk bleibt in beiden Armen im Korpus, und es gibt keinen Ausschluss. Begründung: So bleiben ein
   identischer Korpus und der gültige native Präfix erhalten. Das ist eine eigene Fallbackregel für die
   zusätzliche Joint-Schwelle und keine Wiedergabe einer gleichartig ausgeführten Original-AS-Validierung.
3. Rohantwort, Ablehnungsgrund und Token-/Kostenverbrauch werden erhalten. Der Verbrauch zählt zum Aufwand von
   V1. Berichtet werden Zahl und Anteil abgelehnter Joint-Antworten bei V1. Für AS gibt es keine
   Joint-Aufrufe. Die Quote ist dort **nicht anwendbar** (nicht 0/0).
4. **Geltung nur prospektiv.** B3 ist mit allen 136 nativen Präfixinventaren bereits positiv gebunden und teils
   durch C1 und C2 konsumiert. Nachtrag 5 schreibt keine bestehende Bindung, kein Inventar und kein Label
   rückwirkend um. Gleichartige historische Fälle in B3 werden höchstens diagnostisch gezählt. Die bestehende
   Bindung bleibt erhalten.
5. AS-745 wird rein auf CPU aus den drei gespeicherten Antworten fertiggestellt. Nie gestartete Jobs laufen
   unverändert weiter, im unveränderten Deckel von 25 USD. Keine Antwort wird wiederholt oder teilweise gefiltert.
6. Für Q60 bleibt der Nenner 60. Fehlwerte in der QA folgen G2.
