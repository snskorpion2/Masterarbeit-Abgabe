"""Known synthetic ratios must not hide incomplete H1 or pipeline inputs."""
from copy import deepcopy

from Experiments.fair_v2_oct24.D1 import n8_render as r


def complete_profile():
    return {'population': 'synthetisch', 'arm': 'V2', 'currency': 'USD',
        'cost_scope': 'full_arm', 'cost_per_supported': '123.456789',
        'tokens_per_supported': 234.56,
        'supported_per_1000_construction_tokens': 345.678,
        'support_complete': True, 'usage_complete': True,
        'construction_usage_complete': True, 'cost_complete': True,
        'stage_coverage_complete': True, 'construction_stage_coverage_complete': True,
        'required_stages': ['B3:Extraktion', 'B3:Ergänzung', 'B3:Schema', 'C1:Prüffilter'],
        'missing_stages': [], 'reasons': []}


def table(tmp_path, row):
    return r._efficiency_table({'efficiency': {'rows': [row]}}, tmp_path,
                              r.SYNTHETIC_BANNER).read_text(encoding='utf8')


def test_technical_h1_gap_hides_stale_ratios_and_explains_status(tmp_path):
    row = complete_profile()
    row.update(support_complete=False, reasons=['H1_technical_missing'])
    before = deepcopy(row)
    text = table(tmp_path, row)
    assert all(value not in text for value in ('123,456789', '234,56', '345,678'))
    assert 'unvollständig' in text and 'H1' in text
    assert row == before


def test_missing_construction_stage_hides_every_pipeline_ratio(tmp_path):
    row = complete_profile()
    row.update(stage_coverage_complete=False, construction_stage_coverage_complete=False,
               missing_stages=['B3:Schema'])
    text = table(tmp_path, row)
    assert all(value not in text for value in ('123,456789', '234,56', '345,678'))
    assert 'unvollständig' in text and 'B3:Schema' in text


def test_missing_guard_keeps_only_explicit_construction_token_ratio(tmp_path):
    row = complete_profile()
    row.update(stage_coverage_complete=False, missing_stages=['C1:Prüffilter'])
    text = table(tmp_path, row)
    assert '123,456789' not in text and '234,56' not in text
    assert '345,678' in text
    assert 'unvollständig' in text and 'C1:Prüffilter' in text


def test_unknown_cost_does_not_hide_complete_token_meters(tmp_path):
    row = complete_profile()
    row.update(cost_complete=False)
    text = table(tmp_path, row)
    assert '123,456789' not in text
    assert '234,56' in text and '345,678' in text
    assert 'unvollständig' in text and 'Kosten' in text


def test_missing_completeness_metadata_is_not_silently_complete(tmp_path):
    row = {k: v for k, v in complete_profile().items() if not k.endswith('_complete')}
    text = table(tmp_path, row)
    assert all(value not in text for value in ('123,456789', '234,56', '345,678'))
    assert 'unvollständig' in text


def test_complete_profile_keeps_exact_numbers_and_explicit_status(tmp_path):
    text = table(tmp_path, complete_profile())
    assert all(value in text for value in ('123,456789', '234,56', '345,678'))
    assert 'Status' in text and 'vollständig' in text
