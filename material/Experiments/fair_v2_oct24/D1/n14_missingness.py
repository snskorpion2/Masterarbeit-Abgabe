"""N14's additional H2 source restriction over supplied in-memory statistics.

Selection uses only whether a technically valid judgment exists in both arms.
Negative and semantically unclear valid judgments qualify equally. All planned
within-source draws and reference denominators keep their original G2 scores.
"""
from hashlib import sha256
from math import fsum

import numpy as np

from . import inference as inf


def active(contract):
    return any(row.get('identifier') == 'N14' for row in contract.get('amendments', []))


def _need(value, reason):
    if not value:
        raise ValueError(reason)


def require_publication(contract):
    """Guard the direct natural-analysis API using protocol metadata only."""
    _need(active(contract), 'N14 is required before any natural H2 analysis')
    _need(type(contract.get('N14_publication')) is dict,
          'N14 publication receipt required before any natural H2 analysis')
    from .contract import load_n14_publication
    published = load_n14_publication()
    _need(contract['N14_publication'] == published,
          'N14 publication receipt differs from the approved single-path publication')


def _valid_count(source):
    planned = source.get('planned_draw_statistics')
    _need(isinstance(planned, list) and bool(planned), 'N14 requires original planned-draw H2 statistics')
    valid = 0
    for row in planned:
        denominator, technical = row.get('denominator'), row.get('technical_missing')
        _need(type(denominator) is int and denominator > 0 and type(technical) is int
              and 0 <= technical <= denominator, 'N14 requires explicit H2 technical-missing counts')
        valid += denominator - technical
    return valid


def _missingness(rows):
    if not rows:
        return {'source_count': 0, 'denominator': 0, 'technical_missing': 0,
                'semantic_unclear': 0, 'pooled_missing_rate': None,
                'source_equal_missing_rate': None,
                'pooled_G2_zero_or_unclear_rate': None,
                'source_equal_G2_zero_or_unclear_rate': None}
    draws = [draw for source in rows for draw in source['planned_draw_statistics']]
    denominator = sum(draw['denominator'] for draw in draws)
    technical = sum(draw['technical_missing'] for draw in draws)
    unclear = sum(draw['semantic_unclear'] for draw in draws)
    return {'source_count': len(rows), 'denominator': denominator,
            'technical_missing': technical, 'semantic_unclear': unclear,
            'pooled_missing_rate': technical / denominator,
            'source_equal_missing_rate': fsum(r['technical_missing_rate'] for r in rows) / len(rows),
            'pooled_G2_zero_or_unclear_rate': (technical + unclear) / denominator,
            'source_equal_G2_zero_or_unclear_rate': fsum(r['missing_rate'] for r in rows) / len(rows)}


class SourceRestriction:
    """Reuse full G2 draws; memoize same-seed matrices for fixed source subsets.

    Each restricted matrix has exactly n_eligible sampled clusters per replicate.
    Filtering an original full-population draw would give variable cluster counts
    and is deliberately not used. No original matrix or result is modified.
    """
    def __init__(self, aggregates, sources, indices):
        self.aggregates = aggregates
        self.source_ids = [row['source_id'] for row in sources]
        _need(bool(self.source_ids) and len(set(self.source_ids)) == len(self.source_ids),
              'N14 requires unique original sources in frozen order')
        self.indices = indices
        self.cache = {tuple(self.source_ids): indices}
        self.rows = {}
        self.valid = {}
        for cell, value in aggregates.items():
            rows = value['sources']
            _need([row['source_id'] for row in rows] == self.source_ids,
                  'N14 source order must match the frozen G2 population')
            self.rows[cell] = rows
            self.valid[cell] = {row['source_id']: _valid_count(row) for row in rows}

    def coverage(self):
        return {'source_order': list(self.source_ids),
                'valid_judgments_by_cell_and_source': self.valid,
                'sources_without_valid_judgments_in_any_cell': [
                    sid for sid in self.source_ids if not any(self.valid[cell][sid] for cell in self.valid)],
                'valid_means': 'technically valid, including negative and semantically unclear judgments; not retained-only',
                'selection_is_random_sample': False,
                'inference_scope': 'the contrast-specific sources with valid judgments in both arms, not all planned sources'}

    def contrast(self, control, treatment, *, null_boundary=-.05):
        _need(control in self.rows and treatment in self.rows, 'N14 requires both contrast cells')
        left, right = self.rows[control], self.rows[treatment]
        positions = [i for i, sid in enumerate(self.source_ids)
                     if self.valid[control][sid] > 0 and self.valid[treatment][sid] > 0]
        included = [self.source_ids[i] for i in positions]
        excluded = [sid for i, sid in enumerate(self.source_ids) if i not in positions]
        c, t = [left[i] for i in positions], [right[i] for i in positions]
        if positions:
            key = tuple(included)
            if key not in self.cache:
                self.cache[key] = inf.cluster_indices(len(included))
            matrix = self.cache[key]
            value = inf.paired_source_bootstrap(
                [r['estimate'] for r in c], [r['estimate'] for r in t],
                control_lower=[r['lower'] for r in c], control_upper=[r['upper'] for r in c],
                treatment_lower=[r['lower'] for r in t], treatment_upper=[r['upper'] for r in t],
                indices=matrix, null_boundary=null_boundary)
            matrix_hash = sha256(np.asarray(matrix, dtype='<i8').tobytes()).hexdigest()
            value['delta_identification_bounds'] = {
                'lower': fsum(r['lower'] for r in t)/len(t) - fsum(r['upper'] for r in c)/len(c),
                'upper': fsum(r['upper'] for r in t)/len(t) - fsum(r['lower'] for r in c)/len(c)}
        else:
            matrix_hash = None
            value = inf.bootstrap_from_replicates(None, None, cluster_count=0,
                null_boundary=null_boundary, missing_reason='no_sources_with_valid_judgments_in_both_arms')
            value.update(control_mean=None, treatment_mean=None, defined_source_pairs=0,
                delta_identification_bounds={'lower': None, 'upper': None})
        value.update(control=control, treatment=treatment, endpoint='H2',
            included_source_ids=included, excluded_source_ids=excluded,
            original_source_count=len(self.source_ids), eligible_source_count=len(included),
            exclusion_details=[{'source_id': sid, 'control_valid_judgments': self.valid[control][sid],
                                'treatment_valid_judgments': self.valid[treatment][sid]} for sid in excluded],
            source_matrix_sha256=matrix_hash,
            fixed_clusters_per_replicate=len(included),
            matrix_policy='G2 full matrix reused if no restriction; same G2 PCG64 seed/draws with fixed eligible source count otherwise',
            within_source_G2_unchanged=True, source_selection_depends_on_semantic_success=False,
            inference_scope='contrast-specific sources with valid judgments in both arms',
            role='N14_additional_required_analysis',
            missingness={'full': {'control': _missingness(left), 'treatment': _missingness(right)},
                         'eligible': {'control': _missingness(c), 'treatment': _missingness(t)}},
            hypothesis='noninferiority' if null_boundary < 0 else 'superiority', alternative='greater')
        return value


def apply_decision(original, additional, adjusted):
    """Attach an additional necessary condition; keep all G2 numbers/flags."""
    additional.update(adjusted_p=adjusted['adjusted_p'], reject=adjusted['reject'])
    delta = additional['point_difference']
    additional['criterion_met'] = (additional['reject'] and delta is not None
                                   and delta > additional['null_boundary'])
    original.update(g2_criterion_met=original['criterion_met'],
                    n14_criterion_met=additional['criterion_met'], n14_analysis_required=True)
    original['criterion_met'] = original['g2_criterion_met'] and original['n14_criterion_met']
    original['n14_decision_rule'] = 'G2 and N14 contrast-specific analyses must both satisfy their unchanged-family Holm criterion'
