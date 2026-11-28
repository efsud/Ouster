"""Publish local observed segment groups separately from individual estimates."""
import json
from pathlib import Path

from .trajectory_regime_groups import TrajectoryRegimeGroups, VERSION

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'data/reconstruction/regime-group-study-20261124'


def learning_review():
    try:
        review = json.loads((STUDY/'learner-review/report.json').read_text())
    except (OSError, ValueError):
        try:
            review = json.loads((ROOT/'docs/validation/florida-regime-groups-20261124.json').read_text())['local_review']
        except (OSError, ValueError, KeyError):
            return {}, ['The group-conditioned learner is under evaluation; established individual estimates are retained.']
    if review.get('state') != 'complete':
        return {}, ['Recorded-data validation is not complete; established estimates are retained.']
    row = review['test_methods']['learned_regime']
    common, full = row['common'], row['fallback_included']
    number = lambda x: f'{x:.3f}' if isinstance(x, (float, int)) else 'unavailable'
    notes = [f"Training used {review['training_independent_ids']} independent target IDs. Final-quarter test: "
             f"{common['n']} peer-supported masks from {common['independent_ids']} independent IDs out of {row['eligible']} eligible masks. "
             f"Mean position error {number(common['kinematic'].get('mae_m'))} → {number(common['candidate'].get('mae_m'))} m; "
             f"speed error {number(common['kinematic'].get('speed_mae_mps'))} → {number(common['candidate'].get('speed_mae_mps'))} m/s.",
             f"With fallback on the same {full['n']} baseline-supported masks, mean position error "
             f"{number(full['kinematic'].get('mae_m'))} → {number(full['candidate'].get('mae_m'))} m.",
             ('Renaissance passed the initial site gate, but its ten-vehicle uncertainty interval includes no improvement. Learned refinements are optional and experimental; established estimates remain the default.' if review['deployment_eligible'] else
              'The learned model did not pass every promotion check. It is not replacing the displayed individual estimates.'),
             'Twenty-second gaps worsened on average (0.179 → 0.201 m); improvements are not uniform across gap lengths and motion types.',
             'These are retrospective masked-recording tests. They do not verify cross-intersection identities or recover ground truth inside real outages.']
    return {k: review[k] for k in ('version', 'deployment_eligible', 'enabled_sites',
                                  'training_independent_ids', 'test_methods', 'limitations')}, notes


def build(snapshot):
    sites = [dict(id=s['id'], name=s['name'], **TrajectoryRegimeGroups(s).group())
             for s in snapshot['sites']]
    learning, learning_notes = learning_review()
    return dict(version=VERSION, snapshot_generated_at=snapshot['generated_at'], sites=sites,
                learning=learning, learning_notes=learning_notes,
                notes=[
                    'Blue dashed outlines summarize observed local groups with similar time, road position, speed and slope. They are not vehicle paths.',
                    'One vehicle can belong to separate stopped and moving groups. At least three distinct sensor-local identities support each group.',
                    'Empty time bins stay open. Groups do not join different sensors or establish vehicle identity between intersections.'
                ])
