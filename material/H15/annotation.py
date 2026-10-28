"""Build and validate the offline, blinded H15 author annotation page.

Only an already blinded public packet enters this module. No files, models,
reference stores or private keys are read at import or by the pure functions.
The page displays Python-rendered JSON strings, retaining large integer and
floating-point representations that a browser's JSON number parser can lose.
"""
from __future__ import annotations

import base64
import copy
from hashlib import sha256
import json
from pathlib import Path
import re

PACKET_FORMAT = 'h15-packet-v1'
ANNOTATION_FORMAT = 'h15-human-annotations-v1'
LABELS = ('retained', 'partially_retained', 'not_retained', 'undetermined')
_ID = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _exact(value, fields, message):
    _need(type(value) is dict and set(value) == set(fields), message)


def _text(value, *, empty=False):
    _need(type(value) is str and (empty or bool(value.strip())), 'Text field is invalid')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise ValueError('Text is not valid UTF-8') from exc


def _id(value):
    _need(type(value) is str and _ID.fullmatch(value) is not None, 'Neutral identifier is invalid')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _json_value(value):
    if type(value) is dict:
        _need(all(type(k) is str for k in value), 'Inventory JSON keys must be strings')
        for key, child in value.items():
            _text(key, empty=True)
            _json_value(child)
    elif type(value) is list:
        for child in value:
            _json_value(child)
    elif type(value) is str:
        _text(value, empty=True)
    else:
        _need(value is None or type(value) in (int, float, bool), 'Inventory must contain native JSON values')
    # Also rejects nonfinite numbers and invalid surrogate sequences.
    canonical(value)


def packet_digest(packet):
    return sha256(canonical({k: v for k, v in packet.items() if k != 'packet_sha256'})).hexdigest()


def validate_packet(packet, *, expected_cases=30):
    _need(type(expected_cases) is int and expected_cases > 0, 'Expected case count is invalid')
    _exact(packet, ('format', 'dataset_id', 'packet_sha256', 'items'), 'Unexpected public packet fields')
    _need(packet['format'] == PACKET_FORMAT, 'Unknown H15 packet format')
    _id(packet['dataset_id'])
    _need(type(packet['packet_sha256']) is str and _SHA.fullmatch(packet['packet_sha256']) is not None,
          'Packet SHA256 is invalid')
    _need(type(packet['items']) is list and len(packet['items']) == expected_cases, 'Unexpected H15 case count')
    seen = set()
    for item in packet['items']:
        _exact(item, ('item_id', 'reference_text', 'source_text', 'inventory'), 'Unexpected public case fields')
        _id(item['item_id'])
        _need(item['item_id'] not in seen, 'Duplicate case identifier')
        seen.add(item['item_id'])
        _text(item['reference_text'])
        _text(item['source_text'])
        _need(type(item['inventory']) is list, 'Complete inventory must be a list')
        _json_value(item['inventory'])
    _need(packet_digest(packet) == packet['packet_sha256'], 'Packet fingerprint mismatch')
    return copy.deepcopy(packet)


def seal_packet(base, *, expected_cases=30):
    _exact(base, ('format', 'dataset_id', 'items'), 'Unexpected unsealed packet fields')
    result = copy.deepcopy(base)
    result['packet_sha256'] = packet_digest(result)
    return validate_packet(result, expected_cases=expected_cases)


def validate_annotations(document, packet=None, *, dataset_id=None, packet_sha256=None,
                         item_ids=None, require_complete=False):
    """Return original per-item rows, never remapping labels or rewriting text.

    A trusted full public packet OR its three explicit binding fields is
    accepted. The private evaluation key need not carry source texts.
    The UI-origin marker does not authenticate authorship; the evaluator
    separately requires the user's explicit attribution to the author.
    """
    if packet is not None:
        _need(dataset_id is None and packet_sha256 is None and item_ids is None,
              'Choose either packet or explicit binding metadata')
        _need(type(packet) is dict and type(packet.get('items')) is list, 'Trusted packet required')
        trusted = validate_packet(packet, expected_cases=len(packet['items']))
        dataset_id, packet_sha256 = trusted['dataset_id'], trusted['packet_sha256']
        item_ids = [row['item_id'] for row in trusted['items']]
    _id(dataset_id)
    _need(type(packet_sha256) is str and _SHA.fullmatch(packet_sha256) is not None, 'Expected packet SHA256 required')
    _need(type(item_ids) in (list, tuple) and len(item_ids) > 0 and len(set(item_ids)) == len(item_ids),
          'Distinct expected item IDs required')
    for identity in item_ids:
        _id(identity)
    _exact(document, ('format', 'dataset_id', 'packet_sha256', 'exported_at', 'annotation_origin', 'annotations'),
           'Unexpected direct annotation export fields')
    _need(document['format'] == ANNOTATION_FORMAT, 'Unknown H15 annotation format')
    _need(document['dataset_id'] == dataset_id and document['packet_sha256'] == packet_sha256,
          'Annotation export belongs to another packet')
    _need(document['annotation_origin'] == 'human_ui_input', 'Direct UI export origin required')
    _text(document['exported_at'])
    _need(type(document['annotations']) is list, 'Annotation rows must be a list')
    allowed, rows = set(item_ids), {}
    for row in document['annotations']:
        _exact(row, ('item_id', 'label', 'comment', 'updated_at'), 'Unexpected annotation row fields')
        _need(type(row['item_id']) is str and row['item_id'] in allowed and row['item_id'] not in rows,
              'Unknown or duplicate annotation ID')
        _need(row['label'] is None or row['label'] in LABELS, 'Unknown H15 annotation label')
        _text(row['comment'], empty=True)
        if row['updated_at'] is not None:
            _text(row['updated_at'])
        _need(row['label'] is None or row['updated_at'] is not None, 'Selected labels need their UI timestamp')
        rows[row['item_id']] = copy.deepcopy(row)
    if require_complete:
        _need(set(rows) == allowed and all(row['label'] in LABELS for row in rows.values()),
              'Complete direct author export required')
    return rows


def build_html(packet, *, expected_cases=30):
    """Return one self-contained page, including exact full inventory text."""
    trusted = validate_packet(packet, expected_cases=expected_cases)
    core = {k: v for k, v in trusted.items() if k != 'packet_sha256'}
    # Render JSON on the Python side, before a JavaScript parser could round
    # a native large integer or turn 1.0 into 1. Order and duplicates persist.
    displays = [[json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
                 for value in item['inventory']] for item in trusted['items']]
    payload = {'packet_core_utf8_b64': base64.b64encode(canonical(core)).decode('ascii'),
               'packet_sha256': trusted['packet_sha256'], 'inventory_texts': displays}
    raw = canonical(payload)
    template = Path(__file__).with_name('annotate.html').read_text(encoding='utf-8')
    for marker in ('__H15_EMBEDDED_DATA__', '__H15_PAYLOAD_SHA256__'):
        _need(template.count(marker) == 1, 'HTML replacement marker must occur once')
    return template.replace('__H15_EMBEDDED_DATA__', base64.b64encode(raw).decode('ascii')).replace(
        '__H15_PAYLOAD_SHA256__', sha256(raw).hexdigest())
