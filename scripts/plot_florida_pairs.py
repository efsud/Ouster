import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
folder=Path('data/reconstruction/all-florida');r=json.loads((folder/'current-pair-comparison.json').read_text());a=json.loads((folder/'pair-audit.json').read_text())
fig,axs=plt.subplots(1,2,figsize=(15,8));ys=np.arange(12)
old=r['results']['current'];new=r['results']['screened'];labels=[x['names'][0].split(' &')[0]+' → '+x['names'][1].split(' &')[0]+' · '+('EB' if x['direction']=='eastbound' else 'WB') for x in old]
axs[0].barh(ys-.16,[x['displayed'] for x in old],.3,color='#627787',label='Previous');axs[0].barh(ys+.16,[x['displayed'] for x in new],.3,color='#168d99',label='Screened before matching')
for y,x in zip(ys,new):axs[0].text(x['displayed']+1,y+.16,str(x['displayed']),va='center',fontsize=8)
axs[0].set(yticks=ys,yticklabels=labels,xlabel='Estimated connections · not verified identities',title='All adjacent pairs · same recorded window');axs[0].invert_yaxis();axs[0].legend(fontsize=8)
sites=a['site_validation'];ys=np.arange(len(sites));axs[1].barh(ys-.16,[s['methods']['strict']['accepted'] for s in sites],.3,color='#627787',label='Strict')
axs[1].barh(ys+.16,[s['methods']['noise_0.1']['accepted'] for s in sites],.3,color=['#168d99' if s['correction_enabled'] else '#d39a4b' for s in sites],label='Correction in masked test')
axs[1].set(yticks=ys,yticklabels=[s['name'].split(' &')[0]+(' (withheld)' if not s['correction_enabled'] else '') for s in sites],xlabel='Accepted hidden gaps · different denominators per site',title='Local endpoint correction · site audit');axs[1].invert_yaxis();axs[1].legend(fontsize=8)
for ax in axs:ax.spines[['top','right']].set_visible(False);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True);ax.margins(x=.15)
fig.suptitle('Florida · Boston–Palm Springs and the whole corridor',fontsize=15)
fig.text(.02,.025,'Left: hypotheses in one observed hour; all previous accepted connections retained. Right: saved endpoint-mask validation.\nHattaway correction withheld because new-case position error averaged 5.93 m. Unmatched identity/turning conflicts remain blank.',fontsize=10)
fig.tight_layout(rect=(0,.09,1,.94));fig.savefig(folder/'all-pairs-comparison.png',dpi=160)
