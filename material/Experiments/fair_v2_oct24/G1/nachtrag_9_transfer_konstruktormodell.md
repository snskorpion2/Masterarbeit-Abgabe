# Nachtrag 9: explorative Transferbedingung mit zweitem Konstruktormodell (25.10.2026)

**Status:** explorativ und ausdrücklich **nicht** Teil der primären oder sekundären Testfamilien aus G2 und
Nachtrag 8. Festgelegt bevor eine natürliche Ausgabe dieser Bedingung existiert und bevor aggregierte
C2-/C3-/C6-/C7-Ergebnisse der Hauptbedingung ausgewertet wurden. Ziel: FF3, also ob die Richtung der
Komponenten- und Gesamteffekte bei einem anderen Konstruktormodell erhalten bleibt.

## Bedingung

- **Konstruktor und Schemainduktion:** `qwen.qwen3-235b-a22b-2507` über Bedrock Mantle, T 0,7, max. 8.192
  Ausgabetokens, sonst identische Prompts, Parser, Chunking und Parameter wie B3. Familie Alibaba, also
  verschieden von Prüffilter (Moonshot) und Bewertern (OpenAI, xAI).
- **Population:** die 20 Frischquellen aus A4, **ein Durchlauf** je Arm (AS, V1). Die vier versiegelten Quellen
  werden nicht verwendet.
- **Prüffilter:** unverändert Kimi-K2.5 mit Facettenregel (wie C1), Nachträge 2, 5 und 7 gelten.
- **Zellen:** AS, AS+G, V1, V2 (nur zeilengenauer Export).

## Auswertung (nur wenn die Bewertung stattfindet)

- **H1 und H2** mit identischem Sol-Protokoll (C2/C3, Flex-NoWrite), gleiche Referenzen aus B2.
- Berichtet werden Punktschätzer und 95-%-Cluster-Bootstrap-KI für V2 gegen AS und für die Kontraste K1–K6, **ohne
  Holm und ohne Bestätigungsanspruch**. Die zentrale Frage ist, ob das Vorzeichen der Hauptbedingung erhalten bleibt.
- Findet keine Bewertung statt, werden nur beschreibende Strukturgrößen berichtet (X1-Metriken, Entfernungsraten
  des Prüffilters nach Typ und Facette).

## Ressourcen- und Startregeln

- Konstruktion und Prüffilter: AWS, Deckel 20 USD, sofort startbar, ohne Konkurrenz zu Sol.
- **Bewertung erst, wenn C2 und C3 der Hauptbedingung vollständig abgeschlossen sind** und das verbleibende
  Foundry-Budget im Rahmen der Nutzerfreigabe (50 EUR gesamt) die konservative Prognose für die Transferbewertung
  deckt. Die Hauptbedingung hat immer Vorrang. Die Entscheidung trifft die Koordination am Montag spätestens 14 Uhr.
- Fehlwerte und Ausfälle wie G2 und Nachträge 2–7. Kein Replay von Bewertungsaufrufen.
