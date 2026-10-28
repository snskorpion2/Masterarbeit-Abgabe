"""Freeze N15 once and build its private, offline author packet. No models."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path
import re
import subprocess

from . import annotation, sampling

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
N15_PATH = 'Experiments/fair_v2_oct24/G1/nachtrag_15_menschliche_pruefung_h2.md'
C3_PROTOCOL = 'C3-direct-four-active-inventory-retention:oct24-v1'
G2_SHA = '8377548a064de1fadd28baf674290be02021457ab38b49056ac9dde45dddf9f5'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return sha256(canonical(value)).hexdigest()


def pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}


def read_pinned(binding):
    path = Path(binding['path']).resolve()
    raw = path.read_bytes()
    need(len(raw) == binding['bytes'] and sha256(raw).hexdigest() == binding['sha256'], 'H15_INPUT_BYTE_BINDING_CHANGED')
    def unique(pairs):
        value = {}
        for key, child in pairs:
            need(key not in value, 'H15_DUPLICATE_JSON_KEY')
            value[key] = child
        return value
    def invalid(_):
        raise ValueError('H15_NONFINITE_JSON')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def save(path, value):
    path = Path(path)
    raw = value if isinstance(value, bytes) else canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        need(path.read_bytes() == raw, 'H15_EXISTING_ARTIFACT_MUST_NOT_CHANGE')
    else:
        with path.open('xb') as stream:
            stream.write(raw)
    return pin(path)


def code_pins():
    return [pin(path) for path in sorted(HERE.glob('*.py'))] + [pin(HERE/'annotate.html')]


def verify_publication(binding):
    publication = read_pinned(binding)
    need(publication.get('protocol') == 'H15-N15-single-path-publication:v1'
         and publication.get('only_changed_path') == N15_PATH
         and publication.get('published_before_H15_natural_selection') is True
         and publication.get('H15_natural_draws_started') == 0,
         'H15_N15_SINGLE_PATH_PUBLICATION_REQUIRED')
    commit = publication.get('commit')
    need(type(commit) is str and re.fullmatch('[0-9a-f]{40}', commit) is not None, 'H15_PUBLISHED_COMMIT_REQUIRED')
    raw = subprocess.check_output(['git', 'show', commit+':'+N15_PATH], cwd=ROOT)
    need(sha256(raw).hexdigest() == publication['sha256'] and len(raw) == publication['bytes'],
         'H15_N15_PUBLISHED_BYTES_DIFFER')
    need((ROOT/N15_PATH).read_bytes() == raw, 'H15_N15_WORKING_CONTRACT_DIFFERS')
    return publication


def freeze_selection(manifest_path, private_output, *, allow_real_inputs=False):
    need(allow_real_inputs is True, 'H15_EXPLICIT_REAL_INPUTS_REQUIRED')
    manifest_path, private_output = Path(manifest_path).resolve(), Path(private_output).resolve()
    need(not private_output.is_relative_to(ROOT) and not private_output.exists(), 'H15_FRESH_OUTSIDE_REPOSITORY_SELECTION_REQUIRED')
    manifest_pin = pin(manifest_path)
    manifest = read_pinned(manifest_pin)
    need(manifest.get('protocol') == 'H15-explicit-preparation-inputs:v1'
         and set(manifest) == {'protocol','N15_publication','C3','G2','C3_run'}, 'H15_EXPLICIT_INPUT_MANIFEST_REQUIRED')
    publication = verify_publication(manifest['N15_publication'])
    code = code_pins()
    private_output.mkdir(parents=True, exist_ok=False)
    start = save(private_output/'preparation-start.private.json', {
        'protocol':'H15-N15-preparation-start:v1', 'started_UTC':now(),
        'N15_publication_pin':manifest['N15_publication'], 'input_manifest_pin':manifest_pin,
        'N15_commit':publication['commit'], 'code_pins':code,
        'natural_draws_started':0, 'author_labels_opened':False, 'model_calls':0})
    c3, g2 = read_pinned(manifest['C3']), read_pinned(manifest['G2'])
    need(manifest['G2']['sha256'] == G2_SHA and g2.get('frozen') is True, 'H15_ORIGINAL_FROZEN_G2_REQUIRED')
    need(c3.get('protocol') == 'C3-fixed-roster-source-equal-H2-summary:oct24-v1'
         and c3.get('closed') is True and len(c3.get('records', [])) == 2336, 'H15_FINAL_ORIGINAL_C3_REQUIRED')
    families = {row['source_id']:row['family'] for row in g2['bindings']['A4']['sources']}
    valid = {arm:{row['source_id'] for row in c3['records'] if row['arm'] == arm and row['status'] == 'valid'}
             for arm in ('AS','V2')}
    eligible = sorted(valid['AS'] & valid['V2'])
    save(private_output/'selection-start.private.json', {'started_UTC':now(),
        'preparation_start_pin':start, 'C3_pin':manifest['C3'], 'G2_pin':manifest['G2'],
        'natural_draw_calls_started':1, 'seed':sampling.SEED, 'eligible_source_count':len(eligible)})
    drawn = sampling.draw_sample(c3['records'], families, eligible)
    value = {'protocol':'H15-frozen-selection:v1', 'selected_UTC':now(), 'draw':drawn,
        'N15_publication_pin':manifest['N15_publication'], 'input_manifest_pin':manifest_pin,
        'C3_pin':manifest['C3'], 'G2_pin':manifest['G2'], 'C3_run':manifest['C3_run'],
        'code_pins_at_selection':code, 'natural_draw_calls':1, 'model_calls':0,
        'author_labels_opened':False}
    for item in code:
        need(pin(item['path']) == item, 'H15_CODE_CHANGED_DURING_SELECTION')
    return save(private_output/'selected15.private.json', value)


def materialize_cases(selection, c3, segment_reader):
    """Use only the actual byte-bound original C3 cases, never rebuild them."""
    observations = {(row['source_id'],row['draw'],row['arm'],row['obligation_id']):row
                    for row in c3['records'] if row['arm'] in ('AS','V2')}
    jobs = {row['key']:row for row in c3.get('jobs',[])}
    need(len(jobs) == len(c3.get('jobs',[])) and bool(jobs), 'H15_FINAL_C3_JOB_ROSTER_REQUIRED')
    public, private, originals, source_pins = [], [], [], []
    cache = {}
    for selected in selection['draw']['cases']:
        obs = observations[selected['source_id'],selected['draw'],selected['arm'],selected['obligation_id']]
        observed = obs.get('observation')
        need(type(observed) is dict and type(observed.get('job_key')) is str
             and observed['job_key'] in jobs, 'H15_FINAL_C3_OBSERVATION_JOB_REQUIRED')
        job_meta = jobs[observed['job_key']]
        segment_pin = job_meta.get('segment_pin')
        need(type(segment_pin) is dict and {'path','bytes','sha256'} <= set(segment_pin)
             and type(job_meta.get('id')) is str
             and observed['job_key'] == 'C3:'+segment_pin['sha256']+':'+job_meta['id'],
             'H15_FINAL_C3_JOB_SEGMENT_SHA_DIFFERS')
        cache_key = (segment_pin['path'],segment_pin['bytes'],segment_pin['sha256'])
        if cache_key not in cache:
            cache[cache_key] = segment_reader(segment_pin)
        segment,rows,mapping,bindings = cache[cache_key]
        need(segment.get('protocol') == C3_PROTOCOL and segment.get('source_id') == selected['source_id']
             and segment.get('draw') == selected['draw'], 'H15_ORIGINAL_C3_SEGMENT_BINDING_DIFFERS')
        matching_jobs = [job for job in segment.get('jobs',[]) if job.get('id') == job_meta['id']]
        need(len(matching_jobs) == 1 and 'original_envelope' in matching_jobs[0],
             'H15_FINAL_C3_ORIGINAL_JOB_REQUIRED')
        # Reuse the existing lossless request reconstruction, not an ID-only join.
        from Experiments.fair_v2_oct24.C3.prepare import batch
        reconstructed = batch.reconstruct_cases(matching_jobs[0]['original_envelope'])
        actual = [row['case'] for row in reconstructed if row['case']['id'] == observed.get('case_id')]
        need(len(actual) == 1, 'H15_SOL_AND_ORIGINAL_CASE_JOIN_DIFFERS')
        original = sampling.original_case(rows, mapping, selected)
        need(canonical(actual[0]) == canonical(original), 'H15_FINAL_C3_WHOLE_CASE_INPUT_DIFFERS')
        need(obs['status'] == 'valid' and obs['raw_code'] == selected['sol_raw_code']
             and observed['case_id'] == original['id'], 'H15_SOL_AND_ORIGINAL_CASE_JOIN_DIFFERS')
        inventory, witness_map = sampling.neutral_inventory(original['carrier'])
        obligation = original['obligation']
        text = obligation['meaning']+'\n\nZu erhaltende Aspekte:\n'+'\n'.join('- '+part for part in obligation['required_aspects'])
        public.append({'item_id':selected['item_id'], 'reference_text':text,
            'source_text':original['source']['text'], 'inventory':inventory})
        private.append({**deepcopy(selected), 'original_case_id':original['id'],
            'original_case_sha256':digest(original), 'original_obligation':deepcopy(obligation),
            'original_carrier_sha256':digest(original['carrier']), 'witness_mapping':witness_map})
        originals.append({'item_id':selected['item_id'], 'case':original})
        for binding in bindings:
            if binding not in source_pins:
                source_pins.append(binding)
    need(len(public) == 30 and len({p['item_id'] for p in public}) == 30, 'H15_EXACT_THIRTY_CASES_REQUIRED')
    for pair in selection['draw']['selected_pairs']:
        ids = [row['item_id'] for row in private if row['pair_id'] == pair['pair_id']]
        cases = [row for row in public if row['item_id'] in ids]
        need(len(cases) == 2 and cases[0]['source_text'] == cases[1]['source_text']
             and cases[0]['reference_text'] == cases[1]['reference_text'], 'H15_PAIRED_SOURCE_REFERENCE_DIFFERS')
    return public, private, originals, source_pins


def build_package(selection_pin, author_html, *, public_output=HERE):
    selection = read_pinned(selection_pin)
    need(selection.get('protocol') == 'H15-frozen-selection:v1' and selection.get('natural_draw_calls') == 1,
         'H15_ONE_FROZEN_SELECTION_REQUIRED')
    private_output = Path(selection_pin['path']).resolve().parent
    author_html, public_output = Path(author_html).resolve(), Path(public_output).resolve()
    need(not author_html.is_relative_to(ROOT) and not author_html.is_relative_to(private_output)
         and not author_html.exists() and not (public_output/'result.json').exists(), 'H15_FRESH_AUTHOR_HTML_REQUIRED')
    publication = verify_publication(selection['N15_publication_pin'])
    for binding in selection['code_pins_at_selection']:
        need(pin(binding['path']) == binding, 'H15_CODE_CHANGED_AFTER_SELECTION')
    c3 = read_pinned(selection['C3_pin'])
    def segment_reader(segment_pin):
        # The final C3 export supplies this immutable binding. A current file
        # at the old controller path is not an independent input authority.
        manifest = read_pinned(segment_pin)
        return manifest,read_pinned(manifest['cases_pin']),read_pinned(manifest['mapping_pin']), [segment_pin,manifest['cases_pin'],manifest['mapping_pin']]
    public, private, originals, source_pins = materialize_cases(selection,c3,segment_reader)
    dataset_id = 'd-'+digest(['H15-packet-v1',selection['draw']['seed'],[p['item_id'] for p in public]])[:32]
    packet = annotation.seal_packet({'format':annotation.PACKET_FORMAT,'dataset_id':dataset_id,'items':public})
    key = {'format':'h15-private-key-v1','dataset_id':dataset_id,'packet_sha256':packet['packet_sha256'],'items':private}
    packet_pin = save(private_output/'packet.private.json',packet)
    key_pin = save(private_output/'key.private.json',key)
    original_cases_pin = save(private_output/'original-cases.private.json',originals)
    html = annotation.build_html(packet).encode('utf-8')
    private_html_pin = save(private_output/'author-page.private.html',html)
    html_pin = save(author_html,html)
    need(html_pin['sha256'] == private_html_pin['sha256'], 'H15_AUTHOR_HTML_COPY_DIFFERS')
    for binding in selection['code_pins_at_selection']:
        need(pin(binding['path']) == binding, 'H15_CODE_CHANGED_DURING_PACKET_BUILD')
    terminal = save(private_output/'preparation-complete.private.json',{
        'protocol':'H15-packet-preparation-complete:v1','completed_UTC':now(),
        'selection_pin':selection_pin,'packet_pin':packet_pin,'private_key_pin':key_pin,
        'original_cases_pin':original_cases_pin,'source_pins':source_pins,'author_HTML_pin':html_pin,
        'natural_draws':1,'model_calls':0,'author_labels_created':0,'author_export_received':False,
        'all_required_aspects_shown':True,'full_C3_inventory_values_and_order_preserved':True})
    summary = {'protocol':'H15-N15-author-validation-preparation:v1','status':'prepared_awaiting_author_export',
        'prepared_UTC':now(),'N15_commit':publication['commit'],'N15_sha256':publication['sha256'],
        'seed':sampling.SEED,'meaning_pairs':15,'cases':30,'source_frame':17,
        'family_meaning_quotas':selection['draw']['quotas'],
        'eligible_unique_meanings_by_family':selection['draw']['eligible_unique_meanings_by_family'],
        'sample_source_count':len({row['source_id'] for row in private}),
        'natural_draws':1,'resampling':False,'model_calls':0,
        'author_export_received':False,'author_labels_created':0,'kappa':None,'retention_rates':None,
        'packet_sha256':packet['packet_sha256'],'author_HTML':{'file_name':author_html.name,'bytes':html_pin['bytes'],'sha256':html_pin['sha256']},
        'private_preparation_receipt_sha256':terminal['sha256'],
        'metadata_blinding':True,'technical_access_isolation_claimed':False,
        'full_source_reference_aspects_and_inventory':True,'original_Sol_labels_unchanged':True,
        'no_Holm_or_overall_judgment_input':True,'public_data_scope':'Code, methodology and aggregate preparation counts only'}
    save(public_output/'result.json',summary)
    return summary,terminal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--input-manifest',type=Path)
    group.add_argument('--frozen-selection',type=Path)
    parser.add_argument('--private-output',type=Path)
    parser.add_argument('--author-html',required=True,type=Path)
    parser.add_argument('--allow-real-inputs',action='store_true')
    args = parser.parse_args(argv)
    need(args.allow_real_inputs is True,'H15_EXPLICIT_REAL_INPUTS_REQUIRED')
    need(not args.author_html.resolve().is_relative_to(ROOT) and not args.author_html.exists()
         and not (HERE/'result.json').exists(), 'H15_FRESH_AUTHOR_HTML_REQUIRED')
    if args.input_manifest:
        need(args.private_output is not None,'H15_EXPLICIT_PRIVATE_OUTPUT_REQUIRED')
        selection_pin = freeze_selection(args.input_manifest,args.private_output,allow_real_inputs=True)
    else:
        selection_pin = pin(args.frozen_selection)
    summary,_ = build_package(selection_pin,args.author_html)
    print(json.dumps({key:summary[key] for key in ('status','meaning_pairs','cases','family_meaning_quotas','author_HTML','natural_draws','model_calls')},ensure_ascii=False,indent=2))
    return summary


if __name__ == '__main__':
    main()
