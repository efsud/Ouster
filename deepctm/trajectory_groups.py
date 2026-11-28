"""Observed trajectory cohorts, not time/space grid averages.

Tracks are compared at common *observed* road stations using crossing time,
speed profile and lateral path.  A density neighbourhood needs three distinct
sensor-session/object identities.  Every member must also match its observed
medoid, preventing a chain of nearby cars from joining an entire hour together.
These are exploratory local cohorts, not verified lanes, platoons or identities.

The returned indices always refer to the original ``site['tracks']`` list.
No samples, coordinates or trajectories are changed or synthesized here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import math

import numpy as np


VERSION = "observed_trajectory_density_v1"


@dataclass(frozen=True)
class GroupConfig:
    station_step_m: float = 10.0
    max_observation_gap_s: float = 1.5
    min_shared_stations: int = 3
    min_shared_distance_m: float = 15.0
    max_arrival_lag_s: float = 20.0
    max_time_profile_residual_s: float = 4.0
    max_speed_profile_difference_mps: float = 3.0
    max_lateral_difference_m: float = 2.5
    min_identities: int = 3
    stationary_speed_mps: float = 0.7
    stationary_distance_m: float = 18.0
    stationary_min_overlap_s: float = 2.0
    classification_margin: float = 0.08


def identity(track: dict) -> tuple[str, str] | None:
    """Class-independent, LOCAL identity; never comparable between sites."""
    key = track.get("source_key", ())
    return (str(key[0]), str(key[1])) if len(key) >= 2 else None


def _family(track: dict) -> str:
    c = str(track.get("class_type", "unknown"))
    return "motor_vehicle" if c in {str(x) for x in (*range(1, 10), 15)} else c


def _points(track: dict) -> np.ndarray:
    try:
        p = np.asarray(track.get("points", []), dtype=float)
    except (TypeError, ValueError):
        return np.empty((0, 3))
    if p.ndim != 2 or p.shape[1] < 3:
        return np.empty((0, 3))
    p = p[np.all(np.isfinite(p[:, :3]), axis=1), :3]
    if len(p) < 3:
        return np.empty((0, 3))
    # Reordering a clock discontinuity would turn it into invented motion.
    if np.any(np.diff(p[:, 0]) <= 0):
        return np.empty((0, 3))
    return p


def _lateral(track: dict, points: np.ndarray) -> tuple[float, float] | None:
    values = []
    for key in ("lateral_start_m", "lateral_end_m"):
        v = track.get(key)
        if isinstance(v, (int, float)) and math.isfinite(v):
            values.append(float(v))
    if not values:
        return None
    return float(np.mean(values)), float(values[-1] - values[0])


def _observed(track: dict) -> bool:
    return not track.get("method") and track.get("source") not in {
        "inferred", "estimated", "simulated", "reconstructed"
    }


class TrajectoryGroups:
    """Reusable observed-profile index, with identity-excluded classification.

    Building the peer graph never depends on a proposed gap's hidden samples.
    ``group(excluded_identity=...)`` removes every fragment of that identity
    before finding density support.  ``classify_visible`` then independently
    compares the supplied visible observations to those peer-only cohorts.
    """

    def __init__(self, site: dict, config: GroupConfig | None = None):
        self.site = site
        self.config = config or GroupConfig()
        self.tracks = site.get("tracks", [])
        self.descriptors: dict[int, dict] = {}
        self.edges: dict[int, dict[int, float]] = defaultdict(dict)
        self._cache: dict[tuple | None, dict] = {}
        self._station_origin = float(site.get("station_m", 0.0))
        for i, track in enumerate(self.tracks):
            d = self._descriptor(track)
            if d is not None:
                self.descriptors[i] = d
        self._build_graph()

    def _descriptor(self, track: dict) -> dict | None:
        if not _observed(track) or identity(track) is None:
            return None
        direction = track.get("direction")
        if direction not in {"eastbound", "westbound"}:
            return None
        p = _points(track)
        lateral = _lateral(track, p)
        if len(p) < 3 or lateral is None:
            return None
        cfg = self.config
        sign = 1.0 if direction == "eastbound" else -1.0
        x = sign * (p[:, 1] - self._station_origin)
        dx, dt = np.diff(x), np.diff(p[:, 0])
        valid = (dt <= cfg.max_observation_gap_s) & (dx > 0.02)
        # Crossing samples are obtained only inside actually observed segments.
        crossings = {}
        for j in np.flatnonzero(valid):
            first = math.ceil(x[j] / cfg.station_step_m)
            last = math.floor(x[j + 1] / cfg.station_step_m)
            for k in range(first, last + 1):
                if k not in crossings:
                    alpha = (k * cfg.station_step_m - x[j]) / dx[j]
                    crossings[k] = (float(p[j, 0] + alpha * dt[j]),
                                    float(p[j, 2] + alpha * (p[j + 1, 2] - p[j, 2])))
        speed = float(np.median(p[:, 2]))
        stationary = float(np.ptp(x)) <= cfg.stationary_distance_m and speed <= cfg.stationary_speed_mps
        if not stationary and len(crossings) < cfg.min_shared_stations:
            return None
        movement = track.get("movement") or {}
        return dict(identity=identity(track), direction=direction,
                    family=_family(track), movement=movement.get("movement"),
                    role=movement.get("role"), points=p, crossings=crossings,
                    start=float(p[0, 0]), end=float(p[-1, 0]),
                    station=float(np.median(p[:, 1])), speed=speed,
                    speed_min=float(np.min(p[:, 2])), speed_max=float(np.max(p[:, 2])),
                    lateral=lateral, stationary=stationary)

    def _distance(self, a: dict, b: dict) -> float | None:
        cfg = self.config
        if a["direction"] != b["direction"] or a["family"] != b["family"]:
            return None
        if a["movement"] and b["movement"] and a["movement"] != b["movement"]:
            return None
        if a["role"] and b["role"] and a["role"] != b["role"]:
            return None
        lateral = abs(a["lateral"][0] - b["lateral"][0]) / cfg.max_lateral_difference_m
        lateral_shape = abs(a["lateral"][1] - b["lateral"][1]) / (2 * cfg.max_lateral_difference_m)
        if max(lateral, lateral_shape) > 1:
            return None
        if a["stationary"] or b["stationary"]:
            if not (a["stationary"] and b["stationary"]):
                return None
            overlap = min(a["end"], b["end"]) - max(a["start"], b["start"])
            if overlap < cfg.stationary_min_overlap_s:
                return None
            spatial = abs(a["station"] - b["station"]) / cfg.stationary_distance_m
            speed = abs(a["speed"] - b["speed"]) / cfg.stationary_speed_mps
            dist = max(spatial, speed, lateral, lateral_shape)
            return dist if dist <= 1 else None
        common = a["crossings"].keys() & b["crossings"].keys()
        if len(common) < cfg.min_shared_stations:
            return None
        if (max(common) - min(common)) * cfg.station_step_m < cfg.min_shared_distance_m:
            return None
        differences = np.array([(b["crossings"][k][0] - a["crossings"][k][0],
                                 b["crossings"][k][1] - a["crossings"][k][1]) for k in common])
        lag = float(np.median(differences[:, 0]))
        time_shape = float(np.quantile(np.abs(differences[:, 0] - lag), .8))
        speed_shape = float(np.quantile(np.abs(differences[:, 1]), .8))
        dist = max(abs(lag) / cfg.max_arrival_lag_s,
                   time_shape / cfg.max_time_profile_residual_s,
                   speed_shape / cfg.max_speed_profile_difference_mps,
                   lateral, lateral_shape)
        return float(dist) if dist <= 1 else None

    def _build_graph(self) -> None:
        cfg = self.config
        at_station = defaultdict(list)
        stationary = defaultdict(list)
        for i, d in self.descriptors.items():
            if d["stationary"]:
                stationary[d["direction"], d["family"]].append(i)
            else:
                for k, (time, _) in d["crossings"].items():
                    at_station[d["direction"], d["family"], k].append((time, i))
        # Count shared observed stations before the more expensive profile check.
        shared = defaultdict(int)
        checked = set()
        for items in at_station.values():
            items.sort()
            left = 0
            for right, (time, i) in enumerate(items):
                while items[left][0] < time - cfg.max_arrival_lag_s:
                    left += 1
                for _, j in items[left:right]:
                    pair = (min(i, j), max(i, j))
                    if pair in checked:
                        continue
                    shared[pair] += 1
                    if shared[pair] >= cfg.min_shared_stations:
                        checked.add(pair)
                        dist = self._distance(self.descriptors[i], self.descriptors[j])
                        if dist is not None:
                            self.edges[i][j] = self.edges[j][i] = dist
        for indices in stationary.values():
            indices.sort(key=lambda i: self.descriptors[i]["start"])
            active = []
            for i in indices:
                a = self.descriptors[i]
                active = [j for j in active if self.descriptors[j]["end"] >= a["start"] + cfg.stationary_min_overlap_s]
                for j in active:
                    dist = self._distance(a, self.descriptors[j])
                    if dist is not None:
                        self.edges[i][j] = self.edges[j][i] = dist
                active.append(i)

    def group(self, excluded_identity: tuple | list | None = None) -> dict:
        excluded = tuple(str(x) for x in excluded_identity[:2]) if excluded_identity else None
        if excluded in self._cache:
            return self._cache[excluded]
        available = {i for i, d in self.descriptors.items() if d["identity"] != excluded}
        assignments = [None] * len(self.tracks)
        groups = []
        cfg = self.config

        def neighbourhood(i):
            members = {i} | (self.edges[i].keys() & available)
            # An unknown-movement seed must not bridge two incompatible known
            # turns merely because both share a short approach segment.
            for field in ("movement", "role"):
                known = {self.descriptors[j][field] for j in members if self.descriptors[j][field]}
                if len(known) > 1:
                    selected = self.descriptors[i][field]
                    if not selected:
                        selected = min(known, key=lambda value: (
                            -len({self.descriptors[j]["identity"] for j in members if self.descriptors[j][field] == value}),
                            str(value)))
                    members = {j for j in members if self.descriptors[j][field] in (None, selected)}
            return members

        def identities(indices):
            return {self.descriptors[i]["identity"] for i in indices}

        # A bounded density star avoids unbounded DBSCAN chaining. Recompute
        # support after each extraction, so duplicate fragments cannot create
        # density and each observed fragment belongs to at most one cohort.
        priorities = sorted(available, key=lambda i: (
            -len(identities(neighbourhood(i))), self.descriptors[i]["start"], i))
        for seed in priorities:
            if seed not in available:
                continue
            members = neighbourhood(seed)
            if len(identities(members)) < cfg.min_identities:
                continue
            # The density seed is an observed exemplar. Improve to an observed
            # medoid only when it remains compatible with every cohort member.
            candidates = []
            for candidate in members:
                distances = defaultdict(list)
                for j in members:
                    if j == candidate:
                        continue
                    value = self.edges[candidate].get(j)
                    if value is None:
                        break
                    distances[self.descriptors[j]["identity"]].append(value)
                else:
                    # A repeatedly fragmented object gets one identity's
                    # weight, not one vote per fragment.
                    candidates.append((float(np.mean([np.mean(v) for v in distances.values()])) if distances else 0.0, candidate))
            _, medoid = min(candidates) if candidates else (0, seed)
            ds = [self.descriptors[i] for i in members]
            # Membership signatures, rather than ordinal labels, identify the
            # same local cohort when unrelated target identities are excluded.
            signature = ";".join(str(i) for i in sorted(members))
            label = str(self.site.get("id", "site")) + ":g:" + hashlib.sha1(signature.encode()).hexdigest()[:10]
            group = dict(group_id=label, member_indices=sorted(members),
                         identity_count=len(identities(members)),
                         medoid_index=medoid, representative_track_index=medoid,
                         direction=ds[0]["direction"],
                         movement=self.descriptors[medoid]["movement"],
                         movement_codes=sorted({d["movement"] for d in ds if d["movement"]}),
                         kind="stationary_trajectory_cohort" if ds[0]["stationary"] else "moving_trajectory_cohort",
                         time_start_s=min(d["start"] for d in ds), time_end_s=max(d["end"] for d in ds),
                         speed_median_mps=float(np.median([d["speed"] for d in ds])),
                         speed_min_mps=min(d["speed_min"] for d in ds), speed_max_mps=max(d["speed_max"] for d in ds),
                         lateral_median_m=float(np.median([d["lateral"][0] for d in ds])),
                         observed_only=True, verified_lane=False, verified_platoon=False)
            groups.append(group)
            for i in members:
                assignments[i] = label
            available.difference_update(members)
        result = dict(version=VERSION, groups=groups, assignments=assignments,
                      summary=dict(input_tracks=len(self.tracks), eligible_tracks=len(self.descriptors),
                                   groups=len(groups), grouped_tracks=sum(x is not None for x in assignments),
                                   ungrouped_tracks=sum(x is None for x in assignments),
                                   distinct_grouped_identities=len(identities({i for i, x in enumerate(assignments) if x is not None})),
                                   min_identity_support=cfg.min_identities,
                                   method="observed time-space-speed density cohorts with bounded medoid profiles"),
                      limitations=["Groups are local observed similarity cohorts, not verified lanes or platoons.",
                                   "Lateral position and corridor projection remain provisionally calibrated.",
                                   "Path comparison uses longitudinal profiles and lateral endpoints; full lateral paths are unavailable.",
                                   "Short, sparse, incompatible or isolated trajectories remain ungrouped."])
        self._cache[excluded] = result
        # Masking many objects should not retain thousands of full groupings.
        if len(self._cache) > 32:
            removable = next(key for key in self._cache if key not in (None, excluded))
            del self._cache[removable]
        return result

    def classify_visible(self, target_visible: dict, excluded_identity: tuple | list | None = None) -> dict | None:
        """Assign a masked target using its visible samples and peer-only groups.

        The supplied lateral context must refer to visible samples. Movement
        labels on a target may have used hidden portions, so they are ignored.
        Donor indices returned here are only directly compatible group members.
        """
        excluded = excluded_identity or identity(target_visible)
        if excluded is None:
            return None
        target = dict(target_visible, movement={})
        d = self._descriptor(target)
        if d is None:
            return None
        candidates = []
        for cohort in self.group(excluded)["groups"]:
            if cohort["direction"] != d["direction"]:
                continue
            matches = []
            by_identity = {}
            for i in cohort["member_indices"]:
                peer = self.descriptors[i]
                score = self._distance(d, peer)
                if score is not None:
                    matches.append((score, i))
                    by_identity[peer["identity"]] = min(score, by_identity.get(peer["identity"], math.inf))
            if len(by_identity) < self.config.min_identities:
                continue
            score = float(np.mean(sorted(by_identity.values())[:self.config.min_identities]))
            candidates.append((score, cohort["group_id"], matches, len(by_identity)))
        if not candidates:
            return None
        candidates.sort(key=lambda row: (row[0], row[1]))
        best = candidates[0]
        margin = candidates[1][0] - best[0] if len(candidates) > 1 else None
        if margin is not None and margin < self.config.classification_margin:
            return None
        return dict(group_id=best[1], donor_indices=[i for _, i in sorted(best[2])],
                    score=best[0], scores={str(i): score for score, i in best[2]},
                    identity_count=best[3], margin=margin,
                    excluded_identity=list(excluded[:2]), observed_only=True,
                    evidence="visible time-space-speed profile; all target identity fragments excluded")


def group(site: dict, config: GroupConfig | None = None) -> dict:
    """Convenience API returning groups and original-track-index assignments."""
    return TrajectoryGroups(site, config).group()
