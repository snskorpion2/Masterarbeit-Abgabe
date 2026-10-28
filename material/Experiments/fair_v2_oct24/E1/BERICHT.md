# E1: explorative Reader-Robustheit auf einem gemeinsamen GPU-Server

**Die negative F1-Punktrichtung von V2 gegenüber AS bleibt mit Gemma erhalten.** AS_ORIGINAL erreicht 8,81 %, V2_ROW 8,25 %. Der feste Kontrast V2_ROW minus AS_ORIGINAL beträgt −0,57 Prozentpunkte. In C6 beträgt er −1,44 Punkte. Das ist ein beschreibender Gegenbefund zu einem QA-Vorteil von V2, kein statistischer Unterlegenheits- oder Gleichwertigkeitsnachweis.

| Zelle | Vollständige Antworten | F1 | EM |
| --- | ---: | ---: | ---: |
| AS_ORIGINAL | 60/60 | 8,81 % | 8,33 % |
| AS_ROW | 60/60 | 8,81 % | 8,33 % |
| AS_G_ORIGINAL | 60/60 | 8,64 % | 8,33 % |
| AS_G_ROW | 60/60 | 8,64 % | 8,33 % |
| V1_ORIGINAL | 60/60 | 8,61 % | 6,67 % |
| V1_ROW | 60/60 | 8,61 % | 6,67 % |
| V2_ORIGINAL | 60/60 | 8,25 % | 6,67 % |
| V2_ROW | 60/60 | 8,25 % | 6,67 % |
| EMPTY_CONTROL | 60/60 | 0,00 % | 0,00 % |
| GOLD_PARAGRAPH_CONTROL | 60/60 | 39,40 % | 31,67 % |

Die EM-Differenz beträgt −1,67 Prozentpunkte. C6 hatte einen EM-Gleichstand (Differenz null), deshalb ist dort keine erhaltene Vorteilsrichtung belegbar. `direction_preserved=true` im JSON bezeichnet ausschließlich dieselbe **negative** F1-Richtung, keine Bestätigung eines Vorteils von V2.

Alle 600 C6-Positionen wurden unverändert übernommen: acht Graphzellen und je eine Leer-/Goldkontrolle mit je 60 festen Fragen. Nachrichten, Reihenfolge und Top-30-Kontexte sind gebunden. Nur Modell und Endpunkt wechseln auf `QuantTrio/gemma-4-31B-it-AWQ` über die reguläre gemeinsame Warteschlange. Temperatur 0, höchstens 256 Ausgabetokens, n=1, stream=false, kein Replay. Es gab kein neues Retrieval, keine weitere Kontextkürzung, keine neue KG-Konstruktion und keine Auswahl nach erfolgreichen C6-Antworten.

Der offizielle MuSiQue-Antwortscorer stammt bytegebunden aus Commit `922ac98f19a201998dbdae6d7f2887a5258dbdeb`. Antwort und ursprüngliche Aliase werden wie in C6 bewertet. Goldantworten und Aliase wurden nur lokal zur Auswertung gelesen und nicht an den Reader übertragen. Der C6-Kontrast wurde aus seinem endgültig gebundenen Ergebnis übernommen, nicht neu berechnet.

Explorativ ohne Holm und ohne Ersatz von H4. Es wurden keine Konfidenzintervalle oder Signifikanztests für E1 berechnet. Die JSON-Felder `lower`/`upper` sind Identifikationsschranken bei Fehlwerten, keine Konfidenzintervalle. Mit vollständigen Antworten fallen diese Schranken auf die Punktschätzungen zusammen. Gleiche Fragen und Konstruktionen ergeben keine unabhängige KG-Bestätigung. Leer- und Goldkontrollen sind Readerkontrollen, keine Graphqualitätswerte.

Der Job `6453e4e801f8` endete mit Exit 0. Alle 600 Antworten haben vollständige Originalbelege, null technische oder unbekannte Abschlüsse und null Wiederholungen. Die eigene Lease ist freigegeben. Zusätzlich ist ein Modelllade-POST separat belegt. Der bestätigte NFS-Abschluss und alle 3.013 Archivdateien wurden lokal privat übernommen und gehasht. 144 synthetische CPU-Tests bestanden.

Bekannte Reader-Usage: 717.691 Eingabe- und 1.735 Ausgabetokens. Workerzeit einschließlich Laden, Kontrollen und Archivschreiben: 465,80 s. Reine providerinterne Modellzeit und Geldkosten bleiben unbekannt. Dies ist kein Kostenfaktor der vollständigen KGC-Pipeline.

Die API meldet keine Revision oder Kontextgrenze. Eine lesende Prozessbeobachtung um 12:16:47 UTC nach Start belegt die konfigurierte Grenze 16.384 und den Modellpfad zur Snapshotkennung `37cf6a076672592df03c8d941886a9d70d4338f0`. Sie ist keine rückwirkliche Vorstartattestierung und keine Hashprüfung aller geladenen Gewichtsbytes. Der maximale gemeldete Promptumfang beträgt 2.806 Tokens. Die gemeldete Prompt-Usage liegt bei allen 600 Positionen genau 12 Tokens über der lokalen Zählung, die Ursache ist ungeklärt. Beide Zählungen liegen einschließlich der Ausgabeplätze unter der später beobachteten Konfigurationsgrenze. Die nachgewiesenen Originalnachrichten bleiben unverändert.

Nur Aggregate stehen in [result.json](result.json). Rohfragen, Goldantworten, Originalanfragen, Rohantworten und Einzelwerte bleiben privat. Die `D1_interface` beschreibt den separaten sekundären Anschluss und behauptet keine bereits erfolgte Übernahme in D1 oder Manuskript.
