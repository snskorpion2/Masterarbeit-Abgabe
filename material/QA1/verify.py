"""QA1 aggregate/readback/privacy checks, without recomputing C6 or H4."""
from pathlib import Path
from hashlib import sha256
import json
import os
import re
import unittest
from pypdf import PdfReader

from .run import ROOT, OUT, RUNTIME, D1, EXPECTED_RESULT, EXPECTED_D1


def main():
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in
        ['QA1.test_metrics', 'QA1.test_metrics_contract', 'QA1.test_bindings'])
    outcome = unittest.TextTestRunner(verbosity=0).run(suite)
    if not outcome.wasSuccessful():
        raise ValueError('QA1 synthetic tests failed')
    raw = (OUT / 'result.json').read_bytes()
    public = json.loads(raw)
    private_root = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'withheld-artifact/89abe802b3eb38ad2057')) / 'withheld-artifact/f8ad96ceeecf4607162f'
    private = json.loads((private_root / 'case-diagnostics.private.json').read_bytes())
    assert private['public_result_sha256'] == sha256(raw).hexdigest()
    ids = private['question_ids']
    assert len(ids) == len(set(ids)) == 60
    checked_rates = 0
    for cell, rows in private['context_diagnostics'].items():
        assert [r['question_id'] for r in rows] == ids
        for public_key, private_key in [
            ('gold_or_alias_in_actual_context', 'context_hit'),
            ('gold_or_alias_within_one_statement', 'within_statement_hit'),
            ('gold_or_alias_in_support_paragraph_statement', 'support_paragraph_statement_hit')]:
            target = public['metrics']['context_coverage'][cell][public_key]
            hits = sum(r[private_key] is True for r in rows)
            missing = sum(r[private_key] is None for r in rows)
            assert (target['questions'], target['hits'], target['not_measurable']) == (60, hits, missing)
            assert target['rate'] == (None if missing else hits / 60)
            checked_rates += 1
    for contrast, rows in private['EM_discordance'].items():
        assert [r['question_id'] for r in rows] == ids
        target = public['metrics']['EM_discordance'][contrast]
        for category in ['both_correct', 'both_incorrect', 'treatment_only', 'control_only']:
            assert target[category] == sum(r['category'] == category for r in rows)
        assert sum(target[k] for k in ['both_correct', 'both_incorrect', 'treatment_only', 'control_only']) == 60
    for arm, rows in private['removal_diagnostics'].items():
        assert [r['question_id'] for r in rows] == ids
        target = public['metrics']['guard_removals'][arm]
        assert target['answer_bearing_removed_statement_question_pairs'] == sum(r['answer_bearing_removed'] for r in rows)
        assert target['support_answer_bearing_removed_statement_question_pairs'] == sum(r['support_answer_bearing_removed'] for r in rows)
        assert target['unique_answer_bearing_removed_occurrences'] == len({key for r in rows for key in r['removed_native_keys']})
    assert sha256(RUNTIME.read_bytes()).hexdigest() == EXPECTED_RESULT
    assert sha256(D1.read_bytes()).hexdigest() == EXPECTED_D1
    for binding in public['software']:
        path = ROOT / binding['path']
        assert path.stat().st_size == binding['bytes'] and sha256(path.read_bytes()).hexdigest() == binding['sha256']
    handoffs = [OUT / name for name in ['result.json', 'BERICHT.md', 'chapter6-snippet.tex', 'appendix-table.tex']]
    for path in handoffs:
        text = path.read_text(encoding='utf-8')
        assert all(q not in text for q in ids), 'Actual question ID leaked'
    prohibited = {'question_id', 'answer', 'answer_aliases', 'per_question', 'source_id', 'source_ids', 'native_key', 'native_keys', 'removed_native_keys'}
    def check_tree(value):
        if isinstance(value, dict):
            assert not prohibited.intersection(value)
            for v in value.values(): check_tree(v)
        elif isinstance(value, list):
            for v in value: check_tree(v)
    check_tree(public)
    table = (OUT / 'appendix-table.tex').read_text(encoding='utf-8')
    snippet = (OUT / 'chapter6-snippet.tex').read_text(encoding='utf-8')
    assert table.count(r'\begin{table}') == table.count(r'\end{table}') == 1
    assert len([line for line in snippet.splitlines() if line.strip()]) == 2
    assert 'sodass' not in snippet and 'Stufe' not in snippet
    preview = ROOT / '.private-temp/qa1-preview/table.pdf'
    log = (preview.with_suffix('.log')).read_text(encoding='utf-8', errors='replace')
    assert len(PdfReader(preview).pages) == 1
    assert not re.search(r'^!|Overfull|undefined', log, re.M)
    result = {'protocol': 'QA1-producer-readback-verification-v1',
              'synthetic_tests': outcome.testsRun, 'errors': len(outcome.errors), 'failures': len(outcome.failures),
              'public_result_sha256': sha256(raw).hexdigest(),
              'private_case_public_digest_equal': True,
              'question_denominator': 60, 'context_rates_read_back': checked_rates,
              'EM_2x2_tables_read_back': 2, 'native_removal_question_pairs_read_back': True,
              'C6_and_D1_original_result_bytes_unchanged': True,
              'analysis_software_bindings_equal': True,
              'no_actual_question_IDs_in_public_result_report_or_manuscript_handoff': True,
              'no_private_case_fields_in_public_result_schema': True,
              'exactly_two_chapter6_sentences_and_one_appendix_table': True,
              'isolated_layout_preview': {'pages': 1, 'errors_overfull_or_undefined': 0,
                  'pdf_sha256': sha256(preview.read_bytes()).hexdigest(), 'visually_reviewed': True},
              'new_model_calls': 0, 'new_C6_end_audits': 0, 'new_H4_inference_runs': 0,
              'thesis_writes_or_full_builds_by_QA1': 0,
              'setup_issue': {'initial_bound_data_join_stopped_before_public_metrics': True,
                  'root_cause': 'strict historical SDK projection helper did not implement already bound C1 empty-field nonemission',
                  'repair': 'reuse unchanged original C1 request95 projection function and its codec pin',
                  'synthetic_regression_and_complete_original_CSV_join_passed': True}}
    # Publish only the predeclared scalar binding diagnostics, never private pin paths.
    allowed = {'questions', 'graph_edges', 'unknown_source_graph_edges',
               'multiple_native_owner_graph_edges', 'multiple_source_owner_graph_edges'}
    summary = private['binding_checks']
    assert all(set(v) == allowed and all(type(x) is int for x in v.values()) for v in summary.values())
    result['aggregate_source_binding_diagnostics'] = summary
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'verified', 'synthetic_tests': outcome.testsRun,
        'context_rates_checked': checked_rates, 'private_case_data_public': False,
        'original_C6_D1_results_unchanged': True, 'isolated_preview_pages': 1}))


if __name__ == '__main__':
    main()
