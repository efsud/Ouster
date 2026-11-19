"""Prepare a reproducible candidate using training-only feature calibration."""
import argparse,json,shutil
from pathlib import Path
import numpy as np

def prepare(source,output):
    src=Path(source);out=Path(output);out.mkdir(exist_ok=False)
    data=np.load(src/'features.npz');cfg=json.loads((src/'config.json').read_text());values=[]
    for direction in ['eastbound','westbound']:
        x=data[direction];mask=data[direction+'_feature_mask'];n=int(len(x)*.6)
        values.append([x[:n,...,j][mask[:n,...,j]] for j in range(3)])
    scales=[max(floor,float(np.std(np.concatenate([v[j] for v in values])))) for j,floor in enumerate([100,5,5])]
    speeds=np.concatenate([v[2] for v in values])
    cfg.update(free_speed_kmh=float(max(50,np.quantile(speeds,.99))),balanced_features=True,data_loss_scales=scales,epochs=120)
    cfg['calibration']={'source':'first 60% of original training window only','speed_cap':'99th percentile observed speed, at least 50 km/h; empirical prior, not verified physical free-flow speed','loss_scale':'per-feature training standard deviation with floors 100 veh/h, 5 veh/km, 5 km/h'}
    (out/'config.json').write_text(json.dumps(cfg,indent=2));shutil.copy2(src/'features.npz',out/'features.npz');shutil.copy2(src/'manifest.json',out/'source-manifest.json')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();prepare(a.source,a.output)
