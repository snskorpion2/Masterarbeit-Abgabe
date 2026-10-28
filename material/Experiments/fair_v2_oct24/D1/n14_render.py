"""N14 tables from supplied effects only; no judgment or source-file access."""
from pathlib import Path

from .render import (_count, _finite, _interval, _need, _number,
                     SYNTHETIC_BANNER, _write_longtable)

IDENTIFIERS = ('H2', 'K2', 'K4', 'K5')


def enabled(report):
    value = report.get('N14_H2_missingness')
    return type(value) is dict and value.get('enabled') is True


def note(report):
    if not enabled(report):
        return ''
    return (' N14: Die gezeigten G2-Schätzer, Intervalle und p-Werte bleiben unverändert. '
            'Nichtunterlegenheit bei H2/K2/K4 erfordert zusätzlich das Bestehen nach Holm '
            'auf Quellen mit gültigen Urteilen in beiden Kontrastarmen. Auch eine '
            'Überlegenheitsaussage bei K5 benötigt die Zusatzanalyse. '
            'Die getrennte N14-Tabelle zeigt Zusatzanalyse und Endurteil.')


def final_confirmation(report, identifier, original):
    """Choose only the supplied final criterion; never infer it from a p-value."""
    if not enabled(report) or identifier not in IDENTIFIERS:
        return original.get('reject') is True
    _need(original.get('n14_analysis_required') is True
          and type(original.get('criterion_met')) is bool,
          'D1_N14_RENDER_DECISION_BINDING_REQUIRED')
    return original['criterion_met']


def end_status(report, identifier, original):
    if not enabled(report) or identifier not in IDENTIFIERS:
        return ''
    return 'N14-Endurteil: ' + ('bestätigt' if final_confirmation(report, identifier, original)
                               else 'nicht bestätigt')


def _effects(report):
    value = report['N14_H2_missingness']
    _need(type(value.get('primary')) is dict
          and type(value.get('components')) is dict
          and set(value['components']) == {'K2', 'K4', 'K5'},
          'D1_N14_RENDER_FOUR_CONTRASTS_REQUIRED')
    for identifier in IDENTIFIERS:
        original = (report['primary']['H2'] if identifier == 'H2'
                    else report['components']['contrasts'][identifier])
        extra = value['primary'] if identifier == 'H2' else value['components'][identifier]
        included, excluded = extra.get('included_source_ids'), extra.get('excluded_source_ids')
        _need(type(included) is list and type(excluded) is list
              and all(type(s) is str for s in included + excluded)
              and len(set(included + excluded)) == len(included + excluded)
              and len(included) == extra.get('eligible_source_count')
              and len(included) + len(excluded) == extra.get('original_source_count'),
              'D1_N14_RENDER_EXPLICIT_SOURCE_POPULATION_REQUIRED')
        final_confirmation(report, identifier, original)
        yield identifier, original, extra


def _effect_text(row):
    point = row.get('point_difference')
    limits = _interval(row.get('ci95'))
    _need(point is None or _finite(point) and -1 <= point <= 1,
          'D1_N14_RENDER_VALID_EFFECT_REQUIRED')
    _need(limits is None or all(-1 <= v <= 1 for v in limits),
          'D1_N14_RENDER_VALID_INTERVAL_REQUIRED')
    return (_number(point * 100 if _finite(point) else None, 2) + ' ['
            + (_number(limits[0] * 100, 2) + ', ' + _number(limits[1] * 100, 2)
               if limits else 'n. b.') + ']')


def _test_status(row):
    if row.get('testable') is not True:
        return 'nicht testbar'
    return 'H0 verworfen' if row.get('reject') is True else 'H0 nicht verworfen'


def _contrast_table(report, output, banner):
    rows = []
    for identifier, original, extra in _effects(report):
        rows.append([identifier + ' / G2', _count(extra['original_source_count']),
                     _effect_text(original),
                     _number(original.get('adjusted_p'), 5) + '; ' + _test_status(original)])
        rows.append([identifier + ' / N14',
                     _count(extra['eligible_source_count']) + '/' + _count(extra['original_source_count']),
                     _effect_text(extra), _number(extra.get('adjusted_p'), 5) + '; '
                     + _test_status(extra) + '. ' + end_status(report, identifier, original)])
    return _write_longtable(output, 'h2_n14_contrasts.tex',
        'N14: ursprüngliche G2-Analyse und verbindliche Quellen-Zusatzanalyse.',
        ['Kontrast / Analyse', 'Quellen n/N', 'Differenz [pp] und 95%-KI', 'p Holm, Test und Endurteil'],
        rows,
        'G2 verwendet die volle festgelegte Quellenpopulation. N14 verwendet je Kontrast nur '
        'Quellen mit mindestens einem gültigen Urteil in beiden Armen. Fehlende Positionen '
        'innerhalb einer Quelle behalten die G2-Nullwertung. NI bei H2/K2/K4 ist nur bestätigt, '
        'wenn beide Analysen ihre jeweilige Holm-Prüfung bestehen. K5-Überlegenheit setzt '
        'das N14-Kriterium voraus. Die primäre Dreier- und die sekundäre Sechserfamilie '
        'bleiben getrennt. Marginale 95%-Intervalle sind keine simultanen Holm-Intervalle. '
        'Die ausgewählten Quellen sind keine belegte Zufallsstichprobe aller Quellen. '
        'Synthetische Werte sind keine empirischen Befunde.', banner,
        r'p{.16\linewidth}p{.10\linewidth}p{.27\linewidth}p{.36\linewidth}')


def _source_table(report, output, banner):
    rows = []
    for identifier, _, extra in _effects(report):
        rows.append([identifier, str(extra.get('treatment', '')) + ' - ' + str(extra.get('control', '')),
                     ', '.join(extra['included_source_ids']) or 'keine',
                     ', '.join(extra['excluded_source_ids']) or 'keine'])
    coverage = report['N14_H2_missingness'].get('coverage', {})
    missing = coverage.get('sources_without_valid_judgments_in_any_cell')
    _need(type(missing) is list and all(type(s) is str for s in missing),
          'D1_N14_RENDER_GLOBAL_MISSING_SOURCE_LIST_REQUIRED')
    return _write_longtable(output, 'h2_n14_sources.tex',
        'N14: kontrastspezifische Quellen mit Urteilen und ausgeschlossene Quellen.',
        ['Kontrast', 'Vergleich', 'Quellen mit gültigen Urteilen in beiden Armen', 'Ausgeschlossene Quellen'],
        rows,
        'Ein Ausschluss bedeutet, dass mindestens einer der beiden Kontrastarme für diese '
        'Quelle kein gültiges Urteil hat. Er bedeutet keinen semantischen Fehler. Die '
        'vollständige G2-Primäranalyse behält alle Quellen. Die Listen werden je Kontrast '
        'geführt und nicht aus einer gemeinsamen oder günstig gewählten Teilmenge ersetzt. '
        'Quellen ohne jedes gültige H2-Urteil über alle Zellen: '
        + (', '.join(missing) if missing else 'keine') + '.', banner,
        r'p{.10\linewidth}p{.24\linewidth}p{.28\linewidth}p{.27\linewidth}')


def _missingness_table(report, output, banner):
    rows = []
    for identifier, _, extra in _effects(report):
        values = extra.get('missingness')
        _need(type(values) is dict and {'full', 'eligible'} <= set(values),
              'D1_N14_RENDER_MISSINGNESS_REQUIRED')
        for scope, label in (('full', 'G2 voll'), ('eligible', 'N14 Quellen mit Urteilen')):
            for arm in ('control', 'treatment'):
                value = values[scope][arm]
                rows.append([identifier + ' / ' + label,
                    'Kontrolle' if arm == 'control' else 'Behandlung',
                    _number(value.get('source_equal_missing_rate')),
                    _number(value.get('pooled_missing_rate')),
                    _number(value.get('source_equal_G2_zero_or_unclear_rate')),
                    _number(value.get('pooled_G2_zero_or_unclear_rate'))])
    return _write_longtable(output, 'h2_n14_missingness.tex',
        'N14: technische Fehlwertquoten und Anteile fehlender oder unklarer Urteile je Analyse und Arm.',
        ['Kontrast / Population', 'Arm', 'techn. m Quelle', 'techn. m gepoolt',
         'fehlend + unklar Quelle', 'fehlend + unklar gepoolt'], rows,
        'Alle Quoten liegen auf [0,1]. Technische Fehlwerte haben kein gültiges Urteil. '
        'Semantisch unklare, gültige Urteile bleiben davon getrennt und zählen bei der '
        'Quellenzulassung als gültig. Die Spalten fehlend + unklar zählen technische '
        'Fehlwerte plus gültige semantisch unklare Urteile. Gültige negative Urteile '
        'sind nicht enthalten. Beide gezählten Urteilsarten erhalten nach G2 symmetrisch '
        'den Wert null. Quelle bezeichnet geplante Durchlaufmittel und gleiche '
        'Quellengewichte; gepoolt verwendet die Summe der Positionen als Nenner. '
        'Fehlende Quoten bleiben n. b. Die eingeschränkte Quellenpopulation ersetzt '
        'keinen Nachweis für die volle Population.', banner,
        r'p{.22\linewidth}p{.13\linewidth}p{.13\linewidth}p{.13\linewidth}p{.13\linewidth}p{.13\linewidth}')


def render_n14(report, output_dir, *, banner, allow_real=False):
    """Write only supplied derived effects, never open underlying judgments."""
    if not enabled(report):
        return []
    _need(type(report.get('synthetic')) is bool, 'D1_N14_RENDER_SYNTHETIC_FLAG_REQUIRED')
    _need(report['synthetic'] or allow_real is True,
          'D1_N14_RENDER_REAL_INPUTS_REQUIRE_EXPLICIT_ENABLE')
    banner = SYNTHETIC_BANNER if report['synthetic'] else banner
    _need(type(banner) is str and banner.strip(), 'D1_N14_RENDER_BANNER_REQUIRED')
    list(_effects(report))
    output = Path(output_dir).absolute()
    output.mkdir(parents=True, exist_ok=True)
    return [_contrast_table(report, output, banner), _source_table(report, output, banner),
            _missingness_table(report, output, banner)]
