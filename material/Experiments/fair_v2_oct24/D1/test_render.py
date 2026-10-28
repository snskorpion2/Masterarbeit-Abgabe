"""Small synthetic rendering fixtures. No model, natural input or source file."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

from Experiments.fair_v2_oct24.D1 import render as r


def report_fixture():
    primary = {name: {'point_difference': .04+i*.01, 'ci95': [.01+i*.01,.08+i*.01],
        'raw_p': .01+i*.005, 'adjusted_p': .03+i*.005, 'reject': True,
        'testable': True, 'null_boundary': -.05 if name == 'H2' else 0}
        for i,name in enumerate(('H1','H2','H4'))}
    rows=[]
    for endpoint in r.ENDPOINT_NAMES:
        for i,cell in enumerate(r.CELLS):
            point=.7+i*.02
            rows.append({'endpoint':endpoint,'cell':cell,'estimate':point,'lower':point,
                'upper':min(1,point+.08),'missing_rate':.08,'technical_missing_rate':.02,
                'denominator':120,'defined':True})
    # Undefined H1 denominator and missing QA remain visibly different from0.
    rows[0].update(estimate=None,lower=None,upper=None,denominator=None,defined=False)
    next(row for row in rows if row['endpoint']=='F1' and row['cell']=='V2_ROW').update(estimate=None)
    return {'synthetic':True,'metadata':{'sources':24,'paired_source_draw_units':68,'QA_questions':60},
        'primary':primary,'cells':rows,
        'ablations':[{'endpoint':'H1','control':'AS_ORIGINAL','treatment':'AS_ROW','point_difference':.02}],
        'effort':[{'package':'B3','arm':'AS','calls_known':100,'calls_unknown':1,
            'prompt_tokens_known':100000,'output_tokens_known':10000,'usage_missing':1,
            'currency':'USD','cost_known':1.2,'cost_complete':False,'invoice_verified':False},
            {'package':'C2','arm':'all','calls_known':20,'calls_unknown':0,
            'prompt_tokens_known':None,'output_tokens_known':None,'usage_missing':20,
            'currency':'EUR','cost_known':None,'cost_complete':False,'invoice_verified':False}],
        'agreement':{'human':{'n_pairs':10,'agreement':.8,'kappa':.6,
            'table3x3':[[3,1,0],[0,3,1],[0,0,2]]},'grok':None},'amendments':[]}


def test_tex_escapes_special_input_without_executable_latex():
    escaped = r._tex(r'AS_ROW & 10% #x $y$ {z} \write18')
    assert r'AS\_ROW' in escaped and r'\&' in escaped and r'\%' in escaped
    assert r'\textbackslash{}write18' in escaped


def test_real_inputs_are_rejected_before_importing_matplotlib_or_writing(tmp_path):
    report=report_fixture();report['synthetic']=False
    with pytest.raises(ValueError,match='EXPLICIT_ENABLE'):
        r.render(report,tmp_path/'not-created')
    assert not (tmp_path/'not-created').exists()


def test_unknown_numbers_are_not_formatted_as_zero():
    assert r._number(None)=='n. b.' and r._count(None)=='unbekannt'
    assert r._number(0)=='0,000' and r._count(0)=='0'
    assert r._money('1.2')=='1,200000' and r._money(None)=='n. b.'


def test_tables_keep_currency_and_h3_denominators_separate(tmp_path):
    report=report_fixture();banner=r.SYNTHETIC_BANNER
    paths=[*r._cell_tables(report,tmp_path,banner),*r._effort_tables(report,tmp_path,banner)]
    assert (tmp_path/'effort_costs_usd.tex').exists() and (tmp_path/'effort_costs_eur.tex').exists()
    assert '(Teil)' in (tmp_path/'effort_costs_usd.tex').read_text(encoding='utf8')
    assert 'n. b.' in (tmp_path/'effort_costs_eur.tex').read_text(encoding='utf8')
    assert 'Nenner nativer Objekte' in (tmp_path/'cells_h3_content.tex').read_text(encoding='utf8')
    assert 'Teilnehmerkanten' in (tmp_path/'cells_h3_capacity.tex').read_text(encoding='utf8')
    assert all(banner in p.read_text(encoding='utf8') for p in paths)


def test_long_ablation_table_repeats_banner_on_continuation(tmp_path):
    report=report_fixture()
    report['ablations']*=60
    path=r._ablation_table(report,tmp_path,r.SYNTHETIC_BANNER)
    text=path.read_text(encoding='utf8')
    assert r'\begin{longtable}' in text and r'\endfirsthead' in text and r'\endhead' in text
    assert text.count(r.SYNTHETIC_BANNER)==4
    assert text.count('AS\\_ORIGINAL')==120
    assert '95\\%-KI' in text and 'Identifikationssensitivität' in text


def test_inference_agreement_aliases_and_weighted_prevalence_render(tmp_path):
    report=report_fixture()
    report['agreement']['human']={'N_pair':10,'p_o':.8,'kappa':.6,
        'confusion_matrix':[[3,1,0],[0,3,1],[0,0,2]],
        'weighted_prevalence':[{'arm':'AS','estimate':.7,'lower':.6,'upper':.8,
            'population_count':1000,'sample_count':75}]}
    paths=[*r._agreement_tables(report,tmp_path,r.SYNTHETIC_BANNER),
           *r._weighted_human_table(report,tmp_path,r.SYNTHETIC_BANNER)]
    assert '0,800' in (tmp_path/'agreement.tex').read_text(encoding='utf8')
    assert (tmp_path/'agreement_human_matrix.tex').exists()
    assert '1000' in (tmp_path/'human_weighted_prevalence.tex').read_text(encoding='utf8')
    assert all(r.SYNTHETIC_BANNER in path.read_text(encoding='utf8') for path in paths)


def test_effort_preserves_population_scenario_holds_and_physical_unknowns(tmp_path):
    report=report_fixture()
    first=report['effort'][0]
    first.update(population='fresh24',pricing_scenario='Flex_Long',arm='shared/unallocated',
        reserved_or_held_cost_known='0.125',physical_POSTs_known=None,physical_POSTs_unknown_records=1)
    second=deepcopy(first);second.update(pricing_scenario='Standard_Long',cost_known='2.4')
    report['effort']=[first,second]
    paths=r._effort_tables(report,tmp_path,r.SYNTHETIC_BANNER)
    costs=[path for path in paths if path.name.startswith('effort_costs_')]
    assert len(costs)==2
    assert all('shared/unallocated' in path.read_text(encoding='utf8') for path in costs)
    assert all('0,125000' in path.read_text(encoding='utf8') for path in costs)
    assert all('fresh24' in path.read_text(encoding='utf8') for path in costs)
    wires=[path for path in paths if path.name.startswith('effort_wire_')]
    assert all('unbekannt' in path.read_text(encoding='utf8') for path in wires)


def test_qa_control_does_not_display_complete_case_mean_as_full_q60(tmp_path):
    report=report_fixture()
    report['QA_controls']=[{'mode':'empty','planned':60,'provided':60,'observed':59,
        'F1':.8,'lower':.7,'upper':.9}]
    path=r._qa_control_table(report,tmp_path,r.SYNTHETIC_BANNER)
    text=path.read_text(encoding='utf8')
    assert '0,800' not in text and 'n. b.' in text
    report['QA_controls'][0]['planned']=59
    with pytest.raises(ValueError,match='DENOMINATOR_DRIFT'):
        r._qa_control_table(report,tmp_path,r.SYNTHETIC_BANNER)


def test_sensitivity_outputs_keep_tests_and_identification_bounds_separate(tmp_path):
    report=report_fixture()
    report['primary']['H1']['identification_sensitivity95']={'lower':-.2,'upper':.3}
    report['sensitivities']={'H1_Wilcoxon':{'source_count':24,'nonzero_sources':22,
        'statistic_W_plus':201,'raw_p':.01234},
        'EM_McNemar':{'W':8,'L':2,'paired_count':59,'raw_p':.05469}}
    paths=[r._primary_bounds_table(report,tmp_path,r.SYNTHETIC_BANNER),
        r._sensitivity_table(report,tmp_path,r.SYNTHETIC_BANNER)]
    bounds=paths[0].read_text(encoding='utf8');sensitivity=paths[1].read_text(encoding='utf8')
    assert '-0,200' in bounds and '0,300' in bounds
    assert '201,000' in sensitivity and '0,01234' in sensitivity
    assert '59' in sensitivity and '0,05469' in sensitivity
    assert 'keine zusätzliche Holm' in sensitivity
    assert all(r.SYNTHETIC_BANNER in path.read_text(encoding='utf8') for path in paths)


def test_missingness_and_h3_counts_do_not_invent_pooled_quality(tmp_path):
    report=report_fixture()
    row=next(row for row in report['cells'] if row['endpoint']=='H1' and row['cell']=='AS_ROW')
    row.update(pooled_missing_rate=.1,semantic_unclear_rate=.06,undefined_denominators=2)
    report['H3_original_measurements']=[{'cell':'AS_ORIGINAL','source_id':'synthetic-one',
        'draw':0,'status':'complete','categories':{'ALL':{'direct_content_found':8,'native_objects':10}},
        'projected_occurrence_capacity':{'retained_occurrences':11,'expected_occurrences':12}},
        {'cell':'AS_ORIGINAL','source_id':'synthetic-two','draw':0,'status':'unavailable',
         'categories':{},'projected_occurrence_capacity':{}}]
    missing=r._missingness_table(report,tmp_path,r.SYNTHETIC_BANNER).read_text(encoding='utf8')
    counts=r._h3_counts_table(report,tmp_path,r.SYNTHETIC_BANNER).read_text(encoding='utf8')
    assert '0,100' in missing and '0,060' in missing and 'N undef.' in missing
    assert '8 (Teil)' in counts and '11 (Teil)' in counts and 'unbekannt' in counts
    assert 'keinen gepoolten Qualitätsschätzer' in counts
    assert 'Σ' not in counts
    tables=r._cell_tables(report,tmp_path,r.SYNTHETIC_BANNER)
    assert all('N gesamt' in path.read_text(encoding='utf8') for path in tables)


def test_distinct_counts_and_completion_status_remain_separate(tmp_path):
    report=report_fixture()
    report['distinct_supported']={'by_cell':{'AS_ORIGINAL':{
        'exact_supported_observed_count':12.5,'exact_supported_distinct_count':10.5,
        'semantic_supported_observed_count':12.5,'semantic_supported_distinct_count':9.5,
        'planned_sources':24}},'exact_only':[{'cell':'AS_ORIGINAL',
        'complete_support_membership':True,'exact_count_complete':True,'semantic_review_complete':False}]}
    path=r._distinct_tables(report,tmp_path,r.SYNTHETIC_BANNER)[0]
    text=path.read_text(encoding='utf8')
    assert '12,500' in text and '9,500' in text and '0/1' in text
    assert 'Vollständigkeitsstatus' in text and 'nicht die vollständige Faktenmenge' in text


def test_strata_and_n5_preserve_unknown_and_not_applicable(tmp_path):
    report=report_fixture()
    report['strata']=[{'dimension':'family','level':'synthetic_kind','endpoint':'H1','cell':'AS_ROW',
        'estimate':None,'lower':0,'upper':1,'missing_rate':1,'source_count':1}]
    report['construction_diagnostics']={'N5_joint':{'AS':{'status':'not_applicable'},
        'V1':{'completed_joint_responses':10,'rejected_joint_responses':2,
              'rejection_rate':.2,'status':'provided'}}}
    strata=r._strata_table(report,tmp_path,r.SYNTHETIC_BANNER).read_text(encoding='utf8')
    diagnostic=r._construction_table(report,tmp_path,r.SYNTHETIC_BANNER).read_text(encoding='utf8')
    assert r'\begin{longtable}' in strata and 'synthetic\\_kind' in strata
    assert 'n. b.' in strata and 'n. a.' in diagnostic and '0,200' in diagnostic


def test_weighted_human_prevalence_keeps_missing_point_and_design_details(tmp_path):
    report=report_fixture()
    report['agreement']['human']['weighted_prevalence']=[{'arm':'AS','N':100,'n':10,
        'estimate':None,'lower':.5,'upper':.8,'conservative_verified_supported_fraction':.5,
        'strata':[{'category':'synthetic_A','population_count':100,'sample_count':10,
            'provided_rows':9,'unprovided_selected_rows':1,'supported_count':5,'not_supported_count':2,
            'unclear_count':2,'technical_missing_count':1,'weight':10,
            'estimate':None,'lower':.5,'upper':.8}]}]
    text=r._weighted_human_table(report,tmp_path,r.SYNTHETIC_BANNER)[0].read_text(encoding='utf8')
    assert 'n. b.' in text and 'verifiziert' in text and 'synthetic\\_A' in text
    assert 'kein populationsvollständiger Goldwert' in text
    assert 'menschliche Schichturteile' in text and 'menschliche Schichtgewichte' in text


def test_render_creates_four_vector_pdfs_and_latex_without_mutating_report(tmp_path):
    report=report_fixture();before=deepcopy(report)
    artifacts=[Path(path) for path in r.render(report,tmp_path)]
    assert report==before
    pdfs=[p for p in artifacts if p.suffix=='.pdf']
    assert len(pdfs)==4 and all(p.read_bytes().startswith(b'%PDF-') for p in pdfs)
    assert all(p.stat().st_size>1000 for p in pdfs)
    assert all(p.stat().st_size>100 for p in artifacts)
    tex=[p for p in artifacts if p.suffix=='.tex']
    assert all(r.SYNTHETIC_BANNER in p.read_text(encoding='utf8') for p in tex)
    assert (tmp_path/'tables.tex').is_file()
    import matplotlib.pyplot as plt
    assert not plt.get_fignums()
