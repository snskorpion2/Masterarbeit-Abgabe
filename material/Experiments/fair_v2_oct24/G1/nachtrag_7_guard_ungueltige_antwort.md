# Nachtrag 7: Ungültige Guard-Antwort ohne Entfernung behalten

**Nummerierung:** Dieser Nachtrag bleibt Nachtrag 7 und betrifft ausschließlich die
Behandlung ungültiger Guard-Antworten. Das getrennte Gesamt- und Komponentenurteil
wird unter `nachtrag_8_gesamt_und_komponentenurteil.md` als Nachtrag 8 geführt.
Die hier festgelegten Anwendungsregeln werden durch diese Abgrenzung nicht geändert.

Direkte Nutzerentscheidung vom 25.10.2026, nach Sicht einer bekannten strukturell
ungültigen MuSiQue-Guard-Antwort und vor der weiteren Fortsetzung. Die Entscheidung
bestätigt die bereits in `C1/protocol.json` beschriebene konservative Anwendung:
Bei einem strukturell fehlgeschlagenen Gruppenurteil bleibt der gesamte ursprüngliche
Quellkontext technisch ungeprüft erhalten. Frühere Laufbelege werden nicht geändert.

## Freigabe

Der Nutzer bestätigt ausdrücklich: Original behalten, betroffene Aussagen unverändert
als ungeprüft zählen und nur nie gestartete Restaufträge fortsetzen. Als Begründung
nennt er dieselbe Behandlung wie bei den Konfirmationsquellen und die Begrenzung
neuer Versuche durch Nachtrag 2. Die vorausgehende Auswahl wurde über
`call_2c1f4e311ce8455b9deb57ab3781f328:0` bestätigt.

## Anwendung

- Die bekannte Antwort enthält zwei unterschiedliche Werte für dasselbe JSON-Feld.
  Der strikte Parser bleibt unverändert. Kein Wert wird ausgewählt, zusammengefügt
  oder als reparierte gültige Antwort ausgegeben. Rohantwort und tatsächlicher
  Verbrauch bleiben erhalten.
- Der betroffene ursprüngliche Kontextbestand bleibt vollständig unverändert.
  Ohne gültige Guard-Anwendung erfolgt dort keine Entfernung. Die betroffenen
  EE-/VV-Vorkommen werden als strukturell ungeprüft erfasst, nicht als unterstützt.
- Bereits bezahlte übrige Antworten werden unverändert wiederverwendet. Neue
  Modellaufrufe betreffen ausschließlich ursprüngliche, noch nie gestartete
  Restaufträge. Bekannte Antworten werden nicht erneut generiert.
- Dieselbe konservative Anwendung gilt für gleichartige bekannte, vollständig
  empfangene strukturelle Antwortfehler unabhängig von Quellname und Arm.
  Unbekannte Ausführungen werden dadurch nicht entsperrt. Nachtrag 2 bleibt für
  Netzwerkfehler, Timeouts und unbekannten Abschluss unverändert maßgeblich.
- Modell, Prompt, Gruppierung, IDs, Quelle, Löschregel und derselbe gemeinsame
  C1-Kostenstand bleiben erhalten. Keine Budget- oder Verbrauchsrücksetzung.

## Abschlussbericht

Für MuSiQue werden ungeprüfte EE-/VV-Vorkommen am Ende je Arm mit Anzahl und
zugehörigem Nenner berichtet. Strukturelle Fehler, Zitierfehler und sonstige
Unklarheiten bleiben unterscheidbar. EV wird vom Guard grundsätzlich nicht geprüft
und deshalb separat als nicht anwendbar ausgewiesen, nicht als technischer Ausfall.
Original- und zeilengenauer Export zählen dieselbe Guard-Anwendung nicht doppelt.

Eine vollständig konservativ übernommene Quelle ist keine erfolgreich geprüfte
Quelle. C6 und die einmalige unabhängige Endprüfung bleiben an die vollständige,
korrekt gebundene Übergabe des gesamten MuSiQue-Bestands geknüpft. Die Regeln für
C2/C3-Bewertungen, fehlende Urteile und deren Wiederholungssperre ändern sich nicht.
