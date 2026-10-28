"""Renderer contracts and physical layout from hand-written synthetic values."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from . import ab2_render as ab2


def fixture():
    def effect(identifier, endpoint, control, treatment, value=.1, n=3):
        return {'identifier': identifier, 'endpoint': endpoint, 'control': control,
                'treatment': treatment, 'point_difference': value,
                'ci95': {'lower': value - .03, 'upper': value + .04},
                'raw_p': .031, 'testable': True, 'cluster_count': n,
                'null_boundary': -.05 if identifier in ab2.NI_IDENTIFIERS else 0.}
    report = {'synthetic': True, 'holm_computed': False,
              'overall_judgment_computed': False, 'metadata': {'sources': 3},
              'pending': {key: True for key in ('H4', 'H12', 'S13')}}
    report['primary'] = {
        'H1': effect('H1', 'H1', 'AS_ORIGINAL', 'V2_ROW'),
        'H2': effect('H2', 'H2', 'AS_ORIGINAL', 'V2_ROW', .08),
        'H4': {'identifier': 'H4', 'endpoint': 'F1', 'status': 'pending',
               'control': 'AS_ORIGINAL', 'treatment': 'V2_ROW', 'testable': False,
               'point_difference': None, 'ci95': None, 'raw_p': None, 'null_boundary': 0.}}
    comparisons = [('AS_ORIGINAL', 'AS_G_ORIGINAL'), ('AS_ORIGINAL', 'AS_G_ORIGINAL'),
                   ('V1_ORIGINAL', 'V2_ORIGINAL'), ('V1_ORIGINAL', 'V2_ORIGINAL'),
                   ('AS_ORIGINAL', 'V1_ORIGINAL'), ('AS_ORIGINAL', 'V1_ORIGINAL')]
    report['components'] = {'contrasts': {
        f'K{i}': effect(f'K{i}', 'H1' if i in (1, 3, 6) else 'H2', c, t,
                       0. if i == 4 else .1) for i, (c, t) in enumerate(comparisons, 1)}}
    extra = {}
    for identifier in ('H2', 'K2', 'K4', 'K5'):
        row = deepcopy(report['primary']['H2'] if identifier == 'H2'
                       else report['components']['contrasts'][identifier])
        row['point_difference'] = -.01
        row['ci95'] = {'lower': -.04, 'upper': .02}
        row['eligible_source_count'] = 2
        row['original_source_count'] = 3
        extra[identifier] = row
    report['N14_H2_missingness'] = {'enabled': True, 'primary': extra['H2'],
                                  'components': {k: extra[k] for k in ('K2', 'K4', 'K5')}}
    report['strata'] = []
    for endpoint, dimension, levels in (('H1', 'category', ('EE', 'EV', 'VV')),
                                         ('H2', 'family', ('wikipedia', 'factbook', 'sealed4'))):
        for level in levels:
            for method, cell in ab2.CELL_BINDINGS:
                row = {'endpoint': endpoint, 'dimension': dimension, 'level': level,
                       'cell': cell, 'estimate': .7, 'lower': .7, 'upper': .9,
                       'missing_rate': .2, 'source_count': 3 if endpoint == 'H1' else 1,
                       'CI_scope': 'marginal, supplied'}
                if endpoint == 'H1':
                    row['ci95'] = {'lower': .6, 'upper': .8}
                    if level == 'VV' or level == 'EV' and method in ('AS', 'AS+G'):
                        row['ci95'] = None
                    if level == 'VV' and method in ('V1', 'V2'):
                        row.update(estimate=None, lower=.3, upper=.8)
                elif level == 'sealed4':
                    row.update(estimate=0., lower=0., upper=1., missing_rate=1.)
                report['strata'].append(row)
    return report


def _close(fig):
    import matplotlib.pyplot as plt
    plt.close(fig)


def test_complete_order_units_and_no_mutation():
    report = fixture()
    before = deepcopy(report)
    rows = ab2.forest_rows(report)
    assert [(r['identifier'], r['analysis']) for r in rows] == [
        ('H1', 'G2/N10'), ('H2', 'G2'), ('H2', 'N14'), ('H4', 'ausstehend'),
        ('K1', 'G2/N10'), ('K2', 'G2'), ('K2', 'N14'), ('K3', 'G2/N10'),
        ('K4', 'G2'), ('K4', 'N14'), ('K5', 'G2'), ('K5', 'N14'), ('K6', 'G2/N10')]
    assert rows[0]['point_difference'] == .1
    assert ab2._effect_text(rows[0]) == '10,00 [7,00; 14,00]'
    assert rows[2]['source_count'] == 2 and rows[1]['source_count'] == 3
    assert report == before


def test_missing_H4_is_not_a_zero_effect_but_true_zero_stays_visible():
    fig = ab2.make_forest(fixture())
    try:
        primary, components = fig.axes
        markers = lambda ax: [l for l in ax.lines if l.get_marker() in ('o', 'D')]
        assert len(markers(primary)) == 3
        assert all(list(l.get_ydata()) != [3] for l in markers(primary))
        assert any(t.get_text() == 'ausstehend' for t in primary.texts)
        zero = [l for l in markers(components) if list(l.get_xdata()) == [0.]]
        assert len(zero) == 1
        assert not any('bestätigt' in t.get_text() for t in fig.texts)
    finally:
        _close(fig)


def test_reference_lines_and_family_labels_are_visible_in_grayscale():
    fig = ab2.make_forest(fixture())
    try:
        assert 'Primärfamilie' in fig.axes[0].get_title(loc='left')
        assert 'Sekundäre Komponentenfamilie' in fig.axes[1].get_title(loc='left')
        for ax in fig.axes:
            refs = [l for l in ax.lines if list(l.get_xdata()) in ([0, 0], [-5, -5])
                    and list(l.get_ydata()) == [0, 1]]
            assert len(refs) == 2 and len({l.get_linestyle() for l in refs}) == 2
            assert {l.get_marker() for l in ax.lines if l.get_marker() in ('o', 'D')} == {'o', 'D'}
        notes = '\n'.join(t.get_text() for t in fig.texts)
        assert 'NI-Grenze -5 Pp.' in notes and 'K6' in notes
        assert 'Holm-Entscheidungen' in notes and 'stehen aus' in notes
    finally:
        _close(fig)


def test_subgroups_preserve_nonestimable_points_missing_CI_and_coded_zero():
    report = fixture()
    before = deepcopy(report)
    rows = ab2.detail_rows(report)
    assert len(rows) == 24
    vv = next(r for r in rows if r['level'] == 'VV' and r['method'] == 'V2')
    assert vv['estimate'] is None and vv['ci95'] is None
    assert ab2._detail_text(vv) == 'n. b.\nS [30,0; 80,0]'
    zero = next(r for r in rows if r['level'] == 'sealed4' and r['method'] == 'AS')
    assert ab2._detail_text(zero) == '0,0*\nm = 100,0 %'
    ev = next(r for r in rows if r['level'] == 'EV' and r['method'] == 'AS')
    assert 'S [' in ab2._detail_text(ev) and 'KI [' not in ab2._detail_text(ev)
    assert report == before


def test_export_views_are_selected_explicitly_and_never_averaged():
    report = fixture()
    shadow = deepcopy(next(r for r in report['strata'] if r['cell'] == 'V2_ROW'))
    shadow.update(cell='V2_ORIGINAL', estimate=.999)
    report['strata'].append(shadow)
    selected = next(r for r in ab2.detail_rows(report) if r['cell'] == 'V2_ROW')
    assert selected['estimate'] == .7


@pytest.mark.parametrize('change,code', [
    (lambda d: d['primary']['H4'].update(point_difference=0.), 'pending H4'),
    (lambda d: d['primary']['H2'].update(null_boundary=0.), 'BOUNDARY_MISMATCH'),
    (lambda d: d['primary']['H1'].update(null_boundary=False), 'BOUNDARY_MISMATCH'),
    (lambda d: d['components']['contrasts']['K6'].update(null_boundary=0.), 'BOUNDARY_MISMATCH'),
    (lambda d: d['N14_H2_missingness']['components'].pop('K4'), 'all N14 component'),
    (lambda d: d.update(holm_computed=True), 'multiplicity'),
    (lambda d: d['primary']['H1'].update(adjusted_p=.01), 'final decisions'),
    (lambda d: d['primary']['H1'].update(ci95={'lower': float('nan'), 'upper': .5}), 'finite'),
])
def test_invalid_effect_contracts_fail_closed(change, code):
    report = fixture(); change(report)
    with pytest.raises(ValueError, match=code):
        ab2.forest_rows(report)


def test_missing_or_duplicate_strata_and_invented_family_CI_fail_closed():
    report = fixture(); report['strata'].pop()
    with pytest.raises(ValueError, match='UNIQUE_SAVED_STRATUM'):
        ab2.detail_rows(report)
    report = fixture(); report['strata'].append(deepcopy(report['strata'][0]))
    with pytest.raises(ValueError, match='UNIQUE_SAVED_STRATUM'):
        ab2.detail_rows(report)
    report = fixture()
    next(r for r in report['strata'] if r['endpoint'] == 'H2')['ci95'] = {'lower': .1, 'upper': .9}
    with pytest.raises(ValueError, match='NO_FAMILY_CI'):
        ab2.detail_rows(report)


def _assert_layout(fig):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = list(fig.texts)
    for ax in fig.axes:
        texts += list(ax.texts) + [ax.title, ax._left_title]
        if ax.axison:
            texts += [ax.xaxis.label] + ax.get_xticklabels()
        for table in ax.tables:
            for cell in table.get_celld().values():
                box = cell.get_text().get_window_extent(renderer)
                assert cell.get_window_extent(renderer).contains(box.x0, box.y0)
                assert cell.get_window_extent(renderer).contains(box.x1, box.y1)
    boxes = [(t, t.get_window_extent(renderer)) for t in texts if t.get_visible() and t.get_text()]
    for text, box in boxes:
        assert text.get_fontsize() >= 9, text.get_text()
        assert box.x0 >= -.5 and box.x1 <= fig.bbox.x1 + .5, text.get_text()
        assert box.y0 >= -.5 and box.y1 <= fig.bbox.y1 + .5, text.get_text()
    for i, (left, a) in enumerate(boxes):
        for right, b in boxes[i + 1:]:
            assert not a.overlaps(b), (left.get_text(), right.get_text())


@pytest.mark.parametrize('builder', [ab2.make_forest, ab2.make_details])
def test_final_size_contains_all_text_without_collisions(builder):
    fig = builder(fixture())
    try:
        assert fig.get_figwidth() == 6.0
        assert fig.get_figheight() <= 7.0
        _assert_layout(fig)
    finally:
        _close(fig)


def test_real_input_requires_explicit_enable_before_any_output(tmp_path):
    report = fixture(); report['synthetic'] = False
    with pytest.raises(ValueError, match='EXPLICIT_ENABLE'):
        ab2.render(report, tmp_path / 'blocked')
    assert not (tmp_path / 'blocked').exists()


def test_render_and_cli_reproduce_exact_scalars_without_mutating_input(tmp_path, capsys):
    report = fixture()
    raw = json.dumps(report, ensure_ascii=False).encode('utf-8')
    source = tmp_path / 'analysis.json';source.write_bytes(raw)
    out = tmp_path / 'figures'
    ab2.main(['--analysis', str(source), '--output', str(out)])
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['main_figure_count'] == 1 and receipt['forest_rows'] == 13
    assert receipt['detail_cells'] == 24 and receipt['measurement_or_inference_recomputed'] is False
    assert str(source) not in json.dumps(receipt)
    assert source.read_bytes() == raw
    assert sorted(p.name for p in out.glob('*.pdf')) == ['aufteilungen.pdf', 'hauptabbildung.pdf']
    for p in out.glob('*.pdf'):
        assert p.read_bytes().startswith(b'%PDF-')
    for name in ('hauptabbildung_daten.csv', 'aufteilungen_daten.csv', 'LESEHILFE.md', 'result.json'):
        assert (out / name).is_file()
        assert b'\r' not in (out / name).read_bytes()
    with pytest.raises(ValueError, match='DIRECTORY_MUST_BE_NEW'):
        ab2.render(report, out)
    second = ab2.render(report, tmp_path / 'second')
    assert (out / 'hauptabbildung.pdf').read_bytes() == (second / 'hauptabbildung.pdf').read_bytes()
    assert (out / 'aufteilungen_daten.csv').read_bytes() == (second / 'aufteilungen_daten.csv').read_bytes()
