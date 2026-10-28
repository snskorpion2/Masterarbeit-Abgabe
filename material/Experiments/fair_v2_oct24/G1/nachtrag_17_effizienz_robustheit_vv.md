# Nachtrag 17: Effizienzmaße unter N10, Robustheit der Primärkontraste und explorative VV-Prüfvariante (26.10.2026)

**Status:** sekundär bzw. explorativ. Keine Änderung an H1, H2, H4, den Holm-Familien, der Gesamtstufe oder dem
Komponentenurteil nach N8.

**Chronologie:** festgelegt nach dem D1-Vorlauf. Bekannt waren die H1- und H2-Punktschätzer je Zelle, die
Inventargrößen, die K2-Kostenzeilen, die H1-Typaufteilung, die X1-Strukturzählungen und H12. Die Koordination hat daraus
Effizienzverhältnisse grob überschlagen: V1 liegt je gestützter Aussage etwa gleichauf mit AS und ist je erhaltener
Referenzbedeutung teurer, V2 ist in beiden Maßen deutlich teurer. Das H2-bezogene Maß wird gerade deshalb ergänzt und
unabhängig von seiner Richtung berichtet. Die VV-Variante ist durch H12 motiviert (Präzision der Entfernungen VV 77 %,
EE 31 %) und deshalb nachträglich. Die H1-Projektion nach §3(a) wurde parallel im ursprünglichen X3-Auftrag berechnet
(`X3/result.json`, 26.10. gegen 13:24). Der Koordination war sie beim Schreiben dieses Nachtrags nicht bekannt. Der Nachtrag wird
erst danach committet, deshalb gilt die H1-Projektion nicht als vorab festgelegt. Auch EF1 (§1) und RB1 (§2) haben am
26.10. nach der noch nicht committeten Fassung gerechnet. Sie gelten deshalb als nachträgliche beschreibende
Auswertungen nach schriftlich vorliegenden Regeln, nicht als durch einen Commit belegte Vorabfestlegung. Vorab
festgelegt sind nur der Messlauf §3(b) und die H4-Projektion §3(c), jeweils vor ihrem eigenen Ergebnis und sofern
dieser Nachtrag vor ihnen committet wird. Das C6-Ergebnis war beim Commit bekannt. Korrektur vor dem Commit: Die erste
Fassung sprach von „beiden Durchläufen“. Eingefroren sind drei Durchläufe je neuer und zwei je versiegelter Quelle, zusammen 68 Einheiten. EF1
und RB1 haben bereits mit dieser eingefrorenen Population gerechnet. Die Korrektur ändert keine Berechnung.

## 1. Effizienzmaße nach N8 §3 unter N10

- **Geschätzte Zahl gestützter Aussagen** je Quelle s und Zelle c: Ŝ_sc = I_sc · p̂_sc. I_sc ist die Zahl aller
  Aussagen der Zelle über alle eingefrorenen Durchläufe (ganzer Bestand, nicht nur gezogene). p̂_sc ist der Verhältnisschätzer nach
  N10 unter der konservativen Primärregel (unklar und fehlend gelten als nicht gestützt). Zellwert Ŝ_c = Σ_s Ŝ_sc.
  Das ist eine Schätzung, keine Vollzählung.
- **Maße je Zelle:** Kosten je gestützter Aussage K_c / Ŝ_c, Tokens je gestützter Aussage und gestützte Aussagen je
  1.000 Konstruktionstokens wie in N8. Zusätzlich, nachträglich: Kosten je erhaltener Referenzbedeutung
  K_c / Σ_s R_s · ĥ_sc mit R_s Zahl der Referenzbedeutungen und ĥ_sc dem H2-Quellenwert, einmal nach der G2-Analyse
  und einmal nach der N14-Analyse 2.
- **Kosten K_c:** bekannte Listenpreiskosten der Konstruktion (Extraktion, Ergänzung, Schema), gegebenenfalls plus
  Prüffilter, je Quelle aus den K2-Ledgern zugeordnet. Bewertung, Referenzerstellung und Qualifikation werden getrennt
  als Forschungsaufwand berichtet und nicht eingerechnet.
- **Vergleichspopulation:** nur Quellen mit vollständig bekannten Kosten. Für H1-Maße sind das die 20 neuen Quellen,
  für H2-Maße die Quellen der N14-Analyse 2 mit vollständigen Kosten. Werte über alle 24 Quellen gelten wegen der
  unbekannten historischen Extraktion der versiegelten Quellen nur als unvollständig mit Kostenuntergrenze und tragen
  keine Vergleichsaussage. Lässt sich ein Prüffilteraufruf keiner Quelle zuordnen, ist der betroffene Wert unvollständig.
- **Unsicherheit:** dieselben 10.000 zweistufigen N10-Ziehungen mit dem G2-Seed. Die Kosten einer Quelle wandern mit
  ihr. Berichtet werden 2,5-/97,5-%-Quantile der Maße und der Verhältnisse zu AS. Kein Test und keine
  Überlegenheitsbehauptung (N8). Nicht schätzbare Quellenwerte folgen der G2-Schrankenregel.
- **Beschreibend daneben:** Kosten, Aufrufe und Tokens je Stufe, Wandzeit, soweit protokolliert.

## 2. Robustheit der Primärkontraste (Sensitivität, kein Test)

- **Typstandardisierter H1-Kontrast:** H1_std(c) = Σ_t w_t · p̂_t(c) für t ∈ {EE, EV, VV}. p̂_t stammt aus der
  D1-Typaufteilung, w_t ist der Typanteil im vollständigen AS-Bestand. Sensitivität mit den Typanteilen des gemeinsamen
  Bestands beider Arme. Kontraste V2−AS, V1−AS, AS+G−AS und V2−V1. Die Differenz zum Primärkontrast wird beschreibend
  als Mischungsanteil ausgewiesen. Nicht schätzbare Typwerte einer Zelle machen den Kontrast unbestimmt.
- **Leave-one-source-out** für H1 und beide H2-Analysen: Spannweite des Kontrasts und einflussreichste Quelle.
  Zusätzlich Leave-one-family-out.
- **Je Konstruktionsdurchlauf:** H1 und H2 sowie die Kontraste getrennt für jeden eingefrorenen Durchlauf.
- **Relative Senkung des Anteils nicht gestützter Aussagen:** 1 − (1 − H1_c)/(1 − H1_AS) für V2, V1 und AS+G mit KI
  aus denselben Ziehungen.

## 3. Explorative VV-Prüfvariante (nachträglich)

- **(a) Projektion:** die tatsächlichen Entscheidungen des Prüffilters für AS+G und V2, aber nur die VV-Entfernungen
  angewandt. H1 durch Erbung der C2-Urteile nach N10. H2 nur als Intervall [H2(V2), H2(V1)] bzw. [H2(AS+G), H2(AS)]
  unter der ausdrücklich genannten Annahme, dass ein größerer Bestand keine Bedeutung schlechter erhält. Keine neuen
  C3-Urteile. Die Annahme gilt nicht exakt: K2 zeigt für den kleineren Bestand AS+G einen höheren H2-Punktwert als für
  AS. Das Intervall ist deshalb nur eine Orientierung und keine Schranke.
- **(b) Messlauf:** derselbe Prüffilter (Kimi-K2.5 über dieselbe AWS-Route, gleiche Vorlagen, T 0, 16.384 Tokens,
  gleiche Löschregel), aber nur mit den VV-Aussagen der V1-Zellen aller 68 Quelle-Durchlauf-Einheiten. EE und EV
  bleiben unverändert. Fehlerregeln N2 und N7. Deckel 6 USD Listenpreis, Kostenprognose nach 30 Aufrufen, Stopp bei
  prognostizierter Überschreitung. Frist Dienstag 16:00. Was bis dahin fehlt, wird als unvollständig berichtet.
  Berichtet werden gemessene Kosten, Aufrufe und Tokens gegenüber dem V2-Prüffilter, die Übereinstimmung der
  VV-Entfernungen mit V2, H1 durch Urteilserbung und die Maße nach §1. H2 nur als Orientierung wie in (a): oben
  H2(V1), unten H2(V2) nur, wenn die Entfernungen eine Teilmenge der V2-VV-Entfernungen sind, sonst unbestimmt.
- **(c) H4-Projektion:** nur wenn C6 bis Dienstag 14:00 abgeschlossen ist, unabhängig vom C6-Ergebnis. MuSiQue-Graph
  von V2 mit ausschließlich VV-Entfernungen, gleicher Reader und Retrievalweg, Top-30, jede Frage genau einmal. F1 und
  EM mit gepaartem Bootstrap gegen AS und gegen V2, ohne Holm.

Darstellung ausschließlich als „Effizienzvariante (nachträglich, explorativ)“. Die Variante ersetzt V2 nicht und wirkt
nicht auf vorregistrierte Ergebnisse zurück. Ein Effizienzvorteil wird nur mit gemessenen, vollständigen Kosten
beschrieben.
