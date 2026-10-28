# Nachtrag 11b: letzter Qualifikationsversuch für NIM-2 mit Dreiergruppen (25.10.2026)

**Anlass:** Beide Kandidaten aus N11 verfehlten das Gate. Nemotron 3 Ultra 550B erreichte SS 12/13 und Fein 19 richtige
von 21 auswertbaren Urteilen. Eine Sechsergruppe war wegen eines verletzten Ausgabeauftrags unverwertbar, das Ergebnis
lautet daher 19/27. MiniMax M3.1 Flash endete mit einem unbekannten Abschluss nach 300 s. Natürliche Ausgaben wurden
von keinem NIM-Modell bewertet. Dieser Nachtrag gilt prospektiv und ändert keine primäre Bewertung.

## Einziger weiterer Versuch

- **Technische Bedingung „Dreiergruppen“:** dieselben B1-Kontrollen, derselbe unveränderte Bewertungsprompt, nur
  **höchstens drei Fälle je Anfrage** statt sechs. Wird strukturierte JSON-Ausgabe vom Endpunkt unterstützt, darf sie als
  Formatvorgabe gesetzt werden. Das wird dokumentiert, der Prompttext bleibt unverändert.
- **Kandidaten:** zuerst `nvidia/nemotron-3-ultra-550b-a55b`, bei Nichtbestehen `nvidia/nemotron-3.5-super-vl-120b-a12b`.
  Schluss nach dem ersten bestandenen Kandidaten.
- **Gate unverändert:** mindestens 12/13 SS und 25/27 Fein, kein unbekannter Abschluss. Unverwertbare Ausgaben zählen als
  falsch. Keine Formatreparatur und kein Replay.
- **Bei Bestehen** gilt N11 §2 mit Dreiergruppen als Ausführungsbedingung für alle NIM-2-Bewertungen.
- **Bei Nichtbestehen** wird der NIM-Pfad endgültig beendet. Die Robustheit der Bewertung stützen dann die
  Autorenannotation (C7, κ gegenüber Sol) und die bestandenen Kontrollqualifikationen. Das fehlende zweite
  Modellurteil wird im Manuskript als Grenze genannt. T1 wird dann nur strukturell berichtet (X1-Metriken,
  Entfernungsraten).
- **Zeitgrenze:** Ist die Qualifikation bis Montag 10 Uhr nicht abgeschlossen, gilt sie als nicht bestanden.
