"""Render auditable external-recording evidence, not a simulated corridor plot."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

def render(report,output):
    d=json.loads(Path(report).read_text());fig,axes=plt.subplots(1,3,figsize=(15,5.5))
    colors=['#64748b','#087f8c'];local=d['local']['summary'];assoc=d['association']['totals']
    bars=axes[0].bar(['Previous','Candidate'],[assoc['current']['correct'],assoc['0.5']['correct']],color=colors,width=.6)
    axes[0].bar_label(bars,padding=4);axes[0].set_ylim(0,3000);axes[0].set_ylabel('Correct masked associations')
    axes[0].set_title('Association: more correct, fewer false',fontsize=12)
    axes[0].text(.5,-.18,f"False matches: {assoc['current']['false']} → {assoc['0.5']['false']}\n{assoc['current']['eligible']:,} correlated scenarios",transform=axes[0].transAxes,ha='center',fontsize=10)
    bars=axes[1].bar(['Strict endpoints','Stationary correction'],[local['strict']['accepted'],local['noise']['accepted']],color=colors,width=.6)
    axes[1].bar_label(bars,padding=4);axes[1].set_ylim(0,600);axes[1].set_ylabel('Accepted local hidden-gap cases')
    axes[1].set_title('Local endpoint-noise correction',fontsize=12)
    axes[1].text(.5,-.18,f"{local['noise']['new']['n']} additional cases; mean error\n{local['noise']['new']['mae_m']:.2f} m on those additional cases",transform=axes[1].transAxes,ha='center',fontsize=10)
    labels=['≤30 s','60 s','90 s'];means=[];tails=[];counts=[]
    for gaps in [(10,30),(60,),(90,)]:
        values=[r['metrics']['adaptive']['mae_m'] for r in d['quadratic']['cases'] if r['gap_s'] in gaps and 'adaptive' in r['metrics'] and 'baseline' not in r['metrics']]
        means.append(np.mean(values) if values else np.nan);tails.append(np.quantile(values,.95) if values else np.nan);counts.append(len(values))
    bars=axes[2].bar(labels,means,color=['#087f8c','#c56b33','#aa3f44'],width=.6)
    for i,(mean,tail) in enumerate(zip(means,tails)):
        axes[2].text(i,tail+.65,f'Mean {mean:.2f} m',ha='center',fontsize=9)
    axes[2].plot(range(3),tails,'D',color='#273444',label='95th percentile case MAE',markersize=5)
    axes[2].set_ylabel('Position error (m)');axes[2].set_title('Extra solver paths: longer is less certain',fontsize=12)
    axes[2].legend(fontsize=8,loc='upper left');axes[2].set_ylim(0,max(tails)*1.25)
    axes[2].text(.5,-.18,'Additional cases: '+', '.join(str(n) for n in counts)+'\nSolver fallback remains unpublished',transform=axes[2].transAxes,ha='center',fontsize=10)
    for ax in axes:
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True);ax.tick_params(labelsize=9)
    fig.suptitle('Finch · November 6 recording · frozen-method validation',fontsize=16,fontweight='bold',y=.97)
    fig.text(.5,.015,'Recorded sections were hidden for testing. Repeated masks are correlated. Current provisional alignment; no verified cross-sensor identities.',ha='center',fontsize=9,color='#475569')
    fig.subplots_adjust(top=.82,bottom=.28,wspace=.38)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(output,dpi=180,facecolor='white');plt.close(fig)
    return str(output)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(render(a.report,a.output))
