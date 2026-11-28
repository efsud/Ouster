"""Publish observed trajectory memberships and their reconstruction evidence.

Assignments index the original, unfiltered snapshot tracks. This layer neither
averages vehicles together nor changes measured positions or KPI observations.
"""
import json
from dataclasses import asdict
from pathlib import Path

from .trajectory_groups import TrajectoryGroups, GroupConfig, VERSION

ROOT = Path(__file__).resolve().parents[1]


def _report(path):
    try:
        result = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return result if result.get('state') == 'complete' else None


def build(snapshot, existing_layers=None, report=None):
    sites = []
    for site in snapshot['sites']:
        grouped = TrajectoryGroups(site).group()
        sites.append(dict(id=site['id'], name=site['name'], **grouped))
    notes = [
        'Groups compare observed road-station crossing times, speed profiles, '
        'lateral endpoints and compatible movements. Every group needs three '
        'distinct sensor-local object IDs. No observed line is averaged or moved.',
        'Groups are exploratory similarity groups, not verified lanes, platoons '
        'or cross-intersection vehicle identities. Short or ambiguous paths stay ungrouped.'
    ]
    evidence = {}
    local = _report(ROOT/'data/reconstruction/trajectory-group-local-review/review-002/report.json')
    between = _report(ROOT/'data/reconstruction/trajectory-group-between/20261123/report.json')
    if local:
        t = local['test']; b, g = t['baseline'], t['group']
        if t['n']:
            notes.append(f"Local hidden-gap test: {t['n']} peer-supported masks from "
                         f"{t['distinct_ids']} distinct vehicle IDs. Position MAE "
                         f"{b['mae_m']:.2f} → {g['mae_m']:.2f} m; speed MAE "
                         f"{b['speed_mae_mps']:.2f} → {g['speed_mae_mps']:.2f} m/s. "
                         + ('Only qualified sites use the peer prior.' if local['deployment_eligible'] else
                            'The peer prior did not qualify for deployment; existing estimates are retained.'))
        else:
            notes.append('Local hidden-gap test found no supported peer reconstruction cases; existing estimates are retained.')
        evidence['local'] = {k:local[k] for k in ('test','selected_weight','enabled_sites','deployment_eligible','limitations')}
        if t['n']:
            f = t['fallback_included']
            notes.append(f"Including fallback on the same {f['baseline']['n']} accepted masks: "
                         f"position MAE {f['baseline']['mae_m']:.3f} → {f['hybrid']['mae_m']:.3f} m. "
                         'The local test covered 5, 10 and 20 seconds; no 20-second mask had enough independent peer support. '
                         'Each intersection had fewer than ten supported test IDs, so automatic peer-prior replacement is disabled.')
    if between:
        b, g = between['test']['baseline'], between['test']['group_candidate']
        notes.append(f"Spatial masking test: baseline {b['correct']} correct / {b['false']} wrong "
                     f"matches; group-guided {g['correct']} correct / {g['false']} wrong. "
                     'This hides road strips inside recorded sensor views; actual identities between sensors remain unverified.')
        evidence['between'] = {k:between[k] for k in ('test','deployment_eligible','limitations')}
    output = dict(method=VERSION, snapshot_generated_at=snapshot['generated_at'],
                  sites=sites, validation_notes=notes, validation=evidence,
                  between_intersections=[])
    if (between and between.get('deployment_eligible') and report and existing_layers
            and between['protocol'].get('parameters') == report['calibration']['parameters']
            and between['protocol'].get('grouping_version') == VERSION
            and between['protocol'].get('grouping_config') == asdict(GroupConfig())
            and between['protocol'].get('weight') == .25):
        from .between_group_matching import build_additional
        additions = build_additional(snapshot, report, existing_layers, sites)
        output['between_intersections'] = additions.pop('paths')
        output['association_review'] = additions
        notes.append(f"This hour has {len(output['between_intersections'])} additional group-supported "
                     'individual connection hypotheses. The optional group-assisted layer shows them separately; '
                     'the recorded-data test gain involved only four additional distinct vehicles at one site.')
    return output
