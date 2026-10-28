"""Render EF1 numeric tables and two one-paragraph manuscript drafts."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'EF1'


def n(v,digits=3):
    return 'unbekannt' if v is None else f'{v:,.{digits}f}'.replace(',','_').replace('.',',').replace('_','\u202f')


def stat(x,digits=3,scale=1):
    p=x.get('estimate'); ci=x.get('ci95')
    if p is None:return 'unbestimmt'
    value=n(p*scale,digits)
    if ci and ci.get('lower') is not None and ci.get('upper') is not None:
        return f"{value} [{n(ci['lower']*scale,digits)}; {n(ci['upper']*scale,digits)}]"
    return value+' [KI unbestimmt]'


def table(head,rows):
    return '\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+
                     ['| '+' | '.join(str(c) for c in row)+' |' for row in rows])+'\n'


def render():
    result=json.loads((OUT/'result.json').read_text(encoding='utf-8'))
    stages=json.loads((OUT/'stages.json').read_text(encoding='utf-8'))
    pops=result['populations'];arms=('AS','AS+G','V1','V2')
    h1=pops['H1_NEW20'];h2=pops['H2_N14_NEW20']
    lines=['# EF1 – Aufwand und Qualität nach N17 §1','',
           'Beschreibende sekundäre Auswertung, Stand 26.10.2026. Keine neuen Modellaufrufe, Tests auf Überlegenheit oder Änderungen der primären D1-Urteile. Geldbeträge sind bekannte archivierte Listenpreiskosten in USD, keine geprüften Rechnungen.','',
           '## Population, Nenner und Unsicherheit','',
           f"H1 verwendet {h1['n_sources']} neue Quellen mit vollständigen Kosten aller vier Arme. H2 wird einmal mit der unveränderten konservativen G2-Fehlwertregel auf diesen Quellen und zusätzlich auf den {h2['n_sources']} kostenbekannten Quellen mit gültigen Urteilen nach N14 ausgewiesen. Der tatsächliche N14-Bestand umfasst dieselben 17 neuen Quellen. Die übrigen drei neuen und alle vier versiegelten Quellen haben keine gültigen H2-Urteile. Historische Extraktionskosten der versiegelten Quellen sind außerdem unbekannt, keinesfalls null.", '',
           'Die Rechnung berücksichtigt seit Beginn alle tatsächlich eingefrorenen Durchläufe: NEW20 × 3 und SEALED4 × 2, zusammen 68. Die beim Beginn von EF1 vorliegende, noch nicht committete N17-Arbeitsfassung sprach von „beiden Durchläufen“. Die aktuelle N17-Fassung dokumentiert die Korrektur dieses früheren Wortlauts vor ihrem Commit und verwendet dieselbe eingefrorene Population wie EF1. Die redaktionelle Klarstellung ändert keine Berechnung. Kosten je Quelle summieren alle drei neuen Durchläufe und sind keine Kosten je einzelnem Durchlauf.', '',
           'H1 schätzt je Quelle die vollständige Aussagezahl multipliziert mit ihrem gepoolten N10-Stützungsanteil. Erst danach werden die geschätzten Anzahlen summiert. H2 multipliziert die Zahl der einmal pro Quelle festgelegten Referenzbedeutungen mit dem quellenweisen H2-Wert. H2 bezeichnet ausgewählten Bedeutungserhalt, keinen vollständigen Quellenrecall.', '',
           'Alle 10.000 zweistufigen N10-Ziehungen werden wörtlich wiederverwendet, einschließlich der ursprünglichen globalen Sechsergruppen und des G2-Seeds 2026102407. Matrix: `'+result['bootstrap']['source_group_matrix_sha256']+'`. Die vorher festgelegten kostenbekannten Teilmengen werden in jede unveränderte 24-Quellen-Ziehung projiziert. Kosten wandern mit der Quelle; die Anzahl zulässiger Quellen pro Ziehung variiert. Mittelwerte teilen durch diese Anzahl. Die Kennzahlen und AS-Verhältnisse bleiben gepaart. 95-%-Intervalle sind marginale 2,5-/97,5-%-Quantile, ohne zusätzlichen Test und ohne Holm-Aussage. Nicht schätzbare Werte oder Replikate werden nicht entfernt; Schranken stehen in `result.json`. N10s nur näherungsweise gleiche Inklusionswahrscheinlichkeiten bleiben eine Einschränkung.', '',
           '## Kosten und Qualitätswerte je Quelle','',
           table(['Arm','Kosten/Quelle USD, H1-Population','H1 %','Kosten/Quelle USD, N14-Teilmenge','H2 %'],[
               [a,stat(h1['by_arm'][a]['mean_cost_per_source_usd'],4),stat(h1['by_arm'][a]['H1'],2,100),
                stat(h2['by_arm'][a]['mean_cost_per_source_usd'],4),stat(h2['by_arm'][a]['H2'],2,100)] for a in arms]),
           '![Kosten je Quelle gegenüber H1 und H2](kosten_qualitaet.png)','',
           'Horizontale und vertikale Linien sind marginale Bootstrapintervalle; sie sind keine gemeinsamen Konfidenzregionen und kein Signifikanztest. Verschiedene Marker und direkte Beschriftungen erhalten die Armzuordnung in Graustufen. X3 wird nicht eingezeichnet: Der vorliegende CPU-Projektionscode und seine zusätzlichen Anbietergebühren von null sind kein gemessener unabhängiger VV-Prüffilterlauf.', '',
           '## H1-bezogene Effizienzmaße auf den 20 neuen Quellen','',
           table(['Arm','Vollkosten USD','Geschätzte gestützte Aussagen','USD/gestützter Aussage','Gesamttokens/gestützter Aussage','Gestützte Aussagen/1.000 Konstruktionstokens'],[
               [a,stat(h1['by_arm'][a]['cost_usd'],4),stat(h1['by_arm'][a]['estimated_supported_statements'],1),
                stat(h1['by_arm'][a]['cost_per_supported_usd'],6),stat(h1['by_arm'][a]['tokens_per_supported'],1),
                stat(h1['by_arm'][a]['supported_per_1000_construction_tokens'],3)] for a in arms]),
           'Schätzungen gestützter Aussagen sind keine Vollzählungen. Gesamttokens umfassen gegebenenfalls den Prüffilter. Der Nenner „Konstruktionstokens“ umfasst Extraktion, Ergänzung und Schema, ausdrücklich ohne Prüffilter.', '',
           table(['Arm','USD/gestützt, Verhältnis zu AS','Tokens/gestützt, Verhältnis zu AS','Gestützt/1.000 Konstruktionstokens, Verhältnis zu AS'],[
               [a,stat(h1['by_arm'][a]['ratios_vs_AS']['cost_per_supported_usd']),
                stat(h1['by_arm'][a]['ratios_vs_AS']['tokens_per_supported']),
                stat(h1['by_arm'][a]['ratios_vs_AS']['supported_per_1000_construction_tokens'])] for a in arms]),
           '## H2-bezogene Effizienzmaße','']
    for key,title in [('H2_G2_NEW20','G2-Regel auf den 20 kostenbekannten neuen Quellen'),('H2_N14_NEW20','N14-Analyse 2, Schnittmenge mit vollständigen Kosten')]:
        p=pops[key];lines.extend(['### '+title,'',
            table(['Arm','Quellen','Geschätzte erhaltene Referenzbedeutungen','USD/erhaltener Referenzbedeutung','Verhältnis zu AS'],[
                [a,p['n_sources'],stat(p['by_arm'][a]['estimated_retained_references'],2),
                 stat(p['by_arm'][a]['cost_per_retained_reference_usd'],4),
                 stat(p['by_arm'][a]['ratios_vs_AS']['cost_per_retained_reference_usd'])] for a in arms]),''])
    lines.extend(['## AS+G gegen V1: keine reine Aufwandserklärung','',
        'Die folgenden Differenzen lauten **V1 minus AS+G** und sind beschreibend, ohne neuen Hypothesentest. Qualitätswerte stammen jeweils aus derselben Population wie ihre Kosten.', '',
        table(['Population','H1-Differenz Prozentpunkte','H2-Differenz Prozentpunkte','Kosten-Differenz USD gesamt'],[
            [name,stat(p['contrasts']['V1_minus_AS+G']['H1'],2,100),
             stat(p['contrasts']['V1_minus_AS+G']['H2'],2,100),
             stat(p['contrasts']['V1_minus_AS+G']['cost_usd'],4)] for name,p in [(f"H1, {h1['n_sources']} Quellen",h1),(f"N14, {h2['n_sources']} Quellen",h2)]]),
        'Die unterschiedliche Aufgabenverteilung und der verschiedene Aussagebestand bleiben mit dem Aufwand verbunden. Es fehlt ein rechenaufwandsgleicher AutoSchemaKG-Vergleich. Weder die Erklärung „nur mehr Rechnen“ noch ein isolierter Architektureffekt ist damit kausal nachgewiesen.', '',
        '## Aufteilung nach Stufe und Forschungsaufwand','',
        'Diese Tabelle zählt originale physische Belegidentitäten disjunkt. AS+G nutzt die bei AS gebuchte Grundkonstruktion weiter, V2 die bei V1 gebuchte. Vollkostenvergleiche der vier logischen Arme enthalten diese Grundkosten jeweils, die physischen Gesamtsummen zählen sie einmal. Holds und Reserven werden nicht zu Kosten addiert.', ''])
    def subtotal(m,digits=3):
        v=m['known_subtotal'];return n(v,digits)+(' (Teilsumme)' if not m['complete'] else '')
    lines.append(table(['Arm','Stufe','Aufrufe','Eingabetokens','Ausgabetokens','USD','Summe Anfragedauer s'],[
        [r['arm'],r['stage'],subtotal(r['calls'],0),subtotal(r['prompt_tokens'],0),
         subtotal(r['completion_tokens'],0),subtotal(r['known_cost'],6),subtotal(r['request_elapsed_seconds'],2)]
         for r in stages['new20_construction_and_guard']]))
    lines.extend(['Die Summe einzelner protokollierter Anfragedauern ist **keine Wandzeit**, insbesondere bei Parallelität. Isolierte Wandzeiten der Konstruktionsstufen sind nicht vollständig belegt und bleiben unbekannt. Fehlende Konstruktordauern wurden nicht durch einen erneuten Massenscan rekonstruiert; vorhandene abgeschlossene Kostenbelege bleiben maßgeblich.', '',
       'Der deterministische CPU-Export steht separat unter `stages.json/CPU_export_separate`: C5 belegt 544 Exportzellen für alle 24 Quellen, vier Arme und beide Exportformen, ohne zusätzliche Modellaufrufe. Eine isolierte CPU-Kosten- oder Wandzeitmessung liegt im gebundenen Abschluss nicht vor. Dieser Aufwand ist nicht als kostenloser Gesamtprozess interpretiert und nicht als LLM-Bewertungsaufwand gebucht.', '',
       'Alle Forschungspakete mit Aufrufen, Tokens, Kosten, Währung, Preisszenario und Zeitvollständigkeit stehen vollständig in `stages.json`. C6-Reader und Zugangsprobe, T1 als andere Konstruktormodellbedingung sowie C2/C3, Referenzerstellung und Qualifikationen werden nicht in N17-Konstruktionskosten eingerechnet. EUR und USD bleiben getrennt. C1-MuSiQue kostet 51,68097936 USD bei 3.854 Aufrufen; der Ledger-Gesamtwert 62,82758736 USD enthält zusätzlich 11,14660800 USD Konfirmation. T1: 7.656 Aufrufe, 6,14850118 USD, bislang kein gemeinsamer semantischer Qualitätsvergleich. C6: 0,15451260 USD Reader plus getrennte 0,00002706 USD Zugangsprobe. Seine HTTP- und Workerzeitsummen sind keine gesamte Laufwandzeit.', '',
       '## Vollständigkeit und Grenzen','',
       'Über alle 24 Quellen sind die Gesamtkosten wegen der historischen Extraktion der vier versiegelten Quellen unbekannt. `result.json/full24_cost_scope` nennt deshalb nur bekannte Kostenuntergrenzen und untersagt Vergleichsaussagen daraus. Die vollständigen Effizienzkontraste beschränken sich auf die oben genannten kostenbekannten Populationen. Fehlende historische Kosten sind kein Nachteil eines Arms und kein Nullwert. Qualität und Kosten werden nicht zu einem gemeinsamen Gesamtscore verdichtet.', '',
       'K2 wurde aus Originalbelegen ergänzt: sämtliche Prüffilteraufrufe erhalten eine Quelle; leere Aufrufmengen bleiben als Nicht-Aufrufe gekennzeichnet und erhalten eine gruppenspezifische Belegidentität. Ursprüngliche Antworten, Ausführungsledger und der primäre D1-Ergebnisstand bleiben unverändert. Verifikation und genaue K2-Reparaturbelege stehen in den K2-Dateien und `verification.json`.'])
    (OUT/'BERICHT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    a=h1['by_arm'];b=h2['by_arm']
    kap=(f"Auf den 20 neuen Quellen mit vollständigen Kosten betragen die Listenpreiskosten je Quelle für AS+G {n(a['AS+G']['mean_cost_per_source_usd']['estimate'],3)} USD und für V1 {n(a['V1']['mean_cost_per_source_usd']['estimate'],3)} USD, jeweils über drei Durchläufe. "
         f"Die Quellenstützung H1 liegt bei {n(a['AS+G']['H1']['estimate']*100,2)} beziehungsweise {n(a['V1']['H1']['estimate']*100,2)} Prozent. "
         f"Auf den {h2['n_sources']} kostenbekannten N14-Quellen beträgt der ausgewählte Bedeutungserhalt H2 {n(b['AS+G']['H2']['estimate']*100,2)} beziehungsweise {n(b['V1']['H2']['estimate']*100,2)} Prozent. "
         'Die nachträgliche Aufwand-Qualitäts-Bilanz nach N17 berichtet Kosten je geschätzter gestützter Aussage und je erhaltener Referenzbedeutung mit marginalen 95-Prozent-Intervallen aus denselben N10-Ziehungen. Forschungsaufwand bleibt getrennt. Die unterschiedlichen Ergebnisrichtungen ergeben keine allgemeine Effizienz- oder Überlegenheitsrangfolge.')
    disc=('Der Vergleich von AS+G und V1 trennt eine pauschale Aufwandserklärung von der beobachteten Qualitätsverteilung: '
          f"V1 hat bei Kosten von {n(a['V1']['mean_cost_per_source_usd']['estimate'],3)} statt {n(a['AS+G']['mean_cost_per_source_usd']['estimate'],3)} USD je Quelle einen etwas niedrigeren H1-Punktschätzer und einen höheren ausgewählten Bedeutungserhalt auf der kostenbekannten N14-Teilmenge. "
          'Eine alleinige Aufwandserklärung lässt sich daraus weder bestätigen noch isoliert ausschließen. Ein kausaler Effekt der Architektur oder des Aufwands ist nicht isoliert, weil ein rechenaufwandsgleicher AutoSchemaKG-Vergleich fehlt und Filterung sowie Ergänzung unterschiedliche Aussagebestände erzeugen. Die sekundären Effizienzmaße ergänzen deshalb die getrennten Qualitätsachsen, ohne das vorregistrierte Gesamturteil zu erweitern.')
    (OUT/'textbausteine.md').write_text('# Kapitel 6 – ein Absatz\n\n'+kap+'\n\n# Diskussion – ein Absatz\n\n'+disc+'\n',encoding='utf-8')
    (OUT/'textbausteine.tex').write_text('% Kapitel 6 (Entwurf, nicht automatisch eingebunden)\n'+kap.replace('%',r'\%')+'\n\n% Diskussion (Entwurf, nicht automatisch eingebunden)\n'+disc+'\n',encoding='utf-8')
    print('EF1 tables and two manuscript paragraphs written')


if __name__=='__main__':render()
