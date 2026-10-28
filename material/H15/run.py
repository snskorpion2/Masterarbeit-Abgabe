"""Import one direct, packet-bound H15 author export; keep original bytes private."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from . import annotation, evaluate, prepare as files


def complete(preparation_receipt, author_export, *, author_confirmed=False, public_output=files.HERE):
    files.need(author_confirmed is True,'H15_EXPLICIT_AUTHOR_ATTRIBUTION_REQUIRED')
    preparation_pin = files.pin(preparation_receipt)
    preparation = files.read_pinned(preparation_pin)
    files.need(preparation.get('protocol') == 'H15-packet-preparation-complete:v1'
        and preparation.get('natural_draws') == 1 and preparation.get('author_labels_created') == 0,
        'H15_ORIGINAL_PREPARATION_REQUIRED')
    private = Path(preparation_receipt).resolve().parent
    output = private/'author-analysis'
    raw_export = Path(author_export).resolve().read_bytes()
    sealed_export = files.save(private/'author-imports'/(files.sha256(raw_export).hexdigest()+'.original.json'),raw_export)
    packet = files.read_pinned(preparation['packet_pin'])
    key = files.read_pinned(preparation['private_key_pin'])
    original = files.read_pinned(sealed_export)
    ratings = annotation.validate_annotations(original,packet,require_complete=False)
    files.need(key['dataset_id'] == packet['dataset_id'] and key['packet_sha256'] == packet['packet_sha256'],
               'H15_ORIGINAL_KEY_AND_PACKET_DIFFERS')
    complete_labels = len(ratings)==30 and all(row['label'] in annotation.LABELS for row in ratings.values())
    if not complete_labels:
        # Preserve the partial direct export, but do not consume the one full
        # analysis slot or run its bootstrap. A later complete export may enter.
        return {'status':'pending_author_annotations','annotation_entries':len(ratings),
            'valid_author_labels':sum(row['label'] in annotation.LABELS for row in ratings.values()),
            'agreement':None,'descriptive_retention':None,'H2_qualification':None,
            'original_export_preserved':True,'model_calls':0}
    files.need(not output.exists(),'H15_EXISTING_AUTHOR_ANALYSIS_MUST_NOT_BE_REPLAYED')
    output.mkdir(exist_ok=False)
    code = files.code_pins()
    start = files.save(output/'analysis-start.private.json',{
        'protocol':'H15-direct-author-import-and-N15-analysis:v1',
        'started_UTC':datetime.now(timezone.utc).isoformat(),'preparation_pin':preparation_pin,
        'original_export_pin':sealed_export,'annotation_origin':original['annotation_origin'],
        'author_confirmed':True,'code_pins':code,'model_calls':0,
        'original_annotations_modified':False,'new_selection':False})
    result = evaluate.evaluate(key,original,author_confirmed=True)
    files.need(result['complete_author_export'] is True,'H15_COMPLETE_AUTHOR_ANALYSIS_REQUIRED')
    for binding in code:
        files.need(files.pin(binding['path']) == binding,'H15_CODE_CHANGED_DURING_AUTHOR_ANALYSIS')
    private_result = files.save(output/'result.aggregate.private.json',result)
    end = files.save(output/'analysis-complete.private.json',{'completed_UTC':files.now(),
        'analysis_start_pin':start,'original_export_pin':sealed_export,'result_pin':private_result,
        'models_called':0,'original_export_unchanged':True})
    public_output = Path(public_output).resolve()
    old = public_output/'result.json'
    if old.exists():
        files.save(output/'preparation-public-result.private.json',old.read_bytes())
    result.update(completed_UTC=files.now(),source_preparation_sha256=preparation_pin['sha256'],
        author_original_export_sha256=sealed_export['sha256'],private_analysis_receipt_sha256=end['sha256'],
        actual_N15_evaluations=1,original_author_export_modified=False,original_C3_labels_modified=False)
    public_output.mkdir(parents=True,exist_ok=True)
    target = public_output/'result.author-complete.tmp'
    with target.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')
    target.replace(old)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation-receipt',required=True,type=Path)
    parser.add_argument('--author-export',required=True,type=Path)
    parser.add_argument('--author-confirmed',action='store_true')
    args = parser.parse_args(argv)
    result = complete(args.preparation_receipt,args.author_export,author_confirmed=args.author_confirmed)
    print(json.dumps({'status':result['status'],'annotation_entries':result['annotation_entries'],
        'agreement':result['agreement'],'descriptive_retention':result['descriptive_retention'],
        'H2_qualification':result['H2_qualification'],'model_calls':0},ensure_ascii=False,indent=2))
    return result


if __name__ == '__main__':
    main()
