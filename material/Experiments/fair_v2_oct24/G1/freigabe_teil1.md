# G1-Freigabe, Teil 1 (24.10.2026)

Teilfreigabe. Der Guard ist noch offen und hängt an A3b. Er wird in Teil 2 festgelegt.

## Freigegeben

1. **Konstruktor für B3 und B4:** `deepseek.v3.2` über Bedrock Mantle (eu-north-1), T 0,7,
   max. 8.192 Ausgabetokens, Timeout 300 s, keine Transportwiederholung. Das sind exakt die
   Main12-Parameter aus `Experiments/fair_comparison_oct23_v1/candidate_selection_v1.json`
   (`main_comparison_sampling`), identisch für AS und V1. Die Konstruktion hängt nicht vom Guard
   ab, denn der Guard läuft erst nach der Schemainduktion auf den fertigen Beständen.
   - B3: 20 Frischquellen (`Experiments/data/confirmation_a4_oct24_v1/sources/`) × 3 Durchläufe ×
     {AS, V1} mit Original-AS-Schemainduktion und Export, außerdem Schema und Export für die
     16 vorhandenen Extraktionsinventare der vier versiegelten Quellen. Deckel 20 USD.
   - B4: MuSiQue-Korpus aus A5, ein Durchlauf je Arm, **ohne Schemainduktion**, Kostenmessung nach
     100 Chunks, 100 Fragen nur bei einer Hochrechnung bis 25 USD, sonst `corpus60`. Deckel 25 USD.
2. **Referenzerstellung B2:** `gemini-3.1-pro-preview` (Vertex), T 0, Deckel 1 EUR. Die Trennung von
   den Konstruktoren erfolgt organisatorisch über Dateigrenze und Inputvertrag, wie bei Main12.
3. **Bewerter (Grundlage B1):**
   - Hauptbewerter `gpt-6.1-sol` (Foundry), Temperaturfeld ausgelassen wie in der qualifizierten
     Bedingung, Sechsergruppen. Deckel 25 EUR.
   - Zweitbewerter `grok-4.7` (Foundry), T 0, Sechsergruppen, 15-%-Stichprobe, Kostenprüfung im
     Portal nach ca. 50 Anfragen. Deckel 12 EUR.
   - Qwen3-235B und gpt-oss-120b sind als Bewerter nicht zugelassen (B1-Gate verfehlt).

## Offen (Teil 2)

- Guard-Modell nach A3b. Regel: Guard ≠ Familie des Hauptbewerters (OpenAI). Besteht nur
  gpt-oss-120b, werden die Bewerterrollen getauscht (Grok Haupt-, Sol Zweitbewerter).
- Reader für H4: wird mit Teil 2 festgelegt.
