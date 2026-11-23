"""Show coverage separately from errors on newly admitted held-out gaps."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
folder=Path('data/reconstruction/endpoint-speed/evaluation');r=json.loads((folder/'report.json').read_text());selected=r['selected'];gaps=r['gap_seconds']
fig,ax=plt.subplots(1,2,figsize=(12,5.2));x=np.arange(len(gaps))
for j,name in enumerate(dict.fromkeys(['strict',selected])):
 row=r['test'][name];counts=[row['by_gap'][str(g)]['accepted'] for g in gaps];pos=x+(j-.5)*.32
 ax[0].bar(pos,counts,.3,label=name,color=['#526777','#168d99'][j])
 for xx,n,g in zip(pos,counts,gaps):ax[0].text(xx,n+.5,f"{n}/{row['by_gap'][str(g)]['eligible']}",ha='center',fontsize=9)
ax[0].set(xticks=x,xticklabels=[f'{g}s' for g in gaps],ylabel='Accepted masked gaps',title='Coverage on untouched 17:00–18:00 period');ax[0].legend()
y=[r['test'][selected]['by_gap'][str(g)]['newly_accepted'].get('mae_m',np.nan) for g in gaps]
ax[1].bar(x,y,color='#168d99');ax[1].set(xticks=x,xticklabels=[f'{g}s' for g in gaps],ylabel='Position MAE (m)',title='Error on newly accepted gaps only')
for xx,yy,g in zip(x,y,gaps):
 if np.isfinite(yy):ax[1].text(xx,yy+.03,f"n={r['test'][selected]['by_gap'][str(g)]['newly_accepted']['n']}",ha='center')
for a in ax:a.spines[['top','right']].set_visible(False);a.grid(axis='y',alpha=.2);a.set_axisbelow(True);a.margins(y=.2)
fig.suptitle('Florida · visible-context endpoint-speed correction',fontsize=15)
fig.text(.02,.02,'Selection on AM only; complete earlier-PM IDs excluded. Old successful estimates are unchanged.\nRetrospective local masks; repeated tracks, provisional geometry, no cross-sensor identity validation.',fontsize=9)
fig.tight_layout(rect=(0,.09,1,.93));fig.savefig(folder/'comparison.png',dpi=170)
