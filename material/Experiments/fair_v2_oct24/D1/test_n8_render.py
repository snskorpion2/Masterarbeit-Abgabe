"""Only hand-authored synthetic effects. No natural judgments, answers or labels."""
from copy import deepcopy
from pathlib import Path

import pytest

from Experiments.fair_v2_oct24.D1 import n8_render as r


def report_fixture():
    def effect(point, low, high, boundary=0., *, adjusted=.03, reject=True, testable=True):
        return {'point_difference': point, 'ci95': {'lower': low, 'upper': high},
                'null_boundary': boundary, 'adjusted_p': adjusted,
                'testable': testable, 'reject': reject}
    primary = {'H1': effect(.08, .02, .14), 'H2': effect(-.01, -.035, .02, -.05),
               'H4': effect(.025, -.02, .07, adjusted=.31, reject=False)}
    components = {name: effect(.02 + index * .01, -.01, .10,
                              r.COMPONENT_BOUNDARIES[name], adjusted=.02 + index * .01 if index < 3 else .1 + index * .01,
                              reject=index < 3) for index, name in enumerate(r.COMPONENTS)}
    # One known negative point, and one genuinely unobserved effect.
    components['K5'] = effect(-.02, -.08, .03, adjusted=.61, reject=False)
    components['K6'] = {'point_difference': None, 'ci95': None, 'null_boundary': -.05,
                        'adjusted_p': 1., 'testable': False, 'reject': False}
    h4 = [{'export': export, 'component': component, 'endpoint': 'F1',
           'control': control + '_' + export, 'treatment': treatment + '_' + export,
           'point_difference': .03, 'ci95': {'lower': -.01, 'upper': .08}}
          for export in ('ORIGINAL', 'ROW')
          for component, control, treatment in (('guard_AS', 'AS', 'AS_G'),
                                                ('guard_V1', 'V1', 'V2'),
                                                ('extraction_extension', 'AS', 'V1'))]
    return {'synthetic': True, 'primary': primary,
            'components': {'contrasts': components, 'H4_descriptive': h4},
            'overall_judgment': {'stage': 'B', 'base_stage': 'B',
                'statement': 'Synthetisches Beispiel & keine Überlegenheit.',
                'qualifications': ['H1 ist bewerterabhängig.', 'C7 fehlt.'],
                'evaluator_dependent': True},
            'efficiency': {'rows': [
                {'population': 'synthetisch', 'arm': 'AS', 'currency': 'USD',
                 'cost_per_supported': '0.002', 'tokens_per_supported': 200.,
                 'supported_per_1000_construction_tokens': 5., 'cost_complete': True,
                 'support_complete': True, 'usage_complete': True,
                 'construction_usage_complete': True, 'stage_coverage_complete': True,
                 'construction_stage_coverage_complete': True, 'missing_stages': []},
                {'population': 'synthetisch', 'arm': 'V2', 'currency': 'EUR',
                 'cost_per_supported': None, 'tokens_per_supported': None,
                 'supported_per_1000_construction_tokens': None, 'cost_complete': False}]}}


def test_exact_families_and_fraction_to_percentage_point_limits():
    left, right = r._families(report_fixture())
    assert [row['identifier'] for row in left] == ['H1', 'H2', 'H4']
    assert [row['identifier'] for row in right] == list(r.COMPONENTS)
    assert [row['identifier'] for row in left + right if row['boundary'] == -.05] == ['H2', 'K2', 'K4', 'K6']
    assert r._effect_text(.08, {'lower': -.02, 'upper': .14}) == '8,00 [-2,00, 14,00]'
    assert r._effect_text(None, None) == 'n. b. [n. b.]'


def test_missing_component_or_wrong_boundary_fails_closed():
    report = report_fixture()
    del report['components']['contrasts']['K6']
    with pytest.raises(ValueError, match='EXACT_COMPONENT_FAMILY'):
        r._families(report)
    report = report_fixture()
    report['components']['contrasts']['K2']['null_boundary'] = 0
    with pytest.raises(ValueError, match='FROZEN_NULL_BOUNDARY'):
        r._families(report)


def test_unconfirmed_small_adjusted_p_is_not_misrepresented():
    report = report_fixture()
    report['primary']['H1'].update(reject=False)
    with pytest.raises(ValueError, match='INCONSISTENT_HOLM_DECISION'):
        r._families(report)


@pytest.mark.parametrize('field,value', [('point_difference', float('nan')),
                                         ('point_difference', False), ('adjusted_p', 1.2)])
def test_invalid_effects_are_not_silently_plotted(field, value):
    report = report_fixture()
    report['primary']['H1'][field] = value
    with pytest.raises(ValueError):
        r._families(report)


def test_real_report_is_rejected_before_creating_output(tmp_path):
    report = report_fixture()
    report['synthetic'] = False
    with pytest.raises(ValueError, match='EXPLICIT_ENABLE'):
        r.render_n8(report, tmp_path / 'absent', banner='real')
    assert not (tmp_path / 'absent').exists()


def test_tables_preserve_banners_missingness_and_holm_separation(tmp_path):
    paths = r.render_n8(report_fixture(), tmp_path, banner='caller cannot hide synthetic origin')
    assert {path.name for path in paths} == {
        'forest_primary_components.pdf', 'component_contrasts.tex', 'overall_judgment.tex',
        'H4components_descriptive.tex', 'efficiency_supported.tex'}
    texts = {path.name: path.read_text(encoding='utf8') for path in paths if path.suffix == '.tex'}
    assert all(r.SYNTHETIC_BANNER in text for text in texts.values())
    assert 'sechs Slots' in texts['component_contrasts.tex']
    assert 'Aktuelle H1-Qualifikation: bewerterabhängig' in texts['component_contrasts.tex']
    assert 'keine simultanen Holm' in texts['component_contrasts.tex']
    assert 'C7 fehlt.' in texts['overall_judgment.tex']
    assert r'Beispiel \&' in texts['overall_judgment.tex']
    assert texts['H4components_descriptive.tex'].count('ORIGINAL') >= 3
    assert 'Kein p-Wert' in texts['H4components_descriptive.tex']
    assert 'EUR' in texts['efficiency_supported.tex'] and 'USD' in texts['efficiency_supported.tex']
    assert '0,002000' in texts['efficiency_supported.tex']
    assert 'n. b.' in texts['efficiency_supported.tex']


def test_vector_pdf_and_no_mutation_or_open_figures(tmp_path):
    report = report_fixture()
    before = deepcopy(report)
    paths = r.render_n8(report, tmp_path, banner=r.SYNTHETIC_BANNER)
    assert report == before
    raw = next(path for path in paths if path.suffix == '.pdf').read_bytes()
    assert raw.startswith(b'%PDF-') and len(raw) > 1000
    assert b'/Subtype /Image' not in raw
    import matplotlib.pyplot as plt
    assert not plt.get_fignums()


def test_figure_contains_nine_rows_shared_scale_and_unclipped_text():
    import matplotlib.pyplot as plt
    figure = r._make_forest_figure(report_fixture(), r.SYNTHETIC_BANNER)
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        assert len(figure.axes) == 2
        assert [len(axis.get_yticks()) for axis in figure.axes] == [3, 6]
        assert figure.axes[0].get_xlim() == figure.axes[1].get_xlim()
        assert figure.axes[0].get_xlim()[0] < -5 < 0 < figure.axes[0].get_xlim()[1]
        assert any(text.get_text() == 'n. b.' for axis in figure.axes for text in axis.texts)
        all_text = list(figure.texts)
        for axis in figure.axes:
            all_text += list(axis.texts) + list(axis.get_yticklabels()) + list(axis.get_xticklabels())
            all_text += [axis.title, axis.xaxis.label]
        frame = figure.bbox
        for text in all_text:
            if text.get_visible() and text.get_text():
                box = text.get_window_extent(renderer)
                assert box.x0 >= frame.x0 - .5 and box.x1 <= frame.x1 + .5, text.get_text()
                assert box.y0 >= frame.y0 - .5 and box.y1 <= frame.y1 + .5, text.get_text()
    finally:
        plt.close(figure)


def test_multi_currency_component_is_not_shown_as_pipeline_cost(tmp_path):
    report = report_fixture()
    report['efficiency']['rows'][0].update(cost_scope='currency_component_only', cost_per_supported='99')
    path = r._efficiency_table(report, tmp_path, r.SYNTHETIC_BANNER)
    text = path.read_text(encoding='utf8')
    assert 'n. b. (Währungsteil)' in text and '99,000000' not in text


def test_new_tables_compile_at_thesis_text_width_when_latex_is_available(tmp_path):
    import shutil
    import subprocess
    latex = shutil.which('pdflatex')
    if latex is None:
        pytest.skip('No local pdflatex for the optional CPU layout check')
    paths = r.render_n8(report_fixture(), tmp_path, banner=r.SYNTHETIC_BANNER)
    wrapper = tmp_path / 'n8-tables-check.tex'
    wrapper.write_text('\n'.join([
        r'\documentclass[a4paper,11pt]{article}',
        r'\usepackage[T1]{fontenc}', r'\usepackage[utf8]{inputenc}',
        r'\usepackage[textwidth=155mm,textheight=245mm]{geometry}',
        r'\usepackage{booktabs,longtable}', r'\begin{document}',
        *[r'\input{' + path.name + '}\n' + r'\clearpage'
          for path in paths if path.suffix == '.tex'], r'\end{document}']), encoding='utf8')
    for _ in range(2):
        result = subprocess.run([latex, '-interaction=nonstopmode', '-halt-on-error', wrapper.name],
                                cwd=tmp_path, capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout.decode('utf8', errors='replace')[-4000:]
    log = wrapper.with_suffix('.log').read_text(encoding='utf8', errors='replace')
    assert 'Overfull' not in log and 'Missing character' not in log
    assert wrapper.with_suffix('.pdf').read_bytes().startswith(b'%PDF-')


def test_undefined_c7_kappa_qualification_compiles_without_changing_judgment(tmp_path):
    import shutil
    import subprocess
    from Experiments.fair_v2_oct24.D1.judgment import overall_judgment
    latex = shutil.which('pdflatex')
    if latex is None:
        pytest.skip('No local pdflatex for the optional CPU layout check')
    report = report_fixture()
    for row in report['primary'].values():
        row['criterion_met'] = row['reject']
    report['overall_judgment'] = overall_judgment(report['primary'],
        c7_available=True, human_kappa=None, c4_available=False)
    before = deepcopy(report)
    assert any('Cohen-κ' in text for text in report['overall_judgment']['qualifications'])
    table = r._overall_table(report, tmp_path, r.SYNTHETIC_BANNER)
    wrapper = tmp_path / 'n8-c7-undefined-kappa-check.tex'
    wrapper.write_text('\n'.join([
        r'\documentclass[a4paper,11pt]{article}',
        r'\usepackage[T1]{fontenc}', r'\usepackage[utf8]{inputenc}',
        r'\usepackage[textwidth=155mm,textheight=245mm]{geometry}',
        r'\usepackage{booktabs,longtable}', r'\begin{document}',
        r'\input{' + table.name + '}', r'\end{document}']), encoding='utf8')
    for _ in range(2):
        result = subprocess.run([latex, '-interaction=nonstopmode', '-halt-on-error', wrapper.name],
                                cwd=tmp_path, capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout.decode('utf8', errors='replace')[-4000:]
    text = table.read_text(encoding='utf8')
    assert 'C7-Cohen-kappa' in text and 'κ' not in text
    assert report == before
    log = wrapper.with_suffix('.log').read_text(encoding='utf8', errors='replace')
    assert 'Overfull' not in log and 'Missing character' not in log
    assert wrapper.with_suffix('.pdf').read_bytes().startswith(b'%PDF-')
