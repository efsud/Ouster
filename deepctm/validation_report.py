"""Publish a static local report from saved validation results."""
import argparse,json,html
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

def render(gaps,original,candidate,output):
    r=json.loads(Path(gaps).read_text());old=json.loads(Path(original).read_text());new=json.loads(Path(candidate).read_text());rows=[];md=[]
    for region,d in r['regions'].items():
        end=datetime.fromtimestamp(d['source_end'],ZoneInfo('America/Toronto')).isoformat(timespec='seconds')
        md.append(f'{region}: one-hour source window ending {end}.')
        for duration in [5,10,20,30]:
            gs=[g for g in d['groups'] if g['requested_seconds']==duration];n=sum(g['accepted'] for g in gs);total=sum(g['eligible'] for g in gs);moving=sum(g['moving_accepted'] for g in gs)
            avg=lambda key:sum(g['accepted']*(g[key] or 0) for g in gs)/n if n else float('nan')
            moving_error=sum(g['moving_accepted']*(g['moving_mae_m'] or 0) for g in gs)/moving if moving else float('nan')
            worst=max((g['worst_case_mae_m'] or 0 for g in gs),default=0)
            rows.append([region,str(duration),f'{n:,} / {total:,}',f'{avg("mae_m"):.2f}',f'{avg("linear_mae_m"):.2f}',f'{moving_error:.2f} ({moving:,})',f'{worst:.2f}'])
    def table(headers,rows):
        return '<table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
    headers=['Corridor','Gap target (s)','Accepted / eligible','Mean gap MAE (m)','Linear MAE, same cases (m)','Moving-gap MAE (m), n','Worst gap MAE (m)']
    models=[]
    for direction,n in new['directions'].items():
        o=old['directions'][direction]
        for lead in ['10','60','120']:
            models.append([direction,lead,str(n['n_windows']),f'{o["deepctm"][lead]["speed_kmh"]["rmse"]:.2f}',f'{n["deepctm"][lead]["speed_kmh"]["rmse"]:.2f}',f'{n["persistence"][lead]["speed_kmh"]["rmse"]:.2f}',f'{n["pure_ctm"][lead]["speed_kmh"]["rmse"]:.2f}'])
    mh=['Direction','Lead (s)','Independent windows','Original DeepCTM','Revised DeepCTM','Persistence','Revised pure CTM']
    body='<h1>Trajectory reconstruction validation</h1><p><a href="/">Back to dashboard</a> · Saved experiment, 19 November 2026</p>'
    body+='<h2>Hidden observations versus reconstructed trajectories</h2><p>We removed interior observations from continuous local vehicle tracks, kept five visible samples on either side, and reconstructed without supplying hidden points to the estimator. Gaps target 5, 10, 20 and 30 seconds; frame sampling makes actual durations slightly shorter. No intersections or vehicle identities are joined.</p>'
    body+='<p>'+html.escape(' '.join(md))+'</p>'+table(headers,rows)
    body+='<p>MAE is longitudinal mean absolute position error, averaged equally per accepted gap. Moving gaps have more than 5 m of withheld position range. Linear interpolation is scored on exactly the same accepted cases. Cases across durations overlap and are not independent. Stopped vehicles can lower overall errors; rejected gaps remain unavailable. The same thresholds were used without tuning on these cases.</p>'
    body+='<p><strong>Important failure:</strong> unseen stopping and acceleration can produce large errors even when endpoint checks pass. Low average error does not make every dashed line accurate. Real occlusions may differ from artificially hidden data. Provisional alignment and sensor timing also limit accuracy claims.</p><img src="/trajectory-validation.png" alt="Observed versus estimated trajectories, including worst cases" style="width:100%;height:auto">'
    body+='<h2>DeepCTM model comparison</h2><p>The candidate uses a training-only empirical speed cap of 69.50 km/h instead of 50 km/h, balanced per-feature loss scales, and 120 training epochs. Checkpoints were selected by validation error only. The table is speed RMSE in km/h on 17 later, nonoverlapping context-plus-forecast windows per direction, entirely after the training experiment. No optimization used this later period.</p>'+table(mh,models)
    body+='<p><strong>Decision: keep this candidate experimental.</strong> Westbound 10/60-second speed improves, but results are mixed and some flow and longer-horizon errors worsen. The existing dashboard model has not been replaced. Aggregate endpoint forecasts are separate from the local interpolation above; neither validates trajectories in the unobserved road between sensors. Raising the speed prior also worsened pure CTM errors, so it is not a verified physical calibration.</p>'
    body+='<p>Software checks include hidden-truth isolation, 30-second boundary handling, discontinuous-ground-truth exclusion and existing model/physics tests. Future models require a fresh held-out period: this later dataset has now been evaluated.</p>'
    Path(output).write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trajectory validation</title><style>body{font:16px/1.6 system-ui;max-width:1250px;margin:30px auto;padding:20px;color:#203746}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ccd6dc;padding:8px;text-align:left}th{background:#eef3f6}h2{margin-top:36px}a{color:#0065af}</style>'+body+'</html>')
    return headers,rows,mh,models,md
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--gaps',required=True);p.add_argument('--original',required=True);p.add_argument('--candidate',required=True);p.add_argument('--output',required=True);a=p.parse_args();render(a.gaps,a.original,a.candidate,a.output)
