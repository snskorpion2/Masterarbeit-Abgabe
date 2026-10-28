"""Bind the existing binary AUTHOR C7 rule to N8 without rewriting labels.

The legacy three-class agreement remains descriptive. The current explicit
carrier activates only the already authorized supported-vs-other binary rule.
"""
from . import inference
from .native import need


def author_qualification(human_report, agreement_input, current_rows):
    binding = agreement_input.get('human_binary_N8_override')
    if binding is None:
        return {'kappa': human_report['kappa'], 'source': 'legacy_three_class_interface',
                'current_author_binary_binding': False}
    need(binding.get('annotation_origin') == 'human_ui_input'
         and binding.get('author_confirmed') is True, 'Bound current author confirmation required')
    def binary(label):
        need(label is None or label in inference.LABELS, 'Canonical original nominal labels required')
        return None if label is None else 'supported' if label == 'supported' else 'not_supported'
    comparison = inference.cohens_kappa(
        [binary(row['reference_label']) for row in current_rows],
        [binary(row['label']) for row in current_rows])
    expected = binding['binary_n8_kappa']
    need(comparison['kappa'] == expected and comparison['N_pair'] == binding['pair_count'],
         'Current author binary kappa differs from its bound C7 end result')
    return {'kappa': expected, 'source': 'current_C7_author_binary_rule',
            'current_author_binary_binding': True, 'N_pair': comparison['N_pair'],
            'definition': 'supported versus {not_supported, unclear}; missing excluded',
            'annotation_origin': binding['annotation_origin'], 'author_confirmed': True,
            'annotation_SHA256': binding['annotation_SHA256'],
            'C2_end_export_SHA256': binding['C2_end_export_SHA256'],
            'original_three_class_labels_unchanged': True,
            'three_class_kappa_descriptive': human_report['kappa'],
            'model_counterevaluator_used_for_N8': False}
