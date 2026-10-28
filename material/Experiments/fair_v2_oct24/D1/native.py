"""Pure in-memory D1 projections of existing native interchange formats.

No file reader, provider, model, source reconstruction or natural-data loader.
Native: C2 occurrence/cell export, C3 aggregate records, A6 cells, C6 N5/N6
``cells[cell].scores.per_question``, C7 private key + sealed annotations, and
optional C4 agreement input records. C1 is the positive retained-proof index.

Normalized contract:
sources: source_id/cohort/family/draws; cells: the fixed eight names.
H1: source_id/draw/cell/unit_id/category/raw_code/measurement_status/value.
H1_inventories: source_id/draw/cell/occurrence_count(None if unknown)/completed.
H2: source_id/draw/cell/obligation_id/raw_code/status (two dependent export
views of each of the FOUR directly assessed inventories, not new judgments).
H2_roster: source_id/obligation_id; QA: question_id/cell/context_mode/observed/
f1/em; QA_blocks: lists of fixed IDs. H3 keeps the original A6 ``categories``
and ``projected_occurrence_capacity`` names and their DIFFERENT denominators.
H3.native_diagnostics also keeps the original A6 CSV/node/EV/object diagnostic
fields, with explicit field availability; it does not invent parent coverage.
agreement: human/grok rows with nullable labels and design weights. effort:
original nullable meters/currency, with no zero-filling or currency conversion.
"""
from copy import deepcopy
import math

CELLS = ('AS_ORIGINAL', 'AS_ROW', 'AS_G_ORIGINAL', 'AS_G_ROW',
         'V1_ORIGINAL', 'V1_ROW', 'V2_ORIGINAL', 'V2_ROW')
ARMS = ('AS', 'AS_G', 'V1', 'V2')
LABELS = ('supported', 'not_supported', 'unclear')
NEGATIVE = frozenset(('contradicted', 'unsupported', 'mixed', 'not_in_source', 'not_supported'))
UNCLEAR = frozenset(('ambiguous', 'undetermined', 'not_assessable', 'unclear'))
RETENTION = frozenset(('retained', 'partially_retained', 'not_retained', 'undetermined', 'not_assessable'))
JUDGMENT_STATUSES = frozenset(('valid', 'rated', 'missing', 'technical_failure', 'technical_missing',
                             'unknown_execution', 'pending', 'not_selected'))
QA_MISSING_STATUSES = frozenset(('technical_missing', 'unknown_execution', 'timeout',
                                'truncated', 'unparsed', 'missing'))
A6_DIAGNOSTIC_FIELDS = ('CSV_stages', 'nodes', 'EV', 'object_details',
    'unprojectable_projection_slots', 'graph_Relation_edges_with_missing_label_attributes',
    'SDK_label_ID_alias_groups', 'content_capacity_boundary', 'input_pins', 'error_class', 'error')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def support_label(code, status):
    need(status in JUDGMENT_STATUSES, 'Unknown native judgment status')
    need(code is None or code in NEGATIVE | UNCLEAR | {'supported', 'failed', 'not_judged'},
         'Unknown native support code')
    if status not in ('valid', 'rated') or code in (None, 'failed', 'not_judged'):
        return None
    return 'supported' if code == 'supported' else 'not_supported' if code in NEGATIVE else 'unclear'


def _identity(row, sources):
    source, draw = row['source_id'], row['draw']
    if type(draw) is int:
        need(draw > 0, 'Positive A6 draw number required')
        draw = 'draw_' + str(draw)
    need(source in sources and draw in sources[source]['draws'], 'Foreign source/draw')
    return source, draw


def _metric(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _c2(value, sources):
    need(type(value) is dict and value.get('protocol')=='C2-occurrence-and-cell-label-export-oct24-v1'
         and type(value.get('cells')) is list, 'C2 native cell-label export required')
    rows, inventories, seen_cells, owners = [], [], set(), {}
    sampling = value.get('sampling')
    membership, selected_groups = None, set()
    if sampling is not None:
        need(type(sampling) is dict and sampling.get('protocol') == 'C2-N10-budget-prefix-sampling-v1',
             'Unknown C2 sampling metadata')
        groups, selected = sampling.get('groups'), sampling.get('selected_group_ids')
        need(type(groups) is list and type(selected) is list,
             'Explicit N10 original groups and selected prefix required')
        membership = {uid: group['group_id'] for group in groups for uid in group['unit_ids']}
        selected_groups = set(selected)
    for cell in value['cells']:
        sid, draw = _identity(cell, sources)
        name = cell['target_cell']
        key = sid, draw, name
        need(name in CELLS and key not in seen_cells, 'Foreign/duplicate C2 cell')
        seen_cells.add(key)
        complete = cell['status'] == 'inherited'
        need(cell['status'] in ('inherited', 'pending_subset_proof'), 'Unknown C2 cell status')
        labels = cell.get('labels')
        if complete:
            need(type(labels) is list and cell['occurrence_count'] == len(labels), 'C2 inventory count mismatch')
        else:
            need(labels is None and cell.get('occurrence_count') is None, 'Unknown C2 inventory must stay nullable')
        inventories.append({'source_id': sid, 'draw': draw, 'cell': name,
            'occurrence_count': len(labels) if complete else None, 'completed': complete,
            'status': cell['status'], 'parent_id': cell.get('parent_id')})
        seen_units = set()
        for row in labels or ():
            uid = row['unit_id']
            need(type(uid) is str and uid not in seen_units and row['source_id'] == sid
                 and row['draw'] == draw and row['category'] in ('EE', 'EV', 'VV'), 'C2 occurrence owner mismatch')
            seen_units.add(uid)
            status, raw = row['measurement_status'], row.get('raw_code')
            need(status in ('valid', 'technical_missing') or status == 'not_selected' and membership is not None,
                 'Unknown C2 measurement status')
            if membership is not None:
                need(uid in membership, 'N10 row is absent from original group roster')
                selected = membership[uid] in selected_groups
                need((selected and status != 'not_selected') or
                     (not selected and status == 'not_selected' and raw is None),
                     'N10 selection status must match the original prefix, not the observed answer status')
            need(status != 'valid' or raw not in (None, 'failed', 'not_judged'),
                 'Valid C2 judgment requires semantic raw code')
            canonical = support_label(raw, status)
            if 'label' in row:
                need(row['label'] == canonical, 'C2 canonical label disagreement')
            owner = sid, draw, row['category'], row.get('arm'), row.get('parent_id'), raw, status
            need(uid not in owners or owners[uid] == owner, 'C2 inherited occurrence identity/judgment changed')
            owners[uid] = owner
            rows.append({'source_id': sid, 'draw': draw, 'cell': name, 'unit_id': uid,
                'category': row['category'], 'raw_code': raw, 'measurement_status': status,
                'label': canonical, 'value': deepcopy(row.get('value')),
                'unknown_execution': row.get('unknown_execution'), 'parent_arm': row.get('arm'),
                'parent_id': row.get('parent_id')})
            if membership is not None:
                rows[-1]['selection_status'] = 'selected' if selected else 'not_selected'
    expected = {(sid, draw, cell) for sid, source in sources.items() for draw in source['draws'] for cell in CELLS}
    need(seen_cells == expected, 'C2 needs every planned cell, unknown cells explicit')
    by_key = {(c['source_id'],c['draw'],c['target_cell']):c for c in value['cells']}
    for sid, source in sources.items():
        for draw in source['draws']:
            for arm in ARMS:
                original, row_exact = (by_key[sid,draw,arm+'_'+suffix] for suffix in ('ORIGINAL','ROW'))
                need(original['status']==row_exact['status'] and
                     original.get('occurrence_count')==row_exact.get('occurrence_count') and
                     (None if original['labels'] is None else [r['unit_id'] for r in original['labels']])==
                     (None if row_exact['labels'] is None else [r['unit_id'] for r in row_exact['labels']]),
                     'C2 paired export views must share the same inventory/status/ordered units')
    return rows, inventories


def _c3(value, sources):
    need(type(value) is dict and value.get('protocol')=='C3-fixed-roster-source-equal-H2-summary:oct24-v1'
         and type(value.get('records')) is list and type(value.get('sources')) is list,
         'C3 fixed-roster aggregate required')
    roster, planned = [], {}
    for source in value['sources']:
        sid = source['source_id']
        need(sid in sources and sid not in planned and source['planned_draws'] == sources[sid]['draws'],
             'C3 fixed source/draw roster mismatch')
        ids = source['reference_ids']
        need(type(ids) is list and bool(ids) and len(ids) == len(set(ids)), 'C3 distinct fixed references required')
        planned[sid] = set(ids)
        roster.extend({'source_id': sid, 'obligation_id': ident} for ident in ids)
    need(set(planned) == set(sources), 'C3 reference roster missing source')
    rows, seen = [], set()
    for record in value['records']:
        sid, draw = _identity(record, sources)
        arm, obligation = record['arm'], record['obligation_id']
        key = sid, draw, arm, obligation
        need(arm in ARMS and obligation in planned[sid] and key not in seen, 'C3 foreign/duplicate reference case')
        seen.add(key)
        code, status = record.get('raw_code'), record['status']
        need(code is None or code in RETENTION, 'Unknown C3 retention code')
        need(status == 'valid' or status in ('technical_missing', 'technical_failure', 'format_invalid',
             'unknown_execution', 'failed', 'not_judged', 'pending'), 'Unknown C3 status')
        if status == 'valid':
            need(code in RETENTION, 'Valid C3 judgment requires raw code')
        for suffix in ('ORIGINAL', 'ROW'):
            rows.append({'source_id': sid, 'draw': draw, 'cell': arm + '_' + suffix,
                'obligation_id': obligation, 'raw_code': code, 'status': status,
                'dependent_export_projection': True,
                'direct_inventory_arm': arm})
    expected = {(sid, draw, arm, oid) for sid, source in sources.items() for draw in source['draws']
                for arm in ARMS for oid in planned[sid]}
    need(seen == expected, 'C3 needs every fixed case, missing cases explicit')
    return rows, roster


def _c5(value, sources):
    need(type(value) is dict and value.get('protocol')=='native-direct-edge-H3-export-measurement:v1'
         and type(value.get('cells')) is list, 'A6 measurement cells required')
    result, seen = [], set()
    for row in value['cells']:
        sid, draw = _identity(row, sources)
        export = row['export']
        need(export in ('original_as_digraph', 'row_exact'), 'Exact A6 export identity required')
        name = row['arm'] + ('_ORIGINAL' if export == 'original_as_digraph' else '_ROW')
        key = sid, draw, name
        need(name in CELLS and key not in seen, 'Foreign/duplicate A6 cell')
        seen.add(key)
        categories, capacity = row.get('categories'), row.get('projected_occurrence_capacity')
        need(row['status'] in ('complete','unavailable'), 'Unknown A6 measurement status')
        if row['status'] == 'complete':
            need(type(categories) is dict and set(categories) == {'EE', 'EV', 'VV', 'ALL'}
                 and type(capacity) is dict, 'Complete A6 fields required')
            for category in categories.values():
                n, found = category['native_objects'], category['direct_content_found']
                need(type(n) is int and type(found) is int and 0 <= found <= n, 'Invalid A6 native-object counts')
                need(category['H3_direct_content_fraction'] == (found/n if n else None), 'A6 content fraction mismatch')
            n, found = capacity['expected_occurrences'], capacity['retained_occurrences']
            need(type(n) is int and type(found) is int and 0 <= found <= n
                 and capacity['missing_occurrences'] == n-found
                 and capacity['occurrence_fraction'] == (found/n if n else None), 'Invalid A6 projection capacity')
        else:
            need(categories is None and capacity is None, 'Unavailable A6 values must stay None')
        result.append({'source_id': sid, 'draw': draw, 'cell': name, 'status': row['status'],
            'categories': deepcopy(categories), 'projected_occurrence_capacity': deepcopy(capacity),
            'native_diagnostics': {field:deepcopy(row.get(field)) for field in A6_DIAGNOSTIC_FIELDS},
            'native_diagnostic_availability': {field:{
                'available':field in row and row[field] is not None and
                    (row['status']=='complete' or field in ('error_class','error','input_pins')),
                'reason':None if field in row and row[field] is not None and
                    (row['status']=='complete' or field in ('error_class','error','input_pins')) else
                    'native_measurement_unavailable' if row['status']=='unavailable' else
                    'not_provided_by_native_export'} for field in A6_DIAGNOSTIC_FIELDS},
            'full_original_unfiltered_parent_coverage': {'available':False,'value':None,
                'reason':'A6 measures the current cell inventory; no parent-coverage metric is supplied.',
                'unfiltered_parent_measurement_ref': {'source_id':sid,'draw':draw,
                    'cell':('AS' if row['arm'] in ('AS','AS_G') else 'V1')+
                           ('_ORIGINAL' if export=='original_as_digraph' else '_ROW')}},
            'whole_native_statement_multiplicity_ratio': None,
            'whole_native_statement_multiplicity_ratio_identified': False,
            'EV_whole_native_payload_recovery_verified': False})
    need(seen == {(sid, draw, cell) for sid,s in sources.items() for draw in s['draws'] for cell in CELLS},
         'A6 requires full planned cells, missing cells explicit')
    return result


def _c6(value, question_ids, controls=None):
    need(type(value) is dict and value.get('protocol')=='C6-N5-N6-bound-offline-H4-results-v1'
         and set(value['cells']) == set(CELLS), 'C6 all eight cell score containers required')
    result = []
    def add(scores, name, mode):
        need(scores['protocol'] == 'C6-official-musique-fixed-Q60-scoring-v1'
             and scores['Q'] == 60 and type(scores['per_question']) is list,
             'C6 native fixed Q60 scores required')
        seen = set()
        for row in scores['per_question']:
            qid = row['question_id']
            need(qid in question_ids and qid not in seen, 'C6 foreign/duplicate question')
            seen.add(qid)
            need(row['status'] in QA_MISSING_STATUSES | {'complete'}, 'Unknown C6 scored status')
            observed = row['status'] == 'complete'
            if observed:
                need(_metric(row['f1']) and row['em'] in (0,1) and type(row['em']) in (int,float), 'Observed official scores required')
                need(not row['em'] or row['f1'] == 1, 'Official exact match implies F1 one')
            else:
                need(row['f1'] is None and row['em'] is None, 'Missing QA must remain unknown, not zero')
            result.append({'question_id': qid, 'cell': name, 'context_mode': mode,
                'observed': observed, 'f1': row['f1'], 'em': row['em'], 'status': row['status'],
                'response_status': row.get('response_status')})
        need(seen == set(question_ids), 'C6 score container must retain all 60 questions')
    for name in CELLS:
        add(value['cells'][name]['scores'], name, 'graph')
    for mode, control in (controls or {}).items():
        need(mode in ('empty', 'gold'), 'N6 secondary passage endpoint must not be substituted')
        add(control['scores'], mode.upper(), mode)
    return result


def validate_current_author_binding(c7, *, c2_sha256):
    """Validate the already byte-bound current C7 author/end-export carrier.

    The explicit manifest loader verifies file bytes and supplies its actual C2
    hash here. Nominal labels are checked and preserved, never collapsed for
    normalization. The separately published binary statistic is used only for
    N8's already specified author qualification.
    """
    def valid_sha(value):
        return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
    need(type(c7) is dict and set(c7) == {'current_carrier', 'public_result'},
         'Explicit current C7 carrier and public aggregate required')
    carrier, public = c7['current_carrier'], c7['public_result']
    need(type(carrier) is dict and type(public) is dict and
         carrier.get('protocol') in ('C7-D1-private-original-nominal-agreement-v1',
                                     'C7-D1-private-author-agreement-v2') and
         public.get('protocol') == 'C7-explicit-author-Sol-analysis-v1' and
         public.get('status') == 'complete_author_analysis' and public.get('selected_count') == 150,
         'Current C7 author export protocol required; H12 is a separate study')
    origin = public.get('annotation_provenance', {})
    need(carrier.get('annotation_origin') == 'human_ui_input' and carrier.get('author_confirmed') is True
         and type(origin) is dict and origin.get('annotation_origin') == 'human_ui_input'
         and origin.get('author_confirmed') is True,
         'Current C7 requires direct author confirmation, not an export marker alone')
    provenance = public.get('provenance', {})
    need(type(provenance) is dict and valid_sha(c2_sha256)
         and carrier.get('C2_end_export_SHA256') == c2_sha256 == provenance.get('C2_end_export_SHA256'),
         'Current C7 carrier must bind the exact explicit C2 end export')
    annotation_sha = carrier.get('annotation_SHA256')
    need(valid_sha(annotation_sha) and annotation_sha == provenance.get('annotation_SHA256'),
         'Current C7 author annotation SHA differs from its public result')
    interface = public.get('D1_interface', {})
    need(type(interface) is dict, 'Current C7 public interface must be a mapping')
    if 'current_annotation_SHA256' in interface:
        need(interface['current_annotation_SHA256'] == annotation_sha,
             'Current C7 interface annotation binding differs')
    agreement = carrier.get('agreement')
    need(type(agreement) is dict and set(agreement) == {'human', 'human_strata'}
         and agreement['human_strata'] == [],
         'Current author carrier supplies unweighted nominal rows and no inferred strata')
    rows = agreement['human']
    need(type(rows) is list and len(rows) == 150, 'Current C7 requires all 150 original selected occurrences')
    seen, pairs = set(), 0
    for row in rows:
        need(type(row) is dict and type(row.get('unit_id')) is str and bool(row['unit_id'])
             and row['unit_id'] not in seen, 'Distinct current C7 global occurrence IDs required')
        seen.add(row['unit_id'])
        need(row.get('arm') in ('AS', 'V1') and row.get('category') in ('EE', 'EV', 'VV')
             and row.get('stratum') == row['arm'] + '-' + row['category'],
             'Current C7 nominal row arm/type/stratum differs')
        need('label' in row and 'reference_label' in row and row['label'] in (*LABELS, None)
             and row['reference_label'] in (*LABELS, None), 'Original current C7 nominal labels required')
        status, reference = row.get('status'), row.get('reference_status')
        need(status in ('rated', 'missing') and
             (row['label'] in LABELS if status == 'rated' else row['label'] is None),
             'Current C7 author status and nominal label disagree')
        need(reference in ('valid', 'rated', 'not_selected', 'technical_missing',
                           'technical_failure', 'missing', 'unknown_execution') and
             (row['reference_label'] in LABELS if reference in ('valid', 'rated') else row['reference_label'] is None),
             'Current C7 Sol missingness must retain its original status and null label')
        need(type(row.get('weight')) in (int, float) and row['weight'] == 1.
             and row.get('in_base_sample') is True,
             'Current C7 must not invent population weighting or omit selected rows')
        if 'in_removal_panel' in row:
            need(type(row['in_removal_panel']) is bool, 'Explicit current C7 removal-panel flag required')
        for field in ('source_id', 'parent_id', 'draw'):
            if field in row:
                need(type(row[field]) is str and bool(row[field]), 'Provided current C7 owner metadata must stay explicit')
        pairs += row['label'] is not None and row['reference_label'] is not None
    public_agreement = public.get('agreement', {})
    need(type(public_agreement) is dict, 'Current C7 public agreement must be a mapping')
    binary = public_agreement.get('binary', {})
    override, qualification = carrier.get('binary_N8_override'), public.get('N8_H1_qualification')
    need(type(binary) is dict and type(override) is dict and type(qualification) is dict,
         'Current C7 binary N8 aggregate and explicit qualification required')
    kappa = override.get('binary_n8_kappa')
    need(kappa is None or type(kappa) in (int, float) and math.isfinite(kappa) and -1 <= kappa <= 1,
         'Current C7 binary kappa must be finite or explicitly unknown')
    need(kappa == binary.get('kappa') == qualification.get('binary_n8_kappa')
         and type(binary.get('N_pair')) is int and binary['N_pair'] == pairs,
         'Current C7 binary aggregate differs from its original nominal pair roster')
    for value in (override, qualification):
        need(value.get('threshold_strictly_below') == .4 and value.get('rule_uses_binary_not_three_class') is True
             and value.get('H1_evaluator_dependent') is (kappa < .4 if kappa is not None else None),
             'Current C7 N8 must use the approved binary author threshold only')
    return {'binary_n8_kappa': kappa, 'pair_count': pairs,
            'source': 'C7_current_author_end_export', 'annotation_origin': 'human_ui_input',
            'author_confirmed': True, 'C2_end_export_SHA256': c2_sha256,
            'annotation_SHA256': annotation_sha}


def _agreement(c7, c4):
    human, grok, strata = [], [], []
    author_override = None
    if type(c7) is dict and ('current_carrier' in c7 or 'public_result' in c7):
        # The loader also calls this helper with the manifest's actual C2 pin.
        # Here we recheck internal agreement and preserve the nominal carrier.
        claimed = c7.get('public_result', {}).get('provenance', {}).get('C2_end_export_SHA256')
        author_override = validate_current_author_binding(c7, c2_sha256=claimed)
        human = deepcopy(c7['current_carrier']['agreement']['human'])
        strata = deepcopy(c7['current_carrier']['agreement']['human_strata'])
    elif c7 is not None:
        key, annotations = c7['key'], c7['annotations']
        need(key['format'] == 'c7-private-key-1' and annotations['format'] == 'c7-human-annotations-1'
             and key['dataset_id'] == annotations['dataset_id']
             and key['packet_sha256'] == annotations['packet_sha256'], 'C7 packet binding mismatch')
        ratings = {}
        for rating in annotations['annotations']:
            need(rating['item_id'] not in ratings and rating['label'] in (*LABELS,None), 'C7 invalid/duplicate rating')
            ratings[rating['item_id']] = rating['label']
        need(set(ratings) <= {r['item_id'] for r in key['items']}, 'C7 foreign rating')
        strata = deepcopy(key['strata'])
        designs = {(s['arm'],s['type']): s for s in strata}
        need(len(designs) == len(strata) == 6 and set(designs) ==
             {(a,c) for a in ('AS','V1') for c in ('EE','EV','VV')}, 'C7 six distinct design strata required')
        for design in strata:
            need(type(design['population_count']) is int and type(design['sample_count']) is int
                 and 0 <= design['sample_count'] <= design['population_count'], 'C7 invalid design counts')
        need(key['selected_count'] == len(key['items']) and
             len({r['item_id'] for r in key['items']}) == len(key['items']) and
             len({r['original_id'] for r in key['items']}) == len(key['items']), 'C7 distinct selected originals required')
        seen_strata = {stratum:0 for stratum in designs}
        for item in key['items']:
            design = designs[item['arm'],item['type']]
            need(design['sample_count'] > 0, 'C7 sampled item in empty design stratum')
            seen_strata[item['arm'],item['type']] += 1
            need(item['weight'] == design['population_count']/design['sample_count'] and
                 item['inclusion_probability'] == design['sample_count']/design['population_count'],
                 'C7 design weight mismatch')
            need(item['c2_status'] in ('rated','missing','technical_failure'), 'Unknown C7 reference status')
            need(item['c2_label'] in LABELS if item['c2_status'] == 'rated' else item['c2_label'] is None,
                 'C7 missing reference must remain nullable')
            reference = item['c2_label'] if item['c2_status'] == 'rated' else None
            label = ratings.get(item['item_id'])
            need(reference in (*LABELS,None), 'C7 invalid C2 nominal label')
            human.append({'unit_id': item['original_id'], 'reference_label': reference, 'label': label,
                'reference_status': item['c2_status'], 'status': 'rated' if label is not None else 'missing',
                'arm': item['arm'], 'category': item['type'], 'stratum': item['arm']+'-'+item['type'],
                'weight': item['weight'], 'in_base_sample': True, 'in_removal_panel': False})
        need(all(seen_strata[k] == designs[k]['sample_count'] for k in designs), 'C7 sample count differs from design')
    unique_grok = {}
    for item in c4 or ():
        uid = item['unit_id']
        need(type(uid) is str and bool(uid), 'C4 global unit_id required')
        base, removed = item.get('in_base_sample',True), item.get('in_removal_panel',False)
        need(type(base) is bool and type(removed) is bool, 'C4 explicit boolean panel flags required')
        row = {'unit_id': uid,
            'reference_label': support_label(item.get('c2_code'),item.get('c2_status','rated')),
            'label': support_label(item.get('grok_code'),item.get('grok_status','rated')),
            'reference_raw_code': item.get('c2_code'), 'raw_code': item.get('grok_code'),
            'reference_status': item.get('c2_status','rated'), 'status': item.get('grok_status','rated'),
            'arm': item.get('arm'), 'category': item.get('category'), 'stratum': item.get('stratum'),
            'weight': item.get('weight'), 'in_base_sample': base, 'in_removal_panel': removed}
        if uid in unique_grok:
            old = unique_grok[uid]
            need(all(old[k] == row[k] for k in row if k not in ('in_base_sample','in_removal_panel')),
                 'Conflicting duplicate C4 occurrence judgments')
            old['in_base_sample'] |= base
            old['in_removal_panel'] |= removed
        else:
            unique_grok[uid] = row
    grok = [unique_grok[uid] for uid in sorted(unique_grok)]
    result = {'human': human, 'grok': grok, 'human_strata': strata}
    if author_override is not None:
        result['human_binary_N8_override'] = author_override
    return result


def normalize_native(bundle):
    """Project supplied in-memory containers. This function never loads a path."""
    need(type(bundle) is dict and type(bundle.get('synthetic')) is bool, 'Explicit data-origin flag required')
    need(type(bundle.get('semantic_pairs',[])) is list, 'Explicit semantic-pair list required')
    need(type(bundle.get('construction_diagnostics',{})) is dict, 'Explicit construction diagnostics required')
    need(type(bundle.get('K2_effort', [])) is list, 'Explicit in-memory K2 effort rows required')
    source_list = deepcopy(bundle['sources'])
    sources = {row['source_id']: row for row in source_list}
    need(len(sources) == len(source_list) == 24 and sum(len(s['draws']) for s in source_list) == 68,
         'Fixed 24-source/68-draw metadata required')
    need(all(type(row['source_id']) is str and row['source_id'] and row['cohort'] in ('SEALED4','NEW20')
             and row['draws'] == (['draw_1','draw_2'] if row['cohort']=='SEALED4' else ['draw_1','draw_2','draw_3'])
             for row in source_list) and sum(row['cohort']=='SEALED4' for row in source_list)==4,
         'Frozen source cohort/draw allocation required')
    blocks = deepcopy(bundle['QA_blocks'])
    question_ids = [qid for block in blocks for qid in block]
    need(len(blocks) == 39 and len(question_ids) == len(set(question_ids)) == 60, 'Fixed 39-block/Q60 partition required')
    ordered_questions = bundle.get('question_ids',question_ids)
    need(type(ordered_questions) is list and len(ordered_questions)==60
         and set(ordered_questions)==set(question_ids), 'Question order must bind the same fixed Q60 roster')
    h1, inventories = _c2(bundle['C2'], sources)
    h2, references = _c3(bundle['C3'], sources)
    c1 = bundle.get('C1')
    bound_retained_cells = set()
    if c1 is not None:
        need(c1['protocol'] == 'C1-H1-retained-occurrence-proof-index-v1', 'C1 positive proof index required')
        proof_values = bundle.get('C1_proof_values',{})
        need(c1['proof_count'] == len(c1['proofs']), 'C1 proof count mismatch')
        proof_keys = set()
        for proof in c1['proofs']:
            need(proof['proof_pin']['sha256'] in proof_values, 'C1 pinned in-memory proof missing')
            value = proof_values[proof['proof_pin']['sha256']]
            key = proof['parent_id'],proof['cell']
            need(key not in proof_keys and value['parent_id']==proof['parent_id'] and value['cell']==proof['cell'],
                 'C1 proof owner mismatch or duplicate')
            proof_keys.add(key)
            matches = [c for c in bundle['C2']['cells'] if c['parent_id']==proof['parent_id']
                       and c['target_cell']==proof['cell']]
            need(len(matches)==1, 'C1 proof needs exactly one bound C2 cell')
            selected = matches[0]
            need(selected['source_id']==proof['source_id'] and selected['draw']==proof['draw']
                 and selected['arm']==proof['input_arm'], 'C1 proof source/draw/arm mismatch')
            need(selected['status'] == 'inherited' and value['retained_occurrence_ids'] == [r['unit_id'] for r in selected['labels']],
                 'C1 retained proof disagrees with C2 inherited view')
            bound_retained_cells.add((selected['source_id'],selected['draw'],selected['target_cell']))
    for inventory in inventories:
        derived = inventory['cell'].startswith(('AS_G_','V2_'))
        bound = (inventory['source_id'],inventory['draw'],inventory['cell']) in bound_retained_cells
        inventory['positive_retained_membership_verified'] = inventory['completed'] and (bound if derived else True)
        inventory['positive_retained_membership_source'] = ('C1_retained_occurrence_proof' if bound else
            'original_inventory' if not derived and inventory['completed'] else None)
    return {'protocol': 'D1-normalized-native-input-v1', 'synthetic': bundle['synthetic'],
        'synthetic_label': bundle.get('synthetic_label'), 'sources': source_list, 'cells': list(CELLS),
        'H1': h1, 'H1_inventories': inventories, 'H2': h2, 'H2_roster': references,
        'H1_sampling': deepcopy(bundle['C2'].get('sampling')),
        'H3': _c5(bundle['C5'], sources), 'QA': _c6(bundle['C6'],question_ids,bundle.get('C6_controls')),
        'QA_blocks': blocks, 'question_ids': list(ordered_questions),
        'agreement': _agreement(bundle.get('C7'),bundle.get('C4')),
        'effort': deepcopy(bundle.get('effort',[])),
        'K2_effort': deepcopy(bundle.get('K2_effort', [])),
        'semantic_pairs': deepcopy(bundle.get('semantic_pairs',[])),
        'construction_diagnostics': deepcopy(bundle.get('construction_diagnostics',{})),
        'amendments': deepcopy(bundle.get('amendments',{})),
        'projection_limits': {'H2_export_views_are_dependent': True,
            'H3_whole_statement_multiplicity_identified': False,
            'C1_file_byte_pins_require_external_loader_verification': True,
            'QA_answer_text_projected_out': True, 'no_model_or_file_access': True}}
