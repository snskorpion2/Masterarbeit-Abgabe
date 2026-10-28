# G1-Freigabe, Teil 2 (24.10.2026)

Ergänzt `freigabe_teil1.md`. Damit ist die Rollenbelegung vollständig.

## Rollen

| Rolle | Modell | Bedingung | Nachweis |
| --- | --- | --- | --- |
| Konstruktor (AS und V1) | `deepseek.v3.2`, Mantle | T 0,7, 8.192, Main12-Parameter | Teil 1 |
| Guard (nur EE/VV) | `moonshotai.kimi-k2.5`, Mantle eu-north-1 | Facetten-Guard `make_facet_guard`, deterministische Ganzlöschregel im Code, T 0, 16.384, keine Zitatreparatur, keine automatische Wiederholung | A3d: 7/7 und 8/8 |
| Hauptbewerter | `gpt-6.1-sol`, Foundry | Temperaturfeld ausgelassen, Sechsergruppen, unveränderte Main12-Prompts | B1 |
| Zweitbewerter | `grok-4.7`, Foundry | T 0, Sechsergruppen, 15-%-Stichprobe plus alle vom Guard entfernten Aussagen der Stichprobenquellen | B1 |
| QA-Reader (H4) | `qwen.qwen3-235b-a22b-2507`, Mantle | T 0, kurze Antwort, nur Graphkontext | Zugang A2 |
| Referenzen | `gemini-3.1-pro-preview`, Vertex | T 0 | B2 |

Die Familien sind getrennt: DeepSeek (Konstruktor), Moonshot (Guard), OpenAI (Hauptbewerter),
xAI (Zweitbewerter), Alibaba (Reader), Google (Referenzen).

## Entwicklungsgeschichte des Guards (offen zu berichten)

A3 (gleiches Modell wie der Konstruktor) und A3b (vier Kandidaten) verfehlten das Gate. Die Ursache
war die Lösch- und Erhaltungsanweisung im Prompt. A3c trennte das Facettenurteil des Modells von
einer deterministischen Löschregel. Diese Entscheidung fiel nach Sicht der Kontrollergebnisse und
ist damit Entwicklung auf Kontrollfällen. A3d qualifizierte Kimi-K2.5 frisch. Die Gegenbefunde in den
natürlichen Paaren (Paar 1 vertauscht, Paar 3 überentfernt) und die Teilverluste bleiben im Bericht.
Die unabhängige Bestätigung erfolgt ausschließlich über H1/H2 auf den Konfirmationsquellen mit Sol,
Grok und der menschlichen Stichprobe.

## Deckel

- Guard Konfirmation (24 Quellen): 20 USD.
- Guard MuSiQue: 40 USD, Kostenprüfung nach 200 Chunks. Bei einer Hochrechnung über 40 USD stoppen und an die Koordination melden.
- Reader H4: 5 USD.
