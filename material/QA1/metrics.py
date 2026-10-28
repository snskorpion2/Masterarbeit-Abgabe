"""Pure descriptive calculations. No transport, encoder, reranking or tests of hypotheses."""
from collections import Counter
import math

from Experiments.fair_v2_oct24.C6 import scoring


def validate_roster(question_ids):
    if (type(question_ids) is not list or not question_ids
            or any(type(q) is not str or not q for q in question_ids)
            or len(set(question_ids)) != len(question_ids)):
        raise ValueError('Nonempty unique string question roster required')


def official_normalizer():
    raw = scoring._verified_sources()
    cls = scoring._official_class(raw['answer.py'], raw['metric.py'])
    return cls.__call__.__globals__['normalize_answer']


def aliases(gold, normalize):
    if (not isinstance(gold, dict) or set(gold) != {'answer', 'answer_aliases'}
            or type(gold['answer']) is not str or type(gold['answer_aliases']) is not list
            or any(type(x) is not str for x in gold['answer_aliases'])):
        raise ValueError('Invalid gold projection')
    return sorted({normalize(x) for x in [gold['answer'], *gold['answer_aliases']] if normalize(x)})


def lexical_hit(text, normalized_aliases, normalize):
    """A nonempty contiguous normalized token sequence; never character substring matching."""
    if type(text) is not str:
        raise ValueError('Context must be a string')
    if not normalized_aliases:
        return None
    haystack = ' ' + normalize(text) + ' '
    return any(' ' + answer + ' ' in haystack for answer in normalized_aliases)


def rate(values):
    values = list(values)
    if not values or any(x is not None and type(x) is not bool for x in values):
        raise ValueError('Nonempty tri-state question observations required')
    n = len(values)
    hit, missing = sum(x is True for x in values), sum(x is None for x in values)
    return {'questions': n, 'hits': hit, 'nonhits': n - hit - missing,
            'not_measurable': missing, 'rate': hit / n if not missing else None,
            'identification_lower': hit / n, 'identification_upper': (hit + missing) / n}


def paired_em(question_ids, treatment, control):
    validate_roster(question_ids)
    if set(treatment) != set(question_ids) or set(control) != set(question_ids):
        raise ValueError('EM cells must cover the exact paired roster')
    counts = Counter()
    private = []
    for question_id in question_ids:
        a, b = treatment[question_id], control[question_id]
        if a not in (0.0, 1.0) or b not in (0.0, 1.0):
            raise ValueError('Complete binary official EM values required')
        key = {(1, 1): 'both_correct', (0, 0): 'both_incorrect',
               (1, 0): 'treatment_only', (0, 1): 'control_only'}[(a, b)]
        counts[key] += 1
        private.append({'question_id': question_id, 'treatment_EM': a, 'control_EM': b, 'category': key})
    n = len(question_ids)
    public = {k: counts[k] for k in ('both_correct', 'both_incorrect', 'treatment_only', 'control_only')}
    public.update(questions=n, discordant=counts['treatment_only'] + counts['control_only'],
                  treatment_EM=(counts['both_correct'] + counts['treatment_only']) / n,
                  control_EM=(counts['both_correct'] + counts['control_only']) / n,
                  delta=(counts['treatment_only'] - counts['control_only']) / n,
                  new_significance_test=False)
    return public, private


def interval_precision(effect):
    lo, hi = effect['ci95']['lower'], effect['ci95']['upper']
    point = effect['point_difference']
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in (lo, hi, point)) or lo > hi:
        raise ValueError('Finite original interval required')
    return {'original_point': point, 'original_ci95': {'lower': lo, 'upper': hi},
            'full_width': hi - lo, 'half_width': (hi - lo) / 2,
            'half_width_percentage_points': (hi - lo) * 50,
            'distance_point_to_lower': point - lo, 'distance_upper_to_point': hi - point,
            'symmetric_around_point_assumed': False, 'power_or_MDE_computed': False,
            'new_bootstrap_draws': 0}


def context_diagnostics(question_ids, contexts, gold, normalize=None):
    validate_roster(question_ids)
    normalize = normalize or official_normalizer()
    if set(contexts) != set(question_ids) or set(gold) != set(question_ids):
        raise ValueError('Contexts and gold must match the exact roster')
    rows = []
    for q in question_ids:
        edges = contexts[q]
        if len(edges) > 30 or len({r['occurrence_id'] for r in edges}) != len(edges):
            raise ValueError('Top-30 distinct occurrences required')
        answers = aliases(gold[q], normalize)
        hit = lexical_hit('\n'.join(row['text'] for row in edges), answers, normalize)
        if any(row['is_supporting_source'] is not None and type(row['is_supporting_source']) is not bool for row in edges):
            raise ValueError('Source-support provenance must be bool or unknown')
        supported = [row for row in edges if row['is_supporting_source'] is True]
        known_support_hit = any(lexical_hit(row['text'], answers, normalize) for row in supported)
        possible_unknown_hit = any(row['is_supporting_source'] is None and lexical_hit(row['text'], answers, normalize) for row in edges)
        support_hit = (True if known_support_hit else None if possible_unknown_hit else False) if answers else None
        within_statement = (any(lexical_hit(row['text'], answers, normalize) for row in edges)
                            if answers else None)
        rows.append({'question_id': q, 'context_hit': hit, 'within_statement_hit': within_statement,
                     'support_paragraph_statement_hit': support_hit,
                     'selected_edges': len(edges), 'support_paragraph_selected_edges': len(supported)})
    return {'gold_or_alias_in_actual_context': rate(r['context_hit'] for r in rows),
            'gold_or_alias_within_one_statement': rate(r['within_statement_hit'] for r in rows),
            'gold_or_alias_in_support_paragraph_statement': rate(r['support_paragraph_statement_hit'] for r in rows),
            'selected_edge_question_pairs': sum(r['selected_edges'] for r in rows),
            'support_paragraph_edge_question_pairs': sum(r['support_paragraph_selected_edges'] for r in rows)}, rows


def removal_diagnostics(question_ids, removed, gold, normalize=None):
    validate_roster(question_ids)
    normalize = normalize or official_normalizer()
    if set(removed) != set(question_ids) or set(gold) != set(question_ids):
        raise ValueError('Removed rows must cover the exact roster')
    rows, unique, supporting_unique = [], set(), set()
    for q in question_ids:
        if len({r['native_key'] for r in removed[q]}) != len(removed[q]):
            raise ValueError('Duplicate removed occurrence for one question')
        if any(r['is_supporting_source'] is not None and type(r['is_supporting_source']) is not bool for r in removed[q]):
            raise ValueError('Native source provenance must be bool or unknown')
        answer_aliases = aliases(gold[q], normalize)
        if not answer_aliases:
            rows.append({'question_id': q, 'answer_bearing_removed': None,
                         'support_answer_bearing_removed': None, 'removed_native_keys': []})
            continue
        answer_rows = [r for r in removed[q] if lexical_hit(r['text'], answer_aliases, normalize)]
        if any(r['is_supporting_source'] is None for r in answer_rows):
            raise ValueError('Explicit native removed statements require exact source provenance')
        supporting = [r for r in answer_rows if r['is_supporting_source'] is True]
        unique.update(r['native_key'] for r in answer_rows)
        supporting_unique.update(r['native_key'] for r in supporting)
        rows.append({'question_id': q, 'answer_bearing_removed': len(answer_rows),
                     'support_answer_bearing_removed': len(supporting),
                     'removed_native_keys': [r['native_key'] for r in answer_rows]})
    return {'questions_with_answer_bearing_removal': rate(None if r['answer_bearing_removed'] is None else r['answer_bearing_removed'] > 0 for r in rows),
            'questions_with_support_answer_bearing_removal': rate(None if r['support_answer_bearing_removed'] is None else r['support_answer_bearing_removed'] > 0 for r in rows),
            'answer_bearing_removed_statement_question_pairs': sum(r['answer_bearing_removed'] or 0 for r in rows),
            'support_answer_bearing_removed_statement_question_pairs': sum(r['support_answer_bearing_removed'] or 0 for r in rows),
            'unique_answer_bearing_removed_occurrences': len(unique),
            'unique_support_answer_bearing_removed_occurrences': len(supporting_unique),
            'lexical_proxy_only_not_causal_answer_loss': True}, rows
