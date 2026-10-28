"""Small exact-value synthetic tests, with no private input or provider IO."""
from copy import deepcopy

from Experiments.fair_v2_oct24.D1 import grok_sensitivity as g


CELLS = ['AS_ORIGINAL','AS_ROW','AS_G_ORIGINAL','AS_G_ROW',
         'V1_ORIGINAL','V1_ROW','V2_ORIGINAL','V2_ROW']


def _bundle(draws_by_source=None):
    design = draws_by_source or {'SYNTHETIC-A':['draw_1']}
    bundle = {'synthetic':True,'sources':[{'source_id':sid,'draws':draws} for sid,draws in design.items()],
              'cells':CELLS,'H1':[],'H1_inventories':[],'agreement':{'grok':[]}}
    for sid,draws in design.items():
        for draw in draws:
            originals = {}
            for arm,categories in (('AS',['EE','EV','EV','EV']),('V1',['EE','EE','EV','EV'])):
                originals[arm] = [{'source_id':sid,'draw':draw,'cell':arm+'_ORIGINAL',
                    'unit_id':sid+'-'+draw+'-'+arm+'-'+str(i),'category':category}
                    for i,category in enumerate(categories)]
            for cell in CELLS:
                arm = 'AS' if cell.startswith('AS') else 'V1'
                selected = originals[arm] if not cell.startswith('V2_') else originals['V1'][:2]
                bundle['H1'].extend({**row,'cell':cell} for row in selected)
                bundle['H1_inventories'].append({'source_id':sid,'draw':draw,'cell':cell,
                    'occurrence_count':len(selected),'completed':True,
                    'positive_retained_membership_verified':True})
            for arm,index,label,reference,weight in (
                ('AS',0,'supported','supported',1),('AS',1,'not_supported','not_supported',3),
                ('V1',0,'supported','not_supported',2),('V1',2,'unclear',None,2)):
                bundle['agreement']['grok'].append({'unit_id':originals[arm][index]['unit_id'],
                    'label':label,'reference_label':reference,'in_base_sample':True,
                    'in_removal_panel':False,'weight':weight})
            bundle['agreement']['grok'].append({'unit_id':originals['AS'][2]['unit_id'],
                'label':'supported','reference_label':'not_supported','in_base_sample':False,
                'in_removal_panel':True,'weight':None})
    return bundle


def test_known_hajek_ratio_direction_unknowns_and_nonrepresentative_augmentation():
    bundle = _bundle()
    before = deepcopy(bundle)
    result = g.summarize(bundle)
    assert bundle==before
    cells = {row['cell']:row for row in result['cells']}
    assert cells['AS_ORIGINAL']['point']==.25  # (1*1 + 3*0)/(1+3).
    assert cells['V1_ORIGINAL']['point']==.5 and cells['V1_ORIGINAL']['upper']==1
    assert cells['V2_ORIGINAL']['point']==cells['V2_ROW']['point']==1
    assert result['direction']['point_difference']==.75
    assert result['direction']['lower']==result['direction']['upper']==.75
    assert result['direction']['direction_identified_by_bounds']=='positive'
    assert result['random_core']['unique_occurrences']==4
    assert result['random_core']['paired_nominal_labels']==3
    assert result['random_core']['nominal_disagreements']==1
    assert result['random_core']['C2_technical_missing_labels']==1
    assert result['random_core']['Grok_semantic_unclear_labels']==1
    assert result['removal_augmentation']=={'unique_augmentation_only_occurrences':1,
        'is_population_representative':False,'included_in_direction_estimate':False}
    assert result['inferential_tests_performed'] is False
    assert result['primary_H1_replacement'] is False


def test_planned_draws_then_equal_sources_and_unavailable_draw_never_dropped():
    bundle = _bundle({'SYNTHETIC-A':['draw_1','draw_2'],'SYNTHETIC-B':['draw_1']})
    for rating in bundle['agreement']['grok']:
        if '-AS-' in rating['unit_id'] and rating['in_base_sample']:
            rating['label']='not_supported'
        if '-V1-0' in rating['unit_id']:
            rating['label']='not_supported' if 'SYNTHETIC-A-draw_1-' in rating['unit_id'] else 'supported'
    result = g.summarize(bundle)
    assert result['direction']['point_difference']==.75  # mean(mean(0,1),1), not pooled 2/3.
    selected = lambda row: row['source_id']=='SYNTHETIC-A' and row['draw']=='draw_2' and row['cell'].startswith('V2_')
    for inventory in bundle['H1_inventories']:
        if selected(inventory): inventory.update(completed=False,occurrence_count=None)
    bundle['H1']=[row for row in bundle['H1'] if not selected(row)]
    result = g.summarize(bundle)
    v2 = next(row for row in result['cells'] if row['cell']=='V2_ORIGINAL')
    assert v2['planned_source_count']==2 and v2['defined_source_count']==1
    assert v2['point'] is None and result['direction']['point_difference'] is None


def test_missing_weights_core_roster_and_positive_c1_proof_stay_unidentified():
    bundle = _bundle()
    v1_core = next(row for row in bundle['agreement']['grok'] if '-V1-0' in row['unit_id'])
    v1_core['weight']=None
    result = g.summarize(bundle)
    row = next(row for row in result['draws'] if row['cell']=='V2_ORIGINAL')
    assert row['point'] is None and row['undefined_reason']=='unknown_original_sampling_weights'
    assert result['direction']['point_difference'] is None
    v1_core['weight']=2
    v1_core['label']=None
    result = g.summarize(bundle)
    assert result['direction']['conservative_direction']=='negative'
    assert result['direction']['direction_identified_by_bounds']=='unresolved'
    assert result['direction']['lower']==-.25 and result['direction']['upper']==.75
    for inventory in bundle['H1_inventories']:
        if inventory['cell'].startswith('V2_'):
            inventory['positive_retained_membership_verified']=False
    result = g.summarize(bundle)
    assert all(row['undefined_reason']=='positive_C1_retained_membership_not_verified'
               for row in result['draws'] if row['cell'].startswith('V2_'))
    bundle = _bundle()
    bundle['agreement']['grok']=[row for row in bundle['agreement']['grok'] if '-AS-1' not in row['unit_id']]
    result = g.summarize(bundle)
    row = next(row for row in result['draws'] if row['cell']=='AS_ORIGINAL')
    assert row['original_random_core_roster_complete'] is False
    assert row['point'] is None and row['undefined_reason']=='fixed_15_percent_random_core_roster_incomplete_or_changed'
