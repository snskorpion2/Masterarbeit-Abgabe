"""Small deterministic SYNTHETIC native-format fixtures for D1 development.

24 sources/68 planned draws/eight cells, six whole occurrences per parent,
200 selected reference meanings (2,336 direct four-inventory judgments), and
600 N6 answer positions. No natural source, judgment, prediction or gold file
is loaded. Optional source/QA-block arguments contain identifiers only.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from hashlib import sha256
import json
import math
import random

from . import native


def _sha(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def _pin(value, name):
    encoded = json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    return {'path': 'withheld-artifact/4ed3d11fafc0700eb3ad' + name + '.json', 'bytes': len(encoded),
            'sha256': sha256(encoded).hexdigest()}


def _sources():
    return [{'source_id': 'SYNTHETIC-S%02d' % i,
        'cohort': 'SEALED4' if i < 4 else 'NEW20',
        'family': 'sealed' if i < 4 else 'wikipedia' if i < 16 else 'factbook',
        'draws': ['draw_1','draw_2'] if i < 4 else ['draw_1','draw_2','draw_3']} for i in range(24)]


def _blocks():
    questions = ['SYNTHETIC-Q%02d' % i for i in range(60)]
    sizes = [13] + [2]*9 + [1]*29
    blocks, start = [], 0
    for size in sizes:
        blocks.append(questions[start:start+size]); start += size
    return blocks


def _label(code, status):
    return native.support_label(code,status)


def _h3_category(rows, missing_value=None):
    n = len(rows)
    # One physical witness can represent two identical native contents;
    # multiplicity is retained independently in projected capacity below.
    found = sum(_sha(row['value'])!=missing_value for row in rows)
    return {'native_objects': n, 'projectable_objects': n, 'not_projectable_objects': 0,
        'direct_content_found': found, 'native_objects_without_complete_direct_content': n-found,
        'projectable_content_missing': n-found, 'H3_direct_content_fraction': found/n if n else None,
        'H3_direct_content_projectable_fraction': found/n if n else None,
        'raw_direct_content_found': found, 'raw_direct_content_fraction': found/n if n else None,
        'typed_direct_content_found': found, 'objects_changed_by_SDK_comparison': 0}


def build_native_fixture(seed=20261025, *, sources=None, qa_blocks=None):
    """Build only fictitious outcomes in the real interchange container shapes."""
    rng = random.Random(seed)
    sources = deepcopy(_sources() if sources is None else sources)
    qa_blocks = deepcopy(_blocks() if qa_blocks is None else qa_blocks)
    native.need(len(sources) == 24 and sum(len(s['draws']) for s in sources) == 68,
                'Synthetic design needs 24 sources / 68 draws')
    question_ids = [qid for block in qa_blocks for qid in block]
    native.need(len(qa_blocks) == 39 and len(question_ids) == len(set(question_ids)) == 60,
                'Synthetic QA needs a 39-block / 60-ID partition')
    cells, originals, parent_rows, proof_values, proofs = [], [], {}, {}, []
    c5_cells = []
    for s_index, source in enumerate(sources):
        sid = source['source_id']
        for draw in source['draws']:
            for arm in ('AS','V1'):
                parent = 'syn-parent-' + _sha([sid,draw,arm])[:24]
                rows = []
                for i, category in enumerate(('EE','EE','EV','EV','VV','VV')):
                    uid = 'syn-unit-' + _sha([sid,draw,arm,i])
                    chance = 0.61 + (s_index % 7)*0.035 + (0.07 if arm == 'V1' else 0)
                    roll = rng.random()
                    code = ('supported' if roll < chance else 'ambiguous' if roll < chance+0.07 else 'unsupported')
                    status = 'valid'
                    if status != 'valid': code = None
                    label = _label(code,status)
                    semantic_index = 0 if i == 1 else i  # distinct occurrences, exact duplicated EE meaning
                    value = ({'Event':'SYNTHETIC event '+str(i),'Entity':['SYNTHETIC a','SYNTHETIC b']}
                             if category == 'EV' else {'Head':'SYNTHETIC a '+str(semantic_index),
                                'Relation':'SYNTHETIC relation','Tail':'SYNTHETIC b'})
                    row = {'parent_id':parent,'cell_id':parent,'source_id':sid,'population':source['cohort'],
                        'arm':arm,'draw':draw,'unit_id':uid,'category':category,'value':value,
                        'raw_code':code,'label':label,'measurement_status':status,
                        'primary_numeric':int(label=='supported'),'H1_bucket':'S' if label=='supported' else 'F' if label=='not_supported' else 'M',
                        'unknown_execution':None if status=='technical_missing' else False}
                    rows.append(row); originals.append(deepcopy(row))
                kept = [r for r in rows if r['category']=='EV' or rng.random() < (0.985 if r['label']=='supported' else 0.45)]
                filtered = 'AS_G' if arm == 'AS' else 'V2'
                for inventory_arm, selected in ((arm,rows),(filtered,kept)):
                    parent_rows[sid,draw,inventory_arm] = selected
                    for suffix, export in (('ORIGINAL','original_as_digraph'),('ROW','row_exact')):
                        cell = inventory_arm+'_'+suffix
                        subset = {'parent_id':parent,'cell':cell,'retained_occurrence_ids':[r['unit_id'] for r in selected]}
                        proof_pin = _pin(subset,'proof-'+_sha([sid,draw,cell])) if inventory_arm==filtered else None
                        if proof_pin:
                            proof_values[proof_pin['sha256']] = subset
                            proofs.append({'parent_id':parent,'source_id':sid,'input_arm':arm,'draw':draw,
                                'cell':cell,'proof_pin':proof_pin,'consumer_manifest_pin':_pin({},'consumer'),
                                'status_pin':_pin({},'status')})
                        labels = [{**deepcopy(r),'evaluated_parent_id':parent,'target_cell':cell,
                                   'inherited_without_new_evaluation':True} for r in selected]
                        cells.append({'parent_id':parent,'cell_id':parent,'source_id':sid,'population':source['cohort'],
                            'arm':arm,'draw':draw,'target_cell':cell,'status':'inherited','labels':labels,
                            'occurrence_count':len(labels),'subset_proof_pin':proof_pin,
                            'retained_statement_inventory_empty':not labels})
                        projection_n = sum(2 if r['category']=='EV' else 1 for r in selected)
                        retained = max(0,projection_n-(1 if export=='original_as_digraph' and projection_n else 0))
                        duplicates = len(selected)-len({_sha(r['value']) for r in selected})
                        missing = projection_n-retained
                        missing_value = _sha(selected[0]['value']) if missing and not duplicates else None
                        categories = {category:_h3_category([r for r in selected if r['category']==category],missing_value)
                                      for category in ('EE','EV','VV')}
                        n = len(selected); found = sum(v['direct_content_found'] for v in categories.values())
                        categories['ALL'] = {'native_objects':n,'projectable_objects':n,'not_projectable_objects':0,
                            'direct_content_found':found,'H3_direct_content_fraction':found/n if n else None,
                            'native_objects_without_complete_direct_content':n-found,
                            'projectable_content_missing':n-found,
                            'H3_direct_content_projectable_fraction':found/n if n else None,
                            'raw_direct_content_found':found,'raw_direct_content_fraction':found/n if n else None,
                            'typed_direct_content_found':found,'objects_changed_by_SDK_comparison':0}
                        capacity = {'expected_occurrences':projection_n,'retained_occurrences':retained,
                            'missing_occurrences':missing,'occurrence_fraction':retained/projection_n if projection_n else None,
                            'expected_distinct_contents':projection_n-duplicates,
                            'missing_distinct_contents':max(0,missing-duplicates),
                            'duplicate_occurrences_in_input':duplicates,
                            'missing_additional_identical_occurrences':min(missing,duplicates),
                            'missing_groups':([{'head_node':'synthetic-node-a','head':'SYNTHETIC a',
                                'relation':'SYNTHETIC relation','tail_node':'synthetic-node-b','tail':'SYNTHETIC b',
                                'expected':1+min(1,duplicates),'observed':min(1,duplicates),'missing':1}] if missing else []),
                            'allocation_boundary':'Capacities count projected occurrences, not whole-native-object matching.'}
                        native_to_csv = {**deepcopy(capacity),'retained_occurrences':projection_n,
                            'missing_occurrences':0,'occurrence_fraction':1.0 if projection_n else None,
                            'missing_distinct_contents':0,'missing_additional_identical_occurrences':0,'missing_groups':[]}
                        typed_labels = set()
                        for r in selected:
                            if r['category']=='EV':
                                typed_labels.add(('event',r['value']['Event']))
                                typed_labels.update(('entity',label) for label in r['value']['Entity'])
                            else:
                                namespace = 'entity' if r['category']=='EE' else 'event'
                                typed_labels.update((namespace,r['value'][endpoint]) for endpoint in ('Head','Tail'))
                        c5_cells.append({'source_id':sid,'draw':int(draw.split('_')[-1]),'arm':inventory_arm,
                            'export':export,'status':'complete','categories':categories,
                            'projected_occurrence_capacity':capacity,'object_details':[],
                            'unprojectable_projection_slots':0,
                            'graph_Relation_edges_with_missing_label_attributes':0,
                            'SDK_label_ID_alias_groups':{},
                            'CSV_stages':{'csv_rows':projection_n,'csv_to_graph':deepcopy(capacity),
                                'native_to_csv':native_to_csv,
                                'parallel_endpoint_pairs_with_distinct_relations':0,
                                'parallel_distinct_relation_contents_missing':0,
                                'boundary':'SYNTHETIC native CSV diagnostics; not empirical.'},
                            'nodes':{'distinct_native_typed_label_values':len(typed_labels),
                                'typed_values_with_absent_node_binding':0,
                                'typed_values_with_wrong_stored_namespace':0,
                                'typed_values_with_unrepresented_namespace':0,
                                'typed_values_with_different_stored_label':0,
                                'same_name_typed_node_merge_groups':0,
                                'same_name_typed_values_pooled_beyond_one':0,
                                'all_bound_typed_value_collision_groups':[],
                                'raw_labels_collapsed_by_SDK_display_groups':0,
                                'additional_same_label_source_context_values':0,
                                'wrong_namespace_details':[],'label_binding_mismatch_details':[],
                                'boundary':'SYNTHETIC technical label diagnostics; not real identity.'},
                            'EV':{'native_EV_objects':2,
                                'EV_objects_without_a_complete_nonempty_participant_projection':0,
                                'EV_objects_with_exact_operational_participant_set':categories['EV']['direct_content_found'],
                                'EV_objects_with_exact_operational_participant_multiset':categories['EV']['direct_content_found'],
                                'EV_objects_in_shared_event_node_groups':0,'shared_event_node_groups':0,
                                'distinct_EV_values_pooled_beyond_one':0,
                                'whole_native_EV_payload_recovery_verified':False,
                                'whole_native_EV_payload_recovery_fraction':None,
                                'boundary':'SYNTHETIC operative EV projection; no whole-payload recovery.'},
                            'content_capacity_boundary':'SYNTHETIC content and capacity have separate denominators.'})
    # One failed six-case group scattered across parents by the blinded roster.
    # Its six missing judgments remain nullable in every inherited view.
    missing_units = {r['unit_id'] for r in rng.sample(originals,6)}
    for row in [*originals, *(r for cell in cells for r in cell['labels'])]:
        if row['unit_id'] in missing_units:
            row.update(raw_code=None,label=None,measurement_status='technical_missing',
                       primary_numeric=0,H1_bucket='M',unknown_execution=True)
    references, c3_records, c3_sources = [], [], []
    fresh_index = 0
    for s_index, source in enumerate(sources):
        sealed = source['cohort'].upper() in ('SEALED4','SEALED')
        count = 4 if sealed else 10 if fresh_index < 4 else 9
        if not sealed: fresh_index += 1
        ids = ['syn-obligation-%02d' % i for i in range(count)]
        references.extend({'source_id':source['source_id'],'obligation_id':oid} for oid in ids)
        c3_sources.append({'source_id':source['source_id'],'reference_ids':ids,'R':count,
                          'planned_draws':list(source['draws']),'arms':{}})
        for draw in source['draws']:
            for arm in native.ARMS:
                for oid in ids:
                    roll = rng.random(); base = .69 + (s_index%5)*.025 + (.05 if arm in ('V1','V2') else 0)
                    code = ('retained' if roll < base else 'partially_retained' if roll < base+.1
                            else 'undetermined' if roll < base+.15 else 'not_retained')
                    status = 'technical_missing' if rng.random()<.015 else 'valid'
                    if status != 'valid': code = None
                    retained_rows = parent_rows[source['source_id'],draw,arm]
                    observed = {'source_id':source['source_id'],'draw':draw,'arm':arm,'obligation_id':oid,
                        'raw_code':code,'status':status,'witness_unit_ids':[retained_rows[0]['unit_id']] if code=='retained' else [],
                        'retained_parts':['SYNTHETIC retained aspect'] if code=='retained' else [],
                        'missing_or_altered_aspects':[] if code=='retained' else ['SYNTHETIC nonretained aspect'],
                        'absence_search_complete':code=='not_retained'}
                    c3_records.append({**{k:observed[k] for k in ('source_id','draw','arm','obligation_id','raw_code','status')},
                        'scoring_state':'retained' if code=='retained' else 'technical_missing' if status!='valid' else 'partial' if code=='partially_retained' else 'semantic_unclear' if code in ('undetermined','not_assessable') else 'absent',
                        'primary_score':int(code=='retained'),'observation_present':True,
                        'observation':observed,'unobserved_reason':None})
    qa_cells = {}
    def scores(cell):
        rows = []
        for i,qid in enumerate(question_ids):
            missing = rng.random()<.012
            value = (0.25 + rng.random()*.65 + (.04 if cell in ('V2_ROW','V1_ROW') else 0))
            f1 = min(1.,value); em = int(rng.random() < f1*.7)
            if em: f1 = 1.0
            rows.append({'question_id':qid,'status':'technical_missing' if missing else 'complete',
                'response_status':'technical_missing' if missing else 'complete',
                'answer':None if missing else 'SYNTHETIC answer', 'em':None if missing else em,
                'f1':None if missing else f1})
        summaries = {}
        for metric in ('em','f1'):
            observed = [row[metric] for row in rows if row[metric] is not None]
            total = sum(observed); missing = 60-len(observed)
            summaries[metric] = {'Q':60,'observed':len(observed),'missing':missing,
                'point':total/60 if missing==0 else None,'lower':total/60,'upper':(total+missing)/60,
                'primary_estimable':missing==0}
        return {'protocol':'C6-official-musique-fixed-Q60-scoring-v1','Q':60,
                'question_roster_sha256':_sha(question_ids),'per_question':rows,**summaries,
                'primary_estimable':summaries['f1']['primary_estimable']}
    for cell in native.CELLS:
        qa_cells[cell] = {'metadata':{'synthetic':True},'worker_terminal_pins':[],
                          'worker_ticket_pins':[],'scores':scores(cell)}
    controls = {mode:{'scores':scores(mode)} for mode in ('empty','gold')}
    c6 = {'protocol':'C6-N5-N6-bound-offline-H4-results-v1','synthetic':True,
        'construction_classification':'H4_POST_G2_CONSTRUCTION_AMENDMENT_N5','original_G2_confirmation':False,
        'evaluation_scope_classification':'H4_POST_G2_SECONDARY_ENDPOINT_REDUCTION_N6',
        'answer_position_count':600,'secondary_passage_performed':False,'cells':qa_cells,
        'worker_terminal_count':0,'inference_computed_here':False}
    by_stratum = defaultdict(list)
    for row in originals: by_stratum[row['arm'],row['category']].append(row)
    selection = random.Random(2026102409); selected = []
    strata = []
    for arm in ('AS','V1'):
        for category in ('EE','EV','VV'):
            group = sorted(by_stratum[arm,category],key=lambda r:r['unit_id'])
            selected.extend(selection.sample(group,25))
            strata.append({'arm':arm,'type':category,'population_count':len(group),'sample_count':25})
    selection.shuffle(selected)
    items, annotations = [], []
    dataset = 'd-'+_sha([seed,'dataset'])[:32]; packet_sha = _sha([r['unit_id'] for r in selected])
    for row in selected:
        item = 'i-'+_sha(row['unit_id'])[:32]
        N = len(by_stratum[row['arm'],row['category']]); label = row['label']
        items.append({'item_id':item,'original_id':row['unit_id'],'arm':row['arm'],'type':row['category'],
            'c2_status':'rated' if row['measurement_status']=='valid' else 'technical_failure',
            'c2_label':label,'inclusion_probability':25/N,'weight':N/25})
        human = label if label is not None and rng.random()<.8 else rng.choice(native.LABELS)
        if rng.random()<.025: human = None
        annotations.append({'item_id':item,'label':human,'comment':'SYNTHETIC annotation'})
    key = {'format':'c7-private-key-1','dataset_id':dataset,'packet_sha256':packet_sha,
        'population_sha256':_sha([r['unit_id'] for r in originals]),'cohort':'synthetic_test',
        'seed':2026102409,'requested_size':150,'selected_count':150,'population_count':len(originals),
        'strata':strata,'items':items}
    c7 = {'key':key,'annotations':{'format':'c7-human-annotations-1','dataset_id':dataset,
        'packet_sha256':packet_sha,'annotations':annotations}}
    second = random.Random(2026102410); core_ids = set()
    audit_strata = defaultdict(list)
    for row in originals:
        audit_strata[row['parent_id'],row['category']].append(row)
    for group in audit_strata.values():
        core_ids.update(r['unit_id'] for r in second.sample(sorted(group,key=lambda r:r['unit_id']),math.ceil(.15*len(group))))
    represented_sources = {row['source_id'] for row in originals if row['unit_id'] in core_ids}
    grok = []
    for row in originals:
        guard_arm = 'AS_G' if row['arm']=='AS' else 'V2'
        removed = row['source_id'] in represented_sources and row['unit_id'] not in {
            r['unit_id'] for r in parent_rows[row['source_id'],row['draw'],guard_arm]}
        if row['unit_id'] not in core_ids and not removed: continue
        code = row['raw_code'] if rng.random()<.85 else rng.choice(('supported','unsupported','ambiguous'))
        grok.append({'unit_id':row['unit_id'],'c2_code':row['raw_code'],
            'c2_status':'rated' if row['measurement_status']=='valid' else 'technical_missing',
            'grok_code':code,'grok_status':'rated' if code is not None else 'missing',
            'in_base_sample':row['unit_id'] in core_ids,'in_removal_panel':removed,
            'arm':row['arm'],'category':row['category'],'stratum':row['arm']+'-'+row['category'],
            'weight':len(audit_strata[row['parent_id'],row['category']])/
                     math.ceil(.15*len(audit_strata[row['parent_id'],row['category']]))})
    effort = [{'package':name,'source_id':None,'draw':None,'cell':None,
        'call_count':amount,'physical_POSTs':None,'prompt_tokens':amount*9000,'completion_tokens':amount*400,
        'cache_write_tokens':None,'cache_read_tokens':0,'known_cost':str(round(amount*.009,6)),
        'currency':currency,'cost_complete':False,'unknown_execution':None}
        for name,amount,currency in (('B3',408,'USD'),('C1',68,'USD'),('C2',136,'EUR'),('C3',414,'EUR'),('C6',600,'USD'))]
    return {'protocol':'D1-synthetic-native-fixture-v1','synthetic':True,
        'synthetic_label':'SYNTHETIC ONLY - no empirical thesis result', 'seed':seed,
        'sources':sources,'QA_blocks':qa_blocks,'question_ids':question_ids,
        'C1':{'protocol':'C1-H1-retained-occurrence-proof-index-v1',
              'configuration_pin':_pin({},'configuration'),'original_catalog_pin':_pin({},'catalog'),
              'proofs':proofs,'proof_count':len(proofs),
              'new_model_calls':0,'new_evaluations':0,'new_projections':0,'IDs_recomputed':False},
        'C1_proof_values':proof_values,
        'C2':{'protocol':'C2-occurrence-and-cell-label-export-oct24-v1','private_only':True,
              'original_occurrences':len(originals),'occurrence_labels':originals,'cells':cells,'jobs':[]},
        'C3':{'protocol':'C3-fixed-roster-source-equal-H2-summary:oct24-v1','closed':True,
              'records':c3_records,'sources':c3_sources,'coverage':{'planned':len(c3_records)}},
        'C5':{'protocol':'native-direct-edge-H3-export-measurement:v1','cells':c5_cells},
        'C6':c6,'C6_controls':controls,'C7':c7,'C4':grok,'effort':effort,
        'K2_effort': build_k2_effort_fixture(),
        'amendments':{'N2_H3':'separate unmodified A6 fields and denominators',
            'N5':'post-G2 construction change, not original G2 confirmation',
            'N6':'secondary passage route not performed; 600 answer positions, not POSTs'}}


def build_k2_effort_fixture():
    """Invented meters matching K2's schema, not actual prices or effort."""
    from .efficiency import K2_COLUMNS
    rows = []
    for arm, stage, prompt, output, cost in (
            ('AS', 'Extraktion', 9000, 900, '.99'), ('AS', 'Schema', 1000, 100, '.11'),
            ('V1', 'Extraktion', 10000, 1000, '1.10'),
            ('V1', 'Ergänzung', 8000, 800, '.88'), ('V1', 'Schema', 2000, 200, '.22'),
            ('AS+G', 'Prüffilter', 2000, 200, '.22'), ('V2', 'Prüffilter', 3000, 300, '.33')):
        guard = stage == 'Prüffilter'
        row = dict.fromkeys(K2_COLUMNS)
        row.update(package='C1' if guard else 'B3', population='Konfirmation', arm=arm,
            stage=stage, scope='synthetic_only',
            model='synthetic_guard' if guard else 'synthetic_constructor',
            pricing_scenario='synthetic_guard_list' if guard else 'synthetic_base_list',
            call_kind='generation', status='abgeschlossen', snapshot_UTC='2000-01-01T00:00:00Z',
            calls_known=1, calls_unknown=0, pending_positions=0, call_count=1,
            physical_POSTs=1, physical_POSTs_known_subtotal=1,
            prompt_tokens_known=prompt, output_tokens_known=output, usage_missing=0,
            cache_read_tokens_known=0, cache_write_tokens_known=0,
            currency='USD', cost_known=cost, cost_missing=0, cost_complete=True,
            reserved_or_held_cost='0', invoice_verified=False, used_by_arms=arm,
            notes='SYNTHETIC meters, no empirical price or efficiency evidence',
            receipt_set_sha256=sha256(('synthetic-K2-'+arm+'-'+stage).encode()).hexdigest())
        rows.append(row)
    return rows


def build_fixture(seed=20261025, *, sources=None, qa_blocks=None):
    return native.normalize_native(build_native_fixture(seed,sources=sources,qa_blocks=qa_blocks))
