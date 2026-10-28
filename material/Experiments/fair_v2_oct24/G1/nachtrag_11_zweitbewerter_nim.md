# Nachtrag 11: kostenloser Zweitbewerter über NVIDIA NIM (25.10.2026)

**Status:** sekundär bzw. explorativ, **ohne** Änderung der primären Bewertung. H1 und H2 bleiben bei Sol (G2, N4,
N10). Es gibt keinen Bewerterwechsel innerhalb eines primären Endpunkts. C4 (Grok) bleibt gestrichen. Festgelegt vor
jeder aggregierten Auswertung natürlicher C2-/C3-Urteile und bevor ein NIM-Modell natürliche Vergleichsausgaben
bewertet hat. Gilt nur, wenn das Qualifikationsgate in Abschnitt 1 bestanden ist.

## 1. Qualifikation (Gate wie B1)

- Kandidaten in dieser Reihenfolge: `nvidia/nemotron-3-ultra-550b-a55b`, danach `minimaxai/minimax-m3.1-flash`.
  Beide Familien (NVIDIA, MiniMax) sind verschieden von Konstruktor, Prüffilter und Hauptbewerter.
- Unveränderte B1-Kontrollen (13 SS, 27 Fein mit 15 Quellen- und 12 Erhaltsfällen), unveränderter
  Main12-Bewertungsprompt, Sechsergruppen, T 0 bzw. Modellstandard, falls T 0 nicht unterstützt wird
  (dokumentieren), Ausgabelimit ausreichend für Reasoning.
- Gate: mindestens 12/13 SS und 25/27 Fein, kein unbekannter Abschluss, Format verwertbar. Der erste bestandene
  Kandidat wird Zweitbewerter „NIM-2“.

## 2. Einsatz nach bestandenem Gate

1. **Vollständige Zweitbewertung von H1** auf allen 8.682 Aussagen der 24 Konfirmationsquellen (dieselben
   verblindeten Sechsergruppen wie C2). Berichtet werden:
   - Cohen-κ zwischen NIM-2 und Sol auf allen gemeinsam gültig bewerteten Aussagen,
   - Cohen-κ zwischen NIM-2 und den Autorenlabels (C7),
   - H1-Punktschätzer und 95-%-Cluster-Bootstrap-KI je Zelle sowie für V2 gegen AS und K1, K3, K6 unter NIM-2,
     **ohne Holm, sekundär**,
   - der Anteil gestützter Aussagen unter den vom Prüffilter entfernten Aussagen. Das ist die Gegenprüfung der
     Zirkularität aus einer dritten Modellfamilie.
2. **Herabstufungsregel aus N8:** Zeigt NIM-2 für V2 gegen AS (H1) ein entgegengesetztes Vorzeichen des
   Punktschätzers, wird H1 als „bewerterabhängig“ qualifiziert. Damit übernimmt NIM-2 die vorgesehene Rolle von Grok.
3. **H2-Zweitbewertung (C3-Pakete)** nur, wenn nach Punkt 1 Zeit bleibt. Gleiche Berichtsform, sekundär.
4. **T1 (N9) explorativ** mit NIM-2 als Bewerter für H1 (und H2, falls Zeit bleibt) auf den T1-Zellen. Das
   ersetzt die in N9 vorgesehene Sol-Bewertung, weil das Foundry-Budget nicht reicht. Der Vergleich ist intern
   konsistent (alle T1-Zellen gleicher Bewerter). Die Übertragbarkeit zu Sol wird über das κ aus Punkt 1 eingeordnet.

## 3. Ausführung

Kostenlos, höchstens 40 RPM gemeinsam. Priorität: Qualifikation → H1-Zweitbewertung → T1 → H2. Kein Replay bei
Zeitüberschreitung oder unbekanntem Abschluss (Fehlwert nach G2). Zeitgrenze: Bewertungen, die bis Dienstag 18 Uhr
nicht abgeschlossen sind, werden als Teilbestand berichtet.
