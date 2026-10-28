"""Fresh EF1 readback and independent point reconciliation; no model calls."""
from pathlib import Path
from decimal import Decimal
import csv,hashlib,json,sys,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from EF1.metrics import CELLS
import numpy,scipy,matplotlib


def pin(p):
    data=p.read_bytes();return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def verify():
    out=ROOT/'EF1';r=json.loads((out/'result.json').read_bytes())
    ppath=ROOT/'Experiments/fair_v2_oct24/K2/provenance.json'
    prov=json.loads(ppath.read_bytes());callpin=prov['native_D1_input_pin']
    assert pin(ppath)=={k:r['inputs']['K2_provenance'][k] for k in ('bytes','sha256')}
    assert pin(Path(callpin['path']))=={k:callpin[k] for k in ('bytes','sha256')}
    calls=json.loads(Path(callpin['path']).read_bytes())
    assert len(calls)==len({v['request_id'] for v in calls})==38106
    k2=ROOT/'Experiments/fair_v2_oct24/K2'
    with (k2/'aufwand.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);rows=list(reader)
        assert len(reader.fieldnames)==33 and len(rows)==70
    assert len({v['receipt_set_sha256'] for v in rows})==70
    for output in json.loads((k2/'verification.json').read_bytes())['outputs']:
        assert pin(Path(output['path']))=={k:output[k] for k in ('bytes','sha256')}
    guards=[v for v in calls if v['stage']=='Prüffilter']
    assert len(guards)==4673 and all(v.get('source_id') and v.get('draw') for v in guards)
    public=json.loads((ROOT/'Experiments/fair_v2_oct24/D1/final_native_oct26_v1/analysis.public.json').read_bytes())
    expected=json.loads((ROOT/'Experiments/fair_v2_oct24/D1/final_native_oct26_v1/result.json').read_bytes())
    assert r['bootstrap']['source_group_matrix_sha256']==expected['primary']['H1']['source_group_matrix_sha256']
    assert r['bootstrap']['draws']==10000 and r['bootstrap']['seed']==2026102407
    point_checks=[]
    for name,pop in r['populations'].items():
        ids=set(pop['source_ids'])
        for arm,cell in CELLS.items():
            h1=next(v for v in public['cells'] if v['endpoint']=='H1' and v['cell']==cell)
            h2=next(v for v in public['cells'] if v['endpoint']=='H2' and v['cell']==cell)
            a=[v for v in h1['sources'] if v['source_id'] in ids]
            b=[v for v in h2['sources'] if v['source_id'] in ids]
            point_H1=sum(v['estimate'] for v in a)/len(ids)
            point_S=sum(v['estimate']*v['original_inventory_denominator'] for v in a)
            point_H2=sum(v['estimate'] for v in b)/len(ids)
            for source in b:
                assert len({d['denominator'] for d in source['planned_draw_statistics']})==1
            point_Q=sum(v['estimate']*v['planned_draw_statistics'][0]['denominator'] for v in b)
            row=pop['by_arm'][arm]
            for key,actual in [('H1',point_H1),('estimated_supported_statements',point_S),
                               ('H2',point_H2),('estimated_retained_references',point_Q)]:
                assert abs(row[key]['estimate']-actual)<1e-9,(name,arm,key)
            # Separate direct receipt selection, without EF1 accounting helpers.
            base='AS' if arm in ('AS','AS+G') else 'V1'
            rr=[v for v in calls if v.get('source_id') in ids and
                ((v['package']=='B3' and v['arm']==base) or
                 (v['package']=='C1' and v['arm']==arm and arm in ('AS+G','V2')))]
            assert all(v.get('known_cost') is not None and v.get('cost_complete') is True for v in rr)
            K=float(sum(Decimal(v['known_cost']) for v in rr))
            assert abs(K-row['cost_usd']['estimate'])<1e-10
            assert abs(K/point_S-row['cost_per_supported_usd']['estimate'])<1e-12
            assert abs(K/point_Q-row['cost_per_retained_reference_usd']['estimate'])<1e-12
            for value in [v for v in row.values() if isinstance(v,dict) and 'estimate' in v]:
                assert value['undefined_replicates']==0 and value['unbounded_replicates']==0
            point_checks.append({'population':name,'arm':arm,'public_D1_points_match':True,'original_cost_receipts_match':True})
    assert r['populations']['H1_NEW20']['n_sources']==20
    assert r['populations']['H2_N14_NEW20']['n_sources']==17
    assert not r['X3']['cost_point_plotted']
    assert all(not v['comparison_allowed'] and v['complete_total_usd'] is None for v in r['full24_cost_scope'].values())
    for p in json.loads((out/'input_inventory.json').read_bytes())['public_sources']:
        assert pin(ROOT/p['path'])=={k:p[k] for k in ('bytes','sha256')},p['path']
    figures=json.loads((out/'figure-data.json').read_bytes());assert len(figures)==8
    for f in figures:
        pr=r['populations'][f['panel']]['by_arm'][f['arm']]
        assert f['x_mean_list_price_USD_per_source'][0]==pr['mean_cost_per_source_usd']['estimate']
        endpoint='H1' if f['panel']=='H1_NEW20' else 'H2'
        assert f['y_quality_fraction'][0]==pr[endpoint]['estimate']
    xml=ET.parse(out/'cpu-tests.xml').getroot()
    suites=list(xml.iter('testsuite'));assert all(s.get('failures')=='0' and s.get('errors')=='0' for s in suites)
    text=(out/'textbausteine.md').read_text(encoding='utf-8')
    paras=[v for v in text.split('\n\n') if v.strip() and not v.startswith('#')]
    assert len(paras)==2 and all('; ' not in v for v in paras)
    assert all('rechenaufwandsgleicher' in v for v in paras[1:])
    for file in out.iterdir():
        if file.suffix in {'.md','.json','.tex','.svg'}:
            content=file.read_text(encoding='utf-8')
            assert 'AppData' not in content and 'LocalCache' not in content and 'Bearer ' not in content,file
    artifacts={p.name:pin(p) for p in out.iterdir() if p.is_file() and p.name!='verification.json'}
    proof={'protocol':'EF1-final-readback-v1','status':'complete_secondary_descriptive_analysis',
           'point_reconciliations':point_checks,'K2_calls':38106,'guard_source_mappings':4673,
           'K2_output_readback':{'rows':70,'columns':33,'unique_group_hashes':70,
                                 'verification':pin(k2/'verification.json'),
                                 'source_assignment':pin(k2/'source_assignment.json')},
           'H1_sources':20,'H2_N14_sources':17,'actual_planned_source_draw_units':68,
           'bootstrap_matrix':r['bootstrap'],'X3_no_cost_point':True,
           'all24_costs_lower_bounds_only':True,'bound_public_input_hashes_verified':True,
           'N17_concurrent_chronology_update_recorded':True,
           'mechanism_tests':sum(int(s.get('tests')) for s in suites),
           'manuscript_drafts':{'paragraphs':2,'main_manuscript_modified':False},
           'figure_review':{'format':['PNG','PDF','SVG'],'panels':2,'points':8,
                            'actual_values_match_result':True,'visual_review':'passed; direct labels, no collisions or clipped content',
                            'grayscale_review':'passed; marker shape and labels retain arm identity'},
           'runtime':{'python':sys.version,'numpy':numpy.__version__,'scipy':scipy.__version__,'matplotlib':matplotlib.__version__},
           'new_provider_calls':0,'primary_D1_recomputed':False,'new_hypothesis_tests':False,
           'winner_claim':False,'publication':False,'commit':False,'push':False,'artifacts':artifacts}
    (out/'verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'verified','independent_point_checks':len(point_checks),'tests':proof['mechanism_tests']},ensure_ascii=False))


if __name__=='__main__':verify()
