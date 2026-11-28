"""Standalone figure for the frozen archival experiment."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
folder=Path('data/reconstruction/archive-extension/evaluation');r=json.loads((folder/'report.json').read_text());methods=r['results']['test'];gaps=r['gap_seconds']
fig,axes=plt.subplots(1,2,figsize=(13,5.4));colors=['#526777','#168d99','#c06a29']
for i,(name,row) in enumerate(methods.items()):
 x=np.arange(len(gaps))+(i-(len(methods)-1)/2)*.24;y=[row['by_gap'][str(g)].get('mae_m',np.nan) for g in gaps]
 axes[0].bar(x,y,.23,label=('CTM + available leader' if name=='integrated' else name),color=colors[i]);
 for xx,yy,g in zip(x,y,gaps):
  if np.isfinite(yy):axes[0].text(xx,yy+.07,f"n={row['by_gap'][str(g)]['n']}",ha='center',fontsize=8)
axes[0].set(xticks=np.arange(len(gaps)),xticklabels=[f'{g} s' for g in gaps],ylabel='Mean absolute position error (m)',title='Hidden trajectories · afternoon test');axes[0].legend(fontsize=8)
rows=[]
for scenario,ms in r['association_test'].items():
 for name,m in ms.items():rows.append((scenario+'\n'+name,m))
x=np.arange(len(rows));axes[1].bar(x,[m['correct'] for _,m in rows],color='#168d99',label='Correct');axes[1].bar(x,[m['false'] for _,m in rows],bottom=[m['correct'] for _,m in rows],color='#bd4938',label='Wrong')
for i,(_,m) in enumerate(rows):axes[1].text(i,m['matched']+3,f"{m['correct']}/{m['eligible']} correct\n{m['false']} wrong",ha='center',fontsize=9)
axes[1].set(xticks=x,xticklabels=[n for n,_ in rows],ylabel='Matched pairs',title='Identity-blind spatial masks · proxy');axes[1].legend(fontsize=8)
for ax in axes:ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.margins(y=.2)
fig.suptitle('Florida: additional archival validation — November 13',fontsize=15)
fig.text(.02,.015,'65 common accepted gaps of 168 attempted; current accepted 66, integrated 67. Each duration has a different accepted cohort.\nAM train/select; PM test. No cross-sensor identity truth or verified signal replay. Correlated masks; not field validation.',fontsize=9)
fig.tight_layout(rect=(0,.09,1,.93));fig.savefig(folder/'comparison.png',dpi=170)
