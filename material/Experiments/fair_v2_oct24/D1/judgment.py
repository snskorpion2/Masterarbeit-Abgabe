"""N8's prospective A--F interpretation, without outcome-file access.

The base stage is not moved to an invented lower letter when evaluator
dependence is detected. Instead, every H1 claim is explicitly qualified.
"""
from math import isfinite
from numbers import Real


STATEMENTS = {
    'A': 'V2 übertrifft AutoSchemaKG im untersuchten Versuchsraum auf allen drei primären Achsen.',
    'B': ('V2 erhöht die Quellenstützung bei nicht unterlegenem Bedeutungserhalt. '
          'Ein QA-Vorteil ist nicht nachgewiesen.'),
    'C': 'Höhere Quellenstützung bei erhaltenem Bedeutungsumfang, jedoch mit messbarem QA-Nachteil.',
    'D': ('Höhere Quellenstützung, Nichtunterlegenheit im Bedeutungserhalt nicht belegt '
          '(Zielkonflikt). Keine Überlegenheitsaussage.'),
    'E': 'QA-Vorteil ohne nachgewiesenen Gewinn an Quellenstützung.',
    'F': 'Kein Überlegenheitsnachweis im untersuchten Versuchsraum.',
}
PROTOCOL_STATEMENTS = dict(STATEMENTS)
# Preserve the protocol's wording for traceability without interpreting H2
# noninferiority as a third superiority test or selected retention as recall.
STATEMENTS.update({
    'A': ('V2 verbessert im untersuchten Versuchsraum die Quellenstützung und das QA-F1 '
          'bei nicht unterlegenem ausgewähltem Bedeutungserhalt.'),
    'B': ('V2 erhöht die Quellenstützung bei nicht unterlegenem ausgewähltem Bedeutungserhalt. '
          'Ein QA-Vorteil ist nicht nachgewiesen.'),
    'C': ('Höhere Quellenstützung bei nicht unterlegenem ausgewähltem Bedeutungserhalt. '
          'Das marginale 95%-Intervall der QA-F1-Differenz liegt vollständig unter null.'),
})
SCOPE = {'confirmation_sources': 24, 'constructor': 'DeepSeek-v3.2',
         'guard': 'Kimi-K2.5', 'primary_evaluator': 'Sol', 'MuSiQue_questions': 60,
         'universal_superiority_claim_allowed': False}


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _number(value, name, lower, upper):
    _need(value is None or isinstance(value, Real) and not isinstance(value, bool)
          and isfinite(value) and lower <= value <= upper,
          name + ' must be finite within its legal range or None')
    return None if value is None else float(value)


def overall_judgment(primary, *, human_kappa=None, grok_h1_difference=None,
                     c4_available=False, c7_available=False):
    """Return exactly one applicable A--F stage plus transparent qualifications.

    ``primary`` is D1's already Holm-corrected H1/H2/H4 result mapping. This
    function never recomputes a test or infers a pass from a confidence interval.
    C4/C7 availability means an actual usable countercheck, not its planned size.
    """
    _need(type(primary) is dict and {'H1', 'H2', 'H4'} <= set(primary),
          'The original H1/H2/H4 primary results are required')
    _need(type(c4_available) is bool and type(c7_available) is bool,
          'Explicit boolean countercheck availability required')
    human_kappa = _number(human_kappa, 'C7 Cohen kappa', -1., 1.)
    grok_h1_difference = _number(grok_h1_difference, 'C4 H1 difference', -1., 1.)
    primary_h1 = _number(primary['H1'].get('point_difference'), 'Primary H1 difference', -1., 1.)
    confirmed = {}
    for name in ('H1', 'H2', 'H4'):
        row = primary[name]
        _need(type(row) is dict, 'Primary result must be a mapping')
        for field in ('criterion_met', 'reject'):
            _need(row.get(field) is None or type(row[field]) is bool,
                  'Primary decision flags must be boolean or missing')
        confirmed[name] = row.get('reject') is True and row.get('criterion_met') is True
    ci = primary['H4'].get('ci95')
    _need(ci is None or type(ci) is dict, 'H4 interval must be a bounds mapping or None')
    upper = _number(ci.get('upper') if ci else None, 'H4 upper 95% bound', -1., 1.)
    lower = _number(ci.get('lower') if ci else None, 'H4 lower 95% bound', -1., 1.)
    _need(lower is None or upper is None or lower <= upper, 'H4 bounds must not be inverted')
    stage, reason = None, None
    if confirmed['H1'] and confirmed['H2'] and confirmed['H4']:
        stage = 'A'
    elif confirmed['H1'] and confirmed['H2']:
        if upper is None:
            reason = 'H1/H2 confirmed but H4 upper 95% bound unavailable, B/C not identifiable'
        else:
            stage = 'B' if upper >= 0 else 'C'
    elif confirmed['H1']:
        stage = 'D'
    elif confirmed['H4']:
        stage = 'E'
    else:
        stage = 'F'
    missing, dependence, qualifications = [], [], []
    if not c7_available:
        missing.append('C7')
        qualifications.append('Menschliche Gegenprüfung C7 fehlt, keine Bestätigung.')
    elif human_kappa is None:
        qualifications.append('C7-Cohen-κ ist nicht bestimmbar, keine Bestätigung der Bewerterunabhängigkeit.')
    elif human_kappa < .40:
        dependence.append('C7_kappa_below_0.40')
    if not c4_available:
        missing.append('C4')
        qualifications.append('Grok-Gegenprüfung C4 fehlt, keine Bestätigung.')
    elif grok_h1_difference is None or primary_h1 is None:
        qualifications.append('Das H1-Vorzeichen ist für die Grok-Gegenprüfung nicht bestimmbar.')
    elif primary_h1 * grok_h1_difference < 0:
        dependence.append('C4_opposite_H1_point_estimate_sign')
    dependent = bool(dependence)
    if dependent:
        qualifications.append('Alle Aussagen zur H1-Quellenstützung sind bewerterabhängig.')
    statement = STATEMENTS[stage] if stage else 'Gesamtstufe wegen fehlender H4-Intervallinformation nicht bestimmbar.'
    if dependent:
        statement += ' Aussagen zur H1-Quellenstützung sind bewerterabhängig.'
    return {'base_stage': stage, 'stage': stage, 'statement': statement,
        'base_statement': STATEMENTS.get(stage), 'protocol_statement': PROTOCOL_STATEMENTS.get(stage),
        'H2_confirmed_means': 'noninferiority at -0.05, not superiority or equality',
        'H2_is_selected_retention_not_source_recall': True, 'undefined_reason': reason,
        'confirmed_primary': confirmed, 'H4_upper_95_bound': upper,
        'evaluator_dependent': dependent, 'dependence_reasons': dependence,
        'H1_qualification': 'bewerterabhängig' if dependent else None,
        'qualifications': qualifications, 'missing_counterchecks': missing,
        'counterchecks_confirm_independence': False,
        'counterchecks': {'C4': {'available': c4_available, 'H1_difference': grok_h1_difference},
                         'C7': {'available': c7_available, 'kappa': human_kappa}},
        'thresholds': {'human_kappa_strictly_below': .40,
                       'Grok_opposite_sign': 'strict product < 0, zero is not opposite'},
        'letter_downgrade_invented': False, 'scope': dict(SCOPE)}
