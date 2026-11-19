"""Render saved withheld-ground-truth examples without reading live data."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def plot(source,output):
    report=json.loads(Path(source).read_text());fig,axes=plt.subplots(2,3,figsize=(14,7),constrained_layout=True)
    for row,(region,result) in enumerate(report['regions'].items()):
        for col in range(3):
            ax=axes[row,col]
            if col>=len(result['examples']):ax.text(.5,.5,'No accepted examples',ha='center');continue
            r=result['examples'][col];e=r['example'];offset=e['actual_m'][0]
            ax.plot(e['seconds'],[x-offset for x in e['actual_m']],color='black',label='Withheld observation',lw=2)
            ax.plot(e['seconds'],[x-offset for x in e['estimated_m']],color='#005fbb',ls='--',label='Motion-based estimate',lw=2)
            ax.plot(e['seconds'],[x-offset for x in e['linear_m']],color='#c66c00',ls=':',label='Linear baseline')
            ax.set_title(f"{region}: {['lowest','median','highest'][col]} accepted error\n{r['duration']:.1f} s gap, MAE {r['mae_m']:.2f} m")
            ax.set_xlabel('Seconds after visible boundary');ax.set_ylabel('Longitudinal displacement (m)');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8);fig.suptitle('Hide-and-reconstruct validation: observed local trajectories only\nExamples span all tested gap lengths; retrospective interpolation, not DeepCTM forecasts',fontsize=13)
    fig.savefig(output,dpi=150);plt.close(fig)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();plot(a.source,a.output)
