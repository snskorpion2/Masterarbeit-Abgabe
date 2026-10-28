"""N8's separate, six-slot component family over existing paired draws.

Only supplied in-memory estimands and matrices are used. No outcome files,
model clients, new random draws or primary-family calculations are loaded.
"""
from math import isfinite
from numbers import Real

from . import inference as inf


COMPONENT_FAMILY = ('K1', 'K2', 'K3', 'K4', 'K5', 'K6')
CONTRASTS = (
    ('K1', 'H1', 'AS_ORIGINAL', 'AS_G_ORIGINAL', 0.),
    ('K2', 'H2', 'AS_ORIGINAL', 'AS_G_ORIGINAL', -.05),
    ('K3', 'H1', 'V1_ORIGINAL', 'V2_ORIGINAL', 0.),
    ('K4', 'H2', 'V1_ORIGINAL', 'V2_ORIGINAL', -.05),
    ('K5', 'H2', 'AS_ORIGINAL', 'V1_ORIGINAL', 0.),
    ('K6', 'H1', 'AS_ORIGINAL', 'V1_ORIGINAL', -.05),
)
H4_COMPONENTS = (('guard_AS', 'AS', 'AS_G'),
                 ('guard_V1', 'V1', 'V2'),
                 ('extraction_extension', 'AS', 'V1'))


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def holm_secondary(pvalues, alpha=.05):
    """Exactly K1--K6, independent of G2's unmodified primary family.

    An unavailable raw p retains its place as conservative slot p=1. It is
    never converted into an observed p or removed from the family size.
    """
    _need(type(pvalues) is dict and set(pvalues) == set(COMPONENT_FAMILY),
          'N8 component family is exactly K1/K2/K3/K4/K5/K6')
    _need(isinstance(alpha, Real) and not isinstance(alpha, bool)
          and isfinite(alpha) and 0 < alpha < 1, 'Valid component alpha required')
    slots = {}
    for name in COMPONENT_FAMILY:
        value = pvalues[name]
        _need(value is None or isinstance(value, Real) and not isinstance(value, bool)
              and isfinite(value) and 0 <= value <= 1,
              'Component raw p must be finite [0,1] or None')
        slots[name] = 1. if value is None else float(value)
    ordered = sorted(COMPONENT_FAMILY,
                     key=lambda name: (slots[name], COMPONENT_FAMILY.index(name)))
    adjusted, running = {}, 0.
    for rank, name in enumerate(ordered):
        running = max(running, (len(COMPONENT_FAMILY) - rank) * slots[name])
        value = min(1., running)
        adjusted[name] = {
            'raw_p': None if pvalues[name] is None else float(pvalues[name]),
            'slot_p': slots[name], 'adjusted_p': value,
            'reject': pvalues[name] is not None and value <= alpha,
            'slot_is_missing_placeholder': pvalues[name] is None,
        }
    return {'family': list(COMPONENT_FAMILY), 'family_size': 6,
            'alpha': float(alpha), 'role': 'secondary_confirmatory_separate_family',
            'primary_family_unchanged': True,
            'results': {name: adjusted[name] for name in COMPONENT_FAMILY}}


def _source_rows(aggregates, endpoint, cell, source_ids):
    rows = aggregates[endpoint][cell]['sources']
    _need([row['source_id'] for row in rows] == source_ids,
          'N8 source order must match the primary shared draw matrix')
    return rows


def component_verdicts(contrasts):
    """Interpret only the predefined pairs of Holm-confirmed criteria."""
    _need(set(contrasts) == set(COMPONENT_FAMILY), 'All six component results required')
    def confirmed(name):
        return contrasts[name].get('criterion_met') is True
    result = {}
    for name, support, retention, base in (
            ('guard_AS', 'K1', 'K2', 'AS'), ('guard_V1', 'K3', 'K4', 'V1')):
        both = confirmed(support) and confirmed(retention)
        conflict = confirmed(support) and not confirmed(retention)
        statement = ('verbessert die Quellenstützung bei erhaltenem Bedeutungsumfang'
                     if both else
                     'höhere Quellenstützung, Nichtunterlegenheit im Bedeutungserhalt nicht belegt (Zielkonflikt)'
                     if conflict else 'kein gemeinsamer Komponentennachweis')
        result[name] = {'base': base, 'criteria': [support, retention],
                        'criterion_met': both, 'tradeoff': conflict, 'statement': statement,
                        'H1_evaluator_qualification_required': True}
    extension_met = confirmed('K5') and confirmed('K6')
    result['extraction_extension'] = {
        'criteria': ['K5', 'K6'], 'criterion_met': extension_met,
        'statement': ('erhöht den Bedeutungserhalt ohne relevante Präzisionseinbuße'
                      if extension_met else 'kein gemeinsamer Komponentennachweis'),
        'bundle': 'SCOPE und gemeinsamer Ergänzungspass',
        'individual_effects_identified': False,
        'H1_evaluator_qualification_required': True,
    }
    result['export'] = {'role': 'descriptive_only', 'endpoint': 'H3', 'test': None}
    result['schema'] = {'component_contrast': None, 'improvement_claim_allowed': False,
                        'reason': 'unveränderte Original-AS-Schemainduktion in beiden Armen'}
    return result


def analyze_components(aggregates, qa_maps, contract, *, indices, qa_indices, h1_bootstrap=None,
                       h2_restriction=None):
    """Use the caller's exact existing source and QA bootstrap matrices.

    H1/H2 use the ORIGINAL inventory view because exports cannot change an
    inventory endpoint. H4 keeps all three predefined component contrasts
    separately for BOTH already planned export views. Neither view is chosen
    after seeing results. The H4 rows expose no inferential p or Holm slot.
    """
    _need(indices is not None and qa_indices is not None,
          'N8 requires the existing primary draw matrices, not new random draws')
    source_ids = [row['source_id'] for row in contract['sources']]
    _need(source_ids and len(source_ids) == len(set(source_ids)), 'Unique planned sources required')
    contrasts = {}
    for name, endpoint, control, treatment, boundary in CONTRASTS:
        left = _source_rows(aggregates, endpoint, control, source_ids)
        right = _source_rows(aggregates, endpoint, treatment, source_ids)
        value = (h1_bootstrap(control, treatment, null_boundary=boundary)
                 if endpoint == 'H1' and h1_bootstrap is not None else
                 inf.paired_source_bootstrap(
                     [row['estimate'] for row in left], [row['estimate'] for row in right],
                     control_lower=[row['lower'] for row in left],
                     control_upper=[row['upper'] for row in left],
                     treatment_lower=[row['lower'] for row in right],
                     treatment_upper=[row['upper'] for row in right],
                     indices=indices, null_boundary=boundary))
        value.update(identifier=name, endpoint=endpoint, control=control, treatment=treatment,
                     alternative='greater',
                     hypothesis='noninferiority' if boundary < 0 else 'superiority',
                     role='secondary_confirmatory_separate_family',
                     shared_primary_source_matrix=True)
        if endpoint == 'H1' and h1_bootstrap is not None:
            value['shared_primary_source_group_matrix'] = True
        contrasts[name] = value
    holm = holm_secondary({name: row['raw_p'] for name, row in contrasts.items()})
    for name, row in contrasts.items():
        row.update(adjusted_p=holm['results'][name]['adjusted_p'],
                   reject=holm['results'][name]['reject'])
        delta = row['point_difference']
        row['criterion_met'] = (row['reject'] and delta is not None
                                and delta > row['null_boundary'])
    n14 = None
    if h2_restriction is not None:
        from . import n14_missingness
        additional = {name: h2_restriction.contrast(control, treatment, null_boundary=boundary)
                      for name, endpoint, control, treatment, boundary in CONTRASTS if endpoint == 'H2'}
        additional_holm = holm_secondary({
            name: additional[name]['raw_p'] if name in additional else contrasts[name]['raw_p']
            for name in COMPONENT_FAMILY})
        for name, value in additional.items():
            value.update(identifier=name)
            n14_missingness.apply_decision(contrasts[name], value, additional_holm['results'][name])
        n14 = {'contrasts': additional, 'holm': additional_holm,
               'unchanged_H1_slots': ['K1', 'K3', 'K6'],
               'decision_rule': 'N8 criterion and N14 additional criterion both required for K2/K4/K5'}
    h4 = []
    for export in ('ORIGINAL', 'ROW'):
        for component, left, right in H4_COMPONENTS:
            control, treatment = left + '_' + export, right + '_' + export
            value = inf.paired_question_bootstrap(qa_maps['f1', control],
                qa_maps['f1', treatment], contract['qa_blocks'], indices=qa_indices)
            h4.append({'component': component, 'endpoint': 'F1', 'export': export,
                'control': control, 'treatment': treatment,
                'point_difference': value['point_difference'], 'ci95': value['ci95'],
                'identification_sensitivity95': value['identification_sensitivity95'],
                'question_count': value['question_count'],
                'completed_pair_count': value['completed_pair_count'],
                'role': 'secondary_descriptive', 'no_hypothesis_test': True,
                'CI_scope': 'marginal descriptive percentile, not simultaneous',
                'shared_primary_QA_matrix': True})
    result = {'contrasts': contrasts, 'holm': holm, 'verdicts': component_verdicts(contrasts),
            'H4_descriptive': h4,
            'matrix_policy': ('N10 H1 reuses the exact primary source/group plan; H2/H4 reuse G2 matrices'
                              if h1_bootstrap is not None else
                              'exact caller-provided primary matrices, no new RNG call'),
            'primary_family_unchanged': True}
    if n14 is not None:
        result['N14_H2_missingness'] = n14
    return result
