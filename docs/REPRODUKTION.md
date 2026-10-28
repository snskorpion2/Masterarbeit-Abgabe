# Auswertung nachvollziehen

[Einstieg](../README.md) · [Ergebnisse](ERGEBNISSE.md) · [Methodik](METHODIK.md) · [Kennungen](KENNUNGEN.md)

Die folgenden Befehle werden im Hauptverzeichnis des geklonten oder entpackten Repositorys ausgeführt.

## Synthetische Auswertung ausführen

Festgelegte Umgebung: **Python 3.13.12, NumPy 2.4.4, SciPy 1.17.1, Matplotlib 3.10.8**.
Die Abhängigkeiten stehen in [requirements.txt](../requirements.txt).
Die virtuelle Umgebung und das Ausgabeverzeichnis werden außerhalb des Repositorys angelegt.

```sh
python -m pip install -r requirements.txt
python -B -X utf8 reproduzieren.py demo --output ../masterarbeit-demo
```

Das Zielverzeichnis muss neu sein und außerhalb des Repositorys liegen. Die Demo erzeugt:

| Datei | Inhalt |
| --- | --- |
| `analysis.synthetic.json` | Auswertung der künstlichen Eingaben |
| `result.synthetic.json` | Vertragsbindung, Softwareversionen und Kennzeichnung als synthetischer Lauf |

Die Demo umfasst den Auswertungsweg über 24 synthetische Quellen, nutzt den öffentlichen Vertrag
und benötigt weder GPU noch Modell-API. Die ursprüngliche Hashprüfung der Original-Vorregistrierung
im historischen Statistikcode bleibt erhalten.

## Empirische Ergebnisse und benötigte Eingaben

Die veröffentlichten [Ergebnisberichte](ERGEBNISSE.md) dokumentieren die empirischen Befunde.
Ihre erneute Berechnung benötigt die privat aufbewahrten Einzelurteile und Laufartefakte.
Konstruktionsprogramme, Anbieteranbindungen und natürliche Nachanalysen werden als ausgewählte
Quellprogramme mitgeliefert. Der hier geprüfte öffentliche Ausführungspfad ist die synthetische CPU-Demo.
