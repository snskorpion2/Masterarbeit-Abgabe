# Nachtrag 2 zur Vorregistrierung (24.10.2026, ca. 23:15, korrigierte Fassung)

Prospektiv, vor jedem C2-Urteil außer der einen gesicherten ersten Sechsergruppe sowie vor jedem
C3-, C4-, C5- und C6-Ergebnis. Keine Bewertungsinhalte gesehen. Ersetzt Punkt 3 und 4 von
`nachtrag_c2c3_route.md`, weil die AWS-Route für Sol mit 403 nicht aufrufbar ist.

## 1. Hauptbewerter und Foundry-Budget

- **C2 (H1)** läuft vollständig mit Sol über Foundry, wie in B1 qualifiziert. Kein Wechsel des
  Bewertermodells innerhalb eines Endpunkts.
- **Deckel: Alle Foundry-Bewertungen zusammen höchstens 30 EUR** (direkt vom Nutzer belegte
  Freigabe). Davon zuerst C2, dann C3. C4 (Grok) erhält nur den tatsächlich verbleibenden Rest. Eine
  Erhöhung ist ausschließlich durch den Nutzer möglich.
- **Reihenfolge in C2:** unveränderte globale, verblindete Gruppenreihenfolge der bereits gepackten
  1.447 Sechsergruppen. Es wird nicht neu gepackt. Die ersten 6 bewerteten Fälle bleiben unverändert,
  kein Replay. Bei einem Budgetstopp gelten feste Nenner und G2-Schranken.
- **Kostenmessung:** Nach ca. 50 Gruppen die tatsächlichen Tokenzähler mit der Prognose vergleichen
  und melden. Erst danach wird über C3 entschieden.
- **C3 (H2):** auf Sol/Foundry im verbleibenden Budget. GPT-5/HAWKI ersetzt den Bewerter für H2 nur,
  wenn B1b das vollständige Gate besteht und der Nutzer zustimmt. Bis dahin ist dieser Ersatz gesperrt.

## 2. H3 / C5

C5 berichtet die **unveränderten A6-Felder getrennt, jeweils mit ihrem eigenen Nenner**
(`direct_content_fraction` als Inhaltsauffindbarkeit je nativem Objekt, `occurrence_capacity` als
Multiplizität der Projektionskanten, bei EV je Teilnehmerkante). Ein multiplizitätstreues C/N auf
der Ebene ganzer Aussagen ist mit den vorhandenen Metriken **nicht identifiziert**. Es wird keine neue
Metrik eingeführt und kein Feld umbenannt. H3 bleibt sekundär und beschreibend. H1, H2 und H4 sind
unverändert.

## 3. Ausfallregel gegenüber G2-Fehlwertvertrag

- **Bewertung und Reader (C2, C3, C4, C6):** Es gilt ausschließlich der eingefrorene
  G2-Fehlwertvertrag. Kein Replay, feste Nenner, unbekannte Zustände bleiben unbekannt mit Schranken.
- **Konstruktion und Guard (B3, B4, C1):** Ein Aufruf mit Netzwerkfehler, Timeout oder unbekanntem
  Abschluss wird dokumentiert, möglicher Verbrauch als unbekannt geführt, und genau ein neuer,
  gekennzeichneter Versuch mit identischen Eingaben ist erlaubt. Das ist eine neue Konstruktion,
  kein Replay einer Bewertung.
  - Bleibt eine **Konfirmationszelle** danach unvollständig, gilt sie nach G2 als fehlend bzw.
    unbekannt. Die Quelle wird nicht ausgeschlossen, und kein Nenner wird erfunden.
  - Bleibt ein **MuSiQue-Korpusabsatz** danach unvollständig, wird er in beiden Armen symmetrisch
    aus dem Korpus ausgeschlossen und berichtet. Alle 60 Fragen bleiben im Nenner.
  - Guard (C1): Scheitert der neue Versuch, bleiben die betroffenen Aussagen unverändert im Bestand
    (keine Entfernung ohne gültiges Urteil) und werden als ungeprüft gezählt.
- Die gemeinsamen Regeln in der Übergabedatei sind nachrangig. Bei Widerspruch gelten dieser
  Nachtrag und G2.
