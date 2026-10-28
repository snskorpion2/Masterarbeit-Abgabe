"""X3: nachträglich, explorativ; inherited H1 with unchanged D1/N10 helpers.

Internal D1 codec aliases are local to this adapter. They never replace the
published AS+G/V2 memberships, scores, hypotheses, or decisions.
"""
from collections import Counter, defaultdict
from copy import deepcopy

import numpy as np

from Experiments.fair_comparison_oct23_v1.graph_contract import digest
from Experiments.fair_v2_oct24.D1 import inference as inf
from Experiments.fair_v2_oct24.D1 import n10_sampling as n10


CLASSIFICATION = 'nachträglich, explorativ'
CELLS = ('AS_ORIGINAL', 'AS_G_ORIGINAL', 'V1_ORIGINAL', 'V2_ORIGINAL')
PARENT_CELL = {'AS': 'AS_ORIGINAL', 'V1': 'V1_ORIGINAL'}
FILTER_CELL = {'AS': 'AS_G_ORIGINAL', 'V1': 'V2_ORIGINAL'}
VARIANT_NAMES = {'AS': 'AS+G(VV)', 'V1': 'V1+G(VV)'}
FULL_NAMES = {'AS': 'AS+G', 'V1': 'V2'}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def validate_memberships(rows, sources, memberships):
    """Bind actual new projection membership to all unchanged parent C2 labels."""
    need(type(memberships) is list, 'X3_PARENT_MEMBERSHIP_LIST_REQUIRED')
    expected = {(s['source_id'], draw, arm) for s in sources for draw in s['draws']
                for arm in PARENT_CELL}
    by_key, seen_parent, seen_global = {}, set(), set()
    grouped = defaultdict(dict)
    for row in rows:
        key = row['source_id'], row['draw'], row['cell']
        need(row['unit_id'] not in grouped[key], 'X3_DUPLICATE_C2_OCCURRENCE')
        grouped[key][row['unit_id']] = row
    for member in memberships:
        key = member['source_id'], member['draw'], member['arm']
        pid = member['parent_id']
        need(key in expected and key not in by_key and pid not in seen_parent,
             'X3_UNIQUE_PLANNED_PARENT_REQUIRED')
        original = member['original_unit_ids']
        need(type(original) is list and len(set(original)) == len(original)
             and all(type(uid) is str and uid for uid in original)
             and not seen_global.intersection(original), 'X3_DISTINCT_GLOBAL_ORIGINAL_IDS_REQUIRED')
        parent = grouped[key[:2] + (PARENT_CELL[key[2]],)]
        need(set(parent) == set(original), 'X3_ORIGINAL_C2_PROJECTION_MEMBERSHIP_DIFFERS')
        categories = member['categoriesByUnitId']
        need(set(categories) == set(original)
             and all(categories[uid] == parent[uid]['category'] for uid in original),
             'X3_ORIGINAL_CATEGORY_DIFFERS')
        for row in parent.values():
            need(row.get('parent_id') in (None, pid), 'X3_ORIGINAL_PARENT_ID_DIFFERS')
        hashes = member.get('original_values_sha256_by_unit_id')
        if hashes is not None:
            need(set(hashes) == set(original) and all(
                'value' in parent[uid] and digest(parent[uid]['value']) == hashes[uid]
                for uid in original), 'X3_ORIGINAL_NATIVE_VALUE_DIFFERS')
        sets = {}
        for field in ('full_removed_ids', 'vv_removed_ids', 'ee_restored_ids', 'kept_ids'):
            value = member[field]
            need(type(value) is list and len(value) == len(set(value))
                 and set(value) <= set(original), 'X3_VALID_DISTINCT_MEMBERSHIP_IDS_REQUIRED')
            sets[field] = set(value)
        removed, vv, ee = (sets[k] for k in ('full_removed_ids', 'vv_removed_ids', 'ee_restored_ids'))
        need(vv == {uid for uid in removed if categories[uid] == 'VV'}
             and ee == {uid for uid in removed if categories[uid] == 'EE'}
             and not vv.intersection(ee) and vv | ee == removed,
             'X3_ONLY_PREVIOUS_VV_REMOVALS_AND_EE_RESTORATIONS_ALLOWED')
        need(member['kept_ids'] == [uid for uid in original if uid not in vv],
             'X3_NEW_MEMBERSHIP_MUST_RETAIN_ALL_EE_EV_IN_ORIGINAL_ORDER')
        full_kept = [uid for uid in original if uid not in removed]
        need('full_kept_ids' not in member or member['full_kept_ids'] == full_kept,
             'X3_ORIGINAL_GUARD_RETAINED_MEMBERSHIP_DIFFERS')
        old_filtered = grouped[key[:2] + (FILTER_CELL[key[2]],)]
        need(set(old_filtered) == set(full_kept), 'X3_C2_EXISTING_GUARD_MEMBERSHIP_DIFFERS')
        fields = ('category', 'raw_code', 'measurement_status', 'parent_id', 'value',
                  'selection_status', 'label', 'unknown_execution')
        need(all(all(row.get(f) == parent[uid].get(f) for f in fields)
                 for uid, row in old_filtered.items()), 'X3_EXISTING_C2_INHERITANCE_DIFFERS')
        by_key[key] = member
        seen_parent.add(pid)
        seen_global.update(original)
    need(set(by_key) == expected, 'X3_COMPLETE_PLANNED_PARENT_POPULATION_REQUIRED')
    return by_key, grouped


def prepare_bundles(rows, inventories, sources, sampling, memberships):
    """Two separate, explicitly named internal codec views; original stays intact."""
    selected = [deepcopy(r) for r in rows if r['cell'] in CELLS]
    mapped, grouped = validate_memberships(selected, sources, memberships)
    reference_inventories = [deepcopy(r) for r in inventories if r['cell'] in CELLS]
    for inv in reference_inventories:
        if inv['cell'] in FILTER_CELL.values():
            inv['positive_retained_membership_verified'] = True
            inv['membership_scope'] = 'existing C1 membership, matched to saved original removal IDs'
    reference = {'sources': deepcopy(sources), 'cells': list(CELLS), 'H1': selected,
                 'H1_inventories': reference_inventories, 'H1_sampling': deepcopy(sampling)}
    variant_rows, variant_inventories = [], []
    for source in sources:
        for draw in source['draws']:
            for arm, original_cell in PARENT_CELL.items():
                parent_rows = grouped[source['source_id'], draw, original_cell]
                member = mapped[source['source_id'], draw, arm]
                for cell in (original_cell, FILTER_CELL[arm]):
                    ids = member['original_unit_ids'] if cell == original_cell else member['kept_ids']
                    variant_rows.extend({**deepcopy(parent_rows[uid]), 'cell': cell} for uid in ids)
                    variant_inventories.append({'source_id': source['source_id'], 'draw': draw,
                        'cell': cell, 'completed': True, 'occurrence_count': len(ids),
                        'parent_id': member['parent_id'],
                        'positive_retained_membership_verified': True,
                        'membership_scope': 'new X3 VV-only project_subset proof; local codec alias'})
    variant = {'sources': deepcopy(sources), 'cells': list(CELLS), 'H1': variant_rows,
               'H1_inventories': variant_inventories, 'H1_sampling': deepcopy(sampling)}
    reference['X3_membership_sha256'] = variant['X3_membership_sha256'] = digest(memberships)
    return reference, variant


def removal_summary(memberships, arm, kind):
    originals = Counter()
    removed = Counter()
    restored = 0
    for row in memberships:
        if row['arm'] != arm:
            continue
        originals.update(row['categoriesByUnitId'].values())
        ids = (row['full_removed_ids'] if kind == 'full' else
               row['vv_removed_ids'] if kind == 'vv_only' else [])
        removed.update(row['categoriesByUnitId'][uid] for uid in ids)
        if kind == 'vv_only':
            restored += len(row['ee_restored_ids'])
    n, deleted = sum(originals.values()), sum(removed.values())
    return {'original_native_occurrences': n,
            'original_by_type': {t: originals[t] for t in ('EE', 'EV', 'VV')},
            'removed_occurrences': deleted,
            'removed_by_type': {t: removed[t] for t in ('EE', 'EV', 'VV')},
            'removed_share_of_all_original_occurrences': deleted / n if n else None,
            'removed_share_of_original_VV': removed['VV'] / originals['VV'] if originals['VV'] else None,
            'EE_removals_reversed': restored}


def _score(estimate, cell):
    row = estimate.aggregates[cell]
    sources = row['sources']
    return {'estimate': row['estimate'], 'ci95': estimate.score_interval(cell),
            'identification_bounds': {'lower': row['lower'], 'upper': row['upper']},
            'independent_sources': row['independent_source_count'],
            'planned_source_draw_units': row['planned_draw_count'],
            'selected_occurrences': row['denominator'],
            'not_selected_occurrences': sum(r['not_selected_occurrences'] for r in sources),
            'successes_in_selected_occurrences': sum(r['success'] for r in sources),
            'technical_missing_selected': sum(r['technical_missing'] for r in sources),
            'semantic_unclear_selected': sum(r['semantic_unclear'] for r in sources),
            'undefined_source_denominators': row['undefined_denominators'],
            'aggregation': row['aggregation'],
            'CI_scope': 'marginal two-sided 95% percentile, paired source/original-group bootstrap',
            'N10_exact_equal_inclusion_established': False}


def descriptive_difference(treatment, treatment_cell, control, control_cell):
    """Percentile interval only. In particular, never call SampleEstimate.contrast."""
    need(treatment.matrix is control.matrix, 'X3_SAME_BOOTSTRAP_MATRIX_OBJECT_REQUIRED')
    left, right = control.aggregates[control_cell]['estimate'], treatment.aggregates[treatment_cell]['estimate']
    point = right - left if left is not None and right is not None else None
    samples = (treatment.replicates['estimate'][:, treatment.cells.index(treatment_cell)]
               - control.replicates['estimate'][:, control.cells.index(control_cell)])
    return {'point_difference': point, 'ci95': inf._interval(samples) if point is not None else None,
            'classification': CLASSIFICATION, 'statistical_test_performed': False}


def estimate_h1(reference, variant, memberships, *, matrix=None,
                draws=inf.BOOTSTRAP_DRAWS, seed=inf.BOOTSTRAP_SEED,
                expected_matrix_sha256=None):
    need(reference.get('X3_membership_sha256') == variant.get('X3_membership_sha256')
         == digest(memberships), 'X3_PREPARED_MEMBERSHIP_BINDING_CHANGED')
    full = n10.estimate(reference, CELLS, matrix=matrix, draws=draws, seed=seed, category=None)
    vv = n10.estimate(variant, CELLS, matrix=full.matrix, draws=draws, seed=seed, category=None)
    if expected_matrix_sha256 is not None:
        need(full.matrix.digest == expected_matrix_sha256, 'X3_ORIGINAL_D1_MATRIX_BINDING_DIFFERS')
    result = {}
    for arm in PARENT_CELL:
        parent, filtered = PARENT_CELL[arm], FILTER_CELL[arm]
        for name, computed, cell, kind in (
                (arm, full, parent, 'none'),
                (FULL_NAMES[arm], full, filtered, 'full'),
                (VARIANT_NAMES[arm], vv, filtered, 'vv_only')):
            score = _score(computed, cell)
            row = {'classification': CLASSIFICATION, 'source_parent_arm': arm,
                   'filter': kind, 'H1': score, 'removals': removal_summary(memberships, arm, kind)}
            row['difference_from_original_parent'] = (
                descriptive_difference(computed, cell, full, parent) if kind != 'none' else None)
            row['difference_from_full_filter'] = (
                descriptive_difference(computed, cell, full, filtered) if kind == 'vv_only' else None)
            if kind == 'vv_only':
                row['H2'] = {'status': 'nicht bewertet; nicht geschätzt', 'estimate': None,
                             'ci95': None, 'classification': CLASSIFICATION}
            result[name] = row
        # The unchanged parent is a direct invariance check, not another estimate choice.
        need(full.aggregates[parent] == vv.aggregates[parent]
             and np.array_equal(full.replicates['estimate'][:, full.cells.index(parent)],
                                vv.replicates['estimate'][:, vv.cells.index(parent)], equal_nan=True),
             'X3_UNFILTERED_PARENT_SCORE_OR_REPLICATES_CHANGED')
    return {'classification': CLASSIFICATION, 'post_hoc': True, 'hypothesis_generating': True,
            'inferential_test_performed': False, 'Holm_slots_added': 0,
            'included_in_main_tests_or_overall_judgment': False,
            'scope': {'sources': len(reference['sources']),
                      'source_draw_pairs': sum(len(s['draws']) for s in reference['sources']),
                      'original_parents': len(memberships)},
            'bootstrap': {'draws': draws, 'seed': seed, 'rng': 'PCG64',
                          'source_group_matrix_sha256': full.matrix.digest,
                          'one_shared_matrix_object': full.matrix is vv.matrix,
                          'hypothesis_tests_called': False},
            'sampling': {k: full.sampling_info[k] for k in
                         ('selected_groups', 'population_groups', 'sampling_fraction',
                          'sampling_fraction_is_proven_inclusion_probability', 'not_selected_is_missing',
                          'informative_cost_stopping_possible', 'finite_population_correction',
                          'original_global_groups_preserved')},
            'local_codec_aliases': {'AS_G_ORIGINAL': VARIANT_NAMES['AS'],
                                   'V2_ORIGINAL': VARIANT_NAMES['V1'],
                                   'existing_main_cells_overwritten': False},
            'cells': result}
