# Menschliche Transferstichprobe: Ergebnis nach Nachtrag 16

Am 26.10.2026 sind alle 60 paketgebundenen H16-Urteile eingegangen. Der Autor
hat ausdrücklich bestätigt: „Ja, alle 60 selbst bewertet“. Der Export trägt
`annotation_origin=human_ui_input`. Seine 10.127 Originalbytes wurden unverändert
privat übernommen und zurückgelesen. SHA-256:
`db081264f43bc6952aec49e04c9ec849263221bec5e604700c69380dc63167a6`.
Öffentlich stehen ausschließlich Aggregate, keine Aussagen oder Einzelurteile.

| Arm | Gestützt | Nicht gestützt | Unklar | Gestützt / alle 30 |
|---|---:|---:|---:|---:|
| AS | 26 | 1 | 3 | 86,67 % |
| V2 | 29 | 0 | 1 | 96,67 % |

V2 minus AS beträgt **+10,00 Prozentpunkte**, mit dem vorab festgelegten
95-%-Aussagen-Bootstrapintervall **[−3,33; +23,33] Prozentpunkte**. Der
Punktschätzer hat dieselbe positive Richtung wie die in N16 bekannte
Hauptbedingung (+8,4 Prozentpunkte). Das Intervall enthält null sowie negative
und positive Differenzen. Die kleine Stichprobe liefert deshalb keinen
abgesicherten allgemeinen Überlegenheits- oder Übertragbarkeitsnachweis.
Ein Signifikanztest war nicht vorgesehen und wurde nicht ergänzt.

Die Typaufteilung bleibt beschreibend. Je Arm und Typ wurden zehn Vorkommen
gezogen, „unklar“ bleibt jeweils im Nenner:

| Typ | AS gestützt / 10 | V2 gestützt / 10 |
|---|---:|---:|
| EE | 8 / 10 | 10 / 10 |
| EV | 10 / 10 | 10 / 10 |
| VV | 8 / 10 | 9 / 10 |

Nachtrag 16 wurde unter `2be556304b9a47505fc4c40a84297626484eb07b`
veröffentlicht und vor der einmaligen Ziehung unter
`245864854f66e04f62c7bbaab66d547d8dfdf33f` zeitlich präzisiert. Die Präzisierung
legt offen, dass der Kimi-Prüffilter bereits Teil der T1-Konstruktion war.
Die Vorlaufergebnisse der Hauptbedingung waren bei der Festlegung bekannt.

Die unveränderte Ziehung mit Seed 2026102616 umfasst 60 ursprüngliche
Aussagevorkommen aus 18 der 20 T1-Frischquellen, Qwen3-235B als Konstruktor,
ein Durchlauf je Arm. Es war keine VV-Auffüllung nötig. Technisch ungeprüft
beibehaltene Aussagen waren nicht aus der Auswahlpopulation ausgeschlossen.
Die Metadatenverblindung verdeckte Arm, Typ und Prüffilterstatus, schließt
Hinweise aus Quellen und Aussageformulierungen aber nicht aus.

Die Auswertung verwendete genau einmal den eingefrorenen Auswerter mit
10.000 unabhängigen Ziehungen je Arm über jeweils 30 ganze Aussagevorkommen,
NumPy PCG64, Seed 2026102617 und linearen Perzentilquantilen. Die ungewichteten,
typgeschichteten Stichprobenraten schätzen nicht die natürliche Typmischung der
vollständigen Arme. In 16 der 18 Quellen liegen mehrere Stichprobenaussagen,
höchstens neun in einer Quelle. Das vorgegebene Aussagenintervall korrigiert
diese gemeinsame Quellenabhängigkeit nicht. Die Autorenannotation ist kein
unabhängiger menschlicher Goldstandard. H16 bleibt explorativ außerhalb der
Holm-Familien und ändert das abgeschlossene D1-Gesamturteil nicht.

Die technische Endprüfung fand eine Reihenfolgeabweichung: Der ursprüngliche
Auswerter schrieb die private Originalkopie vor dem Schlüsselzugriff, las sie
jedoch erst nach dem Zugriff und der Statistik zurück. Das Protokoll verlangt
den Readback bereits davor. Die nachträglich festgestellte Bytegleichheit mit
dem unveränderten Export ist belegt. Sie ersetzt keine rückwirkende Einhaltung
dieser Reihenfolge. Der Sicherungsschritt ist für künftige Aufrufe korrigiert
und synthetisch geprüft. Die statistischen Funktionen, ursprünglichen Urteile
und das bereits erzeugte Ergebnis bleiben unverändert, ohne erneute natürliche
Auswertung.

Nachweise: [Ergebnis](result.json),
[Endprüfung und technische Abweichung](evaluation_verification.json),
[eingefrorenes Protokoll](PROTOKOLL.md), [Veröffentlichung](publication.json),
[historische Vorbereitung](preparation.json) und
[Vorbereitungsprüfung](verification.json).
