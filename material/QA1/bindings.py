"""Read-only provenance projection for QA1's private post-hoc diagnostics.

This module never writes files, calls models, rebuilds exports or evaluates a
statement's entailment. Its return value contains private identities and text.
Public output must be produced separately from aggregate values only.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from copy import deepcopy
import csv
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
from functools import lru_cache

from Experiments.fair_v2_oct24.C6 import core as c

CODEC_PATH = Path(__file__).resolve().parents[1] / 'Experiments/fair_v2_oct24/C1/transport_acceleration_oct25_v1/request95.py'
CODEC_SHA256 = 'b21dc03aa8619488bc3beef3dfb0773d4eaa9d0a5883aa8c5b4744637d807b6b'


@lru_cache(maxsize=1)
def _existing_projection_function():
    raw = CODEC_PATH.read_bytes()
    need(sha256(raw).hexdigest() == CODEC_SHA256, 'QA1_BOUND_C1_CODEC_DRIFT')
    tree = ast.parse(raw.decode('utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_projection_positions']
    need(len(nodes) == 1, 'QA1_BOUND_C1_CODEC_FUNCTION')
    namespace = {'need': need}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'original_bound_C1_request95.py', 'exec'), namespace)
    return namespace['_projection_positions']


def need(ok, code):
    if not ok:
        raise ValueError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False)


def _support_projection(question_ids, sealed_records):
    """Use explicit original paragraph indices and content IDs, never titles."""
    by_id = {}
    for row in sealed_records:
        need(type(row) is dict and type(row.get('id')) is str, 'QA1_INVALID_GOLD_RECORD')
        need(row['id'] not in by_id, 'QA1_DUPLICATE_GOLD_ID')
        by_id[row['id']] = row
    need(set(question_ids) <= set(by_id), 'QA1_GOLD_ROSTER_INCOMPLETE')
    gold, supports, source_sets = {}, {}, {}
    for qid in question_ids:
        wrapped = by_id[qid]
        original = wrapped['original_record']
        need(type(original.get('answer')) is str
             and type(original.get('answer_aliases')) is list
             and all(type(x) is str for x in original['answer_aliases']), 'QA1_INVALID_GOLD_TYPES')
        paragraphs = {p['idx']: p for p in original['paragraphs']}
        need(len(paragraphs) == len(original['paragraphs']), 'QA1_DUPLICATE_PARAGRAPH_INDEX')
        occurrence = wrapped['paragraph_occurrences']
        need(len(occurrence) == len(paragraphs), 'QA1_PARAGRAPH_OCCURRENCE_COVERAGE')
        seen, source_ids, texts = set(), set(), []
        for pos, item in enumerate(occurrence):
            idx = item['original_idx']
            need(item['position'] == pos and idx in paragraphs and idx not in seen,
                 'QA1_PARAGRAPH_OCCURRENCE_ORDER')
            seen.add(idx)
            paragraph = paragraphs[idx]
            raw = paragraph['paragraph_text']
            need(type(raw) is str and type(paragraph['is_supporting']) is bool,
                 'QA1_PARAGRAPH_FIELDS')
            expected = 'sha256:' + sha256(raw.encode('utf-8')).hexdigest()
            need(item['corpus_id'] == expected, 'QA1_PARAGRAPH_CONTENT_ID_DRIFT')
            if paragraph['is_supporting']:
                source_ids.add(item['corpus_id'])
                texts.append(raw)
        need(seen == set(paragraphs), 'QA1_PARAGRAPH_OCCURRENCE_COVERAGE')
        gold[qid] = {'answer': original['answer'],
                     'answer_aliases': list(original['answer_aliases'])}
        supports[qid], source_sets[qid] = texts, source_ids
    return gold, supports, source_sets


def _position_projection(records, csv_rows, clean_text, sanitize):
    """Bind original 1-based CSV positions to unchanged full-arm native IDs."""
    positions = _existing_projection_function()(records, clean_text)
    need(len(positions) == len(csv_rows), 'QA1_NATIVE_CSV_POSITION_COVERAGE')
    records_by_id = {r['record_id']: r for r in records}
    need(len(records_by_id) == len(records), 'QA1_DUPLICATE_NATIVE_RECORD')
    result = []
    for ordinal, (position, row) in enumerate(zip(positions, csv_rows), 1):
        expected = [*position['triple'], 'Relation']
        actual = [row.get(k) for k in (':START_ID', 'relation', ':END_ID', ':TYPE')]
        need(actual == expected, 'QA1_NATIVE_CSV_VALUE_OR_ORDER_DRIFT')
        record = position['record']
        text = canonical({'head': sanitize(row[':START_ID']),
                          'relation': sanitize(row['relation']),
                          'tail': sanitize(row[':END_ID'])})
        result.append({'original_csv_ordinal': ordinal,
                       'native_key': record['record_id'], 'source_id': record['source_id'],
                       'projection_index': position['projection_index'], 'text': text})
    return result, records_by_id


def _edge_projection(edge, positions, by_text):
    """A ROW uses its exact active ordinal; ORIGINAL may have multiple owners.

    Only complete actual visible values are matched. Equal endpoints with a
    different relation never acquire each other's provenance. Unmatched values
    (including additional qualifiers) have unknown provenance, not a guessed
    supporting source. Identical native projections may retain multiple owners.
    """
    need(type(edge) is dict and set(edge) >= {'occurrence_id', 'text', 'metadata'},
         'QA1_EDGE_FIELDS')
    need(type(edge['text']) is str and type(edge['occurrence_id']) is str,
         'QA1_EDGE_TYPES')
    raw_ordinal = edge['metadata'].get('native_csv_record')
    if raw_ordinal is not None:
        need(type(raw_ordinal) is str and raw_ordinal.isdecimal()
             and str(int(raw_ordinal)) == raw_ordinal, 'QA1_ACTIVE_CSV_ORDINAL')
        ordinal = int(raw_ordinal)
        need(1 <= ordinal <= len(positions), 'QA1_ACTIVE_CSV_ORDINAL_RANGE')
        owned = [positions[ordinal - 1]]
        need(edge['text'] == owned[0]['text'], 'QA1_ACTIVE_CSV_STATEMENT_DRIFT')
    else:
        owned = by_text.get(edge['text'], [])
    sources = sorted({row['source_id'] for row in owned})
    native_keys = sorted({row['native_key'] for row in owned})
    return {'occurrence_id': edge['occurrence_id'], 'text': edge['text'],
            'source_ids': sources, 'source_id': sources[0] if len(sources) == 1 else None,
            'native_keys': native_keys, 'native_key': native_keys[0] if len(native_keys) == 1 else None,
            'source_binding_status': 'exact_native_projection' if owned else 'unknown_visible_values',
            'multiple_native_owners': len(native_keys) > 1,
            'multiple_source_owners': len(sources) > 1}


def project_data(*, question_ids, contexts, sealed_records, native_by_arm,
                 csv_by_arm, removed_by_arm, edges_by_cell, clean_text, sanitize):
    """Pure synthetic-test seam. It computes bindings, never outcome metrics."""
    need(type(question_ids) is list and question_ids
         and all(type(q) is str and q for q in question_ids)
         and len(set(question_ids)) == len(question_ids), 'QA1_UNIQUE_QUESTION_ROSTER')
    need(set(contexts) == set(edges_by_cell) == set(c.CELLS), 'QA1_EIGHT_CELLS_REQUIRED')
    need(set(native_by_arm) == set(csv_by_arm) == set(removed_by_arm) == {'AS', 'V1'},
         'QA1_TWO_BASE_ARMS_REQUIRED')
    gold, supports, supporting_sources = _support_projection(question_ids, sealed_records)
    by_arm, records = {}, {}
    for arm in ('AS', 'V1'):
        by_arm[arm], records[arm] = _position_projection(
            native_by_arm[arm], csv_by_arm[arm], clean_text, sanitize)
        removed = removed_by_arm[arm]
        need(type(removed) is list and len(set(removed)) == len(removed)
             and set(removed) <= set(records[arm]), 'QA1_EXACT_GUARD_REMOVAL_IDS')
        need(all(records[arm][rid]['category'] in {'EE', 'VV'} for rid in removed),
             'QA1_GUARD_REMOVED_EV')
    result = {'question_ids': list(question_ids), 'gold': gold, 'supports': supports,
              'supporting_source_ids': {q: sorted(ids) for q, ids in supporting_sources.items()},
              'contexts': {}, 'removed': {}, 'aggregate_binding_checks': {}}
    for cell in c.CELLS:
        arm = 'AS' if cell.startswith('AS') else 'V1'
        guarded = cell.startswith('AS_G') or cell.startswith('V2')
        removed = set(removed_by_arm[arm]) if guarded else set()
        positions = [p for p in by_arm[arm] if p['native_key'] not in removed]
        by_text = defaultdict(list)
        for row in positions:
            by_text[row['text']].append(row)
        edge_rows = {}
        for edge in edges_by_cell[cell]:
            need(edge['occurrence_id'] not in edge_rows, 'QA1_DUPLICATE_GRAPH_OCCURRENCE')
            edge_rows[edge['occurrence_id']] = _edge_projection(edge, positions, by_text)
        own_contexts = contexts[cell]
        need([row.get('question_id') for row in own_contexts] == question_ids,
             'QA1_CONTEXT_QUESTION_ORDER')
        cell_rows = {}
        for context in own_contexts:
            qid = context['question_id']
            need(type(context['selected_edges']) is list and len(context['selected_edges']) <= 30,
                 'QA1_TOP30_CONTEXT_BOUNDARY')
            selected = []
            seen = set()
            for edge in context['selected_edges']:
                oid = edge['occurrence_id']
                need(oid in edge_rows and oid not in seen, 'QA1_SELECTED_EDGE_ID_DRIFT')
                seen.add(oid)
                bound = edge_rows[oid]
                need(edge['text'] == bound['text'], 'QA1_SELECTED_EDGE_TEXT_DRIFT')
                # Preserve input order and byte-identical Reader-visible text.
                source_support = (bool(set(bound['source_ids']) & supporting_sources[qid])
                    if bound['source_binding_status'] == 'exact_native_projection' else None)
                selected.append({**bound, 'is_supporting_source': source_support})
            cell_rows[qid] = selected
        result['contexts'][cell] = cell_rows
        result['aggregate_binding_checks'][cell] = {
            'questions': len(own_contexts), 'graph_edges': len(edge_rows),
            'unknown_source_graph_edges': sum(r['source_binding_status'] != 'exact_native_projection'
                                              for r in edge_rows.values()),
            'multiple_native_owner_graph_edges': sum(r['multiple_native_owners'] for r in edge_rows.values()),
            'multiple_source_owner_graph_edges': sum(r['multiple_source_owners'] for r in edge_rows.values()),
        }
    for arm in ('AS', 'V1'):
        removed_rows = []
        for rid in removed_by_arm[arm]:
            native = records[arm][rid]
            sid = native['source_id']
            removed_rows.append({'occurrence_id': rid, 'native_key': rid, 'native_keys': [rid],
                                 'source_id': sid, 'source_ids': [sid],
                                 'category': native['category'], 'text': canonical(native['value']),
                                 'source_binding_status': 'exact_original_native_occurrence'})
        result['removed'][arm] = {qid: [
            {**row, 'is_supporting_source': row['source_id'] in supporting_sources[qid]}
            for row in removed_rows] for qid in question_ids}
    result['measurement_boundary'] = {
        'context_text': 'byte-identical C6 Relation statement JSON, unchanged Top-30 order',
        'removed_text': 'whole original EE/VV native value as canonical JSON, independent of export',
        'support': 'exact original corpus content ID appears among this questions is_supporting paragraphs',
        'multiple_owners': 'only native projections equal to the complete visible statement values',
        'unknown_source_is_not_negative_entailment': True,
        'new_models_exports_or_entailment_judgments': False,
    }
    return result


class _Reads:
    def __init__(self):
        self.pins = {}

    def raw(self, binding):
        need(type(binding) is dict and set(binding) <= {'path', 'bytes', 'sha256'}
             and {'path', 'sha256'} <= set(binding), 'QA1_EXACT_FILE_PIN')
        path = Path(binding['path']).resolve()
        raw = path.read_bytes()
        need(sha256(raw).hexdigest() == binding['sha256']
             and ('bytes' not in binding or len(raw) == binding['bytes']), 'QA1_INPUT_PIN_DRIFT')
        pin = {'path': str(path), 'bytes': len(raw), 'sha256': binding['sha256']}
        key = str(path).casefold()
        need(key not in self.pins or self.pins[key] == pin, 'QA1_INPUT_PIN_CONFLICT')
        self.pins[key] = pin
        return raw

    def doc(self, binding):
        return c.strict_json(self.raw(binding))


def _original_functions(pins, reads):
    """Extract only two exact pinned pure functions and their regex constant."""
    found = {}
    for filename, function in [('json_to_csv.py', 'clean_text'),
                                ('csv_to_graphml.py', 'sanitize_xml_string')]:
        candidates = [p for p in pins if Path(p['path']).name == filename]
        need(len(candidates) == 1, 'QA1_UNIQUE_ORIGINAL_PURE_FUNCTION_SOURCE')
        tree = ast.parse(reads.raw(candidates[0]).decode('utf-8'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function]
        need(len(nodes) == 1, 'QA1_ORIGINAL_PURE_FUNCTION_MISSING')
        if function == 'sanitize_xml_string':
            constants = [n for n in tree.body if isinstance(n, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == '_ILLEGAL_XML_RE' for t in n.targets)]
            need(len(constants) == 1, 'QA1_ORIGINAL_XML_REGEX_MISSING')
            nodes = constants + nodes
        namespace = {'re': re}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), namespace)
        fingerprint = sha256(ast.dump(ast.Module(body=nodes, type_ignores=[]),
                                      include_attributes=False).encode()).hexdigest()
        found[function] = (namespace[function], fingerprint)
    return (found['clean_text'][0], found['sanitize_xml_string'][0],
            (found['clean_text'][1], found['sanitize_xml_string'][1]))


def project_bindings(prepared_pin, runtime_result_pin):
    """Load existing bound files and return private, fully joined projections.

    The caller owns final private storage and publication of aggregates. This
    function cannot start a construction, retriever, Reader or new end audit.
    """
    import networkx as nx
    reads = _Reads()
    prepared = reads.doc(prepared_pin)
    runtime = reads.doc(runtime_result_pin)
    need(runtime.get('gold_pin') == prepared['gold_pin']
         and runtime.get('question_count') == 60, 'QA1_C6_RUNTIME_GOLD_BINDING')
    graph_context = reads.doc(prepared['graph_contexts_pin'])
    need(graph_context.get('gold_opened_during_graph_preparation') is False
         and graph_context['graph_handoff_pin'] == prepared['graph_handoff_pin'],
         'QA1_ORIGINAL_GRAPH_CONTEXT_BINDING')
    # Join the diagnostic text to the exact already completed runtime inputs.
    # This checks only data used here, never transport/provider receipts or a new C6 audit.
    runtime_preparation = reads.doc(runtime['runtime_preparation_pin'])
    expectations = reads.doc(runtime_preparation['expectations_archive_pin'])
    runtime_context = reads.doc(expectations['context_pin'])
    need(runtime_context['graph_handoff_pin'] == prepared['graph_handoff_pin'],
         'QA1_RUNTIME_GRAPH_HANDOFF_BINDING')
    payload_by_position = {r['position']: r['payload_pin'] for r in runtime_context['payloads']}
    need(len(payload_by_position) == len(runtime_context['payloads']) == 600,
         'QA1_RUNTIME_PAYLOAD_ROSTER')
    graph_positions = [r for r in runtime_context['positions'] if r['kind'] == 'graph']
    need(len(graph_positions) == 480, 'QA1_RUNTIME_GRAPH_POSITION_COUNT')
    original_contexts = {cell: {r['question_id']: r for r in graph_context['cells'][cell]}
                         for cell in c.CELLS}
    for slot in graph_positions:
        need(slot['cell'] in original_contexts and slot['question_id'] in original_contexts[slot['cell']],
             'QA1_RUNTIME_GRAPH_SLOT')
        actual_payload = reads.doc(payload_by_position[slot['position']])
        need(actual_payload == original_contexts[slot['cell']][slot['question_id']]['payload'],
             'QA1_RUNTIME_SELECTED_CONTEXT_PAYLOAD_DRIFT')
    question_ids = graph_context['question_ids']
    need(question_ids == prepared['question_ids'] and len(question_ids) == len(set(question_ids)) == 60,
         'QA1_ORIGINAL_Q60_ROSTER')
    need(all(runtime['scores'][cell]['question_roster_sha256'] == c.digest(question_ids)
             for cell in c.CELLS), 'QA1_RUNTIME_QUESTION_ROSTER')
    sealed = reads.doc(prepared['gold_pin'])
    handoff = reads.doc(prepared['graph_handoff_pin'])
    need([row['id'] for row in handoff['cells']] == list(c.CELLS)
         and handoff.get('complete') is True, 'QA1_COMPLETED_EIGHT_CELL_HANDOFF')
    cell_map = {row['id']: row for row in handoff['cells']}
    native_by_arm, csv_by_arm, removed_by_arm, functions = {}, {}, {}, []
    for arm, guarded_cell in [('AS', 'AS_G_ORIGINAL'), ('V1', 'V2_ORIGINAL')]:
        closure = reads.doc(cell_map[guarded_cell]['owner_closure_pin'])
        need(closure['graph_pin'] == cell_map[guarded_cell]['graph_pin']
             and closure.get('QA_rendering_exactly_preserved') is True, 'QA1_GUARDED_CLOSURE')
        final = reads.doc(closure['C1_final_pin'])
        need(final.get('policy_application_complete') is True, 'QA1_FINAL_GUARD_POLICY')
        codec = reads.doc(final['projection']['codec_evidence_pin'])
        need(codec['codec_pin']['sha256'] == CODEC_SHA256
             and codec.get('native_values_or_IDs_changed') is False,
             'QA1_ORIGINAL_C1_EMISSION_CODEC_BINDING')
        reads.raw(codec['codec_pin'])
        plan = reads.doc(final['plan_pin'])
        parent = reads.doc(plan['parent_pin'])
        need(parent['parent_id'] == final['parent_id']
             and parent['descriptor']['arm'] == arm, 'QA1_NATIVE_PARENT_ARM')
        native_by_arm[arm] = parent['native_inventory']['records']
        need(len({r['record_id'] for r in native_by_arm[arm]}) == len(native_by_arm[arm]),
             'QA1_NATIVE_PARENT_DUPLICATE')
        removed_by_arm[arm] = final['removed_full_corpus_native_ids']
        need([parent['unit_to_native'][uid] for uid in final['removed_global_ids']]
             == removed_by_arm[arm], 'QA1_EXPLICIT_GUARD_REMOVAL_BIJECTION')
        producer = parent['no_schema_producer']
        for cell in [arm + '_ORIGINAL', arm + '_ROW']:
            kind = 'original' if cell.endswith('ORIGINAL') else 'relation_rows'
            native_pin, context_pin = producer[kind]['pin'], cell_map[cell]['graph_pin']
            need((native_pin['sha256'], native_pin['bytes']) ==
                 (context_pin['sha256'], context_pin['bytes']), 'QA1_BASE_GRAPH_LINEAGE')
        csv_raw = reads.raw(producer['CSV_pins']['relation_rows'])
        csv_by_arm[arm] = list(csv.DictReader(StringIO(csv_raw.decode('utf-8-sig'), newline='')))
        functions.append(_original_functions(producer['original_module_pins'], reads))
    clean_text, sanitize, function_fingerprints = functions[0]
    # Both AS and V1 producer pins must point to the identical original code.
    need(all(pair[2] == function_fingerprints for pair in functions),
         'QA1_ORIGINAL_CLEANING_CONDITIONS_DIFFER')
    edges_by_cell = {}
    for cell in c.CELLS:
        graph = nx.read_graphml(BytesIO(reads.raw(cell_map[cell]['graph_pin'])), force_multigraph=True)
        edges_by_cell[cell] = [{'occurrence_id': edge.occurrence_id, 'text': edge.text,
                               'metadata': edge.metadata} for edge in c.render_graph(graph)]
    projection = project_data(question_ids=question_ids, contexts=graph_context['cells'],
        sealed_records=sealed['records'], native_by_arm=native_by_arm,
        csv_by_arm=csv_by_arm, removed_by_arm=removed_by_arm,
        edges_by_cell=edges_by_cell, clean_text=clean_text, sanitize=sanitize)
    projection['private_pins'] = list(reads.pins.values())
    return projection
