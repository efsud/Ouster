"""Intersection drill-down for the seven Tier-1 KPIs in the supplied paper."""
from .analytics import METRICS

DEFINITIONS={
 'control_delay':('Mean [(stop-line arrival − entry) − approach length / free-flow speed]', ['Observed entry and stop-line arrival','Verified approach length and free-flow speed']),
 'stopped_delay':('Mean integral of speed ≤ stopped threshold over complete entry-to-exit traversals', ['Complete entry-to-exit trajectories','Valid speeds and a defined 2–3 m/s stopped threshold']),
 'queue_p95':('95th percentile of visible, lane-consistent queue distance upstream of the stop line', ['Verified stop line, lane polygons and queue region','Queue membership, spacing and visibility']),
 'aog':('100 × arrivals during effective green / all stop-line arrivals', ['Stop-line arrivals with approximately 3 m tolerance','Verified phase mapping and synchronized signal clocks']),
 'split_failure':('100 × complete cycles with residual queue at green end / complete observed cycles', ['Verified queue membership and visibility','Effective-green end times and complete cycles']),
 'volume':('Unique directional approach entries × 3600 / window duration in seconds', ['Verified entry/count line and direction','Deduplicated physical vehicle trajectories']),
 'discharge':('Queued departures during green × 3600 / effective-green seconds / lanes', ['Stopped-to-moving stop-line departures during green','Verified phase mapping, green duration and lane count']),
}

def summary(store,site,approach=None,window=None):
    recorded=store.recorded_summary(site['id'])
    # Values must be backed by saved observations, never the learning dataset.
    rows=[r for r in store.history(site=site['id'],limit=-1) if r['source'] in {'sdk-derived','annotated-import'}]
    rows.sort(key=lambda r:(r['end'],r['start'],r['approach'],r['source']),reverse=True)
    approaches=sorted({r['approach'] for r in rows})
    chosen=approach if approach in approaches else approaches[0] if approaches else None
    candidates=[r for r in rows if r['approach']==chosen]
    def key(r):return f"{r['start']}:{r['end']}:{r['source']}"
    selected=next((r for r in candidates if key(r)==window),None) if window else candidates[0] if candidates else None
    items=[]
    for name,(label,unit) in METRICS.items():
        formula,requirements=DEFINITIONS[name]
        value=selected['values'].get(name) if selected else None
        reasons=[]
        if not selected:
            if not recorded['events']:reasons.append('No stored sensor events for this intersection.')
            else:reasons.append('Stored raw events exist, but no observation-derived KPI window has been calculated.')
            if recorded.get('status_counts',{}).get('quarantined'):reasons.append('Recorded timestamps are quarantined; confirm their timezone before processing.')
            if not site.get('scene',{}).get('verified'):reasons.append('Verified scene geometry and approach annotations are missing.')
            reasons.extend(requirements)
        elif value is None:
            reasons=['The saved window does not contain the required observations.']+requirements
        if selected and name=='discharge' and selected['end']-selected['start']>300:
            value=None;reasons=['The paper specifies discharge rate for real-time windows only.']
        items.append({'id':name,'name':label,'unit':unit,'value':value,'status':'provisional' if value is not None else 'unavailable','formula':formula,'requirements':requirements,'reasons':reasons,'cadence':'Real-time only' if name=='discharge' else 'Real-time / daily'})
    return {'site':site['id'],'name':site['name'],'recorded':recorded,'approaches':approaches,'approach':chosen,
        'windows':[{'key':key(r),'start':r['start'],'end':r['end'],'source':r['source']} for r in candidates],
        'selected_window':{k:selected[k] for k in ['start','end','source','quality','provenance'] if k in selected} if selected else None,
        'metrics':items,'rules':{'minimum_traversals':15,'minimum_coverage':.8,'maximum_gap_s':3},
        'note':'Approach-specific saved results; never averages of approach percentiles or rates. Passing input checks does not establish field validity.'}
