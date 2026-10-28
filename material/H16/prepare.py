"""Create one frozen N16 sample with the unchanged local C7 annotation UI."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from Tools.experiments.c7_human_annotation_oct24_v1 import contracts as c
from . import sampling, package, evaluate

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'H16'
PRIVATE = (Path.home() / 'withheld-artifact/02f91f9c36719bce6d28'
           / 'withheld-artifact/5d0c4bec61920b9cc8aa')
AUTHOR = Path.home() / 'Downloads/H16-Transferstichprobe-60'
SINGLE_HTML = Path.home() / 'Downloads/H16-Autorenannotation-60.html'


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(c.canonical(value))
    return c.file_pin(path)


def prepare():
    publication_pin = c.file_pin(PUBLIC / 'publication.json')
    publication = sampling.checked(publication_pin)
    sampling.validate_publication(publication)
    c.require(not PRIVATE.exists() and not AUTHOR.exists() and not SINGLE_HTML.exists()
              and not (PUBLIC / 'preparation.json').exists(),
              'H16 fresh preparation required; existing sample is not redrawn')
    code_pins = [c.file_pin(path) for path in
                 (Path(__file__), Path(sampling.__file__), Path(package.__file__),
                  Path(evaluate.__file__), PUBLIC / 'PROTOKOLL.md', package.c7.TEMPLATE,
                  Path(c.__file__), Path(package.c7.__file__))]
    started = datetime.now(timezone.utc).isoformat()
    save(PRIVATE / 'preparation-start.private.json', {
        'protocol': sampling.PROTOCOL, 'started_UTC': started,
        'publication_pin': publication_pin, 'code_pins': code_pins,
        'sampling_seed': sampling.SEED, 'CI_seed': evaluate.CI_SEED,
        'human_labels_created': 0, 'external_evaluator_labels_read': False,
        'draw_performed': False})
    loaded = sampling.load_population()
    drawn = sampling.draw_sample(loaded['rows'], publication=publication)
    selected = drawn['selected_rows']
    selected_pin = save(PRIVATE / 'selected60.private.json', {
        'protocol': sampling.PROTOCOL, 'created_UTC': datetime.now(timezone.utc).isoformat(),
        **drawn, 'input_pins': loaded['input_pins'], 'publication_pin': publication_pin,
        'code_pins': code_pins, 'actual_draws': 1})
    bundle = package.build_package(selected, design=drawn['design'], provenance={
        'selected_sample_pin': selected_pin, 'publication_pin': publication_pin,
        'input_pins': loaded['input_pins'], 'scientific_status': 'exploratory_N16'},
        synthetic=False)
    receipt = package.publish(bundle, public_out=AUTHOR, private_out=PRIVATE / 'evaluator')
    with SINGLE_HTML.open('xb') as stream:
        stream.write(bundle['html'].encode('utf8'))
    html_pin = c.file_pin(SINGLE_HTML)
    c.require(html_pin['sha256'] == bundle['manifest']['html_sha256'],
              'H16 single-file HTML differs')
    for pin in code_pins:
        c.require(c.file_pin(pin['path']) == pin, 'H16 code changed during preparation')
    terminal = save(PRIVATE / 'preparation-complete.private.json', {
        'protocol': sampling.PROTOCOL, 'finished_UTC': datetime.now(timezone.utc).isoformat(),
        'selected_sample_pin': selected_pin, 'receipt': receipt,
        'single_HTML_pin': html_pin, 'publication_pin': publication_pin,
        'actual_draws': 1, 'human_labels_created': 0, 'model_calls': 0,
        'external_evaluator_labels_read': False, 'code_pins': code_pins})
    summary = {'protocol': sampling.PROTOCOL, 'status': 'prepared_awaiting_author_export',
               'prepared_UTC': datetime.now(timezone.utc).isoformat(),
               'N16_publication_commit': publication['commit'], 'sample_size': 60,
               'sampling_seed': sampling.SEED, 'CI_seed': evaluate.CI_SEED,
               'arm_counts': dict(Counter(r['arm'] for r in selected)),
               'type_counts': drawn['design']['type_counts'],
               'population_counts': drawn['design']['population_counts'],
               'VV_shortfall_documented': drawn['design']['VV_shortfall_documented'],
               'source_population': 20,
               'distinct_sources_in_sample': len({r['source_id'] for r in selected}),
               'source_family_counts': dict(Counter(r['family'] for r in selected)),
               'design': drawn['design'], 'author_HTML_pin': html_pin,
               'packet_sha256': bundle['packet']['packet_sha256'],
               'author_packet_pin': c.file_pin(AUTHOR / 'h16.blind.json'),
               'private_key_pin': receipt['private_key_pin'],
               'private_preparation_pin': terminal, 'code_pins': code_pins,
               'human_labels_created': 0, 'author_export_received': False,
               'supported_rates': None, 'difference_V2_minus_AS': None,
               'difference_CI': None, 'sign_comparison': None,
               'model_calls': 0, 'actual_draws': 1,
               'scientific_status': 'exploratory, outside Holm and overall verdict',
               'public_scope': 'Counts and method only. Statements, mapping and labels remain outside Git.'}
    save(PUBLIC / 'preparation.json', summary)
    print(json.dumps({k: summary[k] for k in
          ('status', 'sample_size', 'arm_counts', 'type_counts', 'distinct_sources_in_sample',
           'author_HTML_pin', 'human_labels_created', 'model_calls')}, ensure_ascii=False))
    return summary


if __name__ == '__main__':
    prepare()
