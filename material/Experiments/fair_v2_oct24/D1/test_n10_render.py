"""The N10 approximation must survive rendering, using invented effects only."""
from . import n8_render
from . import render
from .test_n8_render import report_fixture


def fixture():
    value = report_fixture()
    value['N10_H1_sampling'] = {'selected_groups': 2, 'population_groups': 4,
                              'sampling_fraction': .5, 'inclusion_fraction_is_an_approximation': True}
    return value


def test_primary_and_component_table_notes_disclose_N10_approximation(tmp_path):
    report = fixture()
    primary = render._primary_table(report, tmp_path, render.SYNTHETIC_BANNER).read_text(encoding='utf8')
    components = n8_render._component_table(report, tmp_path, render.SYNTHETIC_BANNER).read_text(encoding='utf8')
    for text in (primary, components):
        assert 'N10' in text and '2/4' in text
        assert 'näherungsweise' in text and 'zweistufiger' in text
        assert 'Nicht gezogene Aussagen sind keine Fehlwerte' in text


def test_forest_legend_discloses_conditional_H1_sampling_without_changing_Holm_slots():
    report = fixture()
    fig = n8_render._make_forest_figure(report, render.SYNTHETIC_BANNER)
    try:
        text = '\n'.join(item.get_text() for item in fig.texts)
        assert 'H1/K1/K3/K6: N10-Näherung' in text
        assert 'Quellen-/Originalgruppenbootstrap' in text
        left, right = n8_render._families(report)
        assert len(left) == 3 and len(right) == 6
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def test_no_N10_note_for_full_G2_census():
    assert render._n10_note(report_fixture()) == ''


def test_separate_G2_sensitivity_and_selection_table_are_explicitly_descriptive(tmp_path):
    report = fixture()
    report['cells'] = [{'endpoint': 'H1', 'cell': cell, 'estimate': .5} for cell in render.CELLS]
    report['sensitivities'] = {'H1_G2_draw_first_aggregation': {
        'cells': {cell: {'estimate': .4} for cell in render.CELLS}}}
    report['N10_H1_sampling']['selection_distributions'] = {'source': [
        {'level': 'SYNTHETIC', 'population_count': 24, 'selected_count': 12, 'sampling_fraction': .5}]}
    text = render._n10_sampling_table(report, tmp_path, render.SYNTHETIC_BANNER).read_text(encoding='utf8')
    assert 'getrennte G2-Aggregationssensitivität' in text
    assert 'kein weiterer Primärtest' in text
    assert 'Fehlversuche bleiben im Präfix' in text
    assert 'weder exakt gleiche' in text and 'Qualitätsvorteil' in text
