# Nachtrag 14: Umgang mit den budgetbedingten C3-Lücken bei H2 (25.10.2026)

**Zeitpunkt:** prospektiv, vor jeder Auswertung natürlicher C3-Urteile. Bekannt sind nur technische Metadaten
(`C3/missing_metadata_v1`): 1.824 von 2.336 Urteilspositionen gültig, 512 fehlend (484 nie gestartet wegen des
42-€-Deckels, 28 begonnen ohne gültiges Urteil). Die Lücken verteilen sich gleichmäßig auf die Arme (je 121 nie
gestartet). Sie konzentrieren sich aber auf Quellen: Nur 17 von 24 Quellen haben überhaupt gültige Urteile.
Fehlwertquote gepoolt 21,9 %, quellengleich gewichtet 31,5 %.

**Problem:** Nach G2 zählen fehlende Urteile in beiden Armen symmetrisch als „nicht erhalten“. Für Quellen ohne jedes
gültige Urteil ergibt das in allen Armen 0 und damit eine Differenz von genau 0. Für den **Nichtunterlegenheitstest**
von H2 (Grenze −5 Prozentpunkte) ist das **antikonservativ**, weil Nullen die Differenz in Richtung „nicht unterlegen“ ziehen.

## Festlegung

1. Die G2-Primäranalyse wird unverändert berechnet und berichtet.
2. **Zusätzlich verbindlich:** dieselbe H2-Analyse (Schätzer, Cluster-Bootstrap, Test gegen −0,05) auf den Quellen, die in
   **beiden** Kontrastarmen gültige Urteile haben („Quellen mit Urteilen“). Innerhalb einer Quelle zählen fehlende
   Positionen weiter symmetrisch nach G2.
3. **Entscheidungsregel für H2:** Nichtunterlegenheit gilt nur dann als bestätigt („✓“ in N8), wenn sie in **beiden**
   Analysen (1 und 2) nach Holm gilt. Sonst wird H2 als „nicht bestätigt“ eingestuft. Das gilt ebenso für K2 und K4 in
   der Komponentenfamilie. Eine Überlegenheit bei H2 bzw. K5 wird nur berichtet, wenn sie in Analyse 2 besteht.
4. Die Fehlwertquoten (21,9 % bzw. 31,5 %) werden als Einschränkung genannt. Liste der Quellen ohne Urteile im Anhang.
5. Keine Nachbewertung, kein Replay, keine Umgewichtung über das Festgelegte hinaus.
