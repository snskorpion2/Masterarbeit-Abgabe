"""Pure synthetic known-value fixtures; no file/provider/natural-data access."""
from copy import deepcopy

import pytest

from Experiments.fair_v2_oct24.D1 import secondary as s


def bundle(cells=('AS_ORIGINAL','V1_ORIGINAL','AS_ROW','V2_ROW')):
    return {'sources':[{'source_id':'syn-s','draws':['draw_1']}], 'cells':list(cells),
        'H1':[], 'H1_inventories':[], 'semantic_pairs':[]}


def add(b, cell, values, *, sid='syn-s', draw='draw_1', codes=None, statuses=None):
    codes = ['supported']*len(values) if codes is None else codes
    statuses = ['valid']*len(values) if statuses is None else statuses
    for i, (value, code, status) in enumerate(zip(values,codes,statuses,strict=True)):
        b['H1'].append({'source_id':sid, 'draw':draw, 'cell':cell,
            'unit_id':sid+draw+cell+str(i), 'category':'EE', 'value':value,
            'raw_code':code, 'measurement_status':status})
    b['H1_inventories'].append({'source_id':sid,'draw':draw,'cell':cell,
        'occurrence_count':len(values),'completed':True})


def pair(left,right,judgment='equivalent',human=True,cell='AS_ORIGINAL'):
    return {'source_id':'syn-s','draw':'draw_1','left_payload':left,'right_payload':right,
            'judgment':judgment,'human_confirmed':human,'cell':cell}


def rows_by_cell(report):
    return {row['cell']:row for row in report['exact_only']}


def three_forms():
    b = bundle()
    a,beta,c = ({'r':'a'},{'r':'b'},{'r':'c'})
    add(b,'AS_ORIGINAL',[a,beta]); add(b,'V1_ORIGINAL',[c])
    add(b,'AS_ROW',[a,beta]); add(b,'V2_ROW',[beta,c])
    b['semantic_pairs'] = [pair(a,beta),pair(beta,c,cell='V2_ROW'),pair(a,c,'not_equivalent',False)]
    return b,a,beta,c


def test_canonical_payload_normalizes_only_string_values_not_keys_or_semantics():
    assert s.canonical_payload({'x':'a\u0308'}) == s.canonical_payload({'x':'ä'})
    assert s.canonical_payload({'a\u0308':1}) != s.canonical_payload({'ä':1})
    assert s.canonical_payload({'Entity':['A','B','B']}) != s.canonical_payload({'Entity':['A','B']})
    assert s.canonical_payload({'Entity':['A','B']}) != s.canonical_payload({'Entity':['B','A']})
    assert s.canonical_payload({'x':1}) != s.canonical_payload({'x':1.0})
    assert s.canonical_payload({'role':'lead'}) != s.canonical_payload({'role':'created_by'})


def test_exact_forms_deduplicate_occurrences_without_erasing_payload_list_multiplicity():
    b=bundle(('AS_ORIGINAL','V1_ORIGINAL'))
    add(b,'AS_ORIGINAL',[{'x':'a\u0308'},{'x':'ä'},{'Entity':['A','B','B']},{'Entity':['A','B']}])
    add(b,'V1_ORIGINAL',[])
    report=s.distinct_supported(b)
    assert rows_by_cell(report)['AS_ORIGINAL']['exact_supported_observed_count']==3
    assert rows_by_cell(report)['AS_ORIGINAL']['exact_supported_distinct_count']==3
    assert report['JSON_key_normalization'] is False


def test_shared_original_pool_clique_count_is_not_per_cell_or_transitive_union():
    b,_,_,_=three_forms()
    before=deepcopy(b)
    report=s.distinct_supported(b)
    by_cell=rows_by_cell(report)
    assert by_cell['AS_ORIGINAL']['exact_supported_distinct_count']==2
    assert by_cell['AS_ORIGINAL']['semantic_supported_distinct_count']==1
    assert by_cell['V1_ORIGINAL']['semantic_supported_distinct_count']==1
    # B~C alone would merge in this cell. In the pooled first-fit partition,
    # B belongs to [A,B], while C cannot join because A!~C.
    assert by_cell['V2_ROW']['semantic_supported_distinct_count']==2
    assert report['pair_reviews'][0]['assessed_unique_pairs']==3
    assert len(report['pair_reviews'][0]['groups'])==2
    assert report['semantic_merges_completed']
    assert b==before


def test_unsupported_early_form_and_its_pairs_do_not_change_supported_partition():
    b,a,beta,_=three_forms()
    baseline=rows_by_cell(s.distinct_supported(b))
    d={'r':'0'}  # Sorts BEFORE A and would split A~B if incorrectly eligible.
    b['H1'].append({'source_id':'syn-s','draw':'draw_1','cell':'AS_ORIGINAL',
        'unit_id':'unsupported-extra','category':'EE','value':d,
        'raw_code':'unsupported','measurement_status':'valid'})
    b['H1_inventories'][0]['occurrence_count']+=1
    b['semantic_pairs'] += [pair(d,a),pair(d,beta,'not_equivalent',False)]
    report=s.distinct_supported(b)
    actual=rows_by_cell(report)
    for cell in baseline:
        for field in ('exact_supported_observed_count','exact_supported_distinct_count',
                      'semantic_supported_observed_count','semantic_supported_distinct_count'):
            assert actual[cell][field]==baseline[cell][field]
    review=report['pair_reviews'][0]
    assert review['pooled_exact_forms']==3 and review['possible_pairs']==3
    assert review['pair_records_outside_supported_original_pool']==2


def test_unconfirmed_unclear_conflicting_and_unassessed_pairs_never_create_merge():
    b=bundle(('AS_ORIGINAL','V1_ORIGINAL'))
    a,c={'x':'a'},{'x':'c'}
    add(b,'AS_ORIGINAL',[a,c]); add(b,'V1_ORIGINAL',[])
    b['semantic_pairs']=[pair(a,c,human=False)]
    report=s.distinct_supported(b)
    assert rows_by_cell(report)['AS_ORIGINAL']['semantic_supported_observed_count']==2
    assert rows_by_cell(report)['AS_ORIGINAL']['semantic_supported_distinct_count'] is None
    assert report['pair_reviews'][0]['unconfirmed_equivalent_pairs']==1
    b['semantic_pairs']=[pair(a,c),pair(a,c,'not_equivalent',False)]
    report=s.distinct_supported(b)
    assert report['pair_reviews'][0]['conflicting_pairs']==1
    assert rows_by_cell(report)['AS_ORIGINAL']['semantic_supported_observed_count']==2
    b['semantic_pairs']=[pair(a,c,'unclear',True)]
    assert s.distinct_supported(b)['pair_reviews'][0]['unclear_pairs']==1
    b['semantic_pairs']=[]
    assert s.distinct_supported(b)['pair_reviews'][0]['unassessed_pairs']==1


def test_pair_cell_metadata_is_ignored_and_duplicate_views_are_one_pair():
    b=bundle(('AS_ORIGINAL','V1_ORIGINAL'))
    a,c={'x':'a'},{'x':'c'}
    add(b,'AS_ORIGINAL',[a]); add(b,'V1_ORIGINAL',[c])
    b['semantic_pairs']=[pair(a,c,cell='AS_ORIGINAL'),pair(c,a,cell='V2_ROW')]
    report=s.distinct_supported(b)
    assert report['pair_reviews'][0]['assessed_unique_pairs']==1
    assert report['pair_reviews'][0]['human_confirmed_equivalent_pairs']==1
    assert len(report['pair_reviews'][0]['groups'])==1


def test_missing_payload_and_h1_judgments_keep_observed_count_separate_from_full_count():
    b=bundle(('AS_ORIGINAL','V1_ORIGINAL'))
    add(b,'AS_ORIGINAL',[{'x':1},None,{'x':3}],codes=['supported','supported',None],
        statuses=['valid','valid','technical_missing'])
    add(b,'V1_ORIGINAL',[])
    row=rows_by_cell(s.distinct_supported(b))['AS_ORIGINAL']
    assert row['exact_supported_observed_count']==1
    assert row['exact_supported_distinct_count'] is None
    assert row['semantic_payload_missing']==1 and row['technical_missing_judgments']==1
    assert not row['exact_count_complete']


def test_unknown_original_pool_never_gains_eligibility_from_observed_guard_form():
    b=bundle(('AS_ORIGINAL','V1_ORIGINAL','V2_ROW'))
    add(b,'AS_ORIGINAL',[]); add(b,'V1_ORIGINAL',[]); add(b,'V2_ROW',[{'x':'guard-observed'}])
    b['H1_inventories'][1].update(completed=False,occurrence_count=None)
    report=s.distinct_supported(b)
    row=rows_by_cell(report)['V2_ROW']
    assert row['exact_supported_observed_count']==1
    assert row['semantic_supported_observed_count'] is None
    assert row['supported_forms_outside_observed_original_pool']==1
    assert report['pair_reviews'][0]['pooled_exact_forms']==0
    assert not report['semantic_merges_completed']


def test_distinct_aggregation_averages_draws_then_sources_not_all_draws_pooled():
    b=bundle(('AS_ORIGINAL','V1_ORIGINAL'))
    b['sources']=[{'source_id':'s1','draws':['d1','d2']},{'source_id':'s2','draws':['d1']}]
    for sid,draw,n in (('s1','d1',1),('s1','d2',3),('s2','d1',0)):
        add(b,'AS_ORIGINAL',[{'x':i} for i in range(n)],sid=sid,draw=draw)
        add(b,'V1_ORIGINAL',[],sid=sid,draw=draw)
    report=s.distinct_supported(b)
    assert report['by_cell']['AS_ORIGINAL']['exact_supported_distinct_count']==1
    assert report['by_cell']['AS_ORIGINAL']['exact_supported_observed_count']==1


def human_fixture():
    strata=[];rows=[]
    for arm,counts in (('AS',(90,9,1)),('V1',(10,10,10))):
        for category,N in zip(('EE','EV','VV'),counts,strict=True):
            strata.append({'arm':arm,'type':category,'population_count':N,'sample_count':1})
            rows.append({'arm':arm,'category':category,'stratum':arm+'-'+category,
                'unit_id':arm+'-'+category,'label':'supported' if arm=='AS' and category=='EE' else 'not_supported',
                'status':'rated','weight':N,'in_base_sample':True})
    return rows,strata


def test_human_population_prevalence_uses_design_weights_not_naive_sample_fraction():
    rows,strata=human_fixture()
    report={r['arm']:r for r in s.human_weighted_prevalence(rows,strata)}
    assert report['AS']['estimate']==report['AS']['lower']==report['AS']['upper']==.9
    assert report['AS']['estimate']!=pytest.approx(1/3)
    assert report['AS']['population_count']==100 and report['AS']['sample_count']==3
    assert report['V1']['estimate']==0


def test_human_unclear_and_technical_missing_are_separate_with_weighted_bounds():
    rows,strata=human_fixture()
    rows[1].update(label='unclear')
    rows[2].update(label=None,status='missing')
    as_row=s.human_weighted_prevalence(rows,strata)[0]
    assert as_row['estimate'] is None and not as_row['support_prevalence_point_identified']
    assert as_row['lower']==as_row['conservative_verified_supported_fraction']==.9
    assert as_row['upper']==1
    assert as_row['unclear_count']==as_row['technical_missing_count']==1
    assert as_row['technical_missing_sample_rate']==pytest.approx(1/3)
    assert as_row['weighted_technical_missing_population_fraction']==.01
    assert as_row['weighted_unclear_population_fraction']==.09


def test_unsampled_positive_stratum_is_unknown_not_a_zero_or_omitted_population():
    rows,strata=human_fixture()
    strata[1]['sample_count']=0
    rows.pop(1)
    result=s.human_weighted_prevalence(rows,strata)[0]
    assert result['estimate'] is None and result['population_count']==100
    assert result['lower']==.9 and result['upper']==.99
    assert result['unsampled_population_fraction']==.09
    assert result['weighted_technical_missing_population_fraction'] is None


def test_unprovided_selected_human_row_keeps_planned_sample_denominator():
    rows,strata=human_fixture(); rows.pop(2)
    result=s.human_weighted_prevalence(rows,strata)[0]
    assert result['sample_count']==3 and result['technical_missing_count']==1
    assert result['lower']==.9 and result['upper']==.91 and result['estimate'] is None
    assert result['strata'][2]['unprovided_selected_rows']==1


def test_invalid_weight_duplicate_unit_or_enriched_panel_cannot_claim_population_prevalence():
    rows,strata=human_fixture()
    changed=deepcopy(rows); changed[0]['weight']=1
    with pytest.raises(ValueError,match='weight'):
        s.human_weighted_prevalence(changed,strata)
    with pytest.raises(ValueError,match='Unique'):
        s.human_weighted_prevalence(rows+[rows[0]],strata)
    changed=deepcopy(rows);changed[0]['in_base_sample']=False
    with pytest.raises(ValueError,match='probability-sample'):
        s.human_weighted_prevalence(changed,strata)
    assert s.human_weighted_prevalence([],[])==[]
