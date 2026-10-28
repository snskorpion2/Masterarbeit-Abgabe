"""EF1 logical arm costs and disjoint stage accounting from K2 original calls."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal


ARMS=('AS','AS+G','V1','V2')
BASE={'AS':'AS','AS+G':'AS','V1':'V1','V2':'V1'}
CONSTRUCTION={'Extraktion','Ergänzung','Schema'}
GUARD={'Prüffilter','Prueffilter'}


def sum_known(rows, key):
    values=[r.get(key) for r in rows]
    known=[Decimal(str(v)) for v in values if v is not None]
    return {'known_subtotal':float(sum(known)) if known else None,
            'missing_rows':sum(v is None for v in values),
            'complete':bool(rows) and all(v is not None for v in values)}


def source_costs(calls, source_ids, planned_draws, *, frozen_source_roster=None):
    """Cost is complete only for a closed set of original per-call receipts.

    Reused base construction is expanded for each logical arm, while stage
    accounting below always counts the physical receipt only once.
    """
    selected=[]
    for r in calls:
        if r.get('stage') in GUARD and r.get('call_kind') not in {'not_executed','token_count_probe'}:
            if not r.get('source_id'):
                raise ValueError('Guard call has no source mapping')
            if (frozen_source_roster is not None and r.get('package')=='C1' and
                    r.get('population')=='Konfirmation' and r['source_id'] not in frozen_source_roster):
                raise ValueError('Confirmation guard source is outside the frozen source roster')
        if r.get('source_id') not in source_ids or r.get('package') not in {'B3','C1'}:
            continue
        if r.get('call_kind') in {'not_executed','token_count_probe'}:
            continue
        if 'pilot' in r.get('scope','').lower():
            continue
        selected.append(r)
    result=[]
    for sid in source_ids:
        for arm in ARMS:
            base=BASE[arm]
            construction=[r for r in selected if r['source_id']==sid and
                          r['package']=='B3' and r['arm']==base and r['stage'] in CONSTRUCTION]
            guard=[r for r in selected if r['source_id']==sid and
                   r['package']=='C1' and r['arm']==arm and r['stage'] in GUARD] if arm in {'AS+G','V2'} else []
            rr=construction+guard
            observed_draws={r.get('draw') for r in construction}
            expected={f'draw_{i}' for i in range(1,planned_draws[sid]+1)}
            expected_stages=('Extraktion','Ergänzung','Schema') if base=='V1' else ('Extraktion','Schema')
            stage_coverage=all(
                any(r.get('draw')==draw and r.get('stage')==stage for r in construction)
                for draw in expected for stage in expected_stages)
            guard_coverage=(arm not in {'AS+G','V2'} or all(any(r.get('draw')==draw for r in guard) for draw in expected))
            missing_cost=sum(r.get('known_cost') is None or r.get('cost_complete') is not True or
                             r.get('unknown_execution') is True or r.get('currency')!='USD' for r in rr)
            complete=bool(construction) and observed_draws==expected and stage_coverage and guard_coverage and missing_cost==0
            pt=sum_known(rr,'prompt_tokens'); ct=sum_known(rr,'completion_tokens')
            cp=sum_known(construction,'prompt_tokens'); cc=sum_known(construction,'completion_tokens')
            cost=sum_known(rr,'known_cost')
            count=sum_known(rr,'call_count')
            result.append({'source_id':sid,'arm':arm,'cost_usd':cost['known_subtotal'] if complete else None,
                           'known_cost_lower_bound_usd':cost['known_subtotal'],'cost_complete':complete,
                           'prompt_tokens':pt['known_subtotal'] if pt['complete'] else None,
                           'completion_tokens':ct['known_subtotal'] if ct['complete'] else None,
                           'construction_prompt_tokens':cp['known_subtotal'] if cp['complete'] else None,
                           'construction_completion_tokens':cc['known_subtotal'] if cc['complete'] else None,
                           'call_count':count['known_subtotal'] if count['complete'] else None,
                           'calls_known_subtotal':count['known_subtotal'],
                           'call_count_missing_rows':count['missing_rows'],
                           'source_draws_expected':sorted(expected),'source_draws_observed':sorted(v for v in observed_draws if v),
                           'stage_coverage':stage_coverage,'guard_coverage':guard_coverage,
                           'incomplete_cost_rows':missing_cost,
                           'construction_receipt_count':len(construction),'guard_receipt_count':len(guard)})
    return result


def stage_accounting(calls, *, source_ids=None):
    """Disjoint original calls, no base-arm replication and no currency conversion."""
    grouped=defaultdict(list);ids=set()
    for r in calls:
        if source_ids is not None and r.get('source_id') not in source_ids:
            continue
        rid=r.get('request_id') or r.get('receipt_id')
        if not rid or rid in ids:
            raise ValueError('Missing or duplicate K2 receipt identity')
        ids.add(rid)
        grouped[(r['package'],r.get('population'),r['arm'],r['stage'],r.get('currency'),r.get('pricing_scenario'))].append(r)
    result=[]
    for key,rr in sorted(grouped.items(),key=lambda v:str(v[0])):
        row=dict(zip(('package','population','arm','stage','currency','pricing_scenario'),key))
        row.update({'receipts':len(rr),'calls':sum_known(rr,'call_count'),'physical_POSTs':sum_known(rr,'physical_POSTs'),
                    'prompt_tokens':sum_known(rr,'prompt_tokens'),'completion_tokens':sum_known(rr,'completion_tokens'),
                    'known_cost':sum_known(rr,'known_cost'),
                    'request_elapsed_seconds':sum_known(rr,'elapsed_seconds'),
                    'stage_wall_seconds':None,
                    'time_note':'Summe einzelner Anfragedauern, soweit belegt; keine additive Wandzeit.',
                    'unknown_execution_rows':sum(r.get('unknown_execution') is True for r in rr)})
        result.append(row)
    return result
