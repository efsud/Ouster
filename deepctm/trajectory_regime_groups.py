"""Unsupervised local time-space-speed *segment* groups.

A vehicle can join a stopped group, then a moving group. These groups summarize
observed pieces; they are not average vehicles and do not fill a missing sample.
Lateral endpoints are provisional path proxies, not a verified lane assignment.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import asdict, dataclass
import hashlib
import math
import numpy as np

VERSION = 'observed_trajectory_regime_density_v1'


@dataclass(frozen=True)
class RegimeConfig:
    max_observation_gap_s: float = 1.5
    min_segment_duration_s: float = 1.5
    min_segment_points: int = 4
    max_segment_duration_s: float = 60.
    stopped_speed_mps: float = .8
    stopped_slope_mps: float = 1.2
    speed_change_mps: float = 3.
    slope_change_mps: float = 3.5
    max_speed_difference_mps: float = 3.
    max_slope_difference_mps: float = 3.5
    max_time_gap_s: float = 12.
    max_passage_lag_s: float = 20.
    max_station_gap_m: float = 35.
    stopped_station_difference_m: float = 35.
    max_lateral_difference_m: float = 3.
    min_identities: int = 3
    envelope_bin_s: float = 1.
    classification_margin: float = .05


# Public spelling used by the supervised reconstruction adapter.
RegimeGroupConfig = RegimeConfig


def identity(track):
    key = track.get('source_key') or []
    return tuple(str(v) for v in key[:2]) if len(key) >= 2 else None


def family(track):
    c = str(track.get('class_type', 'unknown'))
    return 'motor_vehicle' if c in {str(v) for v in (*range(1, 10), 15)} else c


def _points(track):
    try:
        p = np.asarray(track.get('points', []), float)
    except (TypeError, ValueError):
        return None
    if p.ndim != 2 or p.shape[1] < 3 or len(p) < 4:
        return None
    p = p[:, :3]
    if not np.isfinite(p).all() or np.any(np.diff(p[:, 0]) <= 0) or np.any(p[:, 2] < 0):
        return None
    return p


def _lateral(track):
    vals = [track.get(k) for k in ('lateral_start_m', 'lateral_end_m')]
    vals = [float(v) for v in vals if isinstance(v, (int, float)) and math.isfinite(v)]
    return float(np.mean(vals)) if vals else None


def _smooth(values):
    # Bounded local median; no filter ever crosses a missing observation run.
    return np.median(np.vstack([np.r_[values[0], values[:-1]], values,
                                np.r_[values[1:], values[-1]]]), axis=0)


def _regime(speed, slope, cfg):
    if speed <= cfg.stopped_speed_mps and abs(slope) <= cfg.stopped_slope_mps:
        return 'stopped'
    if speed < 5.:
        return 'slow'
    if speed < 12.:
        return 'moving'
    return 'fast'


def segments(track, track_index=0, config=None):
    """Observed-only pieces, with inclusive original sample-index provenance."""
    cfg = config or RegimeConfig()
    if track.get('method') or track.get('source') in ('inferred', 'estimated', 'simulated'):
        return []
    ident = identity(track); p = _points(track); lat = _lateral(track)
    direction = track.get('direction')
    if ident is None or p is None or lat is None or direction not in ('eastbound', 'westbound'):
        return []
    sign = 1. if direction == 'eastbound' else -1.
    cuts = [0, *(np.flatnonzero(np.diff(p[:, 0]) > cfg.max_observation_gap_s)+1), len(p)]
    output = []

    def emit(first, last, regime):
        q = p[first:last+1]
        if len(q) < cfg.min_segment_points or q[-1, 0]-q[0, 0] < cfg.min_segment_duration_s:
            return
        t = q[:, 0]-np.mean(q[:, 0]); x = q[:, 1]-np.mean(q[:, 1])
        slope = float(np.dot(t, x)/np.dot(t, t))
        if sign*slope < -.5:
            return
        movement = track.get('movement') or {}
        segment_id = f'{track_index}:{first}:{last}'
        output.append(dict(segment_id=segment_id, track_index=int(track_index),
            start_index=int(first), end_index=int(last), identity=ident,
            direction=direction, family=family(track), regime=regime,
            movement=movement.get('movement'), role=movement.get('role'),
            start_s=float(q[0, 0]), end_s=float(q[-1, 0]), time_mid=float(np.mean(q[:, 0])),
            station_mid=float(np.mean(q[:, 1])), station_min=float(np.min(q[:, 1])),
            station_max=float(np.max(q[:, 1])), slope_mps=slope,
            forward_slope_mps=sign*slope, speed_mps=float(np.median(q[:, 2])),
            speed_iqr_mps=float(np.quantile(q[:, 2], .75)-np.quantile(q[:, 2], .25)),
            lateral_m=lat, points=q))

    for run_start, run_end in zip(cuts, cuts[1:]):
        q = p[run_start:run_end]
        if len(q) < cfg.min_segment_points:
            continue
        rates = _smooth(sign*np.diff(q[:, 1])/np.diff(q[:, 0]))
        speeds = _smooth((q[:-1, 2]+q[1:, 2])*.5)
        labels = [_regime(float(v), float(r), cfg) for v, r in zip(speeds, rates)]
        first = 0
        speed_sum, rate_sum = float(speeds[0]), float(rates[0])
        for i in range(1, len(labels)):
            # Changes in color-speed AND geometric slope define a new regime.
            changed = labels[i] != labels[first]
            changed |= abs(float(speeds[i])-speed_sum/(i-first)) > cfg.speed_change_mps
            changed |= abs(float(rates[i])-rate_sum/(i-first)) > cfg.slope_change_mps
            changed |= q[i, 0]-q[first, 0] >= cfg.max_segment_duration_s
            if changed:
                emit(int(run_start+first), int(run_start+i), labels[first])
                first = i
                speed_sum = rate_sum = 0.
            speed_sum += float(speeds[i]); rate_sum += float(rates[i])
        emit(int(run_start+first), int(run_end-1), labels[first])
    return output


class TrajectoryRegimeGroups:
    def __init__(self, site, config=None):
        self.site = site; self.config = config or RegimeConfig()
        self.tracks = site.get('tracks', [])
        self.descriptors = {}
        self.by_track = defaultdict(list)
        self.edges = defaultdict(dict)
        self._cohort_cache = OrderedDict()
        self._published = None
        for index, track in enumerate(self.tracks):
            for d in segments(track, index, self.config):
                self.descriptors[d['segment_id']] = d
                self.by_track[index].append(d['segment_id'])
        self._build_graph()

    def _distance(self, a, b):
        c = self.config
        if any(a[k] != b[k] for k in ('direction', 'family', 'regime')):
            return None
        if a.get('movement') and b.get('movement') and a['movement'] != b['movement']:
            return None
        if a.get('role') and b.get('role') and a['role'] != b['role']:
            return None
        time_gap = max(0., a['start_s']-b['end_s'], b['start_s']-a['end_s'])
        station_gap = max(0., a['station_min']-b['station_max'], b['station_min']-a['station_max'])
        lateral = abs(a['lateral_m']-b['lateral_m'])/c.max_lateral_difference_m
        speed = abs(a['speed_mps']-b['speed_mps'])/c.max_speed_difference_mps
        slope = abs(a['forward_slope_mps']-b['forward_slope_mps'])/c.max_slope_difference_mps
        base = max(time_gap/c.max_time_gap_s, station_gap/c.max_station_gap_m, lateral, speed, slope)
        if base > 1:
            return None
        if a['regime'] == 'stopped':
            base = max(base, abs(a['station_mid']-b['station_mid'])/c.stopped_station_difference_m)
        else:
            # Linear-profile intercept is a similarity feature, not a filled path.
            station = .5*(max(a['station_min'], b['station_min'])+min(a['station_max'], b['station_max']))
            if min(abs(a['slope_mps']), abs(b['slope_mps'])) < .5:
                return None
            ta = a['time_mid']+(station-a['station_mid'])/a['slope_mps']
            tb = b['time_mid']+(station-b['station_mid'])/b['slope_mps']
            base = max(base, abs(ta-tb)/c.max_passage_lag_s)
        return float(base) if base <= 1 else None

    def _build_graph(self):
        strata = defaultdict(list)
        for key, d in self.descriptors.items():
            strata[d['direction'], d['family'], d['regime']].append(key)
        for items in strata.values():
            items.sort(key=lambda key: (self.descriptors[key]['start_s'], key))
            active = []
            for key in items:
                a = self.descriptors[key]
                active = [old for old in active if self.descriptors[old]['end_s']+self.config.max_time_gap_s >= a['start_s']]
                for other in active:
                    b = self.descriptors[other]
                    score = self._distance(a, b)
                    if score is not None:
                        self.edges[key][other] = self.edges[other][key] = score
                active.append(key)

    def _envelope(self, ds):
        bins = defaultdict(list)
        for d in ds:
            for t, x, _ in d['points']:
                bins[math.floor(t/self.config.envelope_bin_s)].append((float(t), float(x), d['identity']))
        return [[float(np.mean([r[0] for r in rows])), min(r[1] for r in rows), max(r[1] for r in rows),
                 len({r[2] for r in rows})] for _, rows in sorted(bins.items())]

    @staticmethod
    def _member(d):
        fields = ('segment_id', 'track_index', 'start_index', 'end_index', 'start_s', 'end_s',
                  'regime', 'slope_mps', 'forward_slope_mps', 'speed_mps', 'station_min', 'station_max')
        return {key: d[key] for key in fields}

    def _cohorts(self, excluded=None):
        """Compact deterministic groups; LOO never caches per-group envelopes."""
        if excluded in self._cohort_cache:
            self._cohort_cache.move_to_end(excluded)
            return self._cohort_cache[excluded]
        available = {key for key, d in self.descriptors.items() if d['identity'] != excluded}
        identities = lambda keys: {self.descriptors[k]['identity'] for k in keys}
        neighbourhood = lambda key: {key} | (self.edges[key].keys() & available)
        priority = sorted(available, key=lambda key: (-len(identities(neighbourhood(key))), self.descriptors[key]['start_s'], key))
        cohorts = []
        for seed in priority:
            if seed not in available:
                continue
            members = neighbourhood(seed)
            # Neither an unknown movement nor an unknown role may merge
            # conflicting known labels through a density star.
            for field in ('movement', 'role'):
                codes = defaultdict(set)
                for key in members:
                    code = self.descriptors[key].get(field)
                    if code:
                        codes[code].add(self.descriptors[key]['identity'])
                preferred = self.descriptors[seed].get(field)
                if not preferred and codes:
                    preferred = sorted(codes, key=lambda code: (-len(codes[code]), code))[0]
                if preferred:
                    members = {key for key in members if self.descriptors[key].get(field) in (None, preferred)}
            if len(identities(members)) < self.config.min_identities:
                continue
            cohorts.append((seed, tuple(sorted(members))))
            available.difference_update(members)
        result = (cohorts, len(available))
        self._cohort_cache[excluded] = result
        while len(self._cohort_cache) > 8:
            self._cohort_cache.popitem(last=False)
        return result

    def group(self, excluded_identity=None):
        excluded = tuple(str(v) for v in excluded_identity[:2]) if excluded_identity else None
        if excluded is None and self._published is not None:
            return self._published
        cohorts, ungrouped = self._cohorts(excluded)
        assignments = defaultdict(list); groups = []
        identities = lambda keys: {self.descriptors[k]['identity'] for k in keys}
        for seed, members in cohorts:
            ds = [self.descriptors[key] for key in sorted(members)]
            digest = hashlib.sha1(';'.join(sorted(members)).encode()).hexdigest()[:10]
            group_id = f"{self.site.get('id', 'site')}:r:{digest}"
            # One fragmented identity must not outweigh several intact peers.
            per_id = defaultdict(list)
            for d in ds:
                per_id[d['identity']].append(d)
            speed = [float(np.median([d['speed_mps'] for d in rows])) for rows in per_id.values()]
            slope = [float(np.median([d['slope_mps'] for d in rows])) for rows in per_id.values()]
            record = dict(group_id=group_id, direction=ds[0]['direction'], regime=ds[0]['regime'], family=ds[0]['family'],
                members=[self._member(d) for d in ds], member_indices=sorted({d['track_index'] for d in ds}),
                identity_count=len(identities(members)), representative_member=self._member(self.descriptors[seed]),
                representative_basis='observed density seed, not a synthetic average vehicle',
                start_s=min(d['start_s'] for d in ds), end_s=max(d['end_s'] for d in ds),
                aggregate=dict(speed_median_mps=float(np.median(speed)), speed_iqr_mps=float(np.subtract(*np.percentile(speed, [75,25]))),
                    slope_median_mps=float(np.median(slope)), slope_iqr_mps=float(np.subtract(*np.percentile(slope, [75,25]))),
                    lateral_median_m=float(np.median([d['lateral_m'] for d in ds])), distinct_ids=len(identities(members))),
                envelope=self._envelope(ds), envelope_bin_s=self.config.envelope_bin_s,
                observed_only=True, envelope_is_estimated_trajectory=False,
                aggregate_basis='equal identity weight',
                movement_codes=sorted({d['movement'] for d in ds if d['movement']}),
                movement_roles=sorted({d['role'] for d in ds if d['role']}))
            groups.append(record)
            for d in ds:
                assignments[d['track_index']].append(dict(group_id=group_id, **self._member(d)))
        result = dict(version=VERSION, configuration=asdict(self.config), groups=groups,
            assignments=[assignments.get(i, []) for i in range(len(self.tracks))],
            summary=dict(input_tracks=len(self.tracks), eligible_segments=sum(d['identity'] != excluded for d in self.descriptors.values()), groups=len(groups),
                grouped_segments=sum(len(g['members']) for g in groups),
                grouped_tracks=sum(bool(assignments.get(i)) for i in range(len(self.tracks))),
                ungrouped_segments=ungrouped, minimum_identity_support=self.config.min_identities),
            limitations=['Groups are local observed motion regimes, not verified platoons or cross-sensor identities.',
                        'Lateral endpoints are a path proxy; full lateral trajectories and verified lanes are unavailable.',
                        'Envelopes summarize observed members only; empty time bins remain absent.'])
        if excluded is None:
            self._published = result
        return result

    def classify_visible(self, target_visible, excluded_identity=None, a=None, b=None):
        """Classify visible regime context, never a target's missing samples.

        The donor cohort is rebuilt after excluding ALL target-ID fragments.
        Returned original track indices let a caller fit other members' observed
        shape while preserving each individual's own gap endpoints.
        """
        excluded = excluded_identity or identity(target_visible)
        if excluded is None:
            return None
        target = dict(target_visible, movement={})
        p = _points(target)
        if p is None:
            return None
        if a is not None and b is not None:
            if np.any((p[:, 0] > a['t']+1e-7) & (p[:, 0] < b['t']-1e-7)):
                raise ValueError('Hidden target samples cannot be used by regime grouping')
            # Keep visible context, not an unrelated remote piece of this object.
            chosen = ((p[:, 0] >= a['t']-8) & (p[:, 0] <= a['t'])) | ((p[:, 0] >= b['t']) & (p[:, 0] <= b['t']+8))
            target['points'] = p[chosen].tolist()
        targets = segments(target, -1, self.config)
        if not targets:
            return None
        excluded = tuple(str(v) for v in excluded[:2])
        cohorts, _ = self._cohorts(excluded)
        accepted = []; donor_scores = {}; selected_groups = []
        for target_segment in targets:
            choices = []
            for seed, members in cohorts:
                representative = self.descriptors[seed]
                if representative['direction'] != target_segment['direction'] or representative['regime'] != target_segment['regime']:
                    continue
                matches = []; identities = {}
                for member in members:
                    descriptor = self.descriptors[member]
                    score = self._distance(target_segment, descriptor)
                    if score is not None:
                        matches.append((score, descriptor))
                        ident = descriptor['identity']; identities[ident] = min(identities.get(ident, math.inf), score)
                if len(identities) >= self.config.min_identities:
                    cost = float(np.mean(sorted(identities.values())[:self.config.min_identities]))
                    digest = hashlib.sha1(';'.join(members).encode()).hexdigest()[:10]
                    gid = f"{self.site.get('id', 'site')}:r:{digest}"
                    choices.append((cost, gid, matches))
            choices.sort(key=lambda row: (row[0], row[1]))
            if not choices:
                continue
            if len(choices)>1 and choices[1][0]-choices[0][0] < self.config.classification_margin:
                continue
            _, gid, matches = choices[0]; selected_groups.append(gid)
            for score, descriptor in matches:
                key=descriptor['segment_id']; donor_scores[key]=min(score,donor_scores.get(key,math.inf));accepted.append(descriptor)
        unique = {d['segment_id']:d for d in accepted}
        if len({d['identity'] for d in unique.values()}) < self.config.min_identities:
            return None
        gids = sorted(set(selected_groups))
        return dict(group_id='+'.join(gids), group_ids=gids,
            donor_indices=sorted({d['track_index'] for d in unique.values()}),
            donor_segments=[self._member(d) for d in unique.values()],
            identity_count=len({d['identity'] for d in unique.values()}),
            excluded_identity=list(str(v) for v in excluded[:2]), observed_only=True,
            target_regimes=sorted({d['regime'] for d in targets}),
            evidence='visible local slope/speed regimes; target identity fully excluded')

    def select_donors(self, target_visible, a, b, excluded_identity=None):
        return self.classify_visible(target_visible, excluded_identity=excluded_identity, a=a, b=b)


def group(site, config=None):
    return TrajectoryRegimeGroups(site, config).group()
