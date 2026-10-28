"""Run the explicitly requested post-hoc CPU diagnostics, with aggregate-only output."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
import os

from Experiments.fair_v2_oct24.C6 import core as c
from .metrics import (official_normalizer, aliases, lexical_hit, rate,
                      context_diagnostics, removal_diagnostics, paired_em, interval_precision)

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
RUNTIME = ROOT / 'Experiments/fair_v2_oct24/C6/private/run-oct26-v1/result.private.json'
PREPARED = ROOT / 'Experiments/fair_v2_oct24/C6/private/input-preparation-oct26-v1/prepared.private.json'
D1 = ROOT / 'Experiments/fair_v2_oct24/D1/final_native_oct26_v1/result.json'
EXPECTED_RESULT = '8131c58097903692195cf6405ac925d79bb5602b8862fdb488b507148fac773a'
EXPECTED_D1 = '2260869d48653f314052d167e52e8f32e15ecc3974cc84540bbc87968db8ef12'
PRIMARY_CELLS = ['AS_ORIGINAL', 'AS_G_ORIGINAL', 'V1_ROW', 'V2_ROW']


def write(path, value):
    path.write_bytes(c.canonical(value) + b'\n')


def public_pin(label, pin):
    return {'label': label, 'bytes': pin['bytes'], 'sha256': pin['sha256']}


def main():
    from .bindings import project_bindings
    if (OUT / 'result.json').exists():
        raise ValueError('Existing public result is immutable; no automatic overwrite')
    definition = c.strict_json((OUT / 'definition-binding.json').read_bytes())
    if definition['method_sha256'] != sha256((OUT / 'METHODIK.md').read_bytes()).hexdigest():
        raise ValueError('Operational definitions changed before diagnostics')
    runtime_pin, prepared_pin, d1_pin = c.pin(RUNTIME), c.pin(PREPARED), c.pin(D1)
    if runtime_pin['sha256'] != EXPECTED_RESULT or d1_pin['sha256'] != EXPECTED_D1:
        raise ValueError('Original completed C6 or D1 result changed')
    original = c.strict_json(c.checked(runtime_pin))
    d1 = c.strict_json(c.checked(d1_pin))
    bundle = project_bindings(prepared_pin, runtime_pin)
    ids, gold = bundle['question_ids'], bundle['gold']
    if len(ids) != 60 or len(set(ids)) != 60 or set(gold) != set(ids):
        raise ValueError('The exact bound Q60 roster is required')
    normalize = official_normalizer()
    cells, private_contexts, removals, private_removals = {}, {}, {}, {}
    for cell in c.CELLS:
        cells[cell], private_contexts[cell] = context_diagnostics(ids, bundle['contexts'][cell], gold, normalize)
    for base_arm in ['AS', 'V1']:
        removals[base_arm], private_removals[base_arm] = removal_diagnostics(ids, bundle['removed'][base_arm], gold, normalize)
    em = {}
    for cell in c.CELLS:
        score_rows = original['scores'][cell]['per_question']
        if len(score_rows) != 60 or len({r['question_id'] for r in score_rows}) != 60:
            raise ValueError('Original EM rows do not cover Q60 once')
        em[cell] = {r['question_id']: r['em'] for r in score_rows}
    discordance, private_discordance = {}, {}
    for label, treatment, control in [('V2_ROW_minus_AS_ORIGINAL', 'V2_ROW', 'AS_ORIGINAL'),
                                      ('V2_ROW_minus_V1_ROW', 'V2_ROW', 'V1_ROW')]:
        discordance[label], private_discordance[label] = paired_em(ids, em[treatment], em[control])
        discordance[label].update(treatment=treatment, control=control)
    precision = interval_precision(d1['primary']['H4'])
    if d1['primary']['H4']['cluster_count'] != 39:
        raise ValueError('Original H4 block count differs')
    precision.update(questions=60, paragraph_overlap_blocks=39,
        original_bootstrap_draws=d1['primary']['H4']['bootstrap_draws'],
        original_seed=d1['primary']['H4']['seed'], original_CI_scope=d1['primary']['H4']['CI_scope'])
    supporting = None
    if 'supports' in bundle:
        if set(bundle['supports']) != set(ids):
            raise ValueError('Supporting-paragraph roster differs')
        supporting = rate(lexical_hit('\n'.join(bundle['supports'][q]), aliases(gold[q], normalize), normalize) for q in ids)
    public = {'protocol': 'QA1-posthoc-H4-descriptive-diagnostics-v1',
        'completed_utc': datetime.now(timezone.utc).isoformat(),
        'post_hoc': True, 'new_model_calls': 0, 'new_encoder_calls': 0,
        'new_C6_end_audits': 0, 'new_H4_inference_runs': 0, 'new_significance_tests': 0,
        'question_count': 60, 'primary_table_cells': PRIMARY_CELLS,
        'metrics': {'context_coverage': cells, 'guard_removals': removals,
                    'EM_discordance': discordance, 'H4_interval_precision': precision,
                    'raw_supporting_paragraph_answer_coverage_control': supporting},
        'definitions': {'context_match': 'nonempty complete normalized token sequence in actual stored Top-30 graph text, excluding question',
                        'statement_match': 'same lexical match inside one statement, with exact original supporting-paragraph provenance',
                        'guard_removal_match': 'lexical match in explicitly removed original native EE/VV occurrence; original native JSON fields retained',
                        'not_semantic_entailment_or_full_multihop_support': True,
                        'no_alias_generation_no_retrieval_tuning': True,
                        'empty_normalized_alias_set': 'not measurable; not an automatic match',
                        'normalizer_commit': '922ac98f19a201998dbdae6d7f2887a5258dbdeb',
                        'normalizer_sha256': '10368f619b4d5ef5d83748c05a96c0afd332a14ab5c010740c98d58dfaefe974'},
        'inputs': [public_pin('original_C6_scores', runtime_pin), public_pin('C6_original_preparation', prepared_pin), public_pin('original_D1_final', d1_pin), public_pin('sealed_gold', original['gold_pin'])],
        'software': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                      'sha256': sha256(p.read_bytes()).hexdigest()} for p in sorted(OUT.glob('*.py'))],
        'operational_definition_sha256': definition['method_sha256'],
        'natural_question_ids_answers_aliases_or_statement_texts_public': False,
        'original_primary_component_families_and_overall_stage_changed': False}
    # The public tree is constructed exclusively from fixed labels, counts, rates,
    # original aggregate CI values and opaque file hashes. Case rows are never merged.
    private_root = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'withheld-artifact/89abe802b3eb38ad2057')) / 'Masterarbeit-private-evidence' / '2026-10-26-QA1-v1'
    if private_root.exists():
        raise ValueError('Private diagnostic destination already exists; do not overwrite')
    if private_root.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Private case rows must stay outside the repository')
    private_root.mkdir(parents=True)
    private = {'protocol': public['protocol'], 'source_pins': bundle['private_pins'],
               'runtime_pin': runtime_pin, 'D1_pin': d1_pin,
               'question_ids': ids, 'gold': gold, 'context_diagnostics': private_contexts,
               'removal_diagnostics': private_removals, 'EM_discordance': private_discordance,
               'binding_checks': bundle.get('aggregate_binding_checks', {}),
               'public_result_sha256': sha256(c.canonical(public) + b'\n').hexdigest()}
    write(private_root / 'case-diagnostics.private.json', private)
    write(private_root / 'publication-source.private.json', {'public_result': public})
    write(OUT / 'result.json', public)
    print(json.dumps({'status': 'completed', 'question_count': 60,
        'public_output': 'QA1/result.json', 'private_case_rows_saved_outside_repository': True,
        'new_model_calls': 0, 'H4_half_width_percentage_points': precision['half_width_percentage_points']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        import re
        code = str(error) if re.fullmatch(r'QA1_[A-Z_]+', str(error)) else 'QA1_BINDING_OR_METRIC_FAILURE'
        print(json.dumps({'status': 'failed', 'error_class': type(error).__name__, 'code': code}))
        raise SystemExit(2)
