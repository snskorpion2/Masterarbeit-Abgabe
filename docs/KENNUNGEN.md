# Kennungen und Materialordner

Dieses Verzeichnis übersetzt technische Ordner- und Belegkennungen in verständliche Namen. Die Ordnerangaben beziehen sich auf den erhaltenen Bestand unter `material/`. Der Dateilink führt jeweils zu einem öffentlich beigefügten Bericht, Protokoll oder Codemodul.

Erfasst sind alle **54 Ordner** der öffentlichen Ausgangsfassung `34be2790` sowie zusätzliche Nachtrags- und Registerkennungen. Datierte Unterordner kennzeichnen einen bestimmten Bearbeitungsstand. Historische Kennungen führen zu ihren Registereinträgen.

## Ergebnisse, Versuchsplan und Nachweise

| Kennung oder alter Ordner | Verständlicher Name | Zweck | Datei |
| --- | --- | --- | --- |
| `docs/` | Dokumentation und Nachweisindizes | Chronologie und Nachweisindizes erschließen Festlegungen, Ergebnisse und teils privat erhaltene Originalbelege. | [CHRONOLOGIE.md](../material/docs/CHRONOLOGIE.md) |
| `EF1/` | Aufwand-Qualitäts-Bilanz | Die nachträgliche Auswertung verknüpft dokumentierte Aufwände mit den gebundenen Qualitätsmaßen. | [BERICHT.md](../material/EF1/BERICHT.md) |
| `Experiments/` | Versuchs- und Auswertungsbausteine | Ausgewählte Konstruktionsmodule, der Vergleichsplan und die veröffentlichten Abschlussauswertungen sind nach ihrer Rolle geordnet. | [BERICHT.md](../material/Experiments/fair_v2_oct24/D1/final_native_oct26_v1/BERICHT.md) |
| `Experiments/fair_comparison_oct23_v1/` | Konstruktion und Export des angeglichenen Vergleichs | Ausgewählte Module steuern die AutoSchemaKG-Referenz, die Variante mit Quellenanweisungen und Ergänzungspass sowie gebundene Exportansichten. | [baseline.py](../material/Experiments/fair_comparison_oct23_v1/baseline.py) |
| `Experiments/fair_v2_oct24/` | Vorregistrierter Komponenten- und Gesamtvergleich | Teilordner enthalten die eingefrorene Festlegung, Nachträge, ausgewählten Hilfscode und öffentliche Abschlussberichte des Vergleichs. | [preregistration_v2_frozen.md](../material/Experiments/fair_v2_oct24/A7/preregistration_v2_frozen.md) |
| `Experiments/fair_v2_oct24/A7/` | Eingefrorene Vorregistrierung | Öffentliche Fassungen der Vorregistrierung halten Vergleichsarme, Endpunkte und Regeln des eingefrorenen Auswertungsvertrags fest. | [preregistration_v2_frozen.md](../material/Experiments/fair_v2_oct24/A7/preregistration_v2_frozen.md) |
| `Experiments/fair_v2_oct24/A8/` | Ableitung gefilterter Teilbestände | Der Quellcode erzeugt Teilbestände anhand eindeutiger Vorkommenskennungen und festgelegter Schemazuordnungen. | [project_subset.py](../material/Experiments/fair_v2_oct24/A8/project_subset.py) |
| `Experiments/fair_v2_oct24/B3/` | Bindung der konstruierten Vergleichsbestände | Der Hilfscode prüft abgeschlossene native Bestände und bindet ihre eindeutigen Vorkommenskennungen. | [cell_binding.py](../material/Experiments/fair_v2_oct24/B3/cell_binding.py) |
| `Experiments/fair_v2_oct24/C1/` | Abschlussbeleg des MuSiQue-Prüffilters | Die öffentliche Abschlussquittung dokumentiert Ausführungsstand und vorhandene Endprüfung des auf MuSiQue angewandten Prüffilters. | [actual_end_oct25.json](../material/Experiments/fair_v2_oct24/C1/end_audit_oct25_v1/actual_end_oct25.json) |
| `Experiments/fair_v2_oct24/C1/end_audit_oct25_v1/` | Einmaliger MuSiQue-Prüffilterabschluss | Die maschinenlesbare Quittung hält den technisch abgeschlossenen Filterstand und Bindungen an privat erhaltene Originalbelege fest. | [actual_end_oct25.json](../material/Experiments/fair_v2_oct24/C1/end_audit_oct25_v1/actual_end_oct25.json) |
| `Experiments/fair_v2_oct24/C2/` | Abschluss der Aussagenbewertung | Die Abschlussquittung bindet die exportierten Urteile zu Quellenstützung und Bedeutungserhalt. | [actual_end_oct25.json](../material/Experiments/fair_v2_oct24/C2/n10_finalization_v2/actual_end_oct25.json) |
| `Experiments/fair_v2_oct24/C2/n10_finalization_v2/` | Endexport der Aussagenbewertung | Die Quittung dokumentiert Bewertungsabschluss, verfügbare Urteile, technische Abdeckung und Budgetende. | [actual_end_oct25.json](../material/Experiments/fair_v2_oct24/C2/n10_finalization_v2/actual_end_oct25.json) |
| `Experiments/fair_v2_oct24/C2/n18_completion_v1/` | Nachbewertung fehlender Urteile | Bericht und Ergebnisdatei dokumentieren die nachträgliche Bewertung der 468 zuvor nie gestarteten Gruppen zu Quellenstützung und Bedeutungserhalt. | [BERICHT.md](../material/Experiments/fair_v2_oct24/C2/n18_completion_v1/BERICHT.md) |
| `Experiments/fair_v2_oct24/C3/` | Fehlwertmetadaten des Bedeutungserhalts | Technische Metadaten beschreiben geplante, gültige und fehlende Bewertungspositionen sowie budgetbedingt nicht gestartete oder unklare Ausführungen. | [BERICHT.md](../material/Experiments/fair_v2_oct24/C3/missing_metadata_v1/BERICHT.md) |
| `Experiments/fair_v2_oct24/C3/missing_metadata_v1/` | Fehlwerte der Bedeutungserhaltsprüfung | Bericht und Aggregate ordnen die fehlenden Bewertungen im gebundenen Endstand ein. | [BERICHT.md](../material/Experiments/fair_v2_oct24/C3/missing_metadata_v1/BERICHT.md) |
| `Experiments/fair_v2_oct24/C4/` | Plan einer Zweitbewerter-Stichprobe | Die Änderungsdatei legt Stichprobe und Auswertungsregeln für einen geplanten zweiten Bewerter fest. | [amendment.json](../material/Experiments/fair_v2_oct24/C4/amendment.json) |
| `Experiments/fair_v2_oct24/C6/` | Primäre Prüfung der Antwortnutzbarkeit | Der Teilordner enthält Zellaggregate der gebundenen MuSiQue-Antworten des Qwen-Modells. | [BERICHT.md](../material/Experiments/fair_v2_oct24/C6/actual_end_oct26_v1/BERICHT.md) |
| `Experiments/fair_v2_oct24/C6/actual_end_oct26_v1/` | Endstand der primären Antwortprüfung | Bericht und Ergebnisdatei liefern Zellaggregate mit dem offiziellen MuSiQue-Antwort-F1 und EM für die H4-Auswertung. | [BERICHT.md](../material/Experiments/fair_v2_oct24/C6/actual_end_oct26_v1/BERICHT.md) |
| `Experiments/fair_v2_oct24/C7/` | Autorenprüfung der Aussagenbewertung | Der aggregierte Abgleich der Autorenannotation mit Sol berichtet ihre Übereinstimmung. | [BERICHT.md](../material/Experiments/fair_v2_oct24/C7/BERICHT.md) |
| `Experiments/fair_v2_oct24/D1/` | Statistische Haupt- und Komponentenprüfung | Auswertungscode und synthetische Tests setzen den Analysevertrag um und der Finalordner enthält die empirischen Ergebnisse. | [BERICHT.md](../material/Experiments/fair_v2_oct24/D1/final_native_oct26_v1/BERICHT.md) |
| `Experiments/fair_v2_oct24/D1/final_native_oct26_v1/` | Finale empirische Gesamtauswertung | Bericht, Aggregate, Tabellen und Grafiken dokumentieren die gebundenen primären und Komponentenbefunde samt Grenzen und methodischem Gesamturteil. | [BERICHT.md](../material/Experiments/fair_v2_oct24/D1/final_native_oct26_v1/BERICHT.md) |
| `Experiments/fair_v2_oct24/D1/final_native_oct26_v1/requested_outputs/` | Kompakte Ergebnisauszüge | Die angeforderten Auszüge bündeln Ergebnisse des Finalstands in lesbarer, tabellarischer und maschinenlesbarer Form. | [requested_outputs.md](../material/Experiments/fair_v2_oct24/D1/final_native_oct26_v1/requested_outputs/requested_outputs.md) |
| `Experiments/fair_v2_oct24/E1/` | Explorative Antwortprüfung mit Gemma | Der Bericht beschreibt die zusätzliche Antwortprüfung mit Gemma auf denselben gebundenen MuSiQue-Kontexten. | [BERICHT.md](../material/Experiments/fair_v2_oct24/E1/BERICHT.md) |
| `Experiments/fair_v2_oct24/G1/` | Freigaben und datierte Nachträge | Freigaben und Nachträge dokumentieren den beauftragten Umfang sowie spätere Regelergänzungen und Abweichungen. | [freigabe_teil1.md](../material/Experiments/fair_v2_oct24/G1/freigabe_teil1.md) |
| `Experiments/fair_v2_oct24/H12/` | Menschliche Prüfung der Filterentscheidungen | Protokoll und öffentliche Aggregate beschreiben die verblindete Autorenprüfung entfernter und beibehaltener Aussagen des Prüffilters. | [BERICHT.md](../material/Experiments/fair_v2_oct24/H12/BERICHT.md) |
| `Experiments/fair_v2_oct24/K2/` | Dokumentierter Pipelineaufwand | Die Aufwandsübersicht trennt Stufen und Bedingungen sowie bekannte Kosten, dokumentierte Anfragen und unbekannte Ausführungsanteile. | [README.md](../material/Experiments/fair_v2_oct24/K2/README.md) |
| `Experiments/fair_v2_oct24/Q2/` | Explorative Abruftiefe | Der Bericht vergleicht dieselben Fragen und Graphansichten bei 30, 60 und 100 abgerufenen Kanten. | [BERICHT.md](../material/Experiments/fair_v2_oct24/Q2/BERICHT.md) |
| `Experiments/fair_v2_oct24/T1/` | Transferprobe mit Qwen3-235B als Konstruktor | Berichte und Aggregate dokumentieren die alternative Konstruktion, ihre Filterung und die beschreibenden Strukturmaße. | [BERICHT.md](../material/Experiments/fair_v2_oct24/T1/BERICHT.md) |
| `Experiments/fair_v2_oct24/W3/` | Nachweisgrenze der Antwortqualität | Der Bericht schätzt nachträglich, ab welchem Unterschied der Fragenumfang einen Vorteil erkennbar gemacht hätte. | [BERICHT.md](../material/Experiments/fair_v2_oct24/W3/BERICHT.md) |
| `Experiments/fair_v2_oct24/X1/` | Beschreibende Strukturdiagnostik | Der Bericht untersucht unter anderem Pronomenformen, Entitätslängen und Nähe von Ereignissätzen zum Quelltext als Strukturmerkmale. | [BERICHT.md](../material/Experiments/fair_v2_oct24/X1/BERICHT.md) |
| `Experiments/src/` | Gemeinsame Datei- und Graphhilfen | Die ausgewählten Hilfsmodule unterstützen Dateioperationen, Tripelverarbeitung und GraphML-Export. | [graphml_export.py](../material/Experiments/src/graphml_export.py) |
| `Experiments/strict_autoschemakg/` | Bausteine des strikten Originalpfads und früherer Varianten | Ausgewählte Module binden ursprüngliche AutoSchemaKG-Stufen und Prüfer ein und enthalten Hilfen für frühere Ergänzungs- und Diagnosebedingungen. | [construction.py](../material/Experiments/strict_autoschemakg/construction.py) |
| `H15/` | Autorenprüfung des Bedeutungserhalts | Protokoll, Auswertung und Aggregate dokumentieren die verblindete Autorenprüfung gepaarter Referenzbedeutungen. | [BERICHT.md](../material/H15/BERICHT.md) |
| `H16/` | Autorenprüfung der Transferprobe | Protokoll und Aggregate dokumentieren die Autorenprüfung von Aussagen der Qwen3-235B-Konstruktion. | [BERICHT.md](../material/H16/BERICHT.md) |
| `licenses/` | Lizenz des AutoSchemaKG-Referenzcodes | Der Ordner enthält den Lizenztext des AutoSchemaKG-Referenzcodes. | [AutoSchemaKG-LICENSE.txt](../material/licenses/AutoSchemaKG-LICENSE.txt) |
| `protocols/` | Öffentlicher Auswertungsvertrag | Der exportierte Vertrag bündelt Populationen, Vergleichszellen, Zufallsstarts und Bindungen an Vorregistrierung und Nachträge. | [analysis_contract.public.json](../material/protocols/analysis_contract.public.json) |
| `QA1/` | Lexikalische Antwortdiagnose zur Antwortnutzbarkeit | Die nachträgliche Auswertung untersucht Antwortvorkommen und Quellenbezug der gespeicherten MuSiQue-Kontexte. | [BERICHT.md](../material/QA1/BERICHT.md) |
| `RB1/` | Robustheit der Aussagenvergleiche | Die nachträglichen Auswertungen prüfen Typstandardisierung, Quell- und Durchlaufaufteilungen sowie Weglassanalysen. | [BERICHT.md](../material/RB1/BERICHT.md) |
| `S13/` | Autorenprüfung der Konzeptzuordnungen | Die öffentlichen Aggregate vergleichen die Passung von Konzeptzuordnungen ohne und mit zusätzlichem Quellsatzkontext. | [BERICHT.md](../material/S13/BERICHT.md) |
| `X2/` | Quellenverankerung des vorhandenen Schemas | Bericht und Aggregate bestimmen anhand gestützter Aussagen, welche bestehenden Schemazuordnungen in Quellen verankert sind. | [BERICHT_c_n10_v1.md](../material/X2/BERICHT_c_n10_v1.md) |
| `X3/` | Explorative Filterung nur von Ereignisverknüpfungen | Die nachträgliche Analyse berechnet aus vorhandenen Filterentscheidungen Varianten mit ausschließlich VV-Entfernungen. | [README.md](../material/X3/README.md) |

## Auswertungs- und Konstruktionscode

| Kennung oder alter Ordner | Verständlicher Name | Zweck | Datei |
| --- | --- | --- | --- |
| `Tools/` | Ausgewählte Werkzeug- und Laufzeitmodule | Ausgewählte Adapter, Diagnose- und Prüffiltermodule sowie Paketprüfung und synthetischer CPU-Nachvollzug ergänzen die veröffentlichten Versuchsteile. | [submission_cpu.py](../material/Tools/release/submission_cpu.py) |
| `Tools/abschluss/` | Adapter und Hilfen früherer Abschlussprüfungen | Ausgewählte Module unterstützen Prüferanbindungen, Ressourcenprüfung und den nativen Schema- und Graphnachlauf. | [hipporag2_graph_tail_v1.py](../material/Tools/abschluss/hipporag2_graph_tail_v1.py) |
| `Tools/azure/` | Azure-Anbindung und Antwortdiagnostik | Adapter und Diagnosemodule behandeln Anbieterantworten, Belegprüfungen, Ausgabegrenzen und dokumentierte Nutzungsdaten. | [response_diagnostics_v2.py](../material/Tools/azure/response_diagnostics_v2.py) |
| `Tools/experiments/` | Ausgewählte Entwicklungs- und Vergleichshilfen | Unterordner enthalten eng begrenzte Hilfen für Quellenanweisungen, Ergänzung, Transport, Graphkontrolle und Prüffilter. | [guard.py](../material/Tools/experiments/whole_relation_guard_oct24_v1/guard.py) |
| `Tools/experiments/as_parallel_export_oct20_v1/` | Zeilengenauer Relationsexport | Der Hilfscode erhält einzelne native Relationszeilen als getrennte Exportvorkommen und grenzt frühere Verluste des Originalexports ab. | [export_control.py](../material/Tools/experiments/as_parallel_export_oct20_v1/export_control.py) |
| `Tools/experiments/autoschema_ladder_oct14_v1/` | AutoSchemaKG-Entwicklungspfad | Ausgewählte Lauf- und Diagnosemodule binden native Stufen ein und unterstützen Aussagen- sowie Graphprüfungen. | [runner.py](../material/Tools/experiments/autoschema_ladder_oct14_v1/runner.py) |
| `Tools/experiments/fair_tail_oct23_v1/` | Laufzeitadapter für den nativen Nachlauf | Der Laufzeitadapter unterstützt den bereits konstruierten Bestand bei nachfolgenden nativen Verarbeitungsschritten. | [runtime.py](../material/Tools/experiments/fair_tail_oct23_v1/runtime.py) |
| `Tools/experiments/greenfield_kgc_oct14_v1/` | Foundry-Transportadapter einer Entwicklungsbedingung | Der ausgewählte Adapter trennt native Modellargumente von den tatsächlichen Parametern einer einzelnen Foundry-Anfrage. | [foundry_runtime.py](../material/Tools/experiments/greenfield_kgc_oct14_v1/foundry_runtime.py) |
| `Tools/experiments/independent_repair_transfer_oct23_v1/` | Prüfregeln für quellengebundene Diagnose und Reparatur | Der Hilfscode definiert die Validierung von Diagnose-, Reparatur- und Prüfschritten. | [controller.py](../material/Tools/experiments/independent_repair_transfer_oct23_v1/controller.py) |
| `Tools/experiments/oneagent_roles_oct20_v1/` | Laufzeitadapter der OneAgent-Bedingung | Der ausgewählte Adapter erhält ursprüngliche Anfrage-, Antwort- und Belegbindungen einer einzelnen nativen Modellanfrage. | [native_luna_runtime_v3.py](../material/Tools/experiments/oneagent_roles_oct20_v1/native_luna_runtime_v3.py) |
| `Tools/experiments/source_anchor_gap_oct20_v1/` | Entwicklungsprüfung von Quellenanker-Lücken | Die ausgewählten Module unterstützen eine begrenzte Ergänzungsstudie und ihre native Modellanbindung. | [run_study.py](../material/Tools/experiments/source_anchor_gap_oct20_v1/run_study.py) |
| `Tools/experiments/source_binding_oct23_v1/` | Eingegrenzte Quellenanweisungen für EV und VV | Der Jobcode bereitet eine gebundene Entwicklungsbedingung mit ergänzter Quellenanweisung für Ereignisextraktionen vor. | [event_scope_job.py](../material/Tools/experiments/source_binding_oct23_v1/event_scope_job.py) |
| `Tools/experiments/whole_relation_guard_oct24_v1/` | Quellengebundener Prüffilter für vollständige Aussagen | Die Module definieren Prüfung, reversible Entfernung und Auslieferung vollständiger EE- und VV-Aussagen. | [guard.py](../material/Tools/experiments/whole_relation_guard_oct24_v1/guard.py) |
| `Tools/hawki/` | HAWKI-Zugang und Bewertungsproben | Die ausgewählten Module unterstützen begrenzte Zugangs- und Bewertungsprüfungen für den HAWKI-Dienst. | [probe.py](../material/Tools/hawki/probe.py) |
| `Tools/release/` | Synthetischer CPU-Nachvollzug | Demonstriert den D1-Rechenweg auf synthetischen Daten. | [submission_cpu.py](../material/Tools/release/submission_cpu.py) |
| `Tools/wse/` | Adapter für die WSE-Ausführungsbedingung | Der ausgewählte Adapter bindet die ursprüngliche Extraktionsschnittstelle an eine ausdrücklich getrennte WSE-Laufzeitbedingung. | [strict_native_wse_pipeline_adapter_oct13_v1.py](../material/Tools/wse/strict_native_wse_pipeline_adapter_oct13_v1.py) |

## Nachträge und Bestandskennungen

| Kennung oder alter Ordner | Verständlicher Name | Zweck | Datei |
| --- | --- | --- | --- |
| `G2` | Eingefrorener Analyseplan | Bezeichnet den in A7 abgelegten Versuchs- und Auswertungsplan. | [preregistration_v2_frozen.md](../material/Experiments/fair_v2_oct24/A7/preregistration_v2_frozen.md) |
| `N2` | Bewerterroute, Budget und technische Endpunkte | Legt Bewerter, Bewertungsreihenfolge, Budget und den Umgang mit technischen Endpunkten fest. | [nachtrag_2_nacht.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_2_nacht.md) |
| `N3` | Budget und Reihenfolge der Filterung | Legt Budget und Ausführungsreihenfolge für den Prüffilter fest. | [nachtrag_3_c1_budget.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_3_c1_budget.md) |
| `N4` | Bewertungsplan im Kostenrahmen | Legt die Ausführung der Aussagen- und Erhaltsbewertung im verfügbaren Budget fest. | [nachtrag_4_c2c3_kosten.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_4_c2c3_kosten.md) |
| `N5` | Umgang mit vertragswidrigen gemeinsamen Antworten | Legt den Umgang mit vollständig übertragenen Antworten fest, die den zusätzlichen Ausgabevertrag verletzen. | [nachtrag_5_joint_vertragsverletzung.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_5_joint_vertragsverletzung.md) |
| `N6` | Zusätzlicher Passagenweg der Antwortprüfung | Beschreibt einen sekundären Passagenweg für die Antwortprüfung. | [nachtrag_6_c6_passagenweg.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_6_c6_passagenweg.md) |
| `N7` | Beibehaltung bei ungültiger Filterantwort | Legt fest, dass Aussagen bei ungültiger Filterantwort beibehalten werden. | [nachtrag_7_guard_ungueltige_antwort.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_7_guard_ungueltige_antwort.md) |
| `N8` | Gesamturteil und Komponentenvergleiche | Definiert Gesamtstufen, Herabstufung, Komponentenfamilie und Effizienzmaße. | [nachtrag_8_gesamt_und_komponentenurteil.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_8_gesamt_und_komponentenurteil.md) |
| `N9` | Transfer auf ein anderes Konstruktormodell | Legt eine explorative Konstruktion mit einem zweiten Modell fest. | [nachtrag_9_transfer_konstruktormodell.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_9_transfer_konstruktormodell.md) |
| `N10` | Budgetbedingte Zufallsstichprobe zur Quellenstützung | Legt die Rückfallregel für eine budgetbedingt begrenzte Aussagenbewertung fest. | [nachtrag_10_budgetbedingte_stichprobe_h1.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_10_budgetbedingte_stichprobe_h1.md) |
| `N11` | Zweitbewerter über NVIDIA NIM | Legt Qualifikation und Einsatz eines zusätzlichen NIM-Bewerters fest. | [nachtrag_11_zweitbewerter_nim.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_11_zweitbewerter_nim.md) |
| `N11b` | Qualifikationsversuch mit Dreiergruppen | Legt den letzten NIM-Qualifikationsversuch mit höchstens drei Fällen je Anfrage fest. | [nachtrag_11b_nim_dreiergruppen.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_11b_nim_dreiergruppen.md) |
| `N12` | Autorenprüfung des Prüffilters | Legt die verblindete menschliche Prüfung entfernter und beibehaltener Aussagen fest. | [nachtrag_12_menschliche_pruefung_prueffilter.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_12_menschliche_pruefung_prueffilter.md) |
| `N13` | Schemaprobe mit zusätzlichem Quellsatz | Legt die explorative Autorenprüfung kontextgebundener Konzeptzuordnungen fest. | [nachtrag_13_schemaprobe_kontext.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_13_schemaprobe_kontext.md) |
| `N14` | Fehlwerte der Bedeutungserhaltsbewertung | Legt den Umgang mit budgetbedingt fehlenden Erhaltsurteilen und die Zusatzanalyse fest. | [nachtrag_14_h2_fehlwerte.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_14_h2_fehlwerte.md) |
| `N15` | Autorenprüfung des Bedeutungserhalts | Legt eine menschliche Stichprobe zur Prüfung der Erhaltsurteile fest. | [nachtrag_15_menschliche_pruefung_h2.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_15_menschliche_pruefung_h2.md) |
| `N16` | Autorenprüfung des Modelltransfers | Legt eine menschliche Aussagenstichprobe für die Transferbedingung fest. | [nachtrag_16_transfer_menschlich.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_16_transfer_menschlich.md) |
| `N17` | Nachträgliche Aufwand-, Robustheits- und VV-Analysen | Legt zusätzliche Nachrechnungen zu Aufwand, Robustheit und VV-Filterprojektion fest. | [nachtrag_17_effizienz_robustheit_vv.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_17_effizienz_robustheit_vv.md) |
| `N18` | Nachbewertung fehlender Urteile | Legt die nachträgliche Bewertung der fehlenden Urteile zu Quellenstützung und Bedeutungserhalt fest. | [nachtrag_18_vervollstaendigung_h1_h2.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_18_vervollstaendigung_h1_h2.md) |
| `N21` | Explorative Abruftiefe | Legt die nachträgliche Variation der Abruftiefe für den Graphkontext fest. | [nachtrag_21_h4_abruftiefe.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_21_h4_abruftiefe.md) |
| `C2/C3-Routennachtrag` | Ausführungsroute des Hauptbewerters | Dokumentiert die ursprüngliche Festlegung der Bewertungsroute. | [nachtrag_c2c3_route.md](../material/Experiments/fair_v2_oct24/G1/nachtrag_c2c3_route.md) |
| `A4-W01–A4-W12` | Neue Wikipedia-Quellen | Bezeichnen die Wikipedia-Quellen des neuen Konfirmationsbestands. | [analysis_contract.public.json](../material/protocols/analysis_contract.public.json) |
| `A4-F01–A4-F08` | Neue Factbook-Profile | Bezeichnen die Factbook-Quellen des neuen Konfirmationsbestands. | [analysis_contract.public.json](../material/protocols/analysis_contract.public.json) |
| `RGCONF01–RGCONF04` | Zuvor versiegelte Quellen | Bezeichnen die vier gesondert versiegelten Konfirmationsquellen. | [analysis_contract.public.json](../material/protocols/analysis_contract.public.json) |
| `NEW20` | Neuer Konfirmationsbestand | Fasst die zwölf Wikipedia-Quellen und acht Factbook-Profile zusammen. | [analysis_contract.public.json](../material/protocols/analysis_contract.public.json) |
| `SEALED4` | Versiegelter Konfirmationsbestand | Fasst die vier zuvor versiegelten Quellen zusammen. | [analysis_contract.public.json](../material/protocols/analysis_contract.public.json) |
| `Main12` | Früherer Entwicklungsbestand | Bezeichnet den Zwölfquellenbestand der früheren Verfahrensentwicklung. | [preregistration_v2_frozen.md](../material/Experiments/fair_v2_oct24/A7/preregistration_v2_frozen.md) |
| `GF01` | Quellen- und Konstruktionsbindung der A/B-Arme | Der Index referenziert die Originalbelege zur älteren A/B-Komponentenprüfung. | [nachweisindex-kernbefunde.json](../material/docs/nachweisindex-kernbefunde.json) |
| `N01–N09` | Historische Originalpfad-Aliase | Ordnen ältere Werkzeug- und Befundpfade im Kernbefundindex zu. | [nachweisindex-kernbefunde.json](../material/docs/nachweisindex-kernbefunde.json) |
| `P-01–P-07` | Historische Befund-Aliase | Ordnen Methodenauswahl, Antwortprüfung, Aufwand und ergänzende Ereignis- und Bewertungsprüfungen im Kernbefundindex zu. | [nachweisindex-kernbefunde.json](../material/docs/nachweisindex-kernbefunde.json) |
| `A3/A3b/A3c/A3d, B1/B1b` | Kontrollen von Prüffilter und Bewerter | Der Vergleichsindex referenziert die Kontrollen für Filter und Bewertungsmodelle. | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `A4, B2` | Quellenauswahl und Referenzbedeutungen | Der Vergleichsindex referenziert Auswahl und Referenzgrundlage der natürlichen Konfirmationsquellen. | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `A5` | MuSiQue-Korpus und Trennung der Goldantworten | Der Vergleichsindex referenziert die Zusammenstellung des Fragekorpus und die Trennung der Goldantworten. | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `A6, C5` | Technische Exportmessung | Der Vergleichsindex referenziert die technische Abbildung nativer Bestände in Graphen. | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `B4` | MuSiQue-Instanzgraphkonstruktion | Der Vergleichsindex referenziert die Konstruktion der MuSiQue-Instanzgraphen und ihre dokumentierte Ablaufabweichung. | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |

## Historische Entwicklungskennungen

Diese Kennungen verweisen auf abgeschlossene Entwicklungsfragen und ihre Belege im Register.

| Kennung oder alter Ordner | Verständlicher Name | Datei |
| --- | --- | --- |
| `BR01` | Rollenmaterialisierung | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR02` | Aufteilung langer Texte | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR03` | Mindestquote | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR04` | Einfluss von Schemabeispielen auf die Konzeptinduktion | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR05` | Mehrere Elemente je Schemaanfrage | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR06` | Konzeptinventar | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR07` | Konservative Zusammenführung von Bezeichnungen | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR08` | Erhalt des Ereignisbezugs | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR09` | Folgen eines Zuordnungsfehlers in der früheren Antwortprüfung mit 24 Fragen | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR10` | Zusätzliche Quellenbeschaffung | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR11` | Frühe Prüfung von Bedeutungsfacetten | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR12` | Verortung von Auswahlantworten | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR13` | Frühere Bewertungsmodelle und Prüferkonfigurationen | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR14` | Restbewertung des Zwölfquellenbestands | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR15` | Erster EV-/VV-Durchgang | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR16` | MINE-Benchmark: Einordnung von Rangwerten | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR17` | Konfidenzwerte | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR18` | Unvollständiger Schema-Versuch | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR19` | MAVEN als Ersatz einer Ereignisbezugsprüfung | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR20` | Früherer Vergleich mit 250 Fragen | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR21` | WebNLG-Inventar | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR22` | Vulkannamen | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR23` | Festgelegte Vulkankonzepte | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR24` | Sprachliche Quellenanker | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR25` | VV- und Kausalregeln | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |
| `BR26` | Wörtliche Bindung der Relationsendpunkte | [nachweisindex-entwicklungsverlauf.json](../material/docs/nachweisindex-entwicklungsverlauf.json) |

## Kennungen des elektronischen Nachweisindex

Diese Nummern ordnen Themen im datierten Nachweisindex. Jede Zeile verlinkt den zugehörigen öffentlichen Index.

| Kennung oder alter Ordner | Verständlicher Name | Datei |
| --- | --- | --- |
| `V2-01` | Vorregistrierung und Freigabe | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-02` | Rollenfreigaben und Nachträge | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-03` | Konfirmationsquellen und Quellenrechte | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-04` | MuSiQue-Korpus und Goldtrennung | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-05` | Kontrollen von Prüffilter und Bewerter | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-06` | Konstruktion natürlicher Quellen | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-07` | MuSiQue-Konstruktion und Ablaufabweichung | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-08` | Prüffilterabschluss und technische Übergabe | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-09` | Quellenstützung, Zweitbewertung und Autorenprüfung | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-10` | Bedeutungserhalt und Referenzen | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-11` | Technische Exportmessung | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
| `V2-12` | Graphbasierte Antwortprüfung und Endauswertung | [nachweisindex-v2.json](../material/docs/nachweisindex-v2.json) |
