"""Document-derived, explicitly hypothetical Finch movement groups."""
import json,time,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=ROOT/'data/finch-group-evidence.json'
CONFIG=ROOT/'config/finch_signal_groups.json'
VALID={'GREEN','YELLOW','RED'}

def evaluate_history(rows,labels):
    # Never combine evidence across gaps or reconnects.
    segment=[]
    for row in rows:
        if segment and (row['session']!=segment[-1]['session'] or row['receipt']-segment[-1]['receipt']>5):segment=[]
        segment.append(row)
    complete=[r for r in segment if all(r['phases'].get(n) in VALID for n in labels)]
    span=complete[-1]['receipt']-complete[0]['receipt'] if len(complete)>1 else 0
    agreement=sum(len({r['phases'][n] for n in labels})==1 for r in complete)/len(complete) if complete else 0
    cycles={n:0 for n in labels};previous={}
    for r in segment:
        for n in labels:
            v=r['phases'].get(n)
            if v=='GREEN' and previous.get(n) in {'RED','YELLOW'}:cycles[n]+=1
            previous[n]=v
    enough=span>=240 and len(complete)>=200 and len(complete)>=.9*len(segment) and min(cycles.values(),default=0)>=2
    return dict(eligible=bool(enough and agreement==1),samples=len(complete),span_s=round(span),agreement=round(agreement,4),green_onsets=cycles,
        reason='Observed matching states over repeated cycles' if enough and agreement==1 else 'Phases differ; do not merge' if complete and agreement<1 else 'More continuous cycle evidence needed')

def summarize(raw):
    config=json.loads(CONFIG.read_text());out={}
    for site,groups in config['sites'].items():
        rows=raw.get('sites',{}).get(site,[]);history={}
        for g in groups:
            labels=g['labels'];history[','.join(labels)]=evaluate_history(rows,labels)
            for n in labels:history[n]=evaluate_history(rows,[n])
        out[site]={'session':rows[-1]['session'] if rows else None,'last_receipt':rows[-1]['receipt'] if rows else None,'history':history}
    return {'updated_at':time.time(),'sites':out}

def snapshot(site,phase_snapshot,evidence,estimates,session=None):
    if site.get('region')!='Toronto':return []
    config=json.loads(CONFIG.read_text());proof=evidence.get('sites',{}).get(site['id'],{})
    fresh=0<=time.time()-evidence.get('updated_at',0)<=15 and proof.get('session')==session
    if estimates.get('session')!=session or not 0<=time.time()-(estimates.get('last_receipt') or 0)<=5 or not 0<=time.time()-estimates.get('updated_at',0)<=15:estimates={}
    phase_by={p['phase']:p for p in phase_snapshot['phases']};result=[]
    for g in config['sites'].get(site['id'],[]):
        joint=proof.get('history',{}).get(','.join(g['labels']),{})
        # Incompatible time histories split a proposed duplicate group.
        groups=[g['labels']] if joint.get('eligible') else [[n] for n in g['labels']]
        for labels in groups:
            history=proof.get('history',{}).get(','.join(labels),{})
            statuses=[phase_by.get(n,{}).get('status','UNKNOWN') for n in labels]
            eligible=history.get('eligible',False) and fresh
            colour=statuses[0] if eligible and len(set(statuses))==1 and statuses[0] in VALID else 'UNKNOWN'
            movements=[a['movement'] for a in g['associations'] if 'G' in a['statuses']]
            # Direct vehicle evidence can contradict this assumed label join.
            conflicts=[];support=[]
            for direction,d in estimates.get('directions',{}).items():
                movement={'E':'WE','W':'EW','N':'SN','S':'NS'}[direction]
                for c in d.get('candidates',[]):
                    if c['phase'] in labels and c.get('releases',0)>=8 and c.get('release_cycles',0)>=3 and c.get('green_fraction',0)>=.8 and c.get('onset_fraction',0)>=.5:
                        (support if movement in movements else conflicts).append(movement)
            if conflicts:colour='UNKNOWN'
            through=[m for m in movements if m in ['WE','EW','SN','NS']]
            destination=(through or movements or ['??'])[0][-1]
            result.append(dict(labels=labels,movements=movements,status=colour,estimated=True,
                evidence=history,proposed_group=g['labels'],group_evidence=joint,
                show_on_map=bool(eligible and support and not conflicts and 'unresolved' not in site.get('preview_alignment_note','').lower()),destination=destination,
                flow_support=sorted(set(support)),flow_conflicts=sorted(set(conflicts)),
                placement_reason='Alignment unresolved' if 'unresolved' in site.get('preview_alignment_note','').lower() else 'Conflicting vehicle directions' if conflicts else 'No qualifying vehicle support' if not support else history.get('reason','Waiting for observation'),
                note='DOC EST: assumes phase_label = live phaseNumber. Schematic movement location, not a surveyed physical light.'))
    return result


def main():
    import sqlite3
    seed=ROOT/'data/finch-phase-group-observation.json'
    raw=json.loads(seed.read_text()) if seed.exists() else {'sites':{}}
    db=sqlite3.connect(f'file:{ROOT}/data/finch-live.sqlite3?mode=ro',uri=True);lastsave=0
    while True:
        now=time.time()
        for site,payload in db.execute('select site,payload from live_signal_state'):
            st=json.loads(payload)
            if not st.get('initialized') or not 0<=now-st.get('last_receipt',0)<=3:continue
            phases={n:p['status'] for n,p in st.get('phases',{}).items() if p['status'] in VALID and 0<=now-p['received_at']<=180}
            rows=raw['sites'].setdefault(site,[])
            rows.append(dict(receipt=now,session=st.get('session'),phases=phases))
            raw['sites'][site]=[r for r in rows if now-r['receipt']<=900]
        if now-lastsave>=5:
            temp=EVIDENCE.with_suffix('.tmp');temp.write_text(json.dumps(summarize(raw)));temp.replace(EVIDENCE);lastsave=now
        time.sleep(1)

if __name__=='__main__':main()
