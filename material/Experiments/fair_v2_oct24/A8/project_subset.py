"""A8: exact CPU subset replay with frozen original SDK schema assignments.

The native inventory and the two export conditions remain the existing ones.
No schema model, concept re-induction, label matching or graph-delete repair is
performed. Original occurrence IDs remain cell-local and stable in a sidecar.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import networkx as nx

from Experiments.fair_comparison_oct23_v1 import graph_contract as native
from Experiments.fair_comparison_oct23_v1.sdk_schema_cpu import _OriginalModules
from Tools.experiments.as_parallel_export_oct20_v1 import export_control

PACKAGE = Path(__file__).resolve().parent
INV_VERSION = 'A8-cell-bound-native-subset-v1'
SCHEMA_VERSION = 'A8-frozen-original-schema-subset-v1'
GRAPH_VERSION = 'A8-bound-original-export-subset-v1'
EXPORTS = {'original','relation_rows'}


class ProjectionError(ValueError):
    """Fixed technical code only; never includes natural values or traceback data."""


def _require(condition, code):
    if not condition:
        raise ProjectionError(code)


def _digest(value):
    return native.digest(value)


def _csv_bytes(fields, rows):
    output = StringIO(newline='')
    writer = csv.writer(output,quoting=csv.QUOTE_ALL)
    writer.writerow(fields)
    for row in rows:
        _require(set(row)==set(fields),'A8_INCOMPLETE_CSV_ROW')
        writer.writerow([row[field] for field in fields])
    return output.getvalue().encode('utf8')


def _columns(binding):
    path = Path(binding['path'])
    raw = path.read_bytes()
    _require(sha256(raw).hexdigest()==binding['sha256'],'A8_FROZEN_ARTIFACT_CHANGED')
    fields = csv.DictReader(StringIO(raw.decode('utf-8-sig'),newline='')).fieldnames
    _require(fields and len(set(fields))==len(fields),'A8_INVALID_CSV_COLUMNS')
    return fields


def _snapshot(graph):
    _require(isinstance(graph,nx.Graph) and graph.is_directed(),'A8_DIRECTED_GRAPH_REQUIRED')
    multi=nx.MultiDiGraph(graph)
    snapshot=native._graph_snapshot(multi)
    # The historical snapshot intentionally stringifies keys. For this exact
    # subset contract int0 and str'0' must remain distinct, otherwise an added
    # parallel edge could disappear in the verification dictionary.
    edges={}
    for head,tail,key,attrs in multi.edges(keys=True,data=True):
        _require(type(key) in (str,int),'A8_UNSUPPORTED_GRAPH_EDGE_KEY')
        identity=(head,tail,type(key).__name__,key)
        _require(identity not in edges,'A8_DUPLICATE_GRAPH_EDGE_KEY')
        edges[identity]=dict(attrs)
    snapshot['edges']=edges
    return snapshot


def _origin_inventory(bound):
    _require(type(bound) is dict,'A8_BOUND_INVENTORY_REQUIRED')
    _require(all(key in bound for key in ('native_rows','sources','row_bindings','records')),
             'A8_BOUND_INVENTORY_REQUIRED')
    fresh = native.bind_native_inventory(bound['native_rows'],bound['sources'],row_bindings=bound['row_bindings'])
    _require(fresh['records']==bound['records'],'A8_ORIGINAL_RECORD_LEDGER_DIFFERS')
    return {key:deepcopy(fresh[key]) for key in ('native_rows','sources','row_bindings','records')},fresh


def _inventory_view(origin,cell_id,removed):
    rows = deepcopy(origin['native_rows'])
    records, positions = [],[]
    by_slot = {(r['row_index'],r['native_field'],r['record_index']):r for r in origin['records']}
    for row_index,row in enumerate(rows):
        for field in native._native_fields(row):
            values=[]
            for old_index,value in enumerate(row[field]):
                record=by_slot[(row_index,field,old_index)]
                if record['record_id'] in removed:
                    continue
                positions.append({'record_id':record['record_id'],'original_row_index':row_index,
                    'native_field':field,'original_record_index':old_index,
                    'current_row_index':row_index,'current_record_index':len(values)})
                values.append(value)
                records.append(deepcopy(record))
            row[field]=values
    ordered_ids=[r['record_id'] for r in origin['records']]
    return {'protocol':INV_VERSION,'cell_id':cell_id,'origin':deepcopy(origin),
        'origin_sha256':_digest(origin),'native_rows':rows,'sources':deepcopy(origin['sources']),
        'row_bindings':deepcopy(origin['row_bindings']),'records':records,'positions':positions,
        'removed_ids':[rid for rid in ordered_ids if rid in removed]}


def _pack_from_bridge(bridge,origin,fresh):
    _require(type(bridge) is dict and all(k in bridge for k in ('schema','audit','pins','concept_bindings','relation_bindings')),
             'A8_COMPLETE_FROZEN_SCHEMA_PACK_REQUIRED')
    _require(bridge.get('native_sha256')==fresh['native_sha256'] and
        bridge.get('source_manifest_sha256')==fresh['source_manifest_sha256'],
        'A8_SCHEMA_INVENTORY_BINDING_DIFFERS')
    stored=bridge['schema']; audit=bridge['audit']; pins=bridge['pins']
    _require(audit.get('original_final_graph_replay_equal') is True and
        audit.get('producer_rows_equal_in_order') is True,'A8_UNQUALIFIED_SCHEMA_REPLAY')
    required=('original_final_relation_CSV_rows','original_concept_node_CSV_rows','original_concept_edge_CSV_rows')
    _require(all(k in stored for k in required) and 'relation_rows' in audit and 'native_slot_rows' in audit,
             'A8_COMPLETE_FROZEN_SCHEMA_PACK_REQUIRED')
    records={r['record_id']:r for r in origin['records']}
    final=stored['original_final_relation_CSV_rows']
    original_csv=Path(pins['final_relation_csv']['path']).read_bytes()
    _require(sha256(original_csv).hexdigest()==pins['final_relation_csv']['sha256'],
             'A8_FROZEN_ARTIFACT_CHANGED')
    reader=csv.DictReader(StringIO(original_csv.decode('utf-8-sig'),newline=''))
    _require(list(reader)==final,'A8_FROZEN_CSV_BYTES_AND_ROWS_DIFFER')
    bindings=audit['relation_rows']
    _require(len(final)==len(bindings),'A8_RELATION_ROW_LEDGER_DIFFERS')
    relations=[]
    for ordinal,(row,binding) in enumerate(zip(final,bindings),1):
        rid=binding['record_id']
        _require(binding['final_csv_ordinal']==ordinal and rid in records,
                 'A8_RELATION_ROW_LEDGER_DIFFERS')
        relations.append({'record_id':rid,'projection_index':binding['projection_index'],
            'original_csv_ordinal':ordinal,'row':deepcopy(row)})
    owners={}
    for slot in audit['native_slot_rows']:
        _require(slot['record_id'] in records,'A8_FOREIGN_SCHEMA_OWNER')
        if slot['original_node_id'] is not None:
            owners.setdefault(slot['original_cleaned_label'],set()).add(slot['record_id'])
    edges=[]
    for ordinal,row in enumerate(stored['original_concept_edge_CSV_rows'],1):
        ids=owners.get(row[':START_ID'],set())
        _require(ids,'A8_UNBOUND_NODE_SCHEMA_ASSIGNMENT')
        edges.append({'original_csv_ordinal':ordinal,'owner_record_ids':sorted(ids),'row':deepcopy(row)})
    return {'relations':relations,'concept_edges':edges,
        'concept_nodes':deepcopy(stored['original_concept_node_CSV_rows']),
        'relation_columns':_columns(pins['final_relation_csv']),
        'concept_node_columns':_columns(pins['concept_node_csv']),
        'concept_edge_columns':_columns(pins['concept_edge_csv']),
        'concept_bindings':deepcopy(bridge['concept_bindings']),
        'relation_bindings':deepcopy(bridge['relation_bindings']),
        'original_artifact_pins':deepcopy(pins),
        'original_relation_csv_utf8':original_csv.decode('utf8'),
        'original_relation_csv_sha256':sha256(original_csv).hexdigest(),
        'origin_native_sha256':fresh['native_sha256'],
        'origin_source_manifest_sha256':fresh['source_manifest_sha256']}


def _rebuild(inventory,pack,kind):
    """Original converters + frozen row selection. All output remains buffered."""
    with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
        modules=_OriginalModules()
        jc=modules.load('json_to_csv'); gc=modules.load('csv_to_graphml')
        schema=modules.load('schema').ATLAS_SCHEMA
    kept={r['record_id'] for r in inventory['records']}
    selected=[r for r in pack['relations'] if r['record_id'] in kept]
    with TemporaryDirectory(prefix='a8-subset-cpu-',dir=PACKAGE) as temporary:
        path=Path(temporary).resolve()
        _require(path.is_relative_to(PACKAGE.resolve()),'A8_PRIVATE_TEMP_REQUIRED')
        (path/'input').mkdir()
        raw=b''.join((json.dumps(row,ensure_ascii=True,sort_keys=True)+'\n').encode('ascii') for row in inventory['native_rows'])
        (path/'input/source.jsonl').write_bytes(raw)
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
            jc.json2csv('source',str(path/'input'),str(path/'csv'),schema,False)
        def rows(name):
            with (path/'csv'/name).open('r',encoding='utf-8-sig',newline='') as stream:
                return list(csv.DictReader(stream))
        emitted=rows('triple_edges_source_from_json_without_emb.csv')
        _require(len(emitted)==len(selected),'A8_FILTERED_CSV_COVERAGE_DIFFERS')
        for actual,frozen in zip(emitted,selected):
            _require(all(actual[k]==frozen['row'][k] for k in (':START_ID',':END_ID','relation',':TYPE','synsets')),
                     'A8_FILTERED_CSV_PROJECTION_DIFFERS')
        native_nodes=rows('triple_nodes_source_from_json_without_emb.csv')
        active_names={row['name:ID'] for row in native_nodes}
        edges=[e for e in pack['concept_edges'] if set(e['owner_record_ids']) & kept and e['row'][':START_ID'] in active_names]
        concept_ids={e['row'][':END_ID'] for e in edges}
        nodes=[deepcopy(n) for n in pack['concept_nodes'] if n['concept_id:ID'] in concept_ids]
        if len(selected)==len(pack['relations']):
            final_raw=pack['original_relation_csv_utf8'].encode('utf8')
            _require(sha256(final_raw).hexdigest()==pack['original_relation_csv_sha256'],
                     'A8_FROZEN_CSV_BYTES_CHANGED')
            serialization='original_frozen_bytes'
        else:
            final_raw=_csv_bytes(pack['relation_columns'],[r['row'] for r in selected])
            serialization='canonical_QUOTE_ALL_UTF8_CRLF'
        (path/'final.csv').write_bytes(final_raw)
        (path/'concept-nodes.csv').write_bytes(_csv_bytes(pack['concept_node_columns'],nodes))
        (path/'concept-edges.csv').write_bytes(_csv_bytes(pack['concept_edge_columns'],[e['row'] for e in edges]))
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
            gc.csvs_to_graphml(str(path/'csv/triple_nodes_source_from_json_without_emb.csv'),
                str(path/'csv/text_nodes_source_from_json.csv'),str(path/'final.csv'),
                str(path/'csv/text_edges_source_from_json.csv'),str(path/'concept-nodes.csv'),
                str(path/'concept-edges.csv'),str(path/'original.graphml'),True)
        original=nx.read_graphml(path/'original.graphml',force_multigraph=True)
        if kind=='relation_rows':
            endpoint_ids={row['name:ID']:gc.get_node_id(row['name:ID'],{}) for row in native_nodes}
            with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
                export_control.export_control(original,path/'final.csv',endpoint_ids,path/'rows.graphml')
            graph=nx.read_graphml(path/'rows.graphml',force_multigraph=True)
        else:
            graph=original
    modules.verify_after()
    provenance=[{'output_csv_ordinal':i,'record_id':r['record_id'],
        'original_csv_ordinal':r['original_csv_ordinal'],'projection_index':r['projection_index']}
        for i,r in enumerate(selected,1)]
    active={'relation_rows':[deepcopy(r['row']) for r in selected],
        'relation_csv_sha256':sha256(final_raw).hexdigest(),
        'relation_csv_serialization':serialization,
        'relation_provenance':provenance,'concept_node_rows':nodes,
        'concept_edge_rows':[deepcopy(e['row']) for e in edges],
        'concept_bindings':[deepcopy(b) for b in pack['concept_bindings'] if b['record_id'] in kept],
        'relation_bindings':[deepcopy(b) for b in pack['relation_bindings'] if b['record_id'] in kept]}
    return graph,active


def bind_cell(inventory,sdk_schema_binding,graph,*,cell_id,export_kind='original'):
    """Bind an existing complete cell using its already-qualified SDK CSV bridge."""
    try:
        _require(type(cell_id) is str and bool(cell_id),'A8_CELL_ID_REQUIRED')
        _require(export_kind in EXPORTS,'A8_UNKNOWN_EXPORT_CONDITION')
        origin,fresh=_origin_inventory(inventory)
        pack=_pack_from_bridge(sdk_schema_binding,origin,fresh)
        inv=_inventory_view(origin,cell_id,set())
        expected,active=_rebuild(inv,pack,export_kind)
        _require(_snapshot(expected)==_snapshot(graph),'A8_BOUND_GRAPH_DIFFERS_FROM_FROZEN_REPLAY')
        schema={'protocol':SCHEMA_VERSION,'cell_id':cell_id,'origin_pack':pack,
            'origin_pack_sha256':_digest(pack),**active}
        return inv,schema,{'protocol':GRAPH_VERSION,'cell_id':cell_id,
            'export_kind':export_kind,'value':deepcopy(graph)}
    except ProjectionError:
        raise
    except Exception:
        raise ProjectionError('A8_CELL_BINDING_FAILED') from None


def project_subset(inventory,schema,graph,removed_ids):
    """Return a fresh exact filtered cell; stable original IDs never renumber.

    Input is the tuple returned by bind_cell (or a previous call's three named
    outputs). removed_ids are original cell-local whole-object record IDs. A
    previously removed known original ID is idempotent. Unknown IDs and mismatched
    cells fail closed. Surviving values and frozen schema values are unchanged.
    The full container retains PRIVATE origin/origin_pack for reprojection.
    Never serialize that container to a model/reader. Use active_cell(result)
    and its explicit native rows or graph instead. Original source context is
    retained by the existing contract, not newly filtered or summarized.
    """
    try:
        _require(type(inventory) is dict and inventory.get('protocol')==INV_VERSION,'A8_BOUND_INVENTORY_REQUIRED')
        _require(type(schema) is dict and schema.get('protocol')==SCHEMA_VERSION,'A8_COMPLETE_FROZEN_SCHEMA_PACK_REQUIRED')
        _require(type(graph) is dict and graph.get('protocol')==GRAPH_VERSION,'A8_BOUND_GRAPH_REQUIRED')
        cell_id=inventory['cell_id']
        _require(schema.get('cell_id')==graph.get('cell_id')==cell_id,'A8_CELL_BINDING_DIFFERS')
        _require(graph.get('export_kind') in EXPORTS,'A8_UNKNOWN_EXPORT_CONDITION')
        origin=inventory['origin']; pack=schema['origin_pack']
        _require(inventory['origin_sha256']==_digest(origin) and schema['origin_pack_sha256']==_digest(pack),
                 'A8_ORIGIN_BINDING_CHANGED')
        origin,fresh=_origin_inventory(origin)
        _require(pack['origin_native_sha256']==fresh['native_sha256'] and
            pack['origin_source_manifest_sha256']==fresh['source_manifest_sha256'],'A8_SCHEMA_INVENTORY_BINDING_DIFFERS')
        original_ids=[r['record_id'] for r in origin['records']]
        old_removed=set(inventory['removed_ids'])
        _require(old_removed <= set(original_ids),'A8_UNKNOWN_REMOVED_ID')
        current=_inventory_view(origin,cell_id,old_removed)
        _require(current==inventory,'A8_CURRENT_INVENTORY_CHANGED')
        current_graph,current_active=_rebuild(current,pack,graph['export_kind'])
        _require({k:schema[k] for k in current_active}==current_active,'A8_CURRENT_SCHEMA_CHANGED')
        _require(_snapshot(current_graph)==_snapshot(graph['value']),'A8_CURRENT_GRAPH_CHANGED')
        _require(type(removed_ids) in (list,tuple,set,frozenset) and
            all(type(rid) is str for rid in removed_ids),'A8_REMOVAL_IDS_REQUIRED')
        _require(len(removed_ids)==len(set(removed_ids)),'A8_DUPLICATE_REMOVAL_ID')
        _require(set(removed_ids) <= set(original_ids),'A8_UNKNOWN_REMOVED_ID')
        removed=old_removed | set(removed_ids)
        projected=_inventory_view(origin,cell_id,removed)
        rebuilt,active=_rebuild(projected,pack,graph['export_kind'])
        projected_schema={'protocol':SCHEMA_VERSION,'cell_id':cell_id,'origin_pack':deepcopy(pack),
            'origin_pack_sha256':_digest(pack),**active}
        return {'inventory':projected,'schema':projected_schema,
            'graph':{'protocol':GRAPH_VERSION,'cell_id':cell_id,'export_kind':graph['export_kind'],'value':rebuilt},
            'projection':{'cell_id':cell_id,'removed_ids':projected['removed_ids'],
                'kept_ids':[r['record_id'] for r in projected['records']],
                'original_to_current_positions':deepcopy(projected['positions']),
                'native_to_csv':deepcopy(active['relation_provenance']),
                'new_model_calls':0,'schema_reinduced':False,
                'graph_delete_used':False,'original_IDs_cell_local':True}}
    except ProjectionError:
        raise
    except Exception:
        raise ProjectionError('A8_CPU_PROJECTION_FAILED') from None


def active_cell(projected):
    """Export active fields only; exclude private reprojection origin packs.

    Example: result=project_subset(inv,schema,graph,removed_ids);
    active=active_cell(result). Consumers receive active['inventory']['native_rows']
    or active['graph']['value'], never the complete reprojection container.
    Native rows expose only id, original_text and the three actual native dict
    fields. Whole retained object values are unchanged. Raw generations, traces
    and arbitrary row metadata remain private. Sources expose only the explicit
    graph_contract source/span fields. Source text remains original context.
    """
    try:
        _require(type(projected) is dict and all(k in projected for k in ('inventory','schema','graph')),
                 'A8_PROJECTED_CELL_REQUIRED')
        inv,schema,graph=(projected[k] for k in ('inventory','schema','graph'))
        _require(inv.get('protocol')==INV_VERSION and schema.get('protocol')==SCHEMA_VERSION
                 and graph.get('protocol')==GRAPH_VERSION,'A8_PROJECTED_CELL_REQUIRED')
        _require(inv['cell_id']==schema['cell_id']==graph['cell_id'],'A8_CELL_BINDING_DIFFERS')
        active_inventory={k:deepcopy(inv[k]) for k in ('cell_id','row_bindings','records','positions')}
        active_inventory['native_rows']=[]
        for row in inv['native_rows']:
            fields=native._native_fields(row)
            active_inventory['native_rows'].append({
                key:deepcopy(row[key]) for key in ('id','original_text',*fields)})
        # The original source contract authenticates text and declared spans.
        # Unrecognized metadata was archived by that contract, not made input.
        native.source_registry(inv['sources'])
        active_inventory['sources']=[]
        for source in inv['sources']:
            active_source={key:deepcopy(source[key]) for key in ('id','source_id','text','sha256') if key in source}
            if 'spans' in source:
                span_fields=('id','start','end_exclusive','sha256','coordinate_system')
                active_source['spans']=[{key:deepcopy(span[key]) for key in span_fields}
                    for span in source['spans']]
            active_inventory['sources'].append(active_source)
        active_schema={k:deepcopy(schema[k]) for k in ('cell_id','relation_rows','relation_provenance',
            'relation_csv_sha256','relation_csv_serialization','concept_node_rows','concept_edge_rows',
            'concept_bindings','relation_bindings')}
        return {'protocol':'A8-active-filtered-cell-v1','cell_id':inv['cell_id'],
            'inventory':active_inventory,'schema':active_schema,'graph':deepcopy(graph),
            'private_reprojection_origin_excluded':True,'original_source_context_retained':True}
    except ProjectionError:
        raise
    except Exception:
        raise ProjectionError('A8_ACTIVE_CELL_EXPORT_FAILED') from None
