"""Render transparent spatial-mask validation, separate from temporal-gap tests."""
import argparse,json,html
from pathlib import Path

def render(source,output):
    r=json.loads(Path(source).read_text());rows=[]
    for width in [20,50,100]:
        groups=[g for g in r['groups'] if g['width_m']==width];n=sum(g['common_cases']['count'] for g in groups)
        errors=[]
        for method in ['linear','hermite','monotone','queue']:
            errors.append(sum(g['common_cases']['count']*(g['common_cases']['methods'][method]['mae_m'] or 0) for g in groups)/max(1,n))
        matches=sum(g['association_missing_arrivals']['matched'] for g in groups);correct=sum(g['association_missing_arrivals']['correct'] for g in groups)
        rows.append([str(width),f"{n}/{sum(g['eligible'] for g in groups)}",*(f'{e:.2f}' for e in errors),f'{correct}/{matches}',f'{100*correct/matches:.1f}%' if matches else 'Unavailable'])
    heads=['Hidden road length (m)','Common accepted / eligible','Linear MAE (m)','Hermite MAE (m)','Monotone MAE (m)','Queue candidate MAE (m)','Correct matches with missing arrivals','Match precision']
    table='<table><tr>'+''.join('<th>'+x+'</th>' for x in heads)+'</tr>'+''.join('<tr>'+''.join('<td>'+x+'</td>' for x in row)+'</tr>' for row in rows)+'</table>'
    content='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Florida spatial gap reconstruction</title><style>body{font:16px/1.6 system-ui;max-width:1250px;margin:24px auto;padding:20px;color:#203746}table{border-collapse:collapse;width:100%}th,td{padding:8px;border:1px solid #ccd6dc;text-align:left;font-size:14px}th{background:#edf3f6}img{width:100%;height:auto}a{color:#0069af}</style><h1>Florida: reconstructing the red spatial bands</h1><p><a href="/florida_rolling.html">Open Florida trajectories</a> · <a href="/">Dashboard</a></p><p>The target is the road between observed sections, not the green-marked interruptions within a sensor's observations. The Florida chart now has a separate spatial-estimates switch; the local time-gap layer starts off.</p><h2>Validation on road where trajectories are known</h2><p>Entire 20, 50 and 100 m road strips were hidden. Five visible samples on either side supply endpoint position and speed; the hidden interior is used only for evaluation. All methods below are compared on exactly the same accepted cases. No coefficients were fitted on this sample. The queue candidate was designed after reviewing failures, so its scores are exploratory development results, not an untouched test. Samples come from newly recorded Florida data on 20 November 2026.</p>'''+table+'''<p>MAE is longitudinal position error averaged per reconstructed gap. Different strip widths reuse tracks, so rows are not independent. Matching precision is a separate test: identities are hidden and a quarter of arrival fragments are removed. Many candidates are intentionally left unmatched; precision is not the percentage of all trajectories reconstructed.</p><img src="/spatial-validation.png" alt="Hidden observed positions compared with spatial reconstructions"><h2>Stop-and-go candidate</h2><p>An additional brake–wait–accelerate hypothesis uses assumed 3 m/s² braking/acceleration, an entry-side stop, and visible boundary speeds. It falls back to the monotone curve when this stop is incompatible with distance or time. On six common 100 m stop-and-go cases, average position error changed from 10.28 m (monotone) to 7.25 m. On three 50 m cases it changed from 3.89 m to 0.81 m. These tiny subsets do not establish general accuracy; the queue candidate is not enabled in the rolling chart. Further independent cases are needed.</p><h2>How the red bands are filled</h2><p>For each adjacent Florida pair and travel direction, use actual departing and arriving fragment ends near the sensor coverage boundaries. Score plausible connections by travel time, visible speed and object class. Keep one-to-one matches separated from alternative candidates. Draw a monotone cubic curve constrained by its endpoints; speed and acceleration checks reject impossible curves. Dashed segments take the same speed colors as observations. There are no arbitrary virtual vehicle seeds.</p><p><strong>These are estimated associations, not verified identities.</strong> Same-sensor masking does not test offsets between sensor clocks, field alignment or real turning movements. Plausible-looking curves can still connect the wrong vehicles. Stopping inside the blind band is not uniquely determined by the two visible ends. Unsupported candidates remain blank.</p><h2>Relationship to the papers</h2><p>DeepCTM estimates aggregate states in observed and virtual road cells. LightSim supplies conservation-based traffic evolution and queue dynamics. Neither provides cross-sensor vehicle identity matching. The existing DeepCTM experiment was therefore kept separate rather than labeling these curves DeepCTM predictions. For this retrospective trajectory task, endpoint motion reconstruction is the tested alternative.</p><p>Reference: <a href="https://arxiv.org/abs/2602.21852">LightSim</a>; supplied DeepCTM paper, DOI 10.1007/978-3-032-38410-2_54.</p><p>Known limitations: sample size and one recording period; no intermediate-road ground truth; ambiguous associations excluded; no verified signals, lane assignments or clock offsets. These results are provisional, not field validation.</p></html>'''
    Path(output).write_text(content)
    return heads,rows

def plot(source,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    r=json.loads(Path(source).read_text());fig,axes=plt.subplots(2,3,figsize=(14,7),constrained_layout=True)
    for col,width in enumerate([20,50,100]):
        ex=sorted([x for x in r['examples'] if x['width_m']==width],key=lambda x:x['mae_m'])
        for row in [0,1]:
            ax=axes[row,col]
            if not ex:ax.text(.5,.5,'Insufficient data');continue
            e=ex[len(ex)//2] if row==0 else ex[-1];truth=np.array(e['observed']);pred=np.array(e['estimated']);t0=pred[0,0];x0=pred[0,1]
            ax.plot(truth[:,0]-t0,truth[:,1]-x0,color='#263746',lw=2,label='Hidden actual trajectory')
            ax.plot(pred[:,0]-t0,pred[:,1]-x0,'--',color='#007fb0',lw=2,label='Spatial estimate')
            ax.scatter([0,pred[-1,0]-t0],[0,pred[-1,1]-x0],s=25,color='#007fb0',zorder=4,label='Visible boundaries')
            ax.set_title(f"{width} m strip · {'representative saved example' if row==0 else 'worst saved case'}\n{e['site']} · {e['mae_m']:.2f} m MAE",fontsize=10)
            ax.set_xlabel('Time from departure boundary (s)');ax.set_ylabel('Along-road displacement (m)');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8);fig.suptitle('Spatial masking: estimate the missing road section and compare with withheld observations')
    fig.savefig(output,dpi=150);plt.close(fig)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--html',required=True);p.add_argument('--image',required=True);a=p.parse_args();render(a.source,a.html);plot(a.source,a.image)
