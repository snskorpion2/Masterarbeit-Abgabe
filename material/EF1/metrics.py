"""N17 section 1 descriptive effort/quality ratios over explicit D1/K2 inputs.

No providers, network, writes to original evidence, tests or winner decision.
The full frozen N10 matrix is reused literally. Cost-known domains are fixed
before resampling and projected onto each full draw, retaining variable domain
counts. A missing cost is never a zero-cost source.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from Experiments.fair_v2_oct24.D1 import analysis as d1
from Experiments.fair_v2_oct24.D1 import inference as inf
from Experiments.fair_v2_oct24.D1 import n10_sampling as n10

ARMS = ('AS', 'AS+G', 'V1', 'V2')
CELLS = {'AS': 'AS_ORIGINAL', 'AS+G': 'AS_G_ORIGINAL',
         'V1': 'V1_ORIGINAL', 'V2': 'V2_ROW'}
BASE = {'AS': 'AS', 'AS+G': 'AS', 'V1': 'V1', 'V2': 'V1'}
_UNSET = object()


def need(value, message):
    if not value:
        raise ValueError(message)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value)


def _quantiles(values):
    if values is None or np.isnan(values).any():
        return None
    # Ratios with zero denominators are unbounded, not discarded replicates.
    ordered = np.sort(values)
    def one(q):
        x = (len(ordered)-1)*q
        lo, hi = int(np.floor(x)), int(np.ceil(x))
        if lo == hi:
            return float(ordered[lo])
        if np.isposinf(ordered[hi]):
            return float('inf')
        if np.isneginf(ordered[lo]):
            return float('-inf')
        return float(ordered[lo] + (x-lo)*(ordered[hi]-ordered[lo]))
    low, high = one(.025), one(.975)
    return {'lower': low if np.isfinite(low) else None,
            'upper': high if np.isfinite(high) else None,
            'lower_unbounded': bool(np.isneginf(low)),
            'upper_unbounded': bool(np.isposinf(high))}


def _divide(numerator, denominator):
    """Nonnegative ratio: positive/0 is unbounded, 0/0 is unidentified."""
    n, d = np.broadcast_arrays(np.asarray(numerator, float), np.asarray(denominator, float))
    with np.errstate(divide='ignore', invalid='ignore'):
        out = n/d
    return out


def _stat(point, samples, low=_UNSET, high=_UNSET, low_samples=None, high_samples=None):
    samples = np.asarray(samples, float)
    estimate = float(point) if point is not None and np.isfinite(point) else None
    low = point if low is _UNSET else low
    high = point if high is _UNSET else high
    bounds = {'lower': float(low) if low is not None and np.isfinite(low) else None,
              'upper': float(high) if high is not None and np.isfinite(high) else None,
              'lower_unbounded': bool(low is not None and np.isneginf(low)),
              'upper_unbounded': bool(high is not None and np.isposinf(high))}
    result = {'estimate': estimate, 'ci95': _quantiles(samples),
              'identification_bounds': bounds,
              'undefined_replicates': int(np.isnan(samples).sum()),
              'unbounded_replicates': int(np.isinf(samples).sum()),
              'estimate_unbounded': bool(point is not None and np.isinf(point)),
              'defined': estimate is not None,
              'interval_method': 'linear percentile, 2.5/97.5%; no hypothesis test'}
    if low_samples is not None and high_samples is not None:
        lo_ci, hi_ci = _quantiles(low_samples), _quantiles(high_samples)
        result['identification_sensitivity95'] = {
            'lower': lo_ci['lower'] if lo_ci else None,
            'upper': hi_ci['upper'] if hi_ci else None,
            'upper_unbounded': bool(hi_ci and hi_ci['upper_unbounded'])}
    return result


def load_bundle(repo=ROOT, manifest_pin_path=None):
    """Reuse the exact final native D1 manifest and its original byte checks.

    The default is an explicit known handoff, not private-directory discovery.
    No original D1 analysis is rerun or overwritten.
    """
    from Experiments.fair_v2_oct24.D1.contract import load_contract
    from Experiments.fair_v2_oct24.D1.run import load_explicit_manifest
    from Experiments.fair_v2_oct24.D1.native import normalize_native
    repo = Path(repo)
    pinfile = Path(manifest_pin_path) if manifest_pin_path else repo/'.private-temp/d1-final-oct26/prepared-input-manifest-pin.private.json'
    pin = json.loads(pinfile.read_bytes())
    path = Path(pin['path']); raw = path.read_bytes()
    need(len(raw) == pin['bytes'] and sha256(raw).hexdigest() == pin['sha256'],
         'Final D1 explicit manifest bytes differ')
    reference = json.loads((repo/'Experiments/fair_v2_oct24/D1/final_native_oct26_v1/result.json').read_bytes())
    need(pin['sha256'] == reference['input_manifest_sha256'], 'Manifest is not the final D1 input')
    native, receipt = load_explicit_manifest(path, load_contract(), allow_real=True)
    bundle = normalize_native(native)
    bundle['_ef1_bindings'] = {
        'manifest_sha256': pin['sha256'],
        'input_files': [{k: p[k] for k in ('sha256','bytes')} for p in receipt['input_files']],
        'expected_n10_matrix_sha256': reference['primary']['H1']['source_group_matrix_sha256']}
    return bundle


def _prepare(bundle, draws, seed):
    cells = bundle['cells']
    need(all(cell in cells for cell in CELLS.values()), 'Four native arm cells required')
    need(n10.active(bundle), 'N17 requires the actual budget-stopped N10 population')
    raw, inventories, unit_groups, rosters = n10._validate(bundle, cells)
    sources = bundle['sources']; sids = [s['source_id'] for s in sources]
    matrix = n10.shared_indices(sids, rosters, draws=draws, seed=seed)
    expected = bundle.get('_ef1_bindings', {}).get('expected_n10_matrix_sha256')
    if expected:
        need(draws == inf.BOOTSTRAP_DRAWS and seed == inf.BOOTSTRAP_SEED and matrix.digest == expected,
             'EF1 must reuse the exact frozen final D1/N10 matrix')
    h2_draws = d1._h2_draws(bundle, cells)
    h2 = {c: d1._source_equal(h2_draws[c], sources)['sources'] for c in cells}
    references = Counter(r['source_id'] for r in bundle['H2_roster'])
    prepared = []
    for si, source in enumerate(sources):
        sid = source['source_id']; group_index = {g:i for i,g in enumerate(rosters[si])}
        counts = np.zeros((len(rosters[si]), len(ARMS), 4), dtype=np.int64)
        I = np.zeros(len(ARMS), dtype=np.int64)
        for ai, arm in enumerate(ARMS):
            cell = CELLS[arm]
            for draw in source['draws']:
                I[ai] += inventories[sid,draw,cell]['occurrence_count']
                for uid, row in raw[sid,draw,cell].items():
                    gi = group_index.get(unit_groups[uid])
                    if gi is not None:
                        counts[gi,ai] += n10._score(row)
        positions = np.argwhere(matrix.sources == si)
        inner = matrix.groups[si]
        weights = np.zeros((len(positions),len(rosters[si])), dtype=np.uint32)
        if len(rosters[si]):
            np.add.at(weights, (np.arange(len(positions))[:,None],inner), 1)
            sampled = (weights @ counts.reshape(len(rosters[si]),-1)).reshape(len(positions),len(ARMS),4)
        else:
            sampled = np.zeros((len(positions),len(ARMS),4), dtype=np.int64)
        def rates(c):
            den = c.sum(axis=-1); good = den > 0
            estimate = np.divide(c[...,0], den, out=np.full(den.shape,np.nan), where=good)
            low = np.divide(c[...,0], den, out=np.zeros(den.shape), where=good)
            high = np.divide(c[...,0]+c[...,2]+c[...,3],den,out=np.ones(den.shape),where=good)
            return estimate,low,high
        p, pl, pu = rates(counts.sum(axis=0)); bp,bpl,bpu = rates(sampled)
        H = [h2[CELLS[a]][si] for a in ARMS]
        h = np.array([x['estimate'] for x in H],float)
        hl = np.array([x['lower'] for x in H],float)
        hu = np.array([x['upper'] for x in H],float)
        valid = [sum(x['denominator']-x['technical_missing'] for x in z['planned_draw_statistics']) for z in H]
        prepared.append({'source':source,'source_index':si,'positions':positions[:,0],
                         'inventory':I,'p':p,'pl':pl,'pu':pu,'bp':bp,'bpl':bpl,'bpu':bpu,
                         'h':h,'hl':hl,'hu':hu,'R':references[sid],'h2_valid':valid})
    return matrix,prepared


def analyze(bundle, source_costs, *, draws=inf.BOOTSTRAP_DRAWS, seed=inf.BOOTSTRAP_SEED):
    """Return N17 measures; source_costs has one source/arm full-cost row.

    Required keys: source_id, arm, cost_complete, cost_usd.
    Tokens: prompt_tokens, completion_tokens, optional tokens_complete.
    Optional construction_prompt_tokens/construction_completion_tokens exclude
    the guard. Otherwise the corresponding AS/V1 base-row tokens are reused.
    Each source row combines every actually planned construction draw.
    """
    matrix, prepared = _prepare(bundle, draws, seed)
    source_ids = set(matrix.source_ids); costs = {}
    for row in source_costs:
        key = row['source_id'],row['arm']
        need(key not in costs, 'Duplicate source/arm cost row')
        need(key[0] in source_ids and key[1] in ARMS, 'Foreign source/arm cost row')
        if row.get('cost_complete'):
            need(_number(row.get('cost_usd')) and row['cost_usd'] >= 0, 'Known full cost must be nonnegative USD')
        costs[key] = row
    for item in prepared:
        sid = item['source']['source_id']
        cc=[];tt=[];ct=[];complete=[]
        for arm in ARMS:
            row = costs.get((sid,arm),{})
            known = row.get('cost_complete') is True and _number(row.get('cost_usd'))
            complete.append(known);cc.append(row['cost_usd'] if known else np.nan)
            toks=[row.get(k) for k in ('prompt_tokens','completion_tokens')]
            token_known = row.get('tokens_complete',True) and all(_number(v) and v>=0 for v in toks)
            tt.append(sum(toks) if token_known else np.nan)
            base = costs.get((sid,BASE[arm]),{})
            explicit=[row.get(k) for k in ('construction_prompt_tokens','construction_completion_tokens')]
            if all(_number(v) and v>=0 for v in explicit):
                ct.append(sum(explicit))
            else:
                bt=[base.get(k) for k in ('prompt_tokens','completion_tokens')]
                ct.append(sum(bt) if base.get('tokens_complete',True) and all(_number(v) and v>=0 for v in bt) else np.nan)
        item.update(cost=np.array(cc),tokens=np.array(tt),construction_tokens=np.array(ct),complete=complete)
    complete_ids = {x['source']['source_id'] for x in prepared if all(x['complete'])}
    new_ids = {x['source']['source_id'] for x in prepared if x['source']['cohort']=='NEW20'}
    n14_ids = {x['source']['source_id'] for x in prepared if all(v>0 for v in x['h2_valid'])}
    domains = [('H1_NEW20',new_ids & complete_ids,'H1'),
               ('H2_G2_NEW20',new_ids & complete_ids,'H2'),
               ('H2_N14_NEW20',new_ids & complete_ids & n14_ids,'H2')]
    populations={}
    for name, included, endpoint in domains:
        selected=[x for x in prepared if x['source']['source_id'] in included]
        if not selected:
            populations[name]={'source_ids':[],'n_sources':0,'rows':[],'by_arm':{},'reason':'no_common_fully_cost_known_sources'}
            continue
        n=len(selected); shape=(draws,len(ARMS))
        point={k:np.zeros(len(ARMS)) for k in ('cost','tokens','construction_tokens','S','Sl','Su','P','Pl','Pu','H','Hl','Hu','Q','Ql','Qu')}
        boot={k:np.zeros(shape) for k in point}; domain_count=np.zeros(draws,dtype=np.int64)
        for x in selected:
            I=x['inventory'];pos=x['positions'];R=x['R']
            # An empty full inventory has exactly zero supported statements,
            # even if its sampled rate has no denominator.
            sp=np.where(I==0,0,I*x['p']);bsp=np.where(I[None,:]==0,0,I[None,:]*x['bp'])
            values={'cost':x['cost'],'tokens':x['tokens'],'construction_tokens':x['construction_tokens'],
                    'S':sp,'Sl':I*x['pl'],'Su':I*x['pu'],'P':x['p'],'Pl':x['pl'],'Pu':x['pu'],
                    'H':x['h'],'Hl':x['hl'],'Hu':x['hu'],'Q':R*x['h'],'Ql':R*x['hl'],'Qu':R*x['hu']}
            bvalues={**values,'S':bsp,'Sl':I*x['bpl'],'Su':I*x['bpu'],
                     'P':x['bp'],'Pl':x['bpl'],'Pu':x['bpu']}
            for k in point:
                point[k]+=values[k]
                np.add.at(boot[k],pos,bvalues[k])
            np.add.at(domain_count,pos,1)
        for k in ('P','Pl','Pu','H','Hl','Hu'):
            point[k]/=n
            with np.errstate(invalid='ignore',divide='ignore'):
                boot[k]/=domain_count[:,None]
        metrics={}; arrays={}
        for ai,arm in enumerate(ARMS):
            p={k:point[k][ai] for k in point};b={k:boot[k][:,ai] for k in boot}
            def scalar(key,low=None,high=None):
                return _stat(p[key],b[key],p[low] if low else p[key],p[high] if high else p[key],
                             b[low] if low else None,b[high] if high else None)
            def ratio(num,den,denlo=None,denhi=None,factor=1.):
                v=float(_divide(p[num],p[den])*factor); bs=_divide(b[num],b[den])*factor
                lo=float(_divide(p[num],p[denhi or den])*factor)
                hi=float(_divide(p[num],p[denlo or den])*factor)
                return _stat(v,bs,lo,hi,_divide(b[num],b[denhi or den])*factor,_divide(b[num],b[denlo or den])*factor),bs
            m={'arm':arm,'n_sources':n,'cost_usd':scalar('cost'),
               'mean_cost_per_source_usd':_stat(p['cost']/n,_divide(b['cost'],domain_count)),
               'total_tokens':scalar('tokens'),'construction_tokens':scalar('construction_tokens'),
               'H1':scalar('P','Pl','Pu'),'H2':scalar('H','Hl','Hu'),
               'estimated_supported_statements':scalar('S','Sl','Su'),
               'estimated_retained_references':scalar('Q','Ql','Qu')}
            metrics_to_ratio={}
            for key,num,den,lo,hi,factor in (
                ('cost_per_supported_usd','cost','S','Sl','Su',1.),
                ('tokens_per_supported','tokens','S','Sl','Su',1.),
                ('cost_per_retained_reference_usd','cost','Q','Ql','Qu',1.)):
                m[key],metrics_to_ratio[key]=ratio(num,den,lo,hi,factor)
            v=float(_divide(p['S'],p['construction_tokens'])*1000)
            bs=_divide(b['S'],b['construction_tokens'])*1000
            m['supported_per_1000_construction_tokens']=_stat(v,bs,
                float(_divide(p['Sl'],p['construction_tokens'])*1000),float(_divide(p['Su'],p['construction_tokens'])*1000),
                _divide(b['Sl'],b['construction_tokens'])*1000,_divide(b['Su'],b['construction_tokens'])*1000)
            metrics_to_ratio['supported_per_1000_construction_tokens']=bs
            metrics[arm]=m;arrays[arm]=metrics_to_ratio
        for arm in ARMS:
            metrics[arm]['ratios_vs_AS']={}
            for key,bs in arrays[arm].items():
                left=metrics[arm][key]['estimate'];right=metrics['AS'][key]['estimate']
                value=float(_divide(left,right)) if left is not None and right is not None else None
                l=metrics[arm][key]['identification_bounds'];r=metrics['AS'][key]['identification_bounds']
                def bound(bounds, side):
                    val=bounds[side]
                    if val is not None:
                        return val
                    return (float('inf') if side=='upper' else float('-inf')) if bounds[side+'_unbounded'] else np.nan
                lo=float(_divide(bound(l,'lower'),bound(r,'upper')))
                hi=float(_divide(bound(l,'upper'),bound(r,'lower')))
                metrics[arm]['ratios_vs_AS'][key]=_stat(value,_divide(bs,arrays['AS'][key]),lo,hi)
            metrics[arm]['mean_cost_per_source']=metrics[arm]['mean_cost_per_source_usd']
            metrics[arm]['quality']=metrics[arm][endpoint]
        contrasts={}
        ci,ti=ARMS.index('AS+G'),ARMS.index('V1')
        for label,k in (('H1','P'),('H2','H'),('cost_usd','cost'),('total_tokens','tokens')):
            contrasts[label]=_stat(point[k][ti]-point[k][ci],boot[k][:,ti]-boot[k][:,ci])
        rows=[metrics[a] for a in ARMS]
        populations[name]={'source_ids':[x['source']['source_id'] for x in selected],
            'n_sources':n,'planned_source_draw_units':sum(len(x['source']['draws']) for x in selected),
            'quality_endpoint':endpoint,'rows':rows,'by_arm':metrics,
            'bootstrap_domain_size':{'min':int(domain_count.min()),'max':int(domain_count.max()),
                                     'mean':float(domain_count.mean()),'zero_draws':int((domain_count==0).sum())},
            'contrasts':{'V1_minus_AS+G':contrasts},
            'excluded_from_new20':sorted(new_ids-included),
            'N14_rule':'common sources with at least one technically valid H2 judgment in every arm; G2 within-source missingness unchanged' if 'N14' in name else None}
    source_rows=[]
    for x in prepared:
        for ai,arm in enumerate(ARMS):
            def safe(v):return float(v) if np.isfinite(v) else None
            source_rows.append({'source_id':x['source']['source_id'],'cohort':x['source']['cohort'],
                'arm':arm,'planned_draws':x['source']['draws'], 'inventory_statements':int(x['inventory'][ai]),
                'H1':safe(x['p'][ai]),'H1_lower':safe(x['pl'][ai]),'H1_upper':safe(x['pu'][ai]),
                'estimated_supported_statements':safe(0 if x['inventory'][ai]==0 else x['inventory'][ai]*x['p'][ai]),
                'reference_count':int(x['R']),'H2':safe(x['h'][ai]),'H2_lower':safe(x['hl'][ai]),
                'H2_upper':safe(x['hu'][ai]),'H2_valid_judgments':int(x['h2_valid'][ai]),
                'estimated_retained_references':safe(x['R']*x['h'][ai]),
                'cost_usd':safe(x['cost'][ai]),'cost_complete':bool(x['complete'][ai]),
                'total_tokens':safe(x['tokens'][ai]),'construction_tokens':safe(x['construction_tokens'][ai])})
    return {'protocol':'EF1-N17-section1-descriptive-v1','synthetic':bundle.get('synthetic'),
            'bootstrap':{'draws':draws,'seed':seed,'full_source_count':len(matrix.source_ids),
                'source_group_matrix_sha256':matrix.digest,'frozen_D1_matrix_verified':bool(bundle.get('_ef1_bindings')),
                'domain_policy':'fixed cost-known domain projected onto unchanged full N10 source/group draws; variable domain count retained',
                'costs_travel_with_source':True,'all_arms_and_metrics_paired':True,
                'undefined_replicates_are_not_dropped':True,'no_hypothesis_test':True},
            'actual_planned_draw_count':sum(len(x['source']['draws']) for x in prepared),
            'N17_wording_note':"At EF1 start, an uncommitted N17 working draft said 'both runs'. The current N17 chronology records correction before its commit to SEALED4 x2 and NEW20 x3 (68 units). EF1 already used every frozen draw; calculations and statistical results are unchanged.",
            'cost_known_common_source_ids':[x['source']['source_id'] for x in prepared if x['source']['source_id'] in complete_ids],
            'populations':populations,'source_rows':source_rows,
            'limitations':['Cost-known domains exclude unknown historical extraction, not zero-fill it.',
                          'N10 cost-stopped inclusion probabilities are only approximately equal.',
                          'H2 N14 subset is an availability restriction, not a random transfer sample.',
                          'No compute-matched AS control; an effort-only explanation is not causally identified.']}
