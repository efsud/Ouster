"""Illustrate median/worst accepted recorded masks under the published local policy.

Selection by error is declared; these examples do not establish aggregate accuracy
or cross-sensor identity. No fitting and no raw data archive is created.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from .archive_extension import cases
from .corridor_campaign import subset,earlier_ids,atomic
from .reconstruction_layers import prediction,finch_endpoint_config
from .reconstruction_study import metrics

def run(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root=Path(__file__).resolve().parents[1];output=Path(output)
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained');audit={}
    for row,region in enumerate(('florida','finch')):
        raw=(root/f'data/{region}-rolling/snapshot.json').read_bytes();s=json.loads(raw)
        folder=root/('data/reconstruction/finch' if region=='finch' else 'data/reconstruction/word-v1-collection')
        status=json.loads((folder/'status.json').read_text());report=json.loads(Path(status['report']).read_text())
        config=json.loads((root/f'config/reconstruction/{region}-endpoint-speed.json').read_text())
        if region=='finch':config=finch_endpoint_config(json.loads((folder/'policy.json').read_text()),config)
        selected=subset(s,2730,3600,earlier_ids(s,2700));records=[]
        for rank,site,tr,gap,(a,b,truth) in cases(selected,'test',5):
            policy=config.get('parameters') if site['id'] not in config.get('excluded_sites',[]) else None
            result=prediction(a,b,report,exact_join=True,endpoint_policy=policy)
            if result is None:continue
            p=np.asarray(result);m=metrics(p,truth,report['calibration']['parameters'])
            records.append((m['mae_m'],rank,site,tr,gap,a,b,truth,p,m))
        records.sort(key=lambda r:(r[0],r[1]));audit[region]={'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'window':[s['start'],s['end']],'accepted':len(records),'examples':[]}
        for col,label in enumerate(('Median-error accepted mask','Worst-error accepted mask')):
            ax=axes[row,col]
            if not records:ax.text(.5,.5,'No eligible accepted masks',ha='center',transform=ax.transAxes);continue
            rec=records[len(records)//2 if col==0 else -1];error,rank,site,tr,gap,a,b,truth,p,m=rec
            sign=1 if tr['direction']=='eastbound' else -1
            points=np.array(tr['points']);points[:,1]*=sign
            visible=(points[:,0]>=a['t']-4)&(points[:,0]<=b['t']+4)&((points[:,0]<=a['t'])|(points[:,0]>=b['t']))
            ax.scatter(points[visible,0]-a['t'],points[visible,1]-a['x'],s=10,c='#235a8b',label='Visible observations')
            ax.plot(truth[:,0]-a['t'],truth[:,1]-a['x'],color='#222222',lw=1.8,label='Hidden actual observations')
            ax.plot(p[:,0]-a['t'],p[:,1]-a['x'],'--',color='#d45c1d',lw=2,label='Estimated gap')
            ax.axvspan(0,b['t']-a['t'],color='#dce5ed',alpha=.35)
            ax.set_title(f"{region.title()} · {label}\n{site.get('name',site['id'])} · {gap}s · MAE {error:.2f}m",fontsize=10)
            ax.set_xlabel('Seconds from start of hidden interval');ax.set_ylabel('Distance along travel direction (m)');ax.grid(alpha=.2)
            if row==0 and col==0:ax.legend(fontsize=8)
            audit[region]['examples'].append({'selection':label,'identity_hash':rank,'site':site['id'],'gap_s':gap,'metrics':m})
    fig.suptitle('Recorded-data masking: published local reconstruction\nVisible flanks supplied; hidden observations used only for scoring',fontsize=13)
    fig.supxlabel('Last-quarter examples exclude earlier-hour IDs. Provisional road alignment; no cross-sensor identity validation.',fontsize=9)
    output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(output,dpi=160);plt.close(fig)
    atomic(output.with_suffix('.json'),audit)
    print({r:{'accepted':v['accepted'],'examples':[(x['gap_s'],round(x['metrics']['mae_m'],3)) for x in v['examples']]} for r,v in audit.items()})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
