"""Static, source-backed N17 cost/quality figure; no model or network access."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


ARMS = ('AS', 'AS+G', 'V1', 'V2')
STYLES = {
    'AS': ('#303030', 'o'),
    'AS+G': ('#0072B2', 's'),
    'V1': ('#D55E00', '^'),
    'V2': ('#7A4F9A', 'D'),
}


def interval(value):
    point = value.get('estimate')
    ci = value.get('ci95')
    if point is None:
        return None
    if isinstance(ci, dict):
        lo, hi = ci.get('lower'), ci.get('upper')
    elif ci is not None:
        lo, hi = ci
    else:
        lo = hi = None
    return point, lo, hi


def plot(result: dict, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.titlesize': 11, 'axes.labelsize': 10,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42})
    fig, axes = plt.subplots(1, 2, figsize=(11.7, 4.7))
    points = []
    panels = (
        ('H1_NEW20', 'H1', 'a  Quellenstützung', 'H1: gestützte Aussagen (%)'),
        ('H2_N14_NEW20', 'H2', 'b  Ausgewählter Bedeutungserhalt', 'H2: erhaltene Referenzbedeutungen (%)'),
    )
    for ax, (popname, quality_key, title, ylabel) in zip(axes, panels):
        population = result['populations'][popname]
        rows = population['by_arm']
        for arm in ARMS:
            row = rows[arm]
            x, y = interval(row['mean_cost_per_source_usd']), interval(row[quality_key])
            if x is None or y is None:
                raise ValueError(f'No estimable point for {popname}/{arm}; do not fabricate it')
            color, marker = STYLES[arm]
            # Quantile intervals need not contain the estimate: draw endpoints
            # as segments rather than truncating or replacing their endpoints.
            if x[1] is not None and x[2] is not None:
                ax.plot([x[1], x[2]], [y[0]*100]*2, color=color, alpha=.50, lw=1.2)
            if y[1] is not None and y[2] is not None:
                ax.plot([x[0]]*2, [y[1]*100, y[2]*100], color=color, alpha=.65, lw=1.2)
            ax.scatter(x[0], y[0]*100, color=color, marker=marker, s=53,
                       edgecolor='white', linewidth=.65, zorder=3, label=arm)
            # Four direct labels keep the same identity in monochrome.
            offsets = {'AS':(-7,-17), 'AS+G':(5,7), 'V1':(5,-17), 'V2':(5,7)}
            dx,dy=offsets[arm]
            ax.annotate(arm, (x[0], y[0]*100), xytext=(dx,dy),
                        textcoords='offset points', ha='right' if dx<0 else 'left',
                        va='bottom', color=color, fontsize=10, fontweight='bold')
            points.append({'panel':popname, 'arm':arm, 'n_sources':population['n_sources'],
                           'x_mean_list_price_USD_per_source':x,
                           'y_quality_fraction':y})
        ax.set_title(f"{title}\n{population['n_sources']} Quellen · je 3 Durchläufe", loc='left', pad=12)
        ax.set_xlabel('Listenpreiskosten je Quelle (USD)')
        ax.set_ylabel(ylabel)
        ax.set_xlim(left=0)
        ax.margins(x=.16, y=.18)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_: f'{v:.0f}'))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v,_: f'{v:.2f}'.replace('.',',')))
        ax.grid(axis='both', color='#DFDFDF', lw=.6, zorder=0)
        ax.spines[['top','right']].set_visible(False)
    fig.subplots_adjust(left=.065,right=.98,top=.82,bottom=.23,wspace=.30)
    fig.text(.065,.085,
             'Punkte: Quellenmittel; Linien: marginale 95-%-Bootstrapintervalle aus denselben N10-Ziehungen.\n'
             'Nur vollständige Kosten; H1: neue Quellen, H2: N14-Teilmenge. Forschungskosten getrennt; X3 ohne Messlauf nicht dargestellt.',
             fontsize=9, color='#404040', va='bottom')
    for ext in ('png','pdf','svg'):
        fig.savefig(output/f'kosten_qualitaet.{ext}', dpi=220 if ext=='png' else None,
                    facecolor='white', metadata={'Creator':'EF1 N17 CPU analysis'})
    plt.close(fig)
    (output/'figure-data.json').write_text(json.dumps(points,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return points


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('result',type=Path)
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    args=p.parse_args()
    plot(json.loads(args.result.read_text(encoding='utf-8')),args.output)
