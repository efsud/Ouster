"""Render the saved experimental Florida reconstruction comparison."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]
folder=root/'data/reconstruction/word-v1-collection'
r=json.loads((folder/'integrated-validation.json').read_text())
keys=['test_local','test_outage','test_spatial'];labels=['Local object gap','Recording outage','Spatial blind band\n(proxy only)']
a=[r['results'][k]['current']['common']['mae_m'] for k in keys]
b=[r['results'][k]['integrated']['common']['mae_m'] for k in keys]
fig,axes=plt.subplots(1,2,figsize=(11,4.8));x=np.arange(3)
axes[0].bar(x-.18,a,.36,label='Current',color='#566777');axes[0].bar(x+.18,b,.36,label='Integrated experiment',color='#317bc1')
axes[0].set_xticks(x,labels);axes[0].set_ylabel('Mean position error (m; lower is better)');axes[0].legend(frameon=False)
for i,k in enumerate(keys):axes[0].text(i,max(a[i],b[i])+.03,f"n={r['results'][k]['current']['common']['n']}",ha='center',fontsize=9)
axes[0].set_ylim(0,max(a+b)*1.25)
g=np.array([r['paired_gain'][k]['mean_improvement_m'] for k in keys]);ci=np.array([r['paired_gain'][k]['bootstrap95_m'] for k in keys])
axes[1].errorbar(g,x,xerr=[g-ci[:,0],ci[:,1]-g],fmt='o',capsize=4,color='#317bc1');axes[1].axvline(0,color='#8d4343',linestyle='--');axes[1].set_yticks(x,labels);axes[1].invert_yaxis();axes[1].set_xlabel('Mean error reduction (m; positive is better)');axes[1].set_title('Exploratory 95% paired bootstrap intervals',fontsize=10)
for ax in axes:ax.spines[['top','right']].set_visible(False)
fig.suptitle('Florida: CTM–Newell–signal reconstruction experiment',fontsize=14)
fig.text(.03,.025,'Provisional geometry and estimated signal mappings. Small correlated samples; no real between-sensor ground truth.\nNo scored test case had all three priors available. Current dashboard model remains deployed.',fontsize=9,color='#454545')
fig.tight_layout(rect=[0,.12,1,.93]);fig.savefig(folder/'integrated-comparison.png',dpi=160);plt.close(fig)
