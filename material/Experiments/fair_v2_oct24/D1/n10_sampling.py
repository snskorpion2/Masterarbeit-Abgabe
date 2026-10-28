"""N10's optional H1 budget-prefix estimator, pure in-memory and CPU only.

The original global six-row groups remain the sampling units.  A source uses
only its rows from each original group, never newly packed source-local groups.
``K / N`` is recorded as a sampling fraction, not proved to be an inclusion
probability.  A cost-dependent stopping rule needs separate design admission.
No input file, natural judgment, provider or source text is opened here.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json

import numpy as np

from . import inference as inf


PROTOCOL = 'C2-N10-budget-prefix-sampling-v1'
PARENTS = {'AS': 'AS_ORIGINAL', 'V1': 'V1_ORIGINAL'}
ARM_PARENT = {'AS': 'AS', 'AS_G': 'AS', 'V1': 'V1', 'V2': 'V1'}
NEGATIVE = {'contradicted', 'unsupported', 'mixed', 'not_in_source', 'not_supported'}
UNCLEAR = {'ambiguous', 'undetermined', 'not_assessable', 'unclear'}


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _mean(values):
    return float(np.mean(values)) if values and all(v is not None for v in values) else None


def active(bundle):
    """A complete census uses the existing G2 path, not N10."""
    sample = bundle.get('H1_sampling')
    if sample is None:
        return False
    need(type(sample) is dict and sample.get('protocol') == PROTOCOL,
         'Explicit N10 sampling protocol required')
    groups, selected = sample.get('groups'), sample.get('selected_group_ids')
    need(type(groups) is list and type(selected) is list,
         'N10 original groups and selected prefix required')
    ids = [g.get('group_id') if type(g) is dict else None for g in groups]
    need(all(type(value) is str and value for value in ids) and len(ids) == len(set(ids))
         and len(selected) <= len(ids) and selected == ids[:len(selected)],
         'N10 selected groups must be the unchanged original prefix, including failed groups')
    need(type(sample.get('budget_stopped')) is bool, 'Explicit N10 budget-stop state required')
    if len(selected) == len(groups):
        return False
    need(sample['budget_stopped'] is True, 'Partial H1 requires the explicit N10 budget stop')
    return True


def current_reference_rows(bundle, rows):
    """Keep the fixed C7/C4 roster but use only its final valid C2 references.

    The annotation key can predate the C2 run.  Its cached reference labels
    must not silently turn an unselected or technically failed case into a
    valid comparison. Human/Grok labels, IDs and sample weights are untouched.
    """
    from .native import support_label
    parents = {r['unit_id']: r for r in bundle['H1'] if r['cell'] in PARENTS.values()}
    sample = bundle['H1_sampling']
    groups = set(sample['selected_group_ids'])
    selected = {uid for group in sample['groups'] if group['group_id'] in groups for uid in group['unit_ids']}
    result = []
    for row in rows:
        need(row['unit_id'] in parents, 'N10 countercheck ID is outside the original C2 population')
        parent = parents[row['unit_id']]
        value = dict(row)
        status = parent['measurement_status'] if row['unit_id'] in selected else 'not_selected'
        value.update(reference_label=(support_label(parent.get('raw_code'), status)
                                      if status != 'not_selected' else None),
                     reference_status=status,
                     reference_from_final_C2=True)
        result.append(value)
    return result


def _cell_arm(cell):
    return cell.rsplit('_', 1)[0]


def _score(row):
    status, code = row.get('measurement_status'), row.get('raw_code')
    need(code is None or code in NEGATIVE | UNCLEAR | {'supported', 'failed', 'not_judged'},
         'Unrecognized N10 H1 raw code')
    if status != 'valid' or code in (None, 'failed', 'not_judged'):
        return (0, 0, 0, 1)
    if code == 'supported':
        return (1, 0, 0, 0)
    return (0, 1, 0, 0) if code in NEGATIVE else (0, 0, 1, 0)


def _stat(counts, **metadata):
    success, failure, unclear, technical = (int(x) for x in counts)
    n = success + failure + unclear + technical
    # Empty sampled cells keep [0,1], even if a filtered cell is empty.
    return {**metadata, 'estimate': success / n if n else None,
            'lower': success / n if n else 0.,
            'upper': (success + unclear + technical) / n if n else 1.,
            'denominator': n, 'success': success, 'resolved_failure': failure,
            'semantic_unclear': unclear, 'technical_missing': technical,
            'defined': bool(n), 'reason': None if n else 'no_sampled_occurrences',
            'missing_rate': (unclear + technical) / n if n else None,
            'technical_missing_rate': technical / n if n else None,
            'semantic_unclear_rate': unclear / n if n else None}


def aggregate_sources(rows, sources):
    """Equal weight for every planned source, never complete-case selection."""
    by_id = {r['source_id']: r for r in rows}
    need(len(by_id) == len(rows), 'Unique N10 source estimates required')
    selected = [by_id[source['source_id']] for source in sources]
    fields = ('estimate', 'lower', 'upper', 'missing_rate',
              'technical_missing_rate', 'semantic_unclear_rate')
    out = {field: _mean([r[field] for r in selected]) for field in fields}
    denominator = sum(r['denominator'] for r in selected)
    out.update(defined=out['estimate'] is not None, sources=selected,
               denominator=denominator, independent_source_count=len(selected),
               planned_draw_count=sum(len(s['draws']) for s in sources),
               undefined_denominators=sum(not r['defined'] for r in selected),
               undefined_denominator_states=dict(Counter(
                   r['reason'] for r in selected if not r['defined'])),
               aggregation='pooled sampled occurrences across draws within each source, then equal sources',
               pooled_missing_rate=(sum(r['semantic_unclear'] + r['technical_missing'] for r in selected)
                                    / denominator if denominator else None))
    out['missing_rate_over_10_percent'] = any(
        x is not None and x > .10 for x in (out['missing_rate'], out['pooled_missing_rate']))
    return out


@dataclass(frozen=True)
class SharedIndices:
    source_ids: tuple
    groups_by_source: tuple
    sources: np.ndarray
    groups: tuple
    draws: int
    seed: int

    @property
    def digest(self):
        digest = sha256(json.dumps([self.source_ids, self.groups_by_source],
                                   separators=(',', ':')).encode())
        digest.update(self.sources.tobytes())
        for matrix in self.groups:
            digest.update(str(matrix.shape).encode())
            digest.update(matrix.tobytes())
        return digest.hexdigest()


def shared_indices(source_ids, groups_by_source, *, indices=None,
                   draws=inf.BOOTSTRAP_DRAWS, seed=inf.BOOTSTRAP_SEED):
    """One ragged paired index matrix, including repeated source occurrences.

    Every occurrence of a resampled source receives its own inner group draw.
    The entire plan is made once and reused for all cells and H1 contrasts.
    The outer matrix is identical to G2's matrix.  The inner stream follows
    the outer G2 draws from the same PCG64 seed, not outcome-dependent seeds.
    """
    source_ids = tuple(source_ids)
    rosters = tuple(tuple(g) for g in groups_by_source)
    need(source_ids and len(source_ids) == len(set(source_ids)) == len(rosters),
         'N10 planned source order and group rosters required')
    need(all(len(g) == len(set(g)) for g in rosters), 'Repeated group within N10 source roster')
    outer = inf._indices(indices, len(source_ids), draws, seed).copy()
    rng = np.random.Generator(np.random.PCG64(seed))
    rng.integers(0, len(source_ids), size=(draws, len(source_ids)), dtype=np.int64)
    inner = []
    for source, roster in enumerate(rosters):
        count = int(np.count_nonzero(outer == source))
        dtype = np.uint8 if len(roster) <= 256 else np.uint16 if len(roster) <= 65536 else np.uint32
        matrix = (rng.integers(0, len(roster), size=(count, len(roster)), dtype=dtype)
                  if roster else np.empty((count, 0), dtype=dtype))
        matrix.flags.writeable = False
        inner.append(matrix)
    outer.flags.writeable = False
    return SharedIndices(source_ids, rosters, outer, tuple(inner), draws, seed)


def _validate(bundle, cells):
    sample = bundle['H1_sampling']
    groups, selected = sample['groups'], sample['selected_group_ids']
    need(groups and all(type(g) is dict and type(g.get('group_id')) is str
                        and type(g.get('unit_ids')) is list and len(g['unit_ids']) == 6 for g in groups),
         'Original N10 six-occurrence groups required, no source-local repacking')
    ids = [g['group_id'] for g in groups]
    units = [uid for group in groups for uid in group['unit_ids']]
    need(len(ids) == len(set(ids)) and all(type(uid) is str and uid for uid in units)
         and len(units) == len(set(units)), 'N10 groups must partition distinct original occurrences')
    need(selected == ids[:len(selected)] and len(selected) < len(ids),
         'N10 selected groups must be the unchanged original prefix, including failed groups')
    need(sample.get('global_permutation_before_packing') is True
         and sample.get('order_metadata_verified') is True,
         'N10 needs explicit externally verified order metadata')
    need(sample.get('approximate_design_approved') is True,
         'N10 approximate cost-stopped design must be explicitly approved, never inferred')
    sources = bundle['sources']
    source_ids = [s['source_id'] for s in sources]
    owners, originals = {}, {}
    rows = defaultdict(dict)
    for row in bundle['H1']:
        cell, uid = row['cell'], row['unit_id']
        need(cell in cells and row['source_id'] in source_ids, 'Foreign N10 source/cell')
        source = sources[source_ids.index(row['source_id'])]
        need(row['draw'] in source['draws'], 'Foreign N10 source draw')
        key = row['source_id'], row['draw'], cell
        need(uid not in rows[key], 'Duplicate N10 occurrence in a cell')
        rows[key][uid] = row
        if cell in PARENTS.values():
            need(uid not in originals, 'Original occurrence ID must identify exactly one parent')
            originals[uid] = row
            owners[uid] = (row['source_id'], row['draw'], _cell_arm(cell))
    need(set(originals) == set(units), 'N10 original group roster differs from the complete parent inventories')
    inventories = {(r['source_id'], r['draw'], r['cell']): r for r in bundle['H1_inventories']}
    need(len(inventories) == len(bundle['H1_inventories']), 'Duplicate N10 inventory metadata')
    planned = {(s['source_id'], draw, cell) for s in sources for draw in s['draws'] for cell in cells}
    need(set(inventories) == planned, 'N10 needs every original planned inventory explicitly')
    for key, inventory in inventories.items():
        need(inventory.get('completed') is True and inventory.get('occurrence_count') == len(rows[key]),
             'N10 needs full inventory membership, not only observed judgments')
        arm = _cell_arm(key[2])
        if arm in ('AS_G', 'V2'):
            need(inventory.get('positive_retained_membership_verified') is True,
                 'N10 filtered membership needs the existing C1 retained proof')
        for uid, row in rows[key].items():
            need(uid in originals and owners[uid] == (key[0], key[1], ARM_PARENT[arm]),
                 'N10 inherited occurrence changed its parent/source/draw')
            parent = originals[uid]
            need(all(row.get(field) == parent.get(field) for field in
                     ('raw_code', 'measurement_status', 'category')),
                 'N10 filtered/export views must inherit exactly the parent judgments')
    unit_groups = {uid: group['group_id'] for group in groups for uid in group['unit_ids']}
    selected_set = set(selected)
    source_rosters = []
    for sid in source_ids:
        present = {unit_groups[uid] for uid, owner in owners.items()
                   if owner[0] == sid and unit_groups[uid] in selected_set}
        source_rosters.append(tuple(g for g in selected if g in present))
    return rows, inventories, unit_groups, tuple(source_rosters)


def estimate(bundle, cells, *, matrix=None, indices=None, category=None,
             draws=inf.BOOTSTRAP_DRAWS, seed=inf.BOOTSTRAP_SEED):
    """Prepare all paired H1 cells once, without treating unselected rows as missing."""
    need(active(bundle), 'N10 is only used for a budget-stopped partial prefix')
    rows, inventories, unit_groups, rosters = _validate(bundle, cells)
    sources, sample = bundle['sources'], bundle['H1_sampling']
    source_ids = tuple(s['source_id'] for s in sources)
    if matrix is None:
        matrix = shared_indices(source_ids, rosters, indices=indices, draws=draws, seed=seed)
    need(isinstance(matrix, SharedIndices) and matrix.source_ids == source_ids
         and matrix.groups_by_source == rosters and matrix.draws == draws and matrix.seed == seed,
         'N10 requires the same exact shared source/group index matrix')
    inf._indices(matrix.sources, len(sources), draws, seed)
    need(len(matrix.groups) == len(sources), 'N10 inner matrix must include every planned source')
    counts = [np.zeros((len(roster), len(cells), 4), dtype=np.int64) for roster in rosters]
    draw_counts = defaultdict(lambda: np.zeros(4, dtype=np.int64))
    for si, source in enumerate(sources):
        group_index = {g: j for j, g in enumerate(rosters[si])}
        for draw in source['draws']:
            for ci, cell in enumerate(cells):
                for uid, row in rows[source['source_id'], draw, cell].items():
                    group = unit_groups[uid]
                    if group not in group_index or category is not None and row['category'] != category:
                        continue
                    value = _score(row)
                    counts[si][group_index[group], ci] += value
                    draw_counts[source['source_id'], draw, cell] += value
    by_draw, aggregates = defaultdict(list), {}
    for ci, cell in enumerate(cells):
        per_source = []
        for si, source in enumerate(sources):
            sid = source['source_id']
            for draw in source['draws']:
                by_draw[cell].append(_stat(draw_counts[sid, draw, cell],
                                           source_id=sid, draw=draw, cell=cell, category=category))
            item = _stat(counts[si][:, ci, :].sum(axis=0), source_id=sid, cell=cell,
                         planned_draws=len(source['draws']), cohort=source['cohort'], family=source['family'])
            full_n = sum(inventories[sid, draw, cell]['occurrence_count'] for draw in source['draws'])
            item.update(original_inventory_denominator=full_n,
                        not_selected_occurrences=full_n - item['denominator'] if category is None else None,
                        selected_original_group_ids=list(rosters[si]))
            per_source.append(item)
        aggregates[cell] = aggregate_sources(per_source, sources)
    replicated = {field: np.zeros((draws, len(cells)), dtype=float)
                  for field in ('estimate', 'lower', 'upper')}
    defined = np.ones((draws, len(cells)), dtype=bool)
    for si, roster in enumerate(rosters):
        positions = np.argwhere(matrix.sources == si)
        selected = matrix.groups[si]
        need(selected.shape == (len(positions), len(roster)) and np.issubdtype(selected.dtype, np.integer)
             and np.all(selected >= 0) and np.all(selected < len(roster)),
             'N10 inner matrix differs from the source occurrences')
        weights = np.zeros((len(positions), len(roster)), dtype=np.uint32)
        if roster:
            np.add.at(weights, (np.arange(len(positions))[:, None], selected), 1)
        sampled = (weights @ counts[si].reshape(len(roster), len(cells) * 4)
                   if roster else np.zeros((len(positions), len(cells) * 4), dtype=np.int64))
        sampled = sampled.reshape(len(positions), len(cells), 4)
        denominator = sampled.sum(axis=2)
        numerator = sampled[:, :, 0]
        valid = denominator > 0
        values = np.divide(numerator, denominator, out=np.zeros_like(numerator, dtype=float), where=valid)
        upper = np.divide(numerator + sampled[:, :, 2] + sampled[:, :, 3], denominator,
                          out=np.ones_like(numerator, dtype=float), where=valid)
        index = positions[:, 0]
        np.add.at(replicated['estimate'], index, values)
        np.add.at(replicated['lower'], index, values)
        np.add.at(replicated['upper'], index, upper)
        np.logical_and.at(defined, index, valid)
    for field in replicated:
        replicated[field] /= len(sources)
    replicated['estimate'][~defined] = np.nan
    diagnostics = {}
    original = [r for r in bundle['H1'] if r['cell'] in PARENTS.values()]
    selected_groups = set(sample['selected_group_ids'])
    for dimension, getter in (
            ('source', lambda r: r['source_id']),
            ('arm', lambda r: _cell_arm(r['cell'])),
            ('category', lambda r: r['category'])):
        population = Counter(getter(row) for row in original)
        chosen = Counter(getter(row) for row in original if unit_groups[row['unit_id']] in selected_groups)
        n_chosen = sum(chosen.values())
        diagnostics[dimension] = [{'level': value, 'population_count': population[value],
            'selected_count': chosen[value], 'population_fraction': population[value] / len(original),
            'selected_fraction': chosen[value] / n_chosen if n_chosen else None,
            'sampling_fraction': chosen[value] / population[value]} for value in sorted(population)]
    return SampleEstimate(cells=tuple(cells), sources=sources, aggregates=aggregates,
                          by_draw=dict(by_draw), replicates=replicated, matrix=matrix,
                          sampling_info={
                              'protocol': PROTOCOL, 'selected_groups': len(sample['selected_group_ids']),
                              'population_groups': len(sample['groups']),
                              'sampling_fraction': len(sample['selected_group_ids']) / len(sample['groups']),
                              'approximate_inclusion_probability': len(sample['selected_group_ids']) / len(sample['groups']),
                              'sampling_fraction_is_proven_inclusion_probability': False,
                              'approximate_design_approved': True,
                              'informative_cost_stopping_possible': True,
                              'inclusion_fraction_is_an_approximation': True,
                              'not_selected_is_missing': False, 'finite_population_correction': False,
                              'original_global_groups_preserved': True,
                              'selection_distributions': diagnostics,
                              'selection_distributions_establish_quality_or_exact_inclusion': False,
                              'source_group_matrix_sha256': matrix.digest})


@dataclass
class SampleEstimate:
    cells: tuple
    sources: list
    aggregates: dict
    by_draw: dict
    replicates: dict
    matrix: SharedIndices
    sampling_info: dict

    def contrast(self, control, treatment, *, null_boundary=0., return_samples=False):
        ci, ti = self.cells.index(control), self.cells.index(treatment)
        left, right = self.aggregates[control], self.aggregates[treatment]
        complete = left['estimate'] is not None and right['estimate'] is not None
        delta = right['estimate'] - left['estimate'] if complete else None
        missing = (None if complete else 'undefined_planned_source_pair')
        result = inf.bootstrap_from_replicates(
            delta, self.replicates['estimate'][:, ti] - self.replicates['estimate'][:, ci],
            cluster_count=len(self.sources), null_boundary=null_boundary,
            lower_replicates=self.replicates['lower'][:, ti] - self.replicates['upper'][:, ci],
            upper_replicates=self.replicates['upper'][:, ti] - self.replicates['lower'][:, ci],
            draws=self.matrix.draws, seed=self.matrix.seed, missing_reason=missing,
            return_samples=return_samples)
        result.update(control_mean=left['estimate'], treatment_mean=right['estimate'],
                      aggregation=left['aggregation'], N10_budget_prefix=True,
                      source_group_matrix_sha256=self.matrix.digest,
                      approximate_cost_stopped_sampling=True,
                      exact_inclusion_probabilities_established=False,
                      delta_identification_bounds={'lower': right['lower'] - left['upper'],
                                                   'upper': right['upper'] - left['lower']})
        return result

    def score_interval(self, cell):
        values = self.replicates['estimate'][:, self.cells.index(cell)]
        return inf._interval(values)
