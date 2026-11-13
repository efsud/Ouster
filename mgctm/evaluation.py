"""Compare like metrics at independently observed locations and bin ends."""
from collections import defaultdict
import math
import numpy as np

CONTINUOUS={'count','queue_m','vehicles','speed_kmh'}


def match(predictions, observations):
    pairs=[]
    for o in observations:
        key=(o['target'],o['metric'])
        try:
            y=predictions[o['end_s']][key]
        except KeyError as exc:
            raise ValueError(f"Observation target, metric or time absent: {key}, {o['end_s']}") from exc
        pairs.append({**o,'predicted':y})
    return pairs


def summarize(rows):
    buckets=defaultdict(list)
    for row in rows:
        buckets[row['metric']].append((row['value'],row['predicted']))
    out={}
    for metric, pairs in sorted(buckets.items()):
        obs,pred=np.asarray(pairs).T
        if metric=='spillback':
            if not set(obs)<= {0,1}:
                raise ValueError('Observed spillback must be binary')
            tp=int(sum((obs==1)&(pred==1)));fp=int(sum((obs==0)&(pred==1)));fn=int(sum((obs==1)&(pred==0)))
            out[metric]=dict(n=len(obs),tp=tp,fp=fp,fn=fn,
                precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
        elif metric in CONTINUOUS:
            err=pred-obs
            out[metric]=dict(n=len(obs),mae=float(np.mean(abs(err))),rmse=float(np.sqrt(np.mean(err**2))),
                             bias=float(np.mean(err)))
        else:
            raise ValueError(f'Unsupported metric: {metric}')
    return out


def day_loss(rows, scales):
    values=defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r['metric'] in scales:
            values[r['date'],r['peak']][r['metric']].append(abs(r['predicted']-r['value'])/scales[r['metric']])
    if not values or any(set(v)!=set(scales) for v in values.values()):
        raise ValueError('Every evaluated date/peak needs all declared objective metrics')
    return {key:float(np.mean([np.mean(x) for x in v.values()])) for key,v in values.items()}


def paired_summary(reference, candidate, seed=42):
    if set(reference)!=set(candidate) or not reference:
        raise ValueError('Paired days must be identical')
    d=np.array([candidate[k]-reference[k] for k in sorted(reference)])
    result=dict(days=len(d),mean_delta=float(d.mean()),ci95=None)
    if len(d)>=5:
        rng=np.random.default_rng(seed)
        means=rng.choice(d,size=(3000,len(d)),replace=True).mean(1)
        result['ci95']=np.quantile(means,[.025,.975]).tolist()
    return result


def select(losses, complexity):
    if not losses:
        raise ValueError('No validation results')
    best=min(losses,key=lambda k:np.mean(list(losses[k].values())))
    v=np.array(list(losses[best].values()))
    if len(v)<2:
        return dict(selected=None,best_point_estimate=best,reason='Need independent validation dates')
    threshold=float(v.mean()+v.std(ddof=1)/math.sqrt(len(v)))
    eligible=[k for k in losses if np.mean(list(losses[k].values()))<=threshold]
    return dict(selected=min(eligible,key=lambda k:(complexity[k],np.mean(list(losses[k].values())),k)),
                best_point_estimate=best,one_se_threshold=threshold)
