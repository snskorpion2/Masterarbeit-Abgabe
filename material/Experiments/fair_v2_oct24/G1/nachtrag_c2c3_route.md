# Nachtrag zur Vorregistrierung: Ausführungsroute des Hauptbewerters (24.10.2026)

**Anlass:** Die C2/C3-Kostenprognose (`Experiments/fair_v2_oct24/C2/COST_PREFLIGHT.md`, EUR-Nachtrag)
ergibt für 8.682 C2- und 2.336 C3-Urteile 24,72 EUR bis 55,77 EUR. Das ist mit dem Foundry-Guthaben
(Deckel 25 EUR) nicht sicher abgedeckt.

**Zeitpunkt:** vor dem ersten C2-/C3-Provideraufruf. Es wurde kein Bewertungsergebnis gesehen. Der
Nachtrag ändert weder Modell, Prompt, Gruppierung, Endpunkte, Tests noch Population, sondern nur die
Ausführungsroute.

## Entscheidung

1. **Hauptbewerter für C2 und C3:** `openai.gpt-6.1-sol` über AWS Bedrock (Profil `masterarbeit`,
   Route und Region dokumentieren, ggf. `global.`-Profil). Temperatur- und Reasoningfeld werden wie
   in der qualifizierten Foundry-Bedingung ausgelassen. Unveränderter Main12-Prompt, Sechsergruppen.
2. **Vorbedingung:** Zugangsprobe und Preisprüfung, danach unveränderte B1-Kontrollen (13 SS und
   27 Fein) auf der AWS-Route. Gate wie B1: mindestens 12/13 und 25/27, kein unbekannter Abschluss.
   Die Foundry- und die AWS-Route gelten als getrennte Ausführungsbedingungen desselben Modellnamens.
   Gewichtsgleichheit wird nicht behauptet.
3. **Deckel:** C2+C3 auf AWS 70 USD. Die Hochrechnung nach den ersten 100 Gruppen erneuern. Über 70 USD
   stoppen und melden.
4. **Fallback, falls die AWS-Route das Gate verfehlt oder nicht aufrufbar ist:** Sol über Foundry für
   C2 vollständig, mit Deckel 30 EUR. C3 läuft danach auf derselben Route, soweit das Budget reicht.
   C4 (Grok) wird dann auf das Restbudget begrenzt. Eine kleinere Stichprobe wird nicht als
   vollständige Auswertung ausgegeben.
5. **C4 (Grok, Foundry)** bleibt unverändert, Deckel 12 EUR. Das Foundry-Budget wird durch Punkt 1
   für C4 frei.
