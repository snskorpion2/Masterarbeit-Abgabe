"""Descriptive second-evaluator direction on the fixed random C4 core.

Input is D1's normalized in-memory bundle, never a private file. Each sampled
original global unit_id is joined to positive retained inventories. ORIGINAL
and ROW are dependent views, not independent replications. Provided original
sampling weights are used unchanged. The estimator is a Hajek ratio: the HT
weighted supported sampled-retained total divided by the HT weighted sampled-
retained total, including unknown judgments in the latter. Missing labels give
identification bounds. This is not the primary H1 estimator or a new test.
"""
from collections import Counter, defaultdict
import math


def _need(condition,message):
    if not condition:
        raise ValueError(message)


def _weight(value):
    return type(value) in (int,float) and math.isfinite(value) and value>0


def _average(rows,field):
    values = [row[field] for row in rows]
    return sum(values)/len(values) if values and all(value is not None for value in values) else None


def _difference(treatment,control,field):
    left,right = treatment[field],control[field]
    return left-right if left is not None and right is not None else None


def summarize(bundle, *, core_fraction=.15):
    """Report source-equal V2_ORIGINAL minus AS_ORIGINAL, without inference.

    An unknown planned inventory, absent positive C1 membership proof, unknown
    sampling weight, or empty sampled-retained denominator stays undefined.
    Undefined planned draws/sources are never removed from the final mean.
    Category coverage is diagnostic, not a retrospectively selected sample.
    """
    _need(type(core_fraction) in (int, float) and math.isfinite(core_fraction)
          and 0 < core_fraction <= 1, 'Explicit finite core fraction within (0,1] required')
    sources,cells = bundle['sources'],bundle['cells']
    source_lookup = {row['source_id']:row for row in sources}
    _need(len(source_lookup)==len(sources) and bool(sources), 'Distinct planned sources required')
    planned = {(s['source_id'],draw,cell) for s in sources for draw in s['draws'] for cell in cells}
    inventories = {}
    for inventory in bundle['H1_inventories']:
        key = inventory['source_id'],inventory['draw'],inventory['cell']
        _need(key in planned and key not in inventories, 'Foreign/duplicate Grok inventory')
        inventories[key] = inventory
    _need(set(inventories)==planned, 'Every planned Grok inventory must remain explicit')
    retained = defaultdict(dict)
    for row in bundle['H1']:
        key = row['source_id'],row['draw'],row['cell']
        _need(key in planned and row['unit_id'] not in retained[key], 'Foreign/duplicate retained occurrence')
        retained[key][row['unit_id']] = row
    originals = {}
    for key,rows in retained.items():
        if key[2] in ('AS_ORIGINAL','V1_ORIGINAL'):
            for uid,row in rows.items():
                _need(uid not in originals, 'Original global unit_id must be unique')
                originals[uid] = row
    for sid,draw,cell in planned:
        inventory = inventories[sid,draw,cell]
        count = inventory['occurrence_count']
        _need(type(inventory['completed']) is bool, 'Explicit inventory completion required')
        _need((type(count) is int and count>=0 and count==len(retained[sid,draw,cell]))
              if inventory['completed'] else count is None and not retained[sid,draw,cell],
              'Retained census count/status mismatch')
        parent_arm = 'AS' if cell.startswith('AS') else 'V1'
        for uid,row in retained[sid,draw,cell].items():
            original = originals.get(uid)
            _need(original is not None and original['source_id']==sid and original['draw']==draw
                  and original['cell']==parent_arm+'_ORIGINAL'
                  and original['category']==row['category'], 'Retained occurrence is not its bound original')
        suffix = '_ORIGINAL' if cell.endswith('_ROW') else '_ROW'
        arm = cell.rsplit('_',1)[0]
        partner = sid,draw,arm+suffix
        _need(partner in inventories and inventory['completed']==inventories[partner]['completed']
              and count==inventories[partner]['occurrence_count']
              and list(retained[sid,draw,cell])==list(retained[partner]), 'Dependent export views disagree')
    all_reviewed = {}
    for rating in bundle['agreement'].get('grok',[]):
        uid = rating['unit_id']
        _need(uid in originals and uid not in all_reviewed, 'Grok requires unique original global IDs')
        _need(type(rating['in_base_sample']) is bool and type(rating['in_removal_panel']) is bool,
              'Explicit random-core/removal flags required')
        _need(rating['label'] in ('supported','not_supported','unclear',None) and
              rating['reference_label'] in ('supported','not_supported','unclear',None), 'Unknown nominal support label')
        all_reviewed[uid] = rating
    core = {uid:row for uid,row in all_reviewed.items() if row['in_base_sample']}
    augmentation = [row for row in all_reviewed.values() if not row['in_base_sample'] and row['in_removal_panel']]
    core_design = {}
    for source in sources:
        for draw in source['draws']:
            for arm in ('AS','V1'):
                base = retained[source['source_id'],draw,arm+'_ORIGINAL']
                for category in ('EE','EV','VV'):
                    group = [uid for uid,row in base.items() if row['category']==category]
                    sampled = [uid for uid in group if uid in core]
                    core_design[source['source_id'],draw,arm,category] = {
                        'original_census_count':len(group),
                        'planned_core_count':math.ceil(core_fraction*len(group)),
                        'actual_core_count':len(sampled)}
    draws = []
    for source in sources:
        sid = source['source_id']
        for draw in source['draws']:
            for cell in cells:
                inventory = inventories[sid,draw,cell]
                census = retained[sid,draw,cell]
                sampled = [core[uid] for uid in census if uid in core]
                unknown_weights = sum(not _weight(row.get('weight')) for row in sampled)
                category_census = Counter(row['category'] for row in census.values())
                category_sample = Counter(originals[row['unit_id']]['category'] for row in sampled)
                original_arm = 'AS' if cell.startswith('AS') else 'V1'
                design = {category:core_design[sid,draw,original_arm,category] for category in ('EE','EV','VV')}
                core_complete = all(d['actual_core_count']==d['planned_core_count'] for d in design.values())
                weight_mismatches = sum(_weight(row.get('weight')) and not math.isclose(row['weight'],
                    design[originals[row['unit_id']]['category']]['original_census_count']/
                    design[originals[row['unit_id']]['category']]['actual_core_count'],rel_tol=1e-12,abs_tol=1e-12)
                    for row in sampled)
                unknown_labels = sum(row['label'] in (None,'unclear') for row in sampled)
                reason = None
                if not inventory['completed']:
                    reason = 'unknown_planned_inventory'
                elif cell.startswith(('AS_G_','V2_')) and inventory.get('positive_retained_membership_verified') is not True:
                    reason = 'positive_C1_retained_membership_not_verified'
                elif not core_complete:
                    reason = ('fixed_15_percent_random_core_roster_incomplete_or_changed' if core_fraction == .15
                              else 'fixed_random_core_roster_incomplete_or_changed')
                elif inventory['occurrence_count']==0:
                    reason = 'empty_retained_inventory'
                elif not sampled:
                    reason = 'no_sampled_retained_occurrences'
                elif unknown_weights:
                    reason = 'unknown_original_sampling_weights'
                elif weight_mismatches:
                    reason = 'provided_weight_disagrees_with_original_core_design'
                denominator = sum(row['weight'] for row in sampled) if not unknown_weights else None
                supported = sum(row['weight'] for row in sampled if row['label']=='supported') if denominator is not None else None
                unknown = sum(row['weight'] for row in sampled if row['label'] in (None,'unclear')) if denominator is not None else None
                lower = supported/denominator if reason is None else None
                upper = (supported+unknown)/denominator if reason is None else None
                draws.append({'source_id':sid,'draw':draw,'cell':cell,
                    'retained_inventory_count':inventory['occurrence_count'],
                    'sampled_retained_count':len(sampled),'unknown_label_count':unknown_labels,
                    'technical_missing_label_count':sum(row['label'] is None for row in sampled),
                    'semantic_unclear_label_count':sum(row['label']=='unclear' for row in sampled),
                    'unknown_weight_count':unknown_weights,'weighted_sampled_retained_total':denominator,
                    'provided_weight_mismatch_count':weight_mismatches,
                    'original_random_core_design':design,'original_random_core_roster_complete':core_complete,
                    'HT_supported_sampled_retained_total':supported,'HT_unknown_sampled_retained_total':unknown,
                    'category_coverage':{category:{'retained_census':category_census[category],
                        'sampled_retained':category_sample[category]} for category in ('EE','EV','VV')},
                    'retained_categories_without_a_sample':[category for category in ('EE','EV','VV')
                        if category_census[category]>0 and category_sample[category]==0],
                    'point':lower,'lower':lower,'upper':upper,'undefined_reason':reason})
    source_rows = []
    for source in sources:
        for cell in cells:
            rows = [row for row in draws if row['source_id']==source['source_id'] and row['cell']==cell]
            source_rows.append({'source_id':source['source_id'],'cell':cell,'planned_draw_count':len(rows),
                'defined_draw_count':sum(row['point'] is not None for row in rows),
                **{field:_average(rows,field) for field in ('point','lower','upper')}})
    summaries = []
    for cell in cells:
        rows = [row for row in source_rows if row['cell']==cell]
        summaries.append({'cell':cell,'planned_source_count':len(rows),
            'defined_source_count':sum(row['point'] is not None for row in rows),
            **{field:_average(rows,field) for field in ('point','lower','upper')}})
    lookup = {row['cell']:row for row in summaries}
    _need({'AS_ORIGINAL','V2_ORIGINAL'}<=set(lookup), 'Fixed G2 second-evaluator contrast required')
    control,treatment = lookup['AS_ORIGINAL'],lookup['V2_ORIGINAL']
    difference = _difference(treatment,control,'point')
    lower = treatment['lower']-control['upper'] if treatment['lower'] is not None and control['upper'] is not None else None
    upper = treatment['upper']-control['lower'] if treatment['upper'] is not None and control['lower'] is not None else None
    paired = [row for row in core.values() if row['label'] is not None and row['reference_label'] is not None]
    return {'protocol':'D1-Grok-random-core-descriptive-direction-v1','synthetic':bundle.get('synthetic'),
        'random_core_fraction':core_fraction,
        'estimator':'Hajek ratio of HT sampled-retained support total to HT sampled-retained total',
        'point_rule':'Symmetric conservative point equals lower bound; unclear and technical missing are separate unknowns.',
        'weight_origin':'Provided original random-core inclusion weights, unchanged; never removal augmentation weights.',
        'aggregation_order':'draw ratios within each planned source, then equally weighted sources',
        'primary_H1_replacement':False,'inferential_tests_performed':False,'export_views_dependent':True,
        'draws':draws,'sources':source_rows,'cells':summaries,
        'direction':{'contrast':'V2_ORIGINAL - AS_ORIGINAL','point_difference':difference,
            'lower':lower,'upper':upper,
            'conservative_direction':'undefined' if difference is None else 'positive' if difference>0 else 'negative' if difference<0 else 'zero',
            'direction_identified_by_bounds':'undefined' if lower is None else 'positive' if lower>0 else 'negative' if upper<0 else 'unresolved'},
        'random_core':{'unique_occurrences':len(core),'original_occurrence_census':len(originals),
            'paired_nominal_labels':len(paired),
            'nominal_disagreements':sum(row['label']!=row['reference_label'] for row in paired),
            'C2_technical_missing_labels':sum(row['reference_label'] is None for row in core.values()),
            'Grok_technical_missing_labels':sum(row['label'] is None for row in core.values()),
            'C2_semantic_unclear_labels':sum(row['reference_label']=='unclear' for row in core.values()),
            'Grok_semantic_unclear_labels':sum(row['label']=='unclear' for row in core.values()),
            'unknown_sampling_weights':sum(not _weight(row.get('weight')) for row in core.values())},
        'removal_augmentation':{'unique_augmentation_only_occurrences':len(augmentation),
            'is_population_representative':False,'included_in_direction_estimate':False}}
