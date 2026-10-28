"""CPU-only native-adapter tests; every judgment and answer is synthetic.

These tests never load result.json, sealed sources, annotations or QA outputs.
The native input shapes are taken from the existing exporters' source code.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import json

import pytest

from Experiments.fair_v2_oct24.D1 import native, synthetic


@pytest.fixture(scope='module')
def fixture():
    return synthetic.build_native_fixture()


def test_full_frozen_design_counts_and_native_shapes(fixture):
    result = native.normalize_native(fixture)
    assert result['synthetic'] is True
    assert 'SYNTHETIC ONLY' in result['synthetic_label']
    assert len(result['sources']) == 24
    assert sum(len(row['draws']) for row in result['sources']) == 68
    assert len(result['cells']) == 8
    assert len(result['H1_inventories']) == len(result['H3']) == 544
    assert len(fixture['C2']['occurrence_labels']) == 816
    assert len({row['unit_id'] for row in fixture['C2']['occurrence_labels']}) == 816
    assert fixture['C1']['proof_count'] == len(fixture['C1']['proofs']) == 272
    assert len(fixture['C3']['records']) == 2336
    assert len(result['H2']) == 4672
    assert len(result['H2_roster']) == 200
    assert Counter(row['context_mode'] for row in result['QA']) == {'graph':480,'empty':60,'gold':60}
    assert len(result['QA_blocks']) == 39
    assert len(result['question_ids']) == 60
    assert sorted(map(len,result['QA_blocks'])) == [1]*29 + [2]*9 + [13]
    assert len(result['agreement']['human']) == 150


def test_reproducible_seed_and_no_input_mutation(fixture):
    before = json.dumps(fixture,sort_keys=True)
    assert fixture == synthetic.build_native_fixture()
    assert fixture != synthetic.build_native_fixture(seed=20261026)
    native.normalize_native(fixture)
    assert json.dumps(fixture,sort_keys=True) == before


def test_native_source_identifiers_can_be_bound_without_loading_sources(fixture):
    sources = deepcopy(fixture['sources'])
    for i,row in enumerate(sources):
        row['source_id'] = 'opaque-test-source-'+str(i)
    blocks = [['opaque-test-question-'+q.split('Q')[-1] for q in block]
              for block in fixture['QA_blocks']]
    result = synthetic.build_fixture(sources=sources,qa_blocks=blocks)
    assert result['sources'] == sources
    assert result['QA_blocks'] == blocks
    assert {row['source_id'] for row in result['H1']} == {row['source_id'] for row in sources}


def test_original_occurrences_and_exact_duplicate_semantics_remain_separate(fixture):
    rows = fixture['C2']['occurrence_labels']
    groups = defaultdict(list)
    for row in rows:
        groups[row['parent_id']].append(row)
    assert len(groups) == 136
    for group in groups.values():
        ee = [row for row in group if row['category']=='EE']
        assert len(ee) == 2 and ee[0]['unit_id'] != ee[1]['unit_id']
        assert ee[0]['value'] == ee[1]['value']
    projected = native.normalize_native(fixture)
    one = rows[0]
    views = [row for row in projected['H1'] if row['unit_id']==one['unit_id']]
    assert len(views) >= 2
    assert all(row['value']==one['value'] for row in views)
    assert all(row['raw_code']==one['raw_code'] for row in views)


def test_missing_semantic_payload_is_nullable_not_reconstructed(fixture):
    value = deepcopy(fixture)
    row = value['C2']['cells'][0]['labels'][0]
    row.pop('value')
    output = native.normalize_native(value)
    found = next(r for r in output['H1'] if r['unit_id']==row['unit_id'] and r['cell']==value['C2']['cells'][0]['target_cell'])
    assert found['value'] is None


def test_six_technical_c2_cases_stay_missing_in_all_inherited_views(fixture):
    missing = {r['unit_id'] for r in fixture['C2']['occurrence_labels'] if r['measurement_status']=='technical_missing'}
    assert len(missing)==6
    rows = native.normalize_native(fixture)['H1']
    observed = [r for r in rows if r['unit_id'] in missing]
    assert len(observed)>=12
    assert all(r['raw_code'] is None and r['label'] is None and r['unknown_execution'] is True for r in observed)


def test_unknown_inventory_is_not_invented_as_empty(fixture):
    value = deepcopy(fixture)
    value.pop('C1')
    cell = value['C2']['cells'][0]
    cell.update(status='pending_subset_proof',labels=None,occurrence_count=None)
    partner = next(r for r in value['C2']['cells'] if r['source_id']==cell['source_id']
                   and r['draw']==cell['draw'] and r['target_cell']==cell['target_cell'].replace('_ORIGINAL','_ROW'))
    partner.update(status='pending_subset_proof',labels=None,occurrence_count=None)
    output = native.normalize_native(value)
    inventory = next(r for r in output['H1_inventories'] if r['source_id']==cell['source_id'] and r['draw']==cell['draw'] and r['cell']==cell['target_cell'])
    assert inventory['completed'] is False and inventory['occurrence_count'] is None
    cell['occurrence_count']=0
    with pytest.raises(ValueError,match='nullable'):
        native.normalize_native(value)


def test_cell_rosters_duplicates_unknown_status_and_unit_owners_fail_closed(fixture):
    value = deepcopy(fixture)
    value['C2']['cells'].pop()
    with pytest.raises(ValueError,match='every planned cell'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['C2']['cells'].append(deepcopy(value['C2']['cells'][0]))
    with pytest.raises(ValueError,match='duplicate C2 cell'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['C2']['cells'][0]['status']='mysterious'
    with pytest.raises(ValueError,match='Unknown C2 cell status'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['C2']['cells'][0]['labels'][0]['source_id']='foreign'
    with pytest.raises(ValueError,match='owner mismatch'):
        native.normalize_native(value)


def test_bad_literal_code_and_inconsistent_canonical_label_are_refused(fixture):
    value = deepcopy(fixture)
    value['C2']['cells'][0]['labels'][0]['raw_code']='invented-semantic-label'
    with pytest.raises(ValueError,match='Unknown native support code'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['C2']['cells'][0]['labels'][0].update(raw_code='supported',label='unclear')
    with pytest.raises(ValueError,match='canonical label disagreement'):
        native.normalize_native(value)
    with pytest.raises(ValueError,match='judgment status'):
        native.support_label('supported','unknown-status')


def test_h2_fixed_references_expand_to_dependent_export_views(fixture):
    output = native.normalize_native(fixture)
    roster = Counter(r['source_id'] for r in output['H2_roster'])
    sealed = [s for s in output['sources'] if s['cohort']=='SEALED4']
    fresh = [s for s in output['sources'] if s['cohort']=='NEW20']
    assert sum(roster[s['source_id']] for s in sealed)==16
    assert sum(roster[s['source_id']] for s in fresh)==184
    pairs = defaultdict(list)
    for r in output['H2']:
        pairs[r['source_id'],r['draw'],r['direct_inventory_arm'],r['obligation_id']].append(r)
    assert len(pairs)==2336
    for group in pairs.values():
        assert len(group)==2 and all(r['dependent_export_projection'] for r in group)
        assert group[0]['raw_code']==group[1]['raw_code'] and group[0]['status']==group[1]['status']


def test_h2_missing_cases_must_be_explicit_and_reference_roster_is_fixed(fixture):
    value = deepcopy(fixture)
    value['C3']['records'].pop()
    with pytest.raises(ValueError,match='every fixed case'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['C3']['records'][0]['obligation_id']='foreign'
    with pytest.raises(ValueError,match='foreign/duplicate reference'):
        native.normalize_native(value)


def test_h3_native_object_and_projected_occurrence_denominators_stay_separate(fixture):
    output = native.normalize_native(fixture)
    row = next(r for r in output['H3'] if r['cell']=='AS_ORIGINAL')
    assert row['categories']['ALL']['native_objects']==6
    assert row['projected_occurrence_capacity']['expected_occurrences']==8
    assert row['projected_occurrence_capacity']['expected_distinct_contents']==7
    assert row['projected_occurrence_capacity']['duplicate_occurrences_in_input']==1
    assert row['whole_native_statement_multiplicity_ratio'] is None
    assert row['whole_native_statement_multiplicity_ratio_identified'] is False
    assert row['EV_whole_native_payload_recovery_verified'] is False
    assert 'H3_direct_content_fraction' in row['categories']['EV']


def test_h3_native_integer_draw_and_export_names_are_bound(fixture):
    value = deepcopy(fixture)
    assert type(value['C5']['cells'][0]['draw']) is int
    assert native.normalize_native(value)['H3'][0]['draw']=='draw_1'
    value['C5']['cells'][0]['export']='row'
    with pytest.raises(ValueError,match='Exact A6 export identity'):
        native.normalize_native(value)


def test_h3_unavailable_measurement_is_nullable_and_inconsistent_fraction_rejected(fixture):
    value = deepcopy(fixture)
    value['C5']['cells'][0].update(status='unavailable',categories=None,projected_occurrence_capacity=None)
    assert native.normalize_native(value)['H3'][0]['categories'] is None
    value = deepcopy(fixture)
    value['C5']['cells'][0]['categories']['ALL']['H3_direct_content_fraction']=.1234
    with pytest.raises(ValueError,match='fraction mismatch'):
        native.normalize_native(value)


def test_c1_retained_unit_order_and_original_identity_are_verified(fixture):
    value = deepcopy(fixture)
    proof = value['C1']['proofs'][0]
    value['C1_proof_values'][proof['proof_pin']['sha256']]['retained_occurrence_ids'][0]='wrong-global-unit'
    with pytest.raises(ValueError,match='retained proof disagrees'):
        native.normalize_native(value)


def test_qa_scores_have_no_answers_or_gold_and_missing_never_becomes_zero(fixture):
    output = native.normalize_native(fixture)
    assert len(output['QA'])==600
    assert all('answer' not in r and 'answer_aliases' not in r for r in output['QA'])
    missing = [r for r in output['QA'] if not r['observed']]
    assert missing and all(r['f1'] is None and r['em'] is None for r in missing)
    assert 'SYNTHETIC answer' not in json.dumps(output)
    assert all(r['f1']==1 for r in output['QA'] if r['em']==1)


def test_invalid_qa_status_missing_scores_and_endpoint_substitution_are_refused(fixture):
    value = deepcopy(fixture)
    row = value['C6']['cells']['AS_ORIGINAL']['scores']['per_question'][0]
    row.update(status='technical_missing',f1=0,em=0)
    with pytest.raises(ValueError,match='not zero'):
        native.normalize_native(value)
    row.update(status='complete',f1=None,em=None)
    with pytest.raises(ValueError,match='Observed official'):
        native.normalize_native(value)
    row.update(status='made_up',f1=None,em=None)
    with pytest.raises(ValueError,match='Unknown C6'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['C6_controls']['passage']=value['C6_controls'].pop('gold')
    with pytest.raises(ValueError,match='passage endpoint'):
        native.normalize_native(value)


def test_missing_qa_container_rows_cannot_shrink_fixed_q60(fixture):
    value = deepcopy(fixture)
    value['C6']['cells']['AS_ORIGINAL']['scores']['per_question'].pop()
    with pytest.raises(ValueError,match='retain all 60'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['question_ids'][0]='foreign'
    with pytest.raises(ValueError,match='same fixed Q60'):
        native.normalize_native(value)


def test_human_nominal_three_class_labels_missingness_and_design_weights(fixture):
    value = deepcopy(fixture)
    first, second = value['C7']['key']['items'][:2]
    first.update(c2_status='rated',c2_label='unclear')
    second.update(c2_status='technical_failure',c2_label=None)
    annotation_by_id = {r['item_id']:r for r in value['C7']['annotations']['annotations']}
    annotation_by_id[first['item_id']]['label']='unclear'
    annotation_by_id[second['item_id']]['label']=None
    human = native.normalize_native(value)['agreement']['human']
    by_uid = {r['unit_id']:r for r in human}
    assert by_uid[first['original_id']]['reference_label']=='unclear'
    assert by_uid[first['original_id']]['label']=='unclear'
    assert by_uid[second['original_id']]['reference_label'] is None
    assert by_uid[second['original_id']]['label'] is None
    assert Counter(r['stratum'] for r in human)=={a+'-'+c:25 for a in ('AS','V1') for c in ('EE','EV','VV')}
    assert all(r['weight']==136/25 for r in human)


def test_human_packet_weights_duplicate_originals_and_missing_reference_must_validate(fixture):
    value = deepcopy(fixture)
    value['C7']['annotations']['packet_sha256']='bad'
    with pytest.raises(ValueError,match='packet binding'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['C7']['key']['items'][0]['weight']=1
    with pytest.raises(ValueError,match='design weight'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['C7']['key']['items'][1]['original_id']=value['C7']['key']['items'][0]['original_id']
    with pytest.raises(ValueError,match='distinct selected'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    value['C7']['key']['items'][0].update(c2_status='technical_failure',c2_label='unclear')
    with pytest.raises(ValueError,match='nullable'):
        native.normalize_native(value)


def test_grok_random_core_is_per_parent_category_and_enrichment_remains_separate(fixture):
    original = {r['unit_id']:r for r in fixture['C2']['occurrence_labels']}
    rows = native.normalize_native(fixture)['agreement']['grok']
    core = [r for r in rows if r['in_base_sample']]
    assert len(core)==408
    strata = Counter((original[r['unit_id']]['parent_id'],r['category']) for r in core)
    assert len(strata)==408 and set(strata.values())=={1}
    assert all(r['weight']==2 for r in core)
    assert any(not r['in_base_sample'] and r['in_removal_panel'] for r in rows)


def test_grok_duplicate_export_views_merge_flags_not_judgments(fixture):
    value = deepcopy(fixture)
    row = value['C4'][0]
    row.update(in_base_sample=True,in_removal_panel=False)
    duplicate = {**row,'in_base_sample':False,'in_removal_panel':True}
    value['C4'].append(duplicate)
    expected_count = len(fixture['C4'])
    output = native.normalize_native(value)['agreement']['grok']
    assert len(output)==expected_count
    merged = next(r for r in output if r['unit_id']==row['unit_id'])
    assert merged['in_base_sample'] and merged['in_removal_panel']
    duplicate['grok_code']='supported' if row['grok_code']!='supported' else 'unsupported'
    with pytest.raises(ValueError,match='Conflicting duplicate C4'):
        native.normalize_native(value)


def test_costs_cache_usage_and_unknowns_keep_native_units(fixture):
    output = native.normalize_native(fixture)
    assert output['effort']==fixture['effort']
    assert {r['currency'] for r in output['effort']}=={'USD','EUR'}
    assert all(r['physical_POSTs'] is None and r['cache_write_tokens'] is None and
               r['cost_complete'] is False for r in output['effort'])


def test_in_memory_projection_does_not_open_files_or_network(fixture,monkeypatch):
    import builtins
    import socket
    def denied(*args,**kwargs):
        raise AssertionError('D1 native projection attempted external IO')
    monkeypatch.setattr(builtins,'open',denied)
    monkeypatch.setattr(socket,'socket',denied)
    result = native.normalize_native(fixture)
    assert result['projection_limits']['no_model_or_file_access'] is True


def test_inventory_metrics_cannot_change_between_export_views(fixture):
    value = deepcopy(fixture)
    cell = value['C2']['cells'][1]
    cell['labels']=list(reversed(cell['labels']))
    with pytest.raises(ValueError,match='paired export views'):
        native.normalize_native(value)
    value = deepcopy(fixture)
    cell = value['C2']['cells'][1]
    cell.update(status='pending_subset_proof',labels=None,occurrence_count=None)
    with pytest.raises(ValueError,match='paired export views'):
        native.normalize_native(value)


def test_optional_semantic_pairs_and_construction_diagnostics_are_copied_verbatim(fixture):
    baseline = native.normalize_native(fixture)
    assert baseline['semantic_pairs']==[] and baseline['construction_diagnostics']=={}
    value = deepcopy(fixture)
    value['semantic_pairs']=[{'left_unit_id':'SYNTHETIC-a','right_unit_id':'SYNTHETIC-b',
                              'human_confirmed':True,'synthetic':True}]
    value['construction_diagnostics']={'SYNTHETIC-N5':{'rejected_joint':1,'unknown_execution':None}}
    result = native.normalize_native(value)
    assert result['semantic_pairs']==value['semantic_pairs']
    assert result['construction_diagnostics']==value['construction_diagnostics']
    result['semantic_pairs'][0]['human_confirmed']=False
    result['construction_diagnostics']['SYNTHETIC-N5']['rejected_joint']=2
    assert value['semantic_pairs'][0]['human_confirmed'] is True
    assert value['construction_diagnostics']['SYNTHETIC-N5']['rejected_joint']==1
    assert result['projection_limits']['C1_file_byte_pins_require_external_loader_verification'] is True


def test_native_h3_additional_diagnostics_preserve_fields_counts_and_availability(fixture):
    result = native.normalize_native(fixture)
    original = fixture['C5']['cells'][0]
    normalized = result['H3'][0]
    diagnostics = normalized['native_diagnostics']
    assert diagnostics['CSV_stages']==original['CSV_stages']
    assert diagnostics['nodes']==original['nodes']
    assert diagnostics['EV']==original['EV']
    assert diagnostics['CSV_stages']['csv_rows']==8
    assert diagnostics['CSV_stages']['csv_to_graph']['missing_additional_identical_occurrences']==1
    assert diagnostics['CSV_stages']['native_to_csv']['retained_occurrences']==8
    assert diagnostics['EV']['native_EV_objects']==2
    assert diagnostics['EV']['whole_native_EV_payload_recovery_fraction'] is None
    assert diagnostics['nodes']['same_name_typed_node_merge_groups']==0
    assert normalized['native_diagnostic_availability']['nodes']['available'] is True
    assert normalized['native_diagnostic_availability']['input_pins']['available'] is False
    assert normalized['full_original_unfiltered_parent_coverage']['value'] is None
    assert normalized['full_original_unfiltered_parent_coverage']['available'] is False
    filtered = next(r for r in result['H3'] if r['cell']=='V2_ROW')
    assert filtered['full_original_unfiltered_parent_coverage']['unfiltered_parent_measurement_ref']['cell']=='V1_ROW'
    diagnostics['CSV_stages']['csv_rows']=100
    assert original['CSV_stages']['csv_rows']==8


def test_absent_or_unavailable_h3_diagnostics_are_not_zero_filled(fixture):
    value = deepcopy(fixture)
    value['C5']['cells'][0].pop('nodes')
    value['C5']['cells'][1].update(status='unavailable',categories=None,
        projected_occurrence_capacity=None,nodes=None,EV=None,CSV_stages=None,object_details=None)
    result = native.normalize_native(value)
    assert result['H3'][0]['native_diagnostics']['nodes'] is None
    assert result['H3'][0]['native_diagnostic_availability']['nodes']=={
        'available':False,'reason':'not_provided_by_native_export'}
    assert result['H3'][1]['native_diagnostic_availability']['nodes']=={
        'available':False,'reason':'native_measurement_unavailable'}
    assert result['H3'][1]['native_diagnostics']['EV'] is None
