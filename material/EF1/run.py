"""Reproduce EF1 using frozen D1 evidence and the explicitly pinned final K2 array.

Only generated EF1 derivatives are written. No provider or primary D1 run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from EF1.accounting import source_costs,stage_accounting
from EF1.metrics import analyze,load_bundle


def pin(path):
    data=Path(path).read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def run(repo=ROOT,output=None):
    repo=Path(repo); output=Path(output) if output else repo/'EF1'
    output.mkdir(parents=True,exist_ok=True)
    provpath=repo/'Experiments/fair_v2_oct24/K2/provenance.json'
    prov=json.loads(provpath.read_bytes());callpin=prov['native_D1_input_pin']
    callpath=Path(callpin['path'])
    if pin(callpath)!={k:callpin[k] for k in ('bytes','sha256')}:
        raise ValueError('K2 normalized original-call array does not match its explicit pin')
    calls=json.loads(callpath.read_bytes())
    bundle=load_bundle(repo)
    sids=[s['source_id'] for s in bundle['sources']]
    planned={s['source_id']:len(s['draws']) for s in bundle['sources']}
    newids=[s['source_id'] for s in bundle['sources'] if s['cohort']=='NEW20']
    costs=source_costs(calls,sids,planned,frozen_source_roster=set(sids))
    complete={sid for sid in newids if all(r['cost_complete'] for r in costs if r['source_id']==sid)}
    if len(complete)!=20:
        raise ValueError('EF1 requires the requested 20 fully cost-known sources; incomplete: '+repr(sorted(set(newids)-complete)))
    result=analyze(bundle,costs)
    stage={'protocol':'EF1-disjoint-original-stage-accounting-v1',
           'new20_construction_and_guard':stage_accounting(
               [r for r in calls if r['package'] in {'B3','C1'}],source_ids=set(newids)),
           'all_research_and_construction':stage_accounting(calls),
           'rules':['Original receipt counted once in the disjoint table.',
                    'Logical AS+G and V2 full costs each include their reused AS/V1 base.',
                    'Evaluation, references, qualification and C6 Reader excluded from N17 construction ratios.',
                    'Currencies and price scenarios remain separate.',
                    'Known subtotals do not replace unknown usage, cost, physical POSTs or wall time.']}
    c5path=repo/'Experiments/fair_v2_oct24/C5/result.json'
    c5=json.loads(c5path.read_bytes())
    stage['CPU_export_separate']={
        'stage':'Export','scope':'C5 all 24 sources, four arms, both exports',
        'measured_export_cells':c5['measured_export_cells'],
        'additional_model_calls':c5['new_model_calls'],
        'provider_token_usage':'not_applicable_to_deterministic_CPU_export',
        'CPU_cost_USD':None,'isolated_wall_seconds':None,
        'reason':'CPU export is separate from provider ledgers; no isolated metered CPU cost or wall-time total in this bound result.',
        'evidence':{'path':'Experiments/fair_v2_oct24/C5/result.json',**pin(c5path)}}
    result['inputs']={'K2_provenance':{'path':'Experiments/fair_v2_oct24/K2/provenance.json',**pin(provpath)},
                      'K2_original_call_array':{k:callpin[k] for k in ('bytes','sha256')},
                      'D1_frozen_bindings':bundle['_ef1_bindings']}
    result['X3']={'cost_point_plotted':False,'measured_cost_available':False,
                  'reason':'No measured X3 run/cost result in the inspected package; CPU projection is not independent filter cost.'}
    result['full24_cost_scope']={arm:{
        'known_lower_bound_usd':sum(r['known_cost_lower_bound_usd'] for r in costs
                                    if r['arm']==arm and r['known_cost_lower_bound_usd'] is not None),
        'complete_sources':sum(r['cost_complete'] for r in costs if r['arm']==arm),
        'sources':len(sids),'complete_total_usd':None,
        'comparison_allowed':False,
        'reason':'Historical extraction receipts for SEALED4 are unknown; only a lower bound.'}
        for arm in ('AS','AS+G','V1','V2')}
    write(output/'source-costs.json',costs)
    write(output/'stages.json',stage)
    write(output/'result.json',result)
    print(json.dumps({'status':'computed','source_count':len(complete),
                      'N14_cost_known_sources':result['populations']['H2_N14_NEW20']['n_sources'],
                      'N10_matrix':result['bootstrap']['source_group_matrix_sha256'],
                      'new_model_calls':0},ensure_ascii=False))
    return result,stage


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=ROOT)
    p.add_argument('--output',type=Path)
    a=p.parse_args();run(a.repo,a.output)
