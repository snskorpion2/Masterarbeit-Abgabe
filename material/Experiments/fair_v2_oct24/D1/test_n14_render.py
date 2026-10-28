"""Hand-written N14 render fixtures; no natural judgments or references."""
from copy import deepcopy

import pytest

from . import n14_render as n14
from . import n8_render
from . import render
from .test_n8_render import report_fixture


def fixture():
    report = report_fixture()
    def rates(missing, unclear):
        return {'source_equal_missing_rate': missing, 'pooled_missing_rate': missing / 2,
                'source_equal_G2_zero_or_unclear_rate': unclear,
                'pooled_G2_zero_or_unclear_rate': unclear / 2}
    def extra(identifier):
        return {'point_difference': -.09, 'ci95': {'lower': -.12, 'upper': -.06},
                'raw_p': .8, 'adjusted_p': 1., 'testable': True, 'reject': False,
                'criterion_met': False,
                'control': 'AS_ORIGINAL', 'treatment': 'V2_ROW' if identifier == 'H2' else 'AS_G_ORIGINAL',
                'included_source_ids': ['SYNTH_A', 'SYNTH_B'],
                'excluded_source_ids': ['SYNTH_C'],
                'original_source_count': 3, 'eligible_source_count': 2,
                'missingness': {'full': {'control': rates(.3, .5), 'treatment': rates(.4, .6)},
                               'eligible': {'control': rates(.1, .2), 'treatment': rates(.2, .3)}}}
    report['N14_H2_missingness'] = {
        'enabled': True, 'primary': extra('H2'),
        'components': {key: extra(key) for key in ('K2', 'K4', 'K5')},
        'coverage': {'sources_without_valid_judgments_in_any_cell': ['SYNTH_C']}}
    for identifier in n14.IDENTIFIERS:
        original = (report['primary']['H2'] if identifier == 'H2'
                    else report['components']['contrasts'][identifier])
        original.update(n14_analysis_required=True, criterion_met=False,
                        g2_criterion_met=True, n14_criterion_met=False,
                        reject=True, adjusted_p=.02)
    return report


def test_distinct_G2_subset_and_final_decisions(tmp_path):
    report = fixture()
    before = deepcopy(report)
    primary = render._primary_table(report, tmp_path, render.SYNTHETIC_BANNER).read_text(encoding='utf8')
    components = n8_render._component_table(report, tmp_path, render.SYNTHETIC_BANNER).read_text(encoding='utf8')
    assert 'G2-H0 verworfen; N14-Endurteil: nicht bestätigt' in primary
    assert components.count('G2-Test: bestätigt; N14-Endurteil: nicht bestätigt') == 3
    paths = n14.render_n14(report, tmp_path, banner='cannot hide synthetic')
    assert {p.name for p in paths} == {'h2_n14_contrasts.tex', 'h2_n14_sources.tex', 'h2_n14_missingness.tex'}
    text = paths[0].read_text(encoding='utf8')
    assert text.count(' / G2') == text.count(' / N14') == 4
    assert '-9,00 [-12,00, -6,00]' in text and '0,02000' in text
    assert 'beide Analysen' in text and 'keine simultanen Holm-Intervalle' in text
    assert all(render.SYNTHETIC_BANNER in p.read_text(encoding='utf8') for p in paths)
    assert report == before


def test_sources_and_technical_rates_are_explicit_not_hardcoded(tmp_path):
    paths = n14.render_n14(fixture(), tmp_path, banner='synthetic')
    sources, rates = [p.read_text(encoding='utf8') for p in paths[1:]]
    assert 'SYNTH\\_A, SYNTH\\_B' in sources and 'SYNTH\\_C' in sources
    assert 'Quellen ohne jedes gültige H2-Urteil über alle Zellen' in sources
    assert '0,300' in rates and '0,150' in rates and '0,500' in rates
    assert 'techn. m Quelle' in rates and 'techn. m gepoolt' in rates
    assert 'fehlend + unklar Quelle' in rates and 'fehlend + unklar gepoolt' in rates
    assert 'Gültige negative Urteile sind nicht enthalten' in rates
    assert 'Fehlwerte plus gültige semantisch unklare Urteile' in rates
    assert 'G2-Nullwertungen' not in rates and 'G2 null/unklar' not in rates
    assert '21,9' not in rates and '31,5' not in rates
    assert 'Semantisch unklare, gültige Urteile' in rates


def test_no_eligible_sources_stay_nonestimable(tmp_path):
    report = fixture()
    value = report['N14_H2_missingness']['primary']
    value.update(included_source_ids=[], excluded_source_ids=['SYNTH_A', 'SYNTH_B', 'SYNTH_C'],
                 eligible_source_count=0, point_difference=None, ci95=None,
                 raw_p=None, adjusted_p=1., testable=False)
    for arm in ('control', 'treatment'):
        value['missingness']['eligible'][arm] = {key: None for key in value['missingness']['eligible'][arm]}
    path = n14.render_n14(report, tmp_path, banner='synthetic')[0]
    text = path.read_text(encoding='utf8')
    assert 'H2 / N14 & 0/3 & n. b. [n. b.]' in text
    assert 'nicht testbar. N14-Endurteil: nicht bestätigt' in text


def test_no_N14_preserves_legacy_delivery(tmp_path):
    report = report_fixture()
    assert n14.render_n14(report, tmp_path / 'unused', banner='synthetic') == []
    assert not (tmp_path / 'unused').exists()
    assert n14.note(report) == ''
    assert n14.end_status(report, 'H2', report['primary']['H2']) == ''


def test_real_and_unbound_N14_reports_fail_closed(tmp_path):
    report = fixture()
    report['synthetic'] = False
    with pytest.raises(ValueError, match='EXPLICIT_ENABLE'):
        n14.render_n14(report, tmp_path / 'real', banner='real')
    assert not (tmp_path / 'real').exists()
    report = fixture()
    del report['primary']['H2']['n14_analysis_required']
    with pytest.raises(ValueError, match='DECISION_BINDING_REQUIRED'):
        n14.render_n14(report, tmp_path / 'bad', banner='synthetic')
    assert not (tmp_path / 'bad').exists()


def test_forest_uses_final_N14_criterion_without_changing_G2_p_values():
    report = fixture()
    before = deepcopy(report)
    fig = n8_render._make_forest_figure(report, render.SYNTHETIC_BANNER)
    try:
        texts = '\n'.join(item.get_text() for item in fig.texts)
        assert 'p Holm: G2' in texts and 'Endkriterium bestätigt' in texts
        for axis, positions in ((fig.axes[0], [1]), (fig.axes[1], [1, 3, 4])):
            for y in positions:
                dots = [line for line in axis.lines if line.get_marker() == 'o'
                        and list(line.get_ydata()) == [y]]
                assert len(dots) == 1 and dots[0].get_markerfacecolor() == 'white'
        assert report == before
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def test_holm_confirmed_but_final_N14_failed_is_not_filled():
    report = fixture()
    original = report['components']['contrasts']['K5']
    assert original['reject'] is True and original['adjusted_p'] == .02
    assert n14.final_confirmation(report, 'K5', original) is False
    original['criterion_met'] = True
    assert n14.final_confirmation(report, 'K5', original) is True


def test_N14_and_N10_forest_legend_remain_inside_the_figure():
    report = fixture()
    report['N10_H1_sampling'] = {'selected_groups': 2, 'population_groups': 4}
    fig = n8_render._make_forest_figure(report, render.SYNTHETIC_BANNER)
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for text in fig.texts:
            box = text.get_window_extent(renderer)
            assert box.x0 >= fig.bbox.x0 - .5 and box.x1 <= fig.bbox.x1 + .5
            assert box.y0 >= fig.bbox.y0 - .5 and box.y1 <= fig.bbox.y1 + .5
        footer = min(fig.texts, key=lambda t: t.get_position()[1]).get_window_extent(renderer)
        xlabel = fig.axes[1].xaxis.label.get_window_extent(renderer)
        assert footer.y1 + 3 < xlabel.y0
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def test_N14_tables_compile_when_latex_is_available(tmp_path):
    import shutil
    import subprocess
    latex = shutil.which('pdflatex')
    if latex is None:
        pytest.skip('No local pdflatex available')
    paths = n14.render_n14(fixture(), tmp_path, banner='synthetic')
    wrapper = tmp_path / 'n14.tex'
    wrapper.write_text('\n'.join([
        r'\documentclass[a4paper,12pt]{article}', r'\usepackage[T1]{fontenc}',
        r'\usepackage[utf8]{inputenc}', r'\usepackage[a4paper,margin=25mm]{geometry}',
        r'\usepackage{booktabs,longtable}', r'\begin{document}',
        *[r'\input{' + p.name + r'}\clearpage' for p in paths], r'\end{document}']), encoding='utf8')
    result = subprocess.run([latex, '-interaction=nonstopmode', '-halt-on-error', wrapper.name],
                            cwd=tmp_path, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout.decode(errors='replace')[-4000:]
    log = (tmp_path / 'n14.log').read_text(errors='replace')
    assert 'Overfull \\hbox' not in log
