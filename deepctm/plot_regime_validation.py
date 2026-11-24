"""Plot fixed held-out examples, including truth never supplied to the model."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from .reconstruction_layers import prediction


def plot(study, output):
    study = Path(study)
    examples = json.loads((study/'examples.json').read_text())['examples']
    root = Path(__file__).resolve().parents[1]
    reference = json.loads((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text())
    fig, axes = plt.subplots(len(examples), 2, figsize=(12, 3.3*len(examples)), squeeze=False)
    names = {'OBC-AG-SA-C257222':'Cranes Roost', 'OBC-AG-SA-C257236':'Essex',
             'OBC-AG-SA-C251068':'Renaissance'}
    for row, e in enumerate(examples):
        a, b = e['a'], e['b']; start, end = a['t'], b['t']
        visible = np.array(e['visible']); truth = np.array(e['hidden_truth']); learned = np.array(e['learned'])
        base = np.array(prediction(a, b, reference, exact_join=True))
        for col, axis in enumerate(axes[row]):
            value = col+1
            for part in (visible[(visible[:,0]>=start-5)&(visible[:,0]<=start)],
                         visible[(visible[:,0]>=end)&(visible[:,0]<=end+5)]):
                axis.plot(part[:,0]-start, part[:,value], color='#86949c', lw=2, label='Visible observations' if part is not None else None)
            axis.axvspan(0, end-start, color='#eef1f6', zorder=-1)
            axis.plot(truth[:,0]-start, truth[:,value], color='#182e38', lw=2, label='Hidden recorded truth')
            axis.plot(base[:,0]-start, base[:,value], '--', color='#d99226', lw=1.7, label='Previous estimator')
            axis.plot(learned[:,0]-start, learned[:,value], '--', color='#8c42dc', lw=1.8, label='Group-learned estimate')
            axis.set_xlabel('Seconds from gap start');axis.set_ylabel('Corridor station (m)' if col==0 else 'Speed (m/s)')
            axis.grid(alpha=.2);axis.spines[['top','right']].set_visible(False)
            axis.set_xlim(-5,end-start+5)
        metric=e['metrics'];old=metric['kinematic']['mae_m'];new=metric['learned_regime']['mae_m']
        axes[row,0].set_title(f"{names.get(e['site'],e['site'])} · {e['regime']} · {end-start:.1f} s gap",loc='left',fontsize=11)
        axes[row,1].set_title(f'Position error: {old:.3f} → {new:.3f} m',loc='left',fontsize=11)
    handles, labels = axes[0,0].get_legend_handles_labels();unique=dict(zip(labels,handles))
    fig.legend(unique.values(),unique.keys(),loc='upper center',ncol=4,bbox_to_anchor=(.5,.958),frameon=False)
    fig.suptitle('Florida · recorded-data masking test, November 24',fontsize=16,y=.995)
    fig.text(.5,.01,'First accepted held-out example per motion type; not chosen by error. Shaded intervals were hidden.\nRetrospective local reconstruction; these examples do not verify cross-sensor identities.',ha='center',fontsize=9,color='#53636b')
    fig.tight_layout(rect=(0,.055,1,.925))
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=160,facecolor='white');plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();plot(args.study,args.output)
