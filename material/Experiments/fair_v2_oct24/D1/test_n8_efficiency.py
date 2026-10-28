"""N8 efficiency Sollwerte, generated records only, no natural data-file access."""
from copy import deepcopy
import csv
from decimal import Decimal
from io import StringIO

import pytest

from Experiments.fair_v2_oct24.D1.efficiency import (
    K2_COLUMNS, compute_efficiency, parse_k2_csv)


def csv_text(rows, columns=K2_COLUMNS):
    stream = StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: ('' if row.get(key) is None else
            str(row[key]).lower() if type(row[key]) is bool else row[key]) for key in columns})
    return stream.getvalue()


def meter(arm='AS', *, guard=False, token_in=100, token_out=20, cost='1.2',
          digest='a', population='fixture', currency='USD', scenario='base-list', **changes):
    row = dict.fromkeys(K2_COLUMNS)
    row.update(package='C1' if guard else 'B3', population=population, arm=arm,
        stage='Prüffilter' if guard else 'Extraktion', scope='synthetic_scope', model='synthetic-model',
        pricing_scenario=scenario, call_kind='generation', status='abgeschlossen',
        snapshot_UTC='2000-01-01T00:00:00Z', calls_known=1, calls_unknown=0,
        pending_positions=0, call_count=1, physical_POSTs=1, physical_POSTs_known_subtotal=1,
        prompt_tokens_known=token_in, output_tokens_known=token_out, usage_missing=0,
        cache_read_tokens_known=0, cache_write_tokens_known=0, currency=currency,
        cost_known=cost, cost_missing=0, cost_complete=True, reserved_or_held_cost='0',
        invoice_verified=False, used_by_arms=arm, notes='synthetic', receipt_set_sha256=digest * 64)
    row.update(changes)
    return row


def fixtures():
    sources = [{'source_id': 's1', 'draws': ['d1', 'd2']}]
    support = {'AS': 2, 'AS_G': 2, 'V1': 6, 'V2': 4}
    h1 = {base + '_' + suffix: [dict(source_id='s1', draw=draw, success=count,
        denominator=count + 1, defined=True, technical_missing=0, semantic_unclear=0)
        for draw in ('d1', 'd2')]
        for base, count in support.items() for suffix in ('ORIGINAL', 'ROW')}
    rows = [meter(), meter('V1', token_in=200, token_out=40, cost='2.4', digest='b'),
        meter('AS+G', guard=True, token_in=10, token_out=5, cost='.15', digest='c', scenario='guard-list'),
        meter('V2', guard=True, token_in=20, token_out=10, cost='.3', digest='d', scenario='guard-list')]
    # Full B3 stage roster. These deliberately empty stages have measured zero
    # work, so the fixture's original cost/token arithmetic stays unchanged.
    for arm_name, stage, digest in (('AS', 'Schema', '1'),
                                     ('V1', 'Schema', '2'),
                                     ('V1', 'Ergänzung', '3')):
        rows.append(meter(arm_name, stage=stage, digest=digest,
            token_in=0, token_out=0, cost='0', call_kind='known_zero',
            calls_known=0, call_count=0, physical_POSTs=0,
            physical_POSTs_known_subtotal=0))
    return parse_k2_csv(csv_text(rows)), h1, sources


def calculate(rows=None, h1=None, sources=None, mapping=None):
    default_rows, default_h1, default_sources = fixtures()
    return compute_efficiency(default_rows if rows is None else rows,
        default_h1 if h1 is None else h1, default_sources if sources is None else sources,
        population_sources={'fixture': ['s1']} if mapping is None else mapping)


def arm(result, name):
    return next(row for row in result['rows'] if row['arm'] == name)


def test_parse_real_schema_header_with_generated_rows_and_no_false_truthiness():
    original = meter(notes='A, B\nC', invoice_verified=False, cost_complete=False)
    row = parse_k2_csv('\ufeff' + csv_text([original]))[0]
    assert list(row) == list(K2_COLUMNS)
    assert row['notes'] == 'A, B\nC'
    assert row['cost_complete'] is False and row['invoice_verified'] is False
    assert type(row['calls_known']) is int and row['calls_known'] == 1
    assert row['cost_known'] == '1.2'


@pytest.mark.parametrize('bad', ['False', '0', 'yes', 'TRUE'])
def test_boolean_strings_are_not_guessed(bad):
    with pytest.raises(ValueError, match='literal true/false'):
        parse_k2_csv(csv_text([meter(cost_complete=bad)]))


@pytest.mark.parametrize('bad', ['-1', '1.5', 'NaN', 'true'])
def test_integer_counts_are_nonnegative_exact_integers(bad):
    with pytest.raises(ValueError, match='nonnegative integer'):
        parse_k2_csv(csv_text([meter(calls_unknown=bad)]))


@pytest.mark.parametrize('bad', ['-0.01', 'NaN', 'Infinity', 'not-money'])
def test_money_rejects_nonfinite_negative_or_nonmoney(bad):
    with pytest.raises(ValueError, match='finite nonnegative money'):
        parse_k2_csv(csv_text([meter(cost_known=bad)]))


def test_missing_extra_or_duplicate_headers_fail_closed():
    for header in (K2_COLUMNS[:-1], (*K2_COLUMNS, 'unexpected'),
                   (*K2_COLUMNS[:-1], K2_COLUMNS[0])):
        with pytest.raises(ValueError, match='Exact K2 CSV columns'):
            parse_k2_csv(csv_text([], header))


def test_empty_cells_remain_unknown_not_zero():
    row = parse_k2_csv(csv_text([meter(cost_known=None, calls_unknown=None,
        prompt_tokens_known=None, cost_complete=None)]))[0]
    assert row['cost_known'] is row['calls_unknown'] is row['prompt_tokens_known'] is row['cost_complete'] is None


def test_base_reused_exactly_once_and_row_views_not_counted_twice():
    result = calculate()
    assert len(result['rows']) == 4
    as_row, filtered, v1, v2 = [arm(result, key) for key in ('AS', 'AS+G', 'V1', 'V2')]
    assert as_row['supported_count'] == filtered['supported_count'] == 4
    assert as_row['construction_tokens_known'] == filtered['construction_tokens_known'] == 120
    assert v1['construction_tokens_known'] == v2['construction_tokens_known'] == 240
    assert filtered['total_tokens_known'] == 135
    assert v2['guard_tokens_known'] == 30 and v2['total_tokens_known'] == 270
    assert Decimal(as_row['cost_per_supported']) == Decimal('.3')
    assert Decimal(filtered['cost_per_supported']) == Decimal('.3375')
    assert Decimal(v2['cost_per_supported']) == Decimal('.3375')
    assert v2['tokens_per_supported'] == 33.75
    assert v1['supported_per_1000_construction_tokens'] == 50
    assert v2['supported_per_1000_construction_tokens'] == pytest.approx(100 / 3)
    assert all(row['complete_for_efficiency_comparison'] for row in result['rows'])
    assert all(row['efficiency_superiority_claimed'] is False for row in result['rows'])


def test_export_view_disagreement_is_not_averaged_or_summed():
    rows, h1, sources = fixtures()
    h1['AS_ROW'][0]['success'] += 1
    with pytest.raises(ValueError, match='export views differ'):
        calculate(rows, h1, sources)


def test_guards_need_no_second_base_receipt_and_must_not_allocate_evaluations():
    rows, _, _ = fixtures()
    rows += [parse_k2_csv(csv_text([meter(package='B1', stage='Qualifikation', cost='999',
        token_in=999, digest='e')]))[0],
        parse_k2_csv(csv_text([meter(package='C2', stage='Bewertung', cost='888', digest='f')]))[0],
        parse_k2_csv(csv_text([meter(scope='pilot_extra', cost='777', digest='0')]))[0]]
    result = calculate(rows)
    assert len(result['excluded_rows']) == 3
    assert arm(result, 'AS')['cost_known'] == '1.2'
    assert arm(result, 'AS+G')['cost_known'] == '1.35'


def test_historical_missing_prefix_is_retained_as_unknown_and_holds_are_not_spend():
    rows, _, _ = fixtures()
    history = parse_k2_csv(csv_text([meter(scope='historical_sealed_prefix', digest='e',
        call_kind='historical_incomplete_scope', cost_known=None, cost_complete=False,
        calls_known=None, calls_unknown=None, usage_missing=None, prompt_tokens_known=None,
        output_tokens_known=None, reserved_or_held_cost='90')]))[0]
    result = calculate(rows + [history])
    for name in ('AS', 'AS+G'):
        row = arm(result, name)
        assert row['cost_complete'] is False and row['cost_per_supported'] is None
        assert row['tokens_per_supported'] is None
        assert row['construction_tokens_known'] == 120
        assert row['reserved_cost_is_spend'] is False
        assert row['complete_for_efficiency_comparison'] is False
    assert arm(result, 'AS')['cost_known'] == '1.2'  # not 91.2


def test_historical_schema_is_visible_not_silently_merged():
    rows, _, _ = fixtures()
    history = parse_k2_csv(csv_text([meter(stage='Schema', digest='e', cost='55',
        scope='historical_reused_schema_outside_B3_ledger/sealed4')]))[0]
    result = calculate(rows + [history])
    row = arm(result, 'AS')
    assert row['cost_known'] == '1.2' and row['cost_per_supported'] is None
    assert 'historical_schema_scope_requires_separate_accounting' in row['reasons']
    assert result['excluded_rows'][0]['reason'] == 'historical_schema_kept_separate'


def test_missing_guard_is_unknown_not_zero_final_arm_effort():
    rows, _, _ = fixtures()
    rows = [row for row in rows if row['arm'] != 'V2']
    row = arm(calculate(rows), 'V2')
    assert row['construction_tokens_known'] == 240
    assert row['guard_tokens_known'] is None
    assert row['cost_known'] == '2.4' and row['cost_complete'] is False
    assert row['cost_per_supported'] is row['tokens_per_supported'] is None
    assert 'required_guard_not_documented' in row['reasons']


def test_unstarted_base_does_not_invent_zero_total_tokens():
    rows, _, _ = fixtures()
    rows = [row for row in rows if row['arm'] not in ('AS', 'AS+G')]
    row = arm(calculate(rows), 'AS')
    assert row['total_tokens_known'] is row['construction_tokens_known'] is None
    assert row['cost_known'] is row['cost_per_supported'] is None
    assert 'base_construction_not_documented' in row['reasons']


def test_snapshot_running_or_missing_usage_does_not_claim_complete():
    rows, _, _ = fixtures()
    rows[0]['status'] = 'laufend'
    row = arm(calculate(rows), 'AS')
    assert row['cost_per_supported'] is row['tokens_per_supported'] is None
    assert row['cost_known'] == '1.2' and row['total_tokens_known'] == 120


def test_zero_supported_denominator_and_positive_token_denominator_are_distinct():
    rows, h1, sources = fixtures()
    for suffix in ('ORIGINAL', 'ROW'):
        for row in h1['AS_' + suffix]:
            row['success'] = 0
    row = arm(calculate(rows, h1, sources), 'AS')
    assert row['supported_count'] == 0
    assert row['cost_per_supported'] is row['tokens_per_supported'] is None
    assert row['supported_per_1000_construction_tokens'] == 0


def test_zero_construction_tokens_make_reciprocal_undefined_not_infinite():
    rows, _, _ = fixtures()
    rows[0].update(prompt_tokens_known=0, output_tokens_known=0)
    row = arm(calculate(rows), 'AS')
    assert row['tokens_per_supported'] == 0
    assert row['supported_per_1000_construction_tokens'] is None


def test_exact_meter_duplicates_collapsed_but_conflicting_same_price_rejected():
    rows, _, _ = fixtures()
    assert calculate(rows + [deepcopy(rows[0])]) == calculate(rows)
    changed = {**rows[0], 'cost_known': '9'}
    with pytest.raises(ValueError, match='Conflicting duplicate K2 meter'):
        calculate(rows + [changed])


def test_alternative_price_views_are_profiles_not_extra_spend():
    rows, _, _ = fixtures()
    alternative = {**rows[0], 'pricing_scenario': 'alternative-list', 'cost_known': '2.4'}
    result = calculate(rows + [alternative])
    selected = [r for r in result['rows'] if r['arm'] == 'AS']
    assert len(selected) == 2
    assert {r['cost_known'] for r in selected} == {'1.2', '2.4'}
    assert {r['construction_tokens_known'] for r in selected} == {120}


def test_alternative_pricing_cannot_change_the_same_original_usage_meter():
    rows, _, _ = fixtures()
    alternative = {**rows[0], 'pricing_scenario': 'alternative-list',
        'cost_known': '2.4', 'prompt_tokens_known': 200}
    with pytest.raises(ValueError, match='Conflicting K2 observation across pricing views'):
        calculate(rows + [alternative])


def test_excluded_qualification_meter_does_not_block_construction_efficiency():
    rows, _, _ = fixtures()
    qualification = {**rows[0], 'package': 'B1', 'stage': 'Qualifikation',
        'cost_known': '1000'}
    conflicting = {**qualification, 'prompt_tokens_known': 123, 'cost_known': '2000'}
    result = calculate(rows + [qualification, conflicting])
    assert arm(result, 'AS')['cost_known'] == '1.2'
    assert len(result['excluded_rows']) == 2


def test_mixed_currencies_not_converted_or_claimed_as_one_pipeline_price():
    rows, _, _ = fixtures()
    rows[2]['currency'] = 'EUR'
    selected = [r for r in calculate(rows)['rows'] if r['arm'] == 'AS+G']
    assert {r['currency'] for r in selected} == {'USD', 'EUR'}
    assert {r['cost_known'] for r in selected} == {'1.2', '0.15'}
    assert all(r['cost_scope'] == 'currency_component_only' and r['cost_per_supported'] is None
               and not r['complete_for_efficiency_comparison'] for r in selected)
    assert {r['total_tokens_known'] for r in selected} == {135}


def test_unmapped_population_no_fabricated_h1_denominator():
    row = arm(calculate(mapping={}), 'AS')
    assert row['supported_count'] is None
    assert row['cost_per_supported'] is row['tokens_per_supported'] is None
    assert 'population_has_no_H1_source_mapping' in row['reasons']


def test_foreign_or_missing_source_draw_rejected_not_complete_case_selected():
    rows, h1, sources = fixtures()
    with pytest.raises(ValueError, match='foreign or duplicate source'):
        calculate(rows, h1, sources, {'fixture': ['foreign']})
    h1['AS_ORIGINAL'] = h1['AS_ORIGINAL'][:1]
    with pytest.raises(ValueError, match='Missing planned H1'):
        calculate(rows, h1, sources)


def test_missing_h1_technical_judgments_not_counted_as_false():
    rows, h1, sources = fixtures()
    for suffix in ('ORIGINAL', 'ROW'):
        h1['AS_' + suffix][0]['technical_missing'] = 1
    row = arm(calculate(rows, h1, sources), 'AS')
    assert row['supported_count'] == 4 and row['support_complete'] is False
    assert row['complete_for_efficiency_comparison'] is False
    assert 'H1_technical_missing_not_false' in row['reasons']
    assert row['cost_per_supported'] is row['currency_component_cost_per_supported'] is None
    assert row['tokens_per_supported'] is row['supported_per_1000_construction_tokens'] is None
    assert row['cost_known'] == '1.2' and row['total_tokens_known'] == 120


def test_missing_technical_coverage_field_does_not_invent_complete_h1():
    rows, h1, sources = fixtures()
    for suffix in ('ORIGINAL', 'ROW'):
        del h1['AS_' + suffix][0]['technical_missing']
    row = arm(calculate(rows, h1, sources), 'AS')
    assert row['supported_count'] == 4 and row['support_complete'] is False
    assert row['cost_per_supported'] is row['tokens_per_supported'] is None
    assert row['supported_per_1000_construction_tokens'] is None


def test_unidentified_h1_draw_keeps_known_part_count_but_no_total_quotients():
    rows, h1, sources = fixtures()
    for suffix in ('ORIGINAL', 'ROW'):
        h1['AS_' + suffix][0].update(success=None, defined=False, technical_missing=1)
    row = arm(calculate(rows, h1, sources), 'AS')
    assert row['supported_count'] == 2 and row['support_complete'] is False
    assert 'H1_supported_count_not_identified' in row['reasons']
    assert row['cost_per_supported'] is row['currency_component_cost_per_supported'] is None
    assert row['tokens_per_supported'] is row['supported_per_1000_construction_tokens'] is None


def test_complete_h1_with_valid_unclear_codes_keeps_exact_supported_count():
    rows, h1, sources = fixtures()
    for suffix in ('ORIGINAL', 'ROW'):
        h1['AS_' + suffix][0]['semantic_unclear'] = 1
    row = arm(calculate(rows, h1, sources), 'AS')
    assert row['supported_count'] == 4 and row['support_complete'] is True
    assert Decimal(row['cost_per_supported']) == Decimal('.3')
    assert row['tokens_per_supported'] == 30
    assert row['supported_per_1000_construction_tokens'] == pytest.approx(100 / 3)


@pytest.mark.parametrize('owner,stage,affected', [
    ('AS', 'Extraktion', ('AS', 'AS+G')),
    ('AS', 'Schema', ('AS', 'AS+G')),
    ('V1', 'Extraktion', ('V1', 'V2')),
    ('V1', 'Schema', ('V1', 'V2')),
    ('V1', 'Ergänzung', ('V1', 'V2')),
])
def test_whole_missing_b3_stage_is_unknown_not_zero_complete_work(owner, stage, affected):
    rows, _, _ = fixtures()
    rows = [r for r in rows if not (r['arm'] == owner and r['stage'] == stage)]
    result = calculate(rows)
    for name in affected:
        row = arm(result, name)
        assert row['cost_complete'] is False and row['usage_complete'] is False
        assert row['construction_usage_complete'] is False
        assert row['stage_coverage_complete'] is False
        assert row['construction_stage_coverage_complete'] is False
        assert row['missing_stages'] == ['B3:' + stage]
        assert 'B3:' + stage in row['required_stages']
        assert row['cost_per_supported'] is row['tokens_per_supported'] is None
        assert row['supported_per_1000_construction_tokens'] is None


def test_explicit_known_zero_stages_complete_the_roster_without_fake_calls():
    rows, _, _ = fixtures()
    result = calculate(rows)
    assert sum(r['call_count'] for r in rows) == 4
    for name in ('AS', 'AS+G', 'V1', 'V2'):
        row = arm(result, name)
        expected = ['B3:Extraktion', 'B3:Schema']
        if name in ('V1', 'V2'):
            expected.append('B3:Ergänzung')
        if name in ('AS+G', 'V2'):
            expected.append('C1:Prüffilter')
        assert row['required_stages'] == expected
        assert row['missing_stages'] == [] and row['stage_coverage_complete'] is True
        assert row['construction_stage_coverage_complete'] is True


def test_missing_guard_keeps_known_construction_only_reciprocal_separate():
    rows, _, _ = fixtures()
    rows = [r for r in rows if r['arm'] != 'V2']
    row = arm(calculate(rows), 'V2')
    assert row['missing_stages'] == ['C1:Prüffilter']
    assert row['stage_coverage_complete'] is False
    assert row['construction_stage_coverage_complete'] is True
    assert row['construction_usage_complete'] is True
    assert row['construction_tokens_known'] == 240
    assert row['guard_tokens_known'] is None
    assert row['cost_per_supported'] is row['tokens_per_supported'] is None
    assert row['supported_per_1000_construction_tokens'] == pytest.approx(100 / 3)


def b4_rows():
    rows, _, _ = fixtures()
    return [{**r, 'package': 'B4' if r['package'] == 'B3' else r['package'],
             'population': 'MuSiQue'} for r in rows if r['stage'] != 'Schema']


def test_b4_needs_no_schema_and_does_not_invent_musique_h1_mapping():
    result = calculate(rows=b4_rows(), mapping={})
    for name in ('AS', 'AS+G', 'V1', 'V2'):
        row = arm(result, name)
        assert row['stage_coverage_complete'] is True
        assert row['construction_stage_coverage_complete'] is True
        assert not any('Schema' in s for s in row['required_stages'])
        assert row['missing_stages'] == [] and row['supported_count'] is None
        assert row['cost_per_supported'] is row['tokens_per_supported'] is None
        assert row['supported_per_1000_construction_tokens'] is None


def test_b4_unexecuted_schema_does_not_enter_known_work_or_stage_requirements():
    rows = b4_rows()
    schema = parse_k2_csv(csv_text([meter(package='B4', population='MuSiQue',
        stage='Schema', call_kind='not_executed', token_in=0, token_out=0,
        cost='0', calls_known=0, call_count=0, digest='4')]))[0]
    baseline = calculate(rows=rows, mapping={})
    result = calculate(rows=rows + [schema], mapping={})
    assert result['rows'] == baseline['rows']
    assert result['excluded_rows'][-1]['reason'] == 'not_executed_not_incurred'


def test_missing_whole_b4_joint_stage_is_not_filled_by_extraction():
    rows = [r for r in b4_rows() if r['stage'] != 'Ergänzung']
    row = arm(calculate(rows=rows, mapping={}), 'V2')
    assert row['missing_stages'] == ['B4:Ergänzung']
    assert row['stage_coverage_complete'] is False
    assert row['construction_usage_complete'] is False
    assert row['construction_tokens_known'] == 240
    assert row['cost_per_supported'] is row['tokens_per_supported'] is None


def test_empty_explicit_input_is_not_a_zero_cost_experiment():
    result = calculate(rows=[])
    assert result['status'] == 'not_provided' and result['rows'] == []


@pytest.mark.parametrize('bad', [True, False])
def test_native_boolean_money_is_not_silently_cast_to_one_or_zero(bad):
    rows, _, _ = fixtures()
    rows[0]['cost_known'] = bad
    with pytest.raises(ValueError, match='finite nonnegative money'):
        calculate(rows)
