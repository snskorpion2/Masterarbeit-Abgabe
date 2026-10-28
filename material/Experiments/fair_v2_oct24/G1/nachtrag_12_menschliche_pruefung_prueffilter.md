# Nachtrag 12: menschliche Prüfung der Prüffilter-Entscheidungen (25.10.2026)

**Status:** sekundäre Mechanismusprüfung für die Komponente Prüffilter (K1, K3 aus N8). Dieser Nachtrag wird vor der
C7-Auswertung in diesem Chat und vor der neuen H12-Ziehung und -Annotation veröffentlicht. Ersetzt teilweise die entfallene
modellbasierte Zweitbewertung (C4 und NIM nicht qualifiziert). Gilt nur, wenn der Autor die Annotation durchführt.

**Chronologie der Veröffentlichung:** X2c wurde bereits unter Verwendung natürlicher C2-Urteile ausgewertet
(`X2/result_c_n10_v1.json`, `X2/ausfuehrung_c_n10_v1.json`). Ein allgemeiner Veröffentlichungsstatus vor jeder
aggregierten C2-/C3-Auswertung oder vollständige Ergebnisblindheit des Teams wird deshalb nicht behauptet.
Der frühere Entwurf bezeichnete seine Festlegung als vor diesen Auswertungen erfolgt. Deren genaue externe
Chronologie wird hier nicht bestätigt. Die nachstehenden Stichproben- und Prüfregeln bleiben unverändert.

## Stichprobe (fester Seed 2026102512)

- **60 entfernte Aussagen** aus allen 550 Prüffilter-Entfernungen der 24 Konfirmationsquellen: 30 aus AS→AS+G, 30 aus
  V1→V2, innerhalb dessen EE und VV proportional zu ihren Entfernungszahlen.
- **30 behaltene EE-/VV-Aussagen** als Kontrolle, je 15 aus AS und V1, nur Aussagen mit gültigem Prüffilterurteil
  (keine ungeprüften).
- Aussagen, die bereits in der C7-Stichprobe sind, werden ausgeschlossen und durch die nächste Ziehung ersetzt.
- Verblindet: weder Arm noch Prüffilterentscheidung noch Grund sichtbar, gemischte Reihenfolge, gleiches Werkzeug und
  gleiche Labels wie C7 (gestützt, nicht gestützt, unklar) mit Kommentarfeld.

## Auswertung

- **Primär für diese Prüfung:** Anteil „nicht gestützt“ (Autorenurteil) unter entfernten gegenüber behaltenen Aussagen.
  Einseitiger exakter Fisher-Test (entfernt > behalten), α = 0,05, mit 95-%-KI der Differenz. Unklar zählt
  konservativ als nicht „nicht gestützt“, Sensitivität mit unklar als „nicht gestützt“.
- **Beschreibend:** Prüffilter-Präzision aus Sicht des Autors (Anteil der Entfernungen, die der Autor als nicht gestützt
  beurteilt), getrennt nach AS und V1, EE und VV, Wikipedia und Factbook sowie auslösender Facette. Übereinstimmung mit
  Sol, soweit die Aussagen im C2-Präfix bewertet sind.
- Kein Eingang in die Holm-Familien aus G2 und N8. Bericht als Mechanismusbeleg bzw. Gegenbefund.
