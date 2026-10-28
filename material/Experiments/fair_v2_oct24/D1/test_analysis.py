"""Analytic CPU checks of estimands, missingness, expense and frozen plumbing.

All values/labels/QA are generated here or in synthetic.py. No live result,
judgment, source, answer or gold file is opened.
"""
from copy import deepcopy
from math import isclose

import pytest

from Experiments.fair_v2_oct24.D1 import analysis as a
from Experiments.fair_v2_oct24.D1.contract import load_contract
from Experiments.fair_v2_oct24.D1.native import normalize_native
from Experiments.fair_v2_oct24.D1.synthetic import build_native_fixture


@pytest.fixture(scope='module')
def data():
    contract = load_contract()
    native = build_native_fixture(sources=contract['sources'], qa_blocks=contract['qa_blocks'])
    native['question_ids'] = list(contract['question_ids'])
    bundle = normalize_native(native)
    # Explicitly pin the primary missing case, independently of fixture RNG.
    row = next(r for r in bundle['QA'] if r['cell']=='V2_ROW' and r['context_mode']=='graph')
    row.update(observed=False, f1=None, em=None, status='timeout')
    return bundle, contract


@pytest.fixture(scope='module')
def report(data):
    return a.analyze(*data)


def test_draw_then_source_mean_is_not_pooled_or_draw_weighted():
    sources = [{'source_id':'a','draws':[1,2],'cohort':'SEALED4','family':'x'},
               {'source_id':'b','draws':[1,2,3],'cohort':'NEW20','family':'y'}]
    rows = [a.ratio_record(s,n-s,0,0,n,source_id=sid,draw=d)
            for sid,d,s,n in [('a',1,1,1),('a',2,0,9),('b',1,1,1),('b',2,1,1),('b',3,1,1)]]
    result = a._source_equal(rows,sources)
    assert result['estimate'] == .75  # (.5+1)/2, not 4/5 or 4/13.
    assert result['denominator'] == 13


def test_symmetric_score_bounds_and_missing_state_partition():
    control=a.ratio_record(6,2,1,1,10)
    treated=a.ratio_record(7,1,2,0,10)
    assert isclose(treated['estimate']-control['estimate'], .1)
    assert isclose(treated['lower']-control['upper'], -.1)
    assert control['lower']==.6 and control['upper']==.8
    assert control['missing_rate']==.2 and control['technical_missing_rate']==.1
    assert control['semantic_unclear_rate']==.1


@pytest.mark.parametrize('denominator',[None,0])
def test_empty_or_unknown_denominator_is_neither_zero_nor_perfect(denominator):
    row=a.ratio_record(0,0,0,0,denominator)
    assert row['estimate'] is None and row['defined'] is False
    assert row['lower'] is None and row['upper'] is None


def test_h1_keeps_occurrences_and_unknown_census(data):
    bundle,_=data
    scores=a._h1_draws(bundle,bundle['cells'])
    assert scores['AS_ORIGINAL'][0]['denominator']==6  # equal content != same occurrence
    copy=deepcopy(bundle)
    key=copy['H1_inventories'][0]
    sid,draw,cell=key['source_id'],key['draw'],key['cell']
    key.update(occurrence_count=None,completed=False)
    copy['H1']=[r for r in copy['H1'] if (r['source_id'],r['draw'],r['cell'])!=(sid,draw,cell)]
    row=next(r for r in a._h1_draws(copy,copy['cells'])[cell] if r['source_id']==sid and r['draw']==draw)
    assert row['estimate'] is None and row['denominator'] is None


def test_missing_h2_inventory_retains_fixed_reference_denominator(data):
    bundle,_=data
    copy=deepcopy(bundle)
    sid=copy['sources'][0]['source_id'];draw='draw_1';cell='AS_ORIGINAL'
    copy['H2']=[r for r in copy['H2'] if (r['source_id'],r['draw'],r['cell'])!=(sid,draw,cell)]
    row=next(r for r in a._h2_draws(copy,copy['cells'])[cell] if r['source_id']==sid and r['draw']==draw)
    assert row['denominator']==4 and row['estimate']==0
    assert (row['lower'],row['upper'])==(0,1) and row['technical_missing_rate']==1


def test_missing_qa_keeps_q60_and_holm_slot(report):
    h4=report['primary']['H4']
    assert h4['point_difference'] is None and h4['raw_p'] is None
    assert h4['testable'] is False and h4['reject'] is False
    assert report['holm']['results']['H4']['slot_p']==1
    row=next(r for r in report['cells'] if r['endpoint']=='F1' and r['cell']=='V2_ROW')
    assert row['denominator']==60 and row['estimate'] is None
    assert row['lower']<row['upper'] and row['observed_questions']<60
    assert report['sensitivities']['EM_McNemar']['planned_count']==60


def test_completed_empty_answer_and_missing_are_distinct(data):
    bundle,contract=data
    copy=deepcopy(bundle)
    selected=[r for r in copy['QA'] if r['cell']=='AS_ORIGINAL' and r['context_mode']=='graph']
    for row in selected:
        row.update(observed=True,f1=0.,em=0,status='complete')
    qa,_=a._qa(copy,copy['cells'],contract['question_ids'])
    value=qa['f1','AS_ORIGINAL']
    assert value['estimate']==0 and value['lower']==value['upper']==0 and value['missing_rate']==0


def test_all_eight_cells_and_no_primary_h3_or_extra_holm(report):
    assert set(report['primary'])=={'H1','H2','H4'}
    assert report['holm']['family_size']==3
    for endpoint in ('H1','H2','H3_direct_content_fraction','H3_occurrence_capacity','F1','EM'):
        assert len([r for r in report['cells'] if r['endpoint']==endpoint])==8
    assert all('raw_p' not in row and row['no_extra_primary_family'] for row in report['ablations'])
    # Paired unchanged export views cannot alter inventory H1/H2.
    for endpoint in ('H1','H2'):
        rows={r['cell']:r for r in report['cells'] if r['endpoint']==endpoint}
        for arm in ('AS','AS_G','V1','V2'):
            assert rows[arm+'_ORIGINAL']['estimate']==rows[arm+'_ROW']['estimate']


def test_a6_two_known_denominators_and_unavailable(data):
    bundle,_=data
    copy=deepcopy(bundle)
    row=copy['H3'][0]
    row['categories']['ALL'].update(native_objects=6,direct_content_found=3,H3_direct_content_fraction=.5)
    row['projected_occurrence_capacity'].update(expected_occurrences=8,retained_occurrences=6,occurrence_fraction=.75)
    output=a._h3_draws(copy,copy['cells'])
    assert output['H3_direct_content_fraction'][row['cell']][0]['denominator']==6
    assert output['H3_occurrence_capacity'][row['cell']][0]['denominator']==8
    row.update(status='unavailable',categories=None,projected_occurrence_capacity=None)
    output=a._h3_draws(copy,copy['cells'])
    assert output['H3_direct_content_fraction'][row['cell']][0]['estimate'] is None


def test_effort_unknown_never_zero_and_shared_not_allocated():
    rows=[{'receipt_id':'one','package':'B3','population':'fresh','arm':None,
           'call_count':None,'physical_POSTs':None,'prompt_tokens':None,'completion_tokens':None,
           'currency':'USD','known_cost':None,'reserved_or_held_cost':'0.25','unknown_execution':None}]
    out=a._effort(rows+deepcopy(rows))
    assert len(out)==1 and out[0]['accounting_rows']==1
    row=out[0]
    assert row['arm']=='shared/unallocated' and row['cost_known'] is None
    assert row['calls_known'] is None and row['prompt_tokens_known'] is None
    assert row['unknown_execution']==1 and row['calls_unknown']==1
    assert row['reserved_or_held_cost_known']=='0.25' and not row['held_cost_is_spend']


def test_effort_tariffs_populations_currencies_and_receipt_conflicts():
    row={'receipt_id':'one','package':'C2','population':'fresh','arm':'AS',
         'call_count':1,'physical_POSTs':1,'prompt_tokens':10,'completion_tokens':2,
         'currency':'USD','known_cost':'0.1','pricing_scenario':'list',
         'cost_complete':True,'unknown_execution':False,'invoice_verified':False}
    other={**row,'currency':'EUR','known_cost':'0.09'}
    discounted={**row,'pricing_scenario':'flex','known_cost':'0.05'}
    assert len(a._effort([row,other,discounted]))==3
    with pytest.raises(ValueError,match='Conflicting duplicate'):
        a._effort([row,{**row,'prompt_tokens':11}])
    with pytest.raises(ValueError,match='nonnegative cost'):
        a._effort([{**row,'known_cost':'-1'}])


def test_partial_or_absent_qa_controls_never_complete_case_primary(data):
    bundle,contract=data
    copy=deepcopy(bundle)
    copy['QA']=[r for r in copy['QA'] if r['context_mode']=='graph']
    # The lean helper is covered via the full single report; here only validate QA
    # graph scores do not silently become a passage/empty control.
    values,_=a._qa(copy,copy['cells'],contract['question_ids'])
    assert len(values)==16


def test_amendments_n2_n14_explicit_and_n5_as_not_applicable(report):
    assert [r['identifier'] for r in report['amendments']]==['N2','N3','N4','N5','N6','N7','N8','N10','N14']
    diagnostics=report['construction_diagnostics']
    assert diagnostics['N5_joint']['AS']['status']=='not_applicable'
    assert diagnostics['N5_joint']['AS']['rejection_rate'] is None
    assert diagnostics['N6']['passage_endpoint']=='not_performed'
    assert diagnostics['N6']['answer_positions_are_not_physical_POSTs']


def test_foreign_source_or_question_fails_closed(data):
    bundle,contract=data
    copy=deepcopy(bundle);copy['H1'][0]['source_id']='foreign'
    with pytest.raises(ValueError,match='Foreign H1'):
        a._h1_draws(copy,copy['cells'])
    copy=deepcopy(bundle);copy['QA'][0]['question_id']='foreign'
    with pytest.raises(ValueError,match='Foreign frozen QA'):
        a._qa(copy,copy['cells'],contract['question_ids'])


def test_complete_h4_has_known_difference_and_optional_c7_c4_are_not_required(data):
    bundle,contract=data;copy=deepcopy(bundle)
    copy['agreement']={'human':[],'grok':[],'human_strata':[]}
    for cell in ('AS_ORIGINAL','V2_ROW'):
        selected={r['question_id']:r for r in copy['QA'] if r['cell']==cell and r['context_mode']=='graph'}
        for i,qid in enumerate(contract['question_ids']):
            score=.25 if cell=='AS_ORIGINAL' else .75 if i%3==0 else .5
            selected[qid].update(observed=True,f1=score,em=0,status='complete')
    report=a.analyze(copy,contract)
    assert report['primary']['H4']['point_difference']==pytest.approx(1/3)
    assert report['primary']['H4']['testable']
    assert report['primary']['H4']['raw_p'] is not None
    assert report['primary']['H4']['cluster_count']==39
    assert report['agreement']['human']['kappa'] is None
    assert report['agreement']['grok']['directional_sensitivity'] is None


def test_unknown_h1_planned_denominator_blocks_primary_without_dropping_source(data):
    bundle,contract=data;copy=deepcopy(bundle)
    copy['agreement']={'human':[],'grok':[],'human_strata':[]}
    sid=copy['sources'][0]['source_id'];draw='draw_1'
    for row in copy['H1_inventories']:
        if row['source_id']==sid and row['draw']==draw and row['cell'] in ('AS_ORIGINAL','AS_ROW'):
            row.update(occurrence_count=None,completed=False)
    copy['H1']=[r for r in copy['H1'] if not (r['source_id']==sid and r['draw']==draw and r['cell'] in ('AS_ORIGINAL','AS_ROW'))]
    report=a.analyze(copy,contract)
    assert report['primary']['H1']['point_difference'] is None
    assert report['primary']['H1']['raw_p'] is None and not report['primary']['H1']['testable']
    assert report['holm']['results']['H1']['slot_p']==1
    row=next(r for r in report['cells'] if r['endpoint']=='H1' and r['cell']=='AS_ORIGINAL')
    assert row['independent_source_count']==24 and len(row['sources'])==24
    assert row['undefined_denominators']==1 and row['estimate'] is None


def test_real_manifest_gate_precedes_file_access(tmp_path):
    from Experiments.fair_v2_oct24.D1.run import load_explicit_manifest
    with pytest.raises(ValueError,match='allow-real-inputs'):
        load_explicit_manifest(tmp_path/'not-existing.json',{})
