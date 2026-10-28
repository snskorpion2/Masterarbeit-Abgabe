"""Opt-in saved SDK rows -> unchanged global concept/GraphML tail.

The caller supplies the already configured original extractor and its runtime,
and keeps verified_source_imports open throughout this call. Nothing starts at
import. No extraction, encoder, new client, prompt or retry policy is added.
The original export is NOT lossless: cleaning, first-visited source assignment,
lexical node merging and DiGraph edge collapse remain unchanged and visible.
"""
from collections import Counter
import codecs
import csv
from hashlib import sha256
import json
import io
from pathlib import Path
import re

from Experiments.strict_autoschemakg.contract import (
    DEFAULT_SOURCE, new_output, verify_imports, verify_source,
)
from Experiments.strict_autoschemakg.immutable_publish import publish_bytes

PROTOCOL = 'hipporag2-saved-producer-original-graph-tail:v1'
ROOT = Path(__file__).resolve().parents[2]
FIELDS = ('entity_relation_dict', 'event_entity_dict', 'event_relation_dict')
STEPS = ('convert_json_to_csv', 'generate_concept_csv_temp',
         'create_concept_csv', 'convert_to_graphml')


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _json(value):
    # The original converter opens JSONL with the platform default encoding.
    # ASCII escaping retains every parsed Unicode value on Windows as well.
    return (json.dumps(value, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def _json_types(value):
    if type(value) is dict:
        _require(all(type(key) is str for key in value), 'String JSON object keys required')
        for child in value.values():
            _json_types(child)
    elif type(value) is list:
        for child in value:
            _json_types(child)
    else:
        _require(type(value) in (str, int, float, bool, type(None)), 'Native JSON values required')


def _csv_rows(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def _default_text_encoding():
    # Probe the same implicit text default as open(), without filesystem I/O.
    with io.TextIOWrapper(io.BytesIO()) as stream:
        return stream.encoding


def run_graph_tail(rows, sources, *, extractor, runtime):
    """Run exactly four native tail stages over complete, source-bound rows.

    sources uses the existing sidecar shape {id, text, sha256}. Row order and
    every source ID/text must match, including sources with empty inventories.
    Complete SDK fields are required, not the Main EV alias. Supplied extra
    metadata/raw-output fields remain in the JSONL but the SDK may ignore them.
    Validation finishes before a fresh, private output directory is created.
    A failed native stage leaves its own evidence in place and cannot restart
    in the same directory. The caller owns model accounting and dispatch.
    """
    encoding = _default_text_encoding()
    _require(codecs.lookup(encoding).name == 'utf-8',
             'Original SDK CSV tail requires a UTF-8 process (for example Python -X utf8)')
    from jsonschema import Draft202012Validator, ValidationError
    from atlas_rag.kg_construction.triple_extraction import KnowledgeGraphExtractor
    from atlas_rag.llm_generator.format.validate_json_schema import ATLAS_SCHEMA
    import networkx as nx

    _require(type(extractor) is KnowledgeGraphExtractor, 'Original SDK extractor required')
    source_proof = verify_source(DEFAULT_SOURCE)
    verify_imports(DEFAULT_SOURCE)
    config = extractor.config
    _require(extractor.custom_schema is None and extractor.result_schema == ATLAS_SCHEMA,
             'Unmodified native schema required')
    _require(config.include_concept is True, 'Complete native concept tail required')
    _require(type(config.total_shards_concept) is int and config.total_shards_concept == 1
             and type(config.current_shard_concept) is int and config.current_shard_concept == 0,
             'Single complete global concept shard required')
    _require(type(config.batch_size_concept) is int and config.batch_size_concept > 0,
             'Positive configured concept batch size required')
    pattern = config.filename_pattern
    _require(type(pattern) is str and re.fullmatch(r'[A-Za-z0-9_.-]+', pattern)
             and pattern not in ('.', '..'), 'Simple native filename pattern required')
    _require(callable(getattr(runtime, 'generate', None)), 'Configured runtime required')
    _require(type(rows) is list and type(sources) is list and bool(sources)
             and len(rows) == len(sources), 'Complete ordered producer rows and sources required')
    bindings, ids, payload = [], set(), []
    for row, source in zip(rows, sources, strict=True):
        _require(type(source) is dict and set(source) == {'id', 'text', 'sha256'}
                 and type(source['id']) is str and bool(source['id'])
                 and source['id'] not in ids and type(source['text']) is str
                 and bool(source['text']) and type(source['sha256']) is str,
                 'Unique actual source identity, text and SHA required')
        body = source['text'].encode('utf-8')
        _require(re.fullmatch('[0-9a-f]{64}', source['sha256']) is not None
                 and sha256(body).hexdigest() == source['sha256'], 'Source text SHA mismatch')
        ids.add(source['id'])
        _require(type(row) is dict and type(row.get('id')) is str
                 and row['id'] == source['id'] and row.get('original_text') == source['text']
                 and 'event_entity_relation_dict' not in row,
                 'Ordered source ID/text and native SDK field names required')
        for field, phase in zip(FIELDS, ('entity_relation', 'event_entity', 'event_relation'), strict=True):
            _require(field in row, 'Complete native SDK fields required')
            try:
                Draft202012Validator(ATLAS_SCHEMA[phase]).validate(row[field])
            except ValidationError:
                raise ValueError('Invalid native SDK inventory structure') from None
        _json_types(row)
        payload.append(_json(row))
        bindings.append({'id': source['id'], 'text_sha256': source['sha256'],
                         'utf8_bytes': len(body)})
    raw = b''.join(payload)
    output = Path(config.output_directory).absolute()
    _require(not any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)()
                     for p in (output, *output.parents)), 'Unlinked output path required')
    _require(not output.resolve().is_relative_to(ROOT), 'Private output must be outside repository')
    output = new_output(output)
    producer = output / 'kg_extraction' / f'{pattern}_native.jsonl'
    publish_bytes(producer, raw)
    # Use the existing native class methods, not a substitute extraction or
    # graph builder. No native generation option is passed or rewritten here.
    KnowledgeGraphExtractor.convert_json_to_csv(extractor)
    runtime.phase = 'concept_induction'
    KnowledgeGraphExtractor.generate_concept_csv_temp(extractor, batch_size=config.batch_size_concept)
    KnowledgeGraphExtractor.create_concept_csv(extractor)
    KnowledgeGraphExtractor.convert_to_graphml(extractor)
    _require(producer.read_bytes() == raw, 'Saved producer input changed during native tail')

    graph_path = output / 'kg_graphml' / f'{pattern}_graph.graphml'
    _require(graph_path.is_file(), 'Native GraphML output missing')
    graph = nx.read_graphml(graph_path)
    relation_rows = _csv_rows(output / 'triples_csv' / f'triple_edges_{pattern}_from_json_without_emb.csv')
    source_rows = _csv_rows(output / 'triples_csv' / f'text_edges_{pattern}_from_json.csv')
    passage_texts = {d['id'] for _, d in graph.nodes(data=True) if d.get('type') == 'passage'}
    node_types = Counter(d.get('type') for _, d in graph.nodes(data=True))
    edge_types = Counter(d.get('type') for _, _, d in graph.edges(data=True))
    return {
        'protocol': PROTOCOL, 'steps': list(STEPS), 'source_commit': source_proof['commit'],
        'native_text_encoding': {'implicit_encoding': encoding, 'requires_utf8': True},
        'source_bindings': bindings,
        'producer_jsonl': {'path': str(producer), 'sha256': sha256(raw).hexdigest(), 'rows': len(rows)},
        'graph': {'path': str(graph_path), 'sha256': sha256(graph_path.read_bytes()).hexdigest(),
                  'node_types': dict(node_types), 'edge_types': dict(edge_types)},
        'observations': {
            'input_documents': len(rows),
            'input_relation_slots': sum(len(r[FIELDS[0]]) + len(r[FIELDS[2]])
                                        + sum(len(e['Entity']) for e in r[FIELDS[1]]) for r in rows),
            'native_relation_csv_rows': len(relation_rows),
            'native_source_csv_rows': len(source_rows),
            'relation_csv_rows_over_unique_pairs': len(relation_rows) - len({
                (r[':START_ID'], r[':END_ID']) for r in relation_rows}),
            'graph_relation_edges': edge_types['Relation'],
            'graph_passage_nodes': node_types['passage'],
            'unchanged_source_texts_represented': sum(s['text'] in passage_texts for s in sources),
        },
        'original_export_limits': {
            'first_source_only': 'Source edges are emitted only when a lexical node is first visited.',
            'digraph_first_edge_per_ordered_pair': 'Later relation rows for the same ordered endpoints collapse.',
            'lexical_identity': 'Equal cleaned labels share a node across categories and documents.',
            'source_identity': 'Passages use cleaned-text hashes, not producer document IDs. Equal texts merge.',
            'cleaning': 'Original source/label/XML cleaning can alter or discard text and records.',
            'edge_provenance': 'The original graph has no per-fact document-occurrence witness.',
        },
        'lossless_export': False, 'quality_or_qa_measured': False,
        'extraction_invoked': False, 'encoder_invoked': False,
        'model_accounting_owner': 'caller-supplied runtime; native concept calls are not free or elided',
    }
