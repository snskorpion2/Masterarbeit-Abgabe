"""CPU-only adapters for the prospectively selected AS/SCOPE/Joint candidate.

No worker, transport, credentials, model calls or result discovery live here.
The original SDK callback messages and the declared actual wire messages remain
separately visible. Only the existing SCOPE helper and whole-fence helper apply.
"""
import ast
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any, Dict, List

from jsonschema import Draft202012Validator

from Experiments.strict_autoschemakg import contract
from Tools.experiments.source_binding_oct23_v1 import event_scope_job as scope
from Tools.hawki.evaluation_controls import unwrap_format
from . import baseline
from . import independent_union as original
from . import joint_supplement as joint

PROTOCOL = 'selected-candidate-CPU-adapter:oct23-v1'
CANDIDATE = 'AS_SCOPE_JOINT_ROW_V1'
WIRE = {'model': 'deepseek.v3.2', 'temperature': 0.7, 'max_tokens': 8192, 'stream': False}
SCOPE_CONFIG_PATH = Path('withheld-artifact/7b884cc668b8fbace215')
FIELDS = tuple(c + '_dict' for c in original.CATEGORIES)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_scope_policy(selection_path, expected_selection_sha256, *, scope_config_path=None):
    """Load only method/code/config metadata, never source or result files.

    The caller must later freeze this implementation and the execution plan;
    the method-selection document is not dispatch authorization.
    """
    selected = original.pin(selection_path)
    require(selected['sha256'] == expected_selection_sha256, 'Selection file hash differs')
    selection = contract.parse_json(original.bound(selected).decode('utf8'))
    require(selection.get('candidate_id') == CANDIDATE
            and selection.get('main_dispatch_authorized_by_this_file') is False,
            'Prospective method selection is not an execution approval')
    sampling = selection['main_comparison_sampling']
    require(original.canonical({k: sampling[k] for k in WIRE}) == original.canonical(WIRE)
            and sampling['HTTP_timeout_seconds'] == 300 and sampling['transport_retries'] == 0,
            'Matched primary condition differs')
    components = {entry['stage']: entry for entry in selection['retained_components_in_execution_order']}
    scope_entry = components['EV_VV']
    scope_pin = original.pin(scope.__file__)
    require(scope_pin['sha256'] == scope_entry['sha256']
            and Path(scope_pin['path']).resolve() == (baseline.ROOT / scope_entry['implementation']).resolve(),
            'Selected SCOPE implementation differs')
    baseline_pin = original.pin(baseline.__file__)
    require(baseline_pin['sha256'] == components['source_loading_and_EE']['sha256'],
            'Selected original baseline differs')
    config_pin = original.pin(scope_config_path or SCOPE_CONFIG_PATH)
    require(config_pin['sha256'] == scope_entry['clause_config_sha256'], 'Scope config hash differs')
    config = contract.parse_json(original.bound(config_pin).decode('utf8'))
    clauses = config.get('clauses')
    require(type(clauses) is dict and set(clauses) == set(scope.CHANNELS)
            and all(type(v) is str and bool(v.strip()) for v in clauses.values()),
            'Both exact nonempty EV/VV clauses required')
    # Other config fields are only historical hash-only evaluation metadata.
    # No referenced files are opened here or passed to a constructor.
    value = dict(protocol=PROTOCOL, candidate_id=CANDIDATE, selection_pin=selected,
                 scope_code_pin=scope_pin, scope_config_pin=config_pin,
                 baseline_code_pin=baseline_pin, clauses=deepcopy(clauses),
                 wire_parameters=deepcopy(WIRE), dispatch_authorized=False)
    return {**value, 'policy_sha256': original.digest(value)}


def _check_policy(policy):
    require(type(policy) is dict and policy.get('protocol') == PROTOCOL
            and policy.get('candidate_id') == CANDIDATE
            and policy.get('policy_sha256') == original.digest({k:v for k,v in policy.items() if k != 'policy_sha256'}),
            'Scope policy changed')
    for key in ('selection_pin', 'scope_code_pin', 'scope_config_pin', 'baseline_code_pin'):
        original.bound(policy[key])
    require(original.canonical(policy['wire_parameters']) == original.canonical(WIRE)
            and policy['dispatch_authorized'] is False,
            'CPU policy cannot authorize dispatch')
    rebuilt = load_scope_policy(policy['selection_pin']['path'], policy['selection_pin']['sha256'],
                                scope_config_path=policy['scope_config_pin']['path'])
    require(original.canonical(rebuilt) == original.canonical(policy),
            'Policy differs from the bound selection and exact clause config')


def _original_source_chunks(source, config):
    """Execute only the unchanged SDK chunker and sample-chunk method AST."""
    require(type(config) is dict and type(config.get('chunk_size')) is int
            and config['chunk_size'] > 0 and type(config.get('chunk_overlap')) is int
            and 0 <= config['chunk_overlap'] < config['chunk_size']
            and type(config.get('remove_doc_spaces')) is bool
            and type(config.get('deduplicate_text', False)) is bool,
            'Explicit typed original chunk policy required')
    path = original.DEFAULT_SOURCE / 'atlas_rag/kg_construction/triple_extraction.py'
    tree = ast.parse(path.read_bytes())
    chunker = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TextChunker')
    processor = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DatasetProcessor')
    method = next(n for n in processor.body if isinstance(n, ast.FunctionDef) and n.name == 'create_sample_chunks')
    namespace = dict(ProcessingConfig=object, List=List, Dict=Dict, Any=Any, re=re)
    exec(compile(ast.Module(body=[chunker, method], type_ignores=[]), str(path), 'exec'), namespace)
    native_config = SimpleNamespace(**config)
    instance = SimpleNamespace(config=native_config,
        chunker=namespace['TextChunker'](native_config), deduplicate_text=config.get('deduplicate_text', False))
    sample = dict(id=source['id'], text=source['text'], metadata=deepcopy(source.get('metadata', {'lang': 'en'})))
    return namespace['create_sample_chunks'](instance, sample)


def adapt_prefix_job(original_job, policy):
    """Return a fresh original-EE/SCOPE-EV/VV prefix roster with exact lineage.

    This supports all declared SDK chunks. A separate worker must preserve all
    chunk rows and build the complete source-level carrier before its one Joint.
    This function does not read baseline outputs or approve an execution plan.
    """
    _check_policy(policy)
    before = original.canonical(original_job)
    source = original_job['source_only_input']
    require(source['id'] == original_job['source_id']
            and sha256(source['text'].encode('utf8')).hexdigest() == source['sha256'] == original_job['source_sha256'],
            'Whole source identity/text hash differs')
    chunks = original_job['original_chunks']
    require(type(chunks) is list and bool(chunks), 'All original SDK chunks required')
    by_chunk = {}
    for chunk in chunks:
        key = (chunk['id'], chunk['chunk_id'])
        require(key not in by_chunk and chunk['id'] == source['id'], 'Duplicate or foreign SDK chunk')
        by_chunk[key] = chunk
    native = original._native()
    # _native just verified all original code files. A consistent-looking
    # truncated roster is insufficient: replay the actual original chunker.
    require(original.canonical(chunks) == original.canonical(
        _original_source_chunks(source, original_job['processing_config'])),
        'Declared chunks do not cover the complete original SDK source policy')
    result, lineage, seen = deepcopy(original_job), [], set()
    call_ids = [call.get('physical_call_id') for call in result['calls']]
    require(all(type(ident) is str and bool(ident) for ident in call_ids)
            and len(set(call_ids)) == len(call_ids), 'Unique physical call identities required')
    require(len(result['calls']) == len(chunks) * 3, 'Every chunk requires all three original categories')
    for call in result['calls']:
        for field, value in dict(HTTP_timeout_seconds=300, maximum_physical_POSTs=1,
                                 transport_retries=0, native_validation_regenerations=0).items():
            if field in call:
                require(type(call[field]) is int and call[field] == value,
                        'Call timeout, retry or physical dispatch policy differs')
        category = call['category']
        key = (call['source_id'], call['chunk_id'])
        require(key in by_chunk and category in original.CATEGORIES
                and (*key, category) not in seen, 'Missing, foreign or repeated category/chunk')
        seen.add((*key, category))
        chunk = by_chunk[key]
        language = chunk.get('metadata', {}).get('lang', 'en')
        require(language in native.prompts, 'Original SDK prompt language unavailable')
        expected = [dict(role='system', content=native.prompts[language]['system']),
                    dict(role='user', content=native.prompts[language][category] + '\n' + chunk['text'])]
        require(original.canonical(call['messages']) == original.canonical(expected)
                and original.canonical(call['schema']) == original.canonical(native.schemas[category])
                and original.canonical(call['payload']) == original.canonical({**WIRE, 'messages': expected})
                and call['payload_sha256'] == original.digest(call['payload']),
                'Original source/prompt/schema/payload differs; cannot apply delta twice')
        if 'chunk_text_sha256' in call:
            require(call['chunk_text_sha256'] == sha256(chunk['text'].encode('utf8')).hexdigest(),
                    'Chunk text hash differs')
        changed = (deepcopy(expected) if category == 'entity_relation' else
                   scope.scope_messages(SimpleNamespace(require=require), expected,
                                        policy['clauses'][category], 'SCOPE'))
        lineage.append(dict(physical_call_id=call['physical_call_id'], category=category,
            source_id=key[0], chunk_id=key[1], native_messages_sha256=original.digest(expected),
            original_payload_sha256=call['payload_sha256'], actual_messages_sha256=original.digest(changed),
            intervention='none' if category == 'entity_relation' else 'exact_system_LF_LF_scope_clause'))
        call['native_messages'] = deepcopy(expected)
        call['messages'] = changed
        call['payload'] = {**deepcopy(WIRE), 'messages': deepcopy(changed)}
        call['payload_sha256'] = original.digest(call['payload'])
    require(original.canonical(original_job) == before, 'Input job mutated')
    return dict(protocol=PROTOCOL, candidate_id=CANDIDATE, job=result, lineage=lineage,
                policy_sha256=policy['policy_sha256'], prefix_POSTs=len(result['calls']),
                additional_Joint_POSTs=1 if len(chunks) == 1 else None,
                joint_prefix_compatible=len(chunks) == 1,
                multichunk_Joint_contract_required=len(chunks) != 1,
                Joint_contract_scope='The selected SCOPE-Joint prefix condition requires exactly one complete source chunk. A worker must reject incompatible jobs before any POST.',
                dispatch_authorized=False,
                execution_plan_namespace_and_physical_order_owned_by_worker=True)


def parse_joint_with_common_fence(plan, raw, *, expected_plan_sha256, **parser_kwargs):
    """Existing lossless wrapper only, then the entire bound Joint parser."""
    require(type(raw) is str, 'Original joint response text required')
    try:
        contract.parse_json(raw)
        strict = True
    except (ValueError, TypeError):
        strict = False
    inner, bridges = unwrap_format(raw)
    parsed = joint.parse_joint_supplement(plan, inner,
        expected_plan_sha256=expected_plan_sha256, **parser_kwargs)
    return dict(parsed=parsed, format_bridges=bridges, strict_raw_JSON_valid=strict,
                raw_sha256=sha256(raw.encode('utf8')).hexdigest(),
                inner_sha256=sha256(inner.encode('utf8')).hexdigest(),
                native_value_changes=False, new_model_calls=0)


def append_joint_result(parsed_result):
    """Append every whole unverified proposal. No filter, fusion or deduplication."""
    row, additions = parsed_result['baseline'], parsed_result['separate_additions']
    require(type(row) is dict and type(additions) is dict and set(additions) == set(FIELDS)
            and 'event_entity_relation_dict' not in row, 'Original native field spelling required')
    native = original._native()
    result = deepcopy(row)
    for category, field in zip(original.CATEGORIES, FIELDS, strict=True):
        Draft202012Validator(native.schemas[category]).validate(row[field])
        Draft202012Validator(native.schemas[category]).validate(additions[field])
        result[field].extend(deepcopy(additions[field]))
        require(result[field][:len(row[field])] == row[field], 'Original native values changed')
    return dict(native_row=result, semantic_status='unverified_proposals_appended',
                output_field_scope='Existing *_output fields describe S0 responses only; additional raw Joint response and provenance must remain separate.',
                semantic_deduplication=False, source_or_identity_repair=False)
