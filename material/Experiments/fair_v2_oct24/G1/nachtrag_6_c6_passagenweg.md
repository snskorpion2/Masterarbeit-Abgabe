# Nachtrag 6 zur Vorregistrierung: sekundärer Passagenweg in H4 (25.10.2026, präzisierte Fassung)

Vor jedem C6-Aufruf, aber nach G2. Es wurden keine Fragen, Goldwerte, Passagen oder QA-Ausgaben gesehen.

**Einordnung:** Dieser Nachtrag **reduziert einen vorregistrierten sekundären Endpunkt**. Die Entscheidung
fiel nach G2, aber vor C6. Sie ist getrennt von Nachtrag 5 (Joint-Fallback in der Konstruktion), und beide
bleiben im Bericht sichtbar.

**Belegter Status des Passagenwegs:** Ein Pfad ist vorhanden. Es handelt sich um den AutoSchemaKG-SDK- bzw.
Autorennotebookpfad in `Tools/ReferenceRepos/benchmark_autoschemakg_original` (AutoSchemaKG-Commit
`d0a1666ae6621806faf814504c73678de4e809f2`), angebunden über `Tools/abschluss/hipporag2_fixed_probe_v1.py`,
`notebook_route()`. Er umfasst:
- Graph- und Passagenindex samt Embeddings,
- Query-Embedding,
- standardmäßig einen LLM-Kantenfilter,
- PPR mit Passagen-Fallback,
- einen separaten LLM-Passagenreader, der eigenes Modellwissen nutzen darf.

Der Pfad ist keine exakte Reproduktion des eigenständigen HippoRAG2-Papers. Für C6 gibt es **keine
qualifizierte vollständige Q60-, Aufruf- und Kostenbindung** dieses Pfads. SDK-Wiederholungen und der
MuSiQue-Q60-Anschluss sind nicht qualifiziert.

## Entscheidung

1. Der sekundäre Passagenweg wird **in dieser Studie nicht durchgeführt**. Grund ist eine
   ressourcenbedingte Scopeentscheidung: Es gibt keine qualifizierte vollständige Q60-, Aufruf- und
   Kostenbindung. Eine Unmöglichkeit innerhalb von Zeit oder Budget wird nicht behauptet. Der Weg wird
   weder durch die Haupt- und Kontrollantworten ersetzt noch durch eine neue Passagenselektion nachgebildet.
2. Der frühere HippoRAG2-Vergleich auf Main12 (QA24) bleibt im Manuskript nur als **getrennte, begrenzte
   Entwicklungsbeobachtung**. Er gilt **nicht** als Ersatz oder Abdeckung des weggefallenen
   MuSiQue-Endpunkts.
3. C6 umfasst damit genau die **600 gebundenen Antwortpositionen**: 480 Antworten aus dem graphgebundenen
   Reader sowie 60 Leer- und 60 Goldkontrollen. Das sind Antwortpositionen, keine behauptete Zahl
   physischer POSTs. Der Kostenplan gilt für diese Positionen im unveränderten Deckel von 5 USD.
4. H4 (F1 primär, EM sekundär, Nenner 60) betrifft nur den festen graphgebundenen Reader samt Kontrollen.
   Daraus folgt **keine Aussage über Überlegenheit** gegenüber dem originalen SDK-Passagenweg oder dem
   HippoRAG2-Paper auf MuSiQue. Im Manuskript wird der Wegfall des sekundären Weges offen genannt.
