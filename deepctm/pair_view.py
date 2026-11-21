"""Export fixed-origin forecasts as virtual tracers; never join sensor identities."""
import argparse,json,math
from pathlib import Path
from .capture import atomic


def paths(field,lengths,interval,direction,spacing):
    import numpy as np
    # Coordinates use Palm Springs origin 0 m and Boston origin +spacing.
    sign=1 if direction=='eastbound' else -1
    origin=30 if sign==1 else spacing-30;finish=spacing-30 if sign==1 else 30
    bounds=np.cumsum(np.array(lengths)*1000);duration=len(field)*interval;out=[]
    for seed in range(0,duration,20):
        t=float(seed);pos=origin;points=[]
        while t<duration:
            lead=min(len(field)-1,int(t//interval))
            distance=pos+30 if sign==1 else spacing+30-pos
            cell=min(len(lengths)-1,max(0,int(np.searchsorted(bounds,distance,side='right'))))
            speed=max(0,float(field[lead,cell,2])/3.6)
            if not math.isfinite(speed):break
            points.append([round(t,3),round(pos,3),round(speed,3)])
            dt=min(1.,duration-t)
            if speed>0:dt=min(dt,abs(finish-pos)/speed)
            if dt<1e-8:break
            pos+=sign*speed*dt;t+=dt
            if sign*(finish-pos)<=1e-7:
                points.append([round(t,3),round(finish,3),round(speed,3)]);break
        if len(points)>1:out.append({'seed_offset_s':seed,'points':points,'completed':abs(pos-finish)<1e-6})
    return out


def export(directory):
    import numpy as np
    directory=Path(directory);report=json.loads((directory/'report.json').read_text());cfg=json.loads((directory/'config.json').read_text())
    result={'state':report['state'],'start':report['start'],'end':report['end'],'config':cfg,'directions':{},
            'note':'Fixed-origin forecasts using only earlier context. Virtual tracers are not tracked vehicles; dashed colors are predicted speed.'}
    for direction,summary in report['directions'].items():
        if summary['state']!='trained_provisional':result['directions'][direction]=summary;continue
        raw=np.load(directory/(direction+'-heldout.npz'));lengths=cfg['cell_lengths_km'] if direction=='eastbound' else cfg['cell_lengths_km'][::-1]
        runs=[]
        for j,index in enumerate(raw['origin_bins']):
            runs.append({'origin':report['start']+int(index)*cfg['interval_s'],
                         'models':{name:paths(raw[key][j],lengths,cfg['interval_s'],direction,cfg['origin_distance_m']) for name,key in [('DeepCTM','prediction'),('Persistence','persistence'),('Pure CTM','pure_ctm')]}})
        result['directions'][direction]={'state':summary['state'],'counts':summary['counts'],'best_epoch':summary['best_epoch'],
            'metrics':{name:summary[key] for name,key in [('DeepCTM','deepctm'),('Persistence','persistence'),('Pure CTM','pure_ctm')]},
            'mean_mass_residual_vehicles':summary['mean_mass_residual_vehicles'],'runs':runs}
    atomic(directory/'viewer.json',result)
    atomic(Path('data/florida-pair/current.json'),{'experiment':directory.name})
    return result


def read():
    root=Path(__file__).resolve().parents[1]/'data/florida-pair'
    name=json.loads((root/'current.json').read_text())['experiment'];folder=(root/name).resolve()
    if folder.parent!=root.resolve():raise ValueError('Invalid experiment')
    return json.loads((folder/'viewer.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--experiment',required=True);a=p.parse_args();export(a.experiment)
