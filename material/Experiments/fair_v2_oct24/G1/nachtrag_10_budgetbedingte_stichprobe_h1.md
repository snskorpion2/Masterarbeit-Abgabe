# Nachtrag 10: budgetbedingte Zufallsstichprobe für H1 als Rückfall (25.10.2026)

**Anlass:** Das tatsächliche Foundry-Guthaben beträgt insgesamt ca. 42 EUR seit dem 24.10. Es kann nicht
aufgestockt werden (Nutzer, 25.10.). Die konservative Prognose für das vollständige C2 und C3 liegt darüber.
**Zeitpunkt:** prospektiv, vor jeder aggregierten Auswertung natürlicher C2-/C3-Urteile. Der in Nachtrag 8
offengelegte Einzeleinblick eines Helfers gilt unverändert. Dieser Nachtrag ersetzt den unfreigegebenen
Entwurf `entwurf_planB_stichprobe_unfreigegeben.md` und behebt dessen drei offene Punkte.

## Ausführungsregel

1. **C3 (H2) hat Vorrang, mit vollständiger Bewertung als Ziel.** C2 läuft parallel in seiner unveränderten Reihenfolge weiter, soweit die folgende Budgetregel dies zulässt. Nach direkter Nutzerpräzisierung vom 25.10. bleibt der Gesamtdeckel von 42 EUR hart. Reicht er auch für C3 nicht aus, wird C3 nur bis zu diesem Deckel fortgesetzt und der verbleibende Rest ausdrücklich als fehlend ausgewiesen. Keine Wiederholung bereits versuchter Anfragen.
2. **Budgetstopp für C2:** Vor jeder neuen C2-Gruppe wird geprüft:
   bisheriger Foundry-Verbrauch (Tokenzähler, konservativer Tarif) + konservative Restprognose C3 + Sicherheitsreserve
   1,50 EUR ≤ 42 EUR. Sonst stoppt C2 an dieser Gruppengrenze. Kein Replay, keine Neuordnung.
3. Wird C2 vollständig, gilt ausschließlich G2. Dieser Nachtrag wird dann nicht angewendet.

## Stichprobe und Schätzung, nur bei Budgetstopp

- **Stichprobe:** Die gezogenen Positionen einschließlich Fehlversuchen bilden ein Präfix der vorab geseedeten, inhaltsunabhängigen globalen
  Permutation aller 8.682 Aussagen, die vor dem Packen in Sechsergruppen permutiert wurden (Seed und Orderhash
  belegt). Der Präfix umfasst auch administrativ fehlende, ungültige und unbekannt abgeschlossene Gruppen. Nur die gültigen Antworten bilden keinen Präfix.
  Die Reihenfolge ist zufällig und ergebnisunabhängig. Der Umfang K hängt vom Budget über die Gruppenkosten ab,
  nicht von einer Sichtung der Qualitätsurteile. Wegen des kostenabhängigen Stopps sind gleiche Inklusionswahrscheinlichkeiten
  jedoch nur näherungsweise anzunehmen. K/1.447 wird als Näherung verwendet, nicht als nachgewiesene exakte
  Inklusionswahrscheinlichkeit. Mit Einheitenmerkmalen zusammenhängende Tokenkosten können die Stoppzeit informativ machen.
- **Status:** „nicht gezogen“ ist kein Fehlwert. Fehlwerte innerhalb der Stichprobe folgen G2 (symmetrisch
  konservativ).
- **Primärschätzer H1 je Quelle und Zelle:** gepoolter Anteil gestützter Aussagen unter allen gezogenen Aussagen
  dieser Quelle über alle ihre Durchläufe (Verhältnisschätzer). Danach Quellen gleich gewichtet. Diese
  Aggregation gilt einheitlich für alle Zellen und Quellen. Sie vermeidet, dass leere Durchlaufzellen die
  Gewichtung still verschieben (offener Punkt 3). Die G2-Aggregation (erst Durchläufe, dann Quellen) wird als
  Sensitivität berichtet, soweit definiert.
- **Gefilterte Zellen** (AS+G, V2) erben genau die gezogenen Urteile ihrer Elternaussagen. Eltern- und gefilterte Zelle
  verwenden damit dieselbe Stichprobe, und die Paarung bleibt erhalten (offener Punkt 1).
- **Unsicherheit:** zweistufiger gepaarter Bootstrap mit 10.000 Ziehungen und dem Seed aus G2. Zuerst werden
  Quellen mit Zurücklegen gezogen, dann innerhalb jeder Quelle die **gezogenen Sechsergruppen** als
  Stichprobeneinheit mit Zurücklegen. Alle Zellen und Kontraste verwenden dieselbe Indexmatrix (offener Punkt 2).
  Die ursprünglichen globalen Gruppenkennungen bleiben erhalten. Da Gruppen mehrere Quellen enthalten, werden innerhalb einer Quelle nur deren Aussagen aus den jeweiligen Originalgruppen verwendet. Es werden keine neuen quelllokalen Sechsergruppen gebildet.
  Eine Endlichkeitskorrektur wird nicht angewandt. Das ist konservativ und wird so benannt.
- **Nicht schätzbar:** Hat eine Quelle in einer Zelle keine gezogene Aussage, ist ihr H1-Wert nicht schätzbar. Es
  gilt die G2-Regel für nicht schätzbare Werte (Schranken 0 bis 1 in der Sensitivität, kein Weglassen der Quelle).
- **Tests und Holm** unverändert (G2, N8 für K1, K3, K6). H2 und H4 sind nicht betroffen.
- **C7 (Autor) und X2(c):** κ und die Verankerungsquote nur über Aussagen mit gültigem C2-Urteil. Die Anzahl wird berichtet.
- **Beschreibende Auswahlprüfung:** Die Verteilungen von Quellen, Armen und Aussagetypen im gesamten gezogenen Präfix werden der vollständigen Population gegenübergestellt. Fehlversuche bleiben im Präfix. Diese Prüfung nutzt keine Qualitätsurteile und begründet weder exakte Inklusionswahrscheinlichkeiten noch einen Qualitätsvorteil.

## Darstellung

Im Manuskript wird offen genannt, dass das begrenzte Bewertungsbudget vor jeder aggregierten Auswertung zur
Schätzung von H1 auf einem zufällig angeordneten, kostenbegrenzt gezogenen Präfix von K der 1.447 Gruppen führte, mit Stichprobenquote je Arm.
Die nur näherungsweise gleichen Inklusionswahrscheinlichkeiten und die beschreibenden Auswahlverteilungen werden ausdrücklich genannt. Schätzer, Bootstrap und Holm-Regeln bleiben unverändert. Eine mögliche budgetbedingte Unvollständigkeit von C3 folgt weiterhin den G2-Fehlwertregeln und wird nicht als vollständiger H2-Nachweis dargestellt.
