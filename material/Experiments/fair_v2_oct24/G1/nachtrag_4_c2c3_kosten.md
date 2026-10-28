# Nachtrag 4 zur Vorregistrierung: Bewertungsplan unter dem 30-EUR-Rahmen (25.10.2026, korrigierte Fassung)

Prospektiv. Grundlage ist der C2-Kostencheckpoint nach 50 Gruppen (`checkpoint50-token-forecast.private.json`,
SHA 76024a54…). Gesehen wurden nur Token- und Gültigkeitszahlen, keine Urteilsinhalte oder Verteilungen.
Nachträge 2 und 3 bleiben gültig, soweit hier nichts anderes steht. Die Sol-Route über AWS ist unbrauchbar
(403 `access_denied`, auch per SigV4).

## Lage

Das vollständige C2 kostet bei Standardtarif hochgerechnet 33,64 EUR (Short) bis 64,76 EUR (Long), C3 zusätzlich
8,71 bzw. 15,89 EUR. Welche Kontextpreisstufe gilt, ist **nicht belegt**. Die nativen Anbieterzähler melden
448.985 Cache-Schreibtokens von 449.135 Inputtokens und 0 Cache-Lesetokens. Die tatsächliche
Rechnungszuordnung ist weiterhin unbelegt. Der Foundry-Deckel beträgt 30 EUR.

## Allgemeine Regel für alle Bewertungsaufrufe

**Kein Replay für jeden versuchten Bewertungsaufruf**, auch bei Timeout, HTTP 429, Flex-Kapazitätsablehnung
oder ungeklärtem Abschluss. Betroffene Fälle folgen der G2-Fehlwertregel und gehen sichtbar in die
Fehlwertquote ein. Es gibt keinen automatischen Rückfall vom Flex- auf den Standardtarif.

## Plan A: Flex ohne Cachewrite (zuerst prüfen)

1. **Neue Ausführungsbedingung „Sol-Flex-NoWrite“:** dieselbe Bereitstellung (Version 2026-09-29,
   GlobalStandard, ChatCompletions), identische Messages, identisches Sampling, Ausgabelimit 8.192.
   Das Bodydelta beschränkt sich auf `prompt_cache_options={"mode":"explicit","ttl":"30m"}` **ohne jeden
   `prompt_cache_breakpoint`**, dazu den Header `x-ms-service-tier: flex`. Laut Microsoft-Dokumentation
   entstehen dabei keine Cache-Reads und keine Cachewrite-Gebühren, und der Ausgabeinhalt ändert
   sich durch Caching nicht. Das wird als neue Bedingung dokumentiert, ohne eine allgemeine Ersparnis
   zu behaupten.
2. **Frisches B1-Gate** unter genau dieser Bedingung: 13 SS und 27 Fein, Sechsergruppen, Deckel 0,50 EUR,
   Gate wie B1 (mindestens 12/13 und 25/27, kein unbekannter Abschluss). Native Nutzungsfelder je
   Anfrage erfassen (Input, Cachewrite, Cache-Read, Output).
3. **Neue Kostenprognose** aus den nativen Nutzungsfeldern und belegten Tarifszenarien dieses Gates für die restlichen
   C2-Gruppen und das vollständige C3, jeweils in beiden Kontextpreisstufen, solange Short nicht belegt
   ist.
   Die Prognose wird an die Koordination und den Nutzer gemeldet.

**Freigabeumfang: Jetzt freigegeben sind ausschließlich der B1-Pilot und die Kostenprüfung. Die
natürliche C2-/C3-Fortsetzung bleibt unabhängig vom Pilotergebnis bis zur direkten Budgetentscheidung
des Nutzers gesperrt.** Für eine spätere Fortsetzung gilt vorgesehen: restliche C2-Gruppen in
unveränderter Reihenfolge, danach C3 unter Sol-Flex-NoWrite. Die bereits im Standardtarif bewerteten
98 Gruppen bleiben gültig, der Tarif wird als Ausführungsdetail je Fall erfasst.

4. Für eine spätere Fortsetzung gilt: Die Last wird nach tatsächlich gemeldeten bzw. reservierten Tokens mit 50 % Reserve gesteuert. Bei
   429 oder Flex-Ablehnung: Abkühlung, Parallelität halbieren, kein Replay.

## Plan B

Plan B ist **nicht Teil dieses Nachtrags und nicht freigegeben**. Er steht als Entwurf in
`entwurf_planB_stichprobe_unfreigegeben.md` und braucht vor jeder Bindung eine eigene CPU-Qualifikation.
Passt Plan A nicht in den Rahmen, wird ohne neue Freigabe nichts umgestellt, sondern an die Koordination und
den Nutzer gemeldet.

## Unverändert

Modell, Prompt-Messages, Gruppierung, Fallpopulation, Endpunkte, Hypothesen und Holm-Familie. Eine
Budgeterhöhung über 30 EUR bleibt eine direkte Nutzerentscheidung. Der laufende Worker bleibt unverändert, bis Main eine belegbar sichere administrative
Grenze hat.
