# D1: ausdrücklich angeforderte Endausgaben

Reine Ausgabeprojektion vorhandener Zahlen. Keine neu berechneten Tests oder Konfidenzintervalle.

## N10: G2-Aggregation erst Durchläufe, dann Quellen

| Zelle | G2-Schätzer | Geplante Quellen |
| --- | ---: | ---: |
| AS_ORIGINAL | 0.8192137864061997 | 24 |
| AS_ROW | 0.8192137864061997 | 24 |
| AS_G_ORIGINAL | 0.8801840756268557 | 24 |
| AS_G_ROW | 0.8801840756268557 | 24 |
| V1_ORIGINAL | 0.8693737652489867 | 24 |
| V1_ROW | 0.8693737652489867 | 24 |
| V2_ORIGINAL | 0.9010059205907024 | 24 |
| V2_ROW | 0.9010059205907024 | 24 |

Primärkontrast dieser Sensitivität: 0.08179213418450271; 95-%-KI {'lower': 0.06198576787809507, 'upper': 0.10107246906428698}.

## H2: G2 und N14 getrennt

| Analyse | Quellen | Differenz | 95-%-KI | p roh | p Holm | Kriterium dieser Analyse |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| G2 | 24 | 0.09685395622895625 | {'lower': 0.042340067340067344, 'upper': 0.15796603184624014} | 9.999000099990002e-05 | 0.00029997000299970003 | True |
| N14 | 17 | 0.13673499702911468 | {'lower': 0.06467419290948703, 'upper': 0.20939703406615165} | 9.999000099990002e-05 | 0.00029997000299970003 | True |

Kombiniertes H2-Kriterium: True.

## Identifikationsschranken und Intervalle

| Endpunkt | Punkt-Schranken | Bootstrap-Sensitivität 95 % | Marginales 95-%-KI |
| --- | --- | --- | --- |
| H1 | {'lower': 0.05561154121349832, 'upper': 0.11820500874539652} | {'lower': 0.026603295932061226, 'upper': 0.14475438200212062} | {'lower': 0.05481386316811773, 'upper': 0.11140709884884337} |
| H2 | {'lower': -0.22125771604938282, 'upper': 0.4162001964085297} | {'lower': -0.43021701388888883, 'upper': 0.584302662037037} | {'lower': 0.042340067340067344, 'upper': 0.15796603184624014} |
| H4 | {'lower': -0.014411699411699416, 'upper': -0.014411699411699416} | {'lower': -0.08285620636141132, 'upper': 0.0391081187469247} | {'lower': -0.08285620636141132, 'upper': 0.0391081187469247} |

## Wilcoxon-Sensitivität

| Endpunkt | Quellen | W+ | p roh |
| --- | ---: | ---: | ---: |
| H1 | 24 | 294.0 | 9.999000099990002e-05 |
| H2 | 24 | 287.5 | 9.999000099990002e-05 |

## Quellenweise V2 gegenüber AS, beschreibend

| Analyse | Geplant | Vergleichsumfang | Paarweise schätzbar | V2 größer | Gleich | V2 kleiner | Nicht schätzbar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| H1 | 24 | 24 | 24 | 21 | 0 | 3 | 0 |
| H2 | 24 | 24 | 24 | 14 | 8 | 2 | 0 |
| H2_N14_eligible | 24 | 17 | 17 | 14 | 1 | 2 | 0 |

## H1 bei VV über schätzbare Quellen, beschreibend

| Zelle | Mittelwert über schätzbare Quellen | Schätzbare Quellen n | Geplante Quellen N |
| --- | ---: | ---: | ---: |
| V1_ROW | 0.5988717740060451 | 23 | 24 |
| V2_ROW | 0.7272652530089602 | 23 | 24 |

Die VV-Mittelwerte ergänzen die Primäranalyse rein beschreibend. Zusätzliche Intervalle werden nicht ausgewiesen.
Strikte Vergleiche auf ungerundeten Quellenwerten, ohne Toleranz. Quellenzahlen sind keine zusätzlichen Hypothesentests.
N14s ausgewählte Quellen sind keine belegte Zufallsstichprobe aller geplanten Quellen.
