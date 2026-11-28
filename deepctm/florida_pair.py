"""Palm Springs/Boston data preparation and reproducible paper-method experiment."""
import argparse,json,math,sqlite3,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from .features import extract_site,split_sequences
from .capture import atomic
ROOT=Path(__file__).resolve().parents[1]


def configuration():
    from dashboard.server import sites
    cfg=json.loads((ROOT/'config/florida-palm-boston.json').read_text())
    lookup={s['id']:s for s in sites()};metadata=[lookup[i] for i in cfg['sites_west_to_east']]
    a,b=[s['reference_location'] for s in metadata]
    east=(b['lng']-a['lng'])*111320*math.cos(math.radians((a['lat']+b['lat'])/2));north=(b['lat']-a['lat'])*111320
    spacing=math.hypot(east,north);virtual=spacing-cfg['roi_length_m']
    count=math.ceil(virtual/40)
    cfg.update(cell_lengths_km=[.06]+[virtual/count/1000]*count+[.06],
               observed_nodes=[0,count+1],origin_distance_m=spacing,
               road_bearing_east_deg=math.degrees(math.atan2(north,east)),site_metadata=metadata)
    return cfg


def pair_sequences(mask,context,horizon):
    """Disjoint chronological partitions; retain explicit missing-input masks."""
    n=len(mask);cuts=[0,int(n*.6),int(n*.8),n];result={}
    for label,left,right in zip(['train','validation','test'],cuts,cuts[1:]):
        result[label]=[i for i in range(left+context,right-horizon+1)
                       if (mask[i-context:i][:,[0,-1]].mean(axis=0)>=.8).all()
                       and (mask[i:i+horizon][:,[0,-1]].mean(axis=0)>=.8).all()]
    return result


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);cfg=configuration()
    source=ROOT/'data/florida-rolling/buffer.sqlite3'
    db=sqlite3.connect(f'file:{source}?mode=ro',uri=True,timeout=30)
    # Copy only the selected bounded rows into memory, not a new raw-data archive.
    end=math.floor(time.time()/cfg['interval_s'])*cfg['interval_s'];start=end-5400
    records={}
    for site in cfg['sites_west_to_east']:
        records[site]=db.execute('SELECT session,received,payload FROM frames WHERE site=? AND received>=? AND received<? ORDER BY received',(site,start,end)).fetchall()
    db.close();values=[];masks=[];quality=[];speed_masks=[]
    for site,meta in zip(cfg['sites_west_to_east'],cfg['site_metadata']):
        rows=({'session':session,'received_at':receipt,'payload':json.loads(payload)} for session,receipt,payload in records[site])
        f,m,q=extract_site(rows,start,end,meta['preview_rotation_deg'],{**cfg,'mirror_y':meta.get('preview_mirror_y',False),'empty_bins_valid':True})
        values.append(f);masks.append(m);speed_masks.append(np.array(q['speed_observed']));quality.append({'site':site,**q,'valid_bins_by_direction':m.sum(axis=0).tolist(),'raw_rows':len(records[site])})
    arrays={};splits={};n=len(cfg['cell_lengths_km'])
    for d,direction in enumerate(['eastbound','westbound']):
        x=np.zeros((len(values[0]),n,3),np.float32);mask=np.zeros(x.shape[:2],bool)
        for node,site_index in zip([0,n-1],[0,1] if d==0 else [1,0]):
            x[:,node]=values[site_index][:,d];mask[:,node]=masks[site_index][:,d]
        fm=np.repeat(mask[:,:,None],3,axis=2)
        for node,site_index in zip([0,n-1],[0,1] if d==0 else [1,0]):fm[:,node,2] &= speed_masks[site_index][:,d]
        arrays[direction]=x;arrays[direction+'_mask']=mask;arrays[direction+'_feature_mask']=fm
        ids=pair_sequences(mask,cfg['context_steps'],cfg['horizon_steps'])
        splits[direction]={'counts':{k:len(v) for k,v in ids.items()},'target_bins':ids}
    np.savez_compressed(output/'features.npz',**arrays,start=start,end=end)
    atomic(output/'config.json',cfg);atomic(output/'quality.json',quality)
    manifest={'state':'features_ready','created_at':time.time(),'start':start,'end':end,'source':str(source.relative_to(ROOT)),
              'raw_data_copied':False,'sites':cfg['sites_west_to_east'],'splits':splits,
              'note':'Derived aggregates only; original raw trajectories remain subject to 90-minute retention. Virtual labels masked.'}
    atomic(output/'manifest.json',manifest)
    print(json.dumps({'output':str(output),'window_s':end-start,'splits':splits,'quality':[{'site':q['site'],'raw_rows':q['raw_rows'],'valid_bins':q['valid_bins_by_direction']} for q in quality]},indent=2),flush=True)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();prepare(a.output)
