"""Observed SDK track segments and reception audit; no cross-sensor matching."""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import heapq
import json
import math
from pathlib import Path
from .capture import atomic
from .florida_capture import BASE, CONFIG, GAP_S

CLASSES = dict(enumerate(('Pedestrian (legacy)', 'Vehicle (legacy)', 'Car', 'Van', 'Truck',
    'Bus', 'SUV', 'Construction vehicle', 'Trailer', 'Tractor', 'Pedestrian', 'Person sitting',
    'Cyclist', 'Bicycle', 'Person', 'Motorcycle', 'Rollerblader', 'Cyclist')))
VEHICLES = {'1', '2', '3', '4', '5', '6', '7', '8', '9', '15'}
MAX_PAIR_S = 1.0


def events(directory, site, issues):
    def read(path):
        try:
            with gzip.open(path, 'rt', encoding='utf-8') as source:
                for line in source:
                    try:
                        row = json.loads(line)
                        if (row['site'] != site or not math.isfinite(row['received_at'])
                                or not isinstance(row['payload'], dict) or not row['session']):
                            raise ValueError
                        yield row
                    except (KeyError, TypeError, ValueError):
                        issues['invalid_archive_rows'] += 1
        except (OSError, EOFError, UnicodeError):
            issues['incomplete_archive_files'] += 1
    return heapq.merge(*(read(p) for p in sorted(directory.glob(site + '-*.jsonl.gz'))),
                       key=lambda row: row['received_at'])


def calibration(entry):
    if entry is None:
        return None
    # The eastward unit vector is in the native sensor XY plane. A signed
    # origin offset locates local (0,0) relative to the FDOT signal station.
    ex, ey = map(float, entry['east_unit_xy'])
    off = float(entry['origin_station_offset_m'])
    roi = list(map(float, entry['roi_m']))
    lat, lon = float(entry['origin_lat']), float(entry['origin_lon'])
    if (not math.isclose(math.hypot(ex, ey), 1, abs_tol=.001)
            or len(roi) != 4 or not all(map(math.isfinite, [ex, ey, off, lat, lon, *roi]))
            or not (-90 <= lat <= 90 and -180 <= lon <= 180)
            or roi[0] >= roi[1] or roi[2] >= roi[3]
            or not isinstance(entry.get('source'), str) or not entry['source'].strip()):
        raise ValueError('Invalid calibration (expected measured origin, unit vector, ROI and source)')
    return ex, ey, off, roi


def extract(records, site, start, end, issues, cal=None):
    station = site['station_m']
    pieces, completed, previous, previous_clock = {}, [], {}, {}
    frames = []
    sessions, types, counts = set(), Counter(), Counter()
    first_sensor = last_sensor = None
    last_session = None

    def finish(key):
        pts = pieces.pop(key, [])
        if len(pts) < 2:
            return
        # Direction is a net movement classification, never a lane/turn match.
        delta = pts[-1][1] - pts[0][1]
        travel = sum(abs(b[1]-a[1]) for a,b in zip(pts,pts[1:]))
        direction = 'unknown'
        if cal and abs(delta) >= 3 and abs(delta) >= .7 * travel:
            direction = 'eastbound' if delta > 0 else 'westbound'
        # Keep up to two adjacent observed pairs per second per fragment for
        # browser display. Each row is independent, never a gap-spanning join.
        sampled, last_bucket = [], None
        for a, b in zip(pts, pts[1:]):
            bucket = math.floor(b[0]*2)
            if bucket != last_bucket:
                sampled.append([a[0], a[1], b[0], b[1], b[2]])
                last_bucket = bucket
        completed.append([key[2], direction, sampled])

    for row in records:
        t, session = row['received_at'], row['session']
        if not start <= t < end:
            continue
        event = row['payload']
        if 'frame' not in event or not isinstance(event['frame'], dict):
            continue
        frame = event['frame']
        frames.append(t)
        sessions.add(session)
        stamp = frame.get('timestamp') or event.get('timestamp')
        if isinstance(stamp, str):
            first_sensor = first_sensor or stamp
            last_sensor = stamp
        try:
            clock = datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            clock = None
            counts['invalid_frame_timestamp'] += 1
        if session != last_session:
            if last_session is not None:
                counts['session_transitions'] += 1
            for key in list(pieces):
                finish(key)
            previous.clear()
            last_session = session
        old_clock = previous_clock.get(session)
        previous_clock[session] = clock
        bad_clock = clock is None
        if clock is not None and old_clock is not None:
            try:
                dt = (clock-old_clock).total_seconds()
                if dt <= 0 or dt > MAX_PAIR_S:
                    counts['sensor_clock_step_breaks'] += 1
                    bad_clock = True
            except TypeError:
                counts['mixed_timezone_breaks'] += 1
                bad_clock = True
        if bad_clock:
            for key in list(pieces):
                finish(key)
            previous.clear()
            continue
        current = {}
        for o in frame.get('objects', []):
            if not isinstance(o, dict):
                counts['invalid_objects'] += 1
                continue
            code = str(o.get('classType', 'unknown'))
            types[code] += 1
            try:
                ident = str(o['id'])
                x, y = float(o['centerX']), float(o['centerY'])
                if not ident or not math.isfinite(x+y):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                counts['invalid_objects'] += 1
                continue
            key = session, ident, code
            if key in current:
                counts['duplicate_objects'] += 1
                continue
            along = station
            if cal:
                ex, ey, off, roi = cal
                dx, dy = ex*x+ey*y, -ey*x+ex*y
                if not roi[0] <= dx <= roi[1] or not roi[2] <= dy <= roi[3]:
                    counts['outside_roi'] += 1
                    finish(key)
                    continue
                along = station + off + dx
            current[key] = t, clock, x, y, along
            prior = previous.get(key)
            if not prior:
                counts['new_track_keys'] += 1
                continue
            at, ac, ax, ay, aa = prior
            try:
                dt = (clock-ac).total_seconds()
            except TypeError:
                dt = 0
            dr = t-at
            if not (0 < dt <= MAX_PAIR_S and 0 < dr <= MAX_PAIR_S and .5 <= dt/dr <= 2):
                counts['pair_time_breaks'] += 1
                finish(key)
                continue
            speed = math.hypot(x-ax,y-ay)/dt*3.6
            if speed > 216:
                counts['implausible_speed_breaks'] += 1
                finish(key)
                continue
            if key not in pieces:
                pieces[key] = [[round(at-start, 4), round(aa, 2), None]]
            pieces[key].append([round(t-start, 4), round(along, 2), round(speed, 1)])
        ended = set(previous)-set(current)
        counts['object_disappearances'] += len(ended)
        for key in ended:
            finish(key)
        previous = current
    for key in list(pieces):
        finish(key)
    intervals = [(a,b) for a,b in zip([start,*frames], [*frames,end]) if b-a > GAP_S]
    quality = dict(frames=len(frames), first_receipt=frames[0] if frames else None,
        last_receipt=frames[-1] if frames else None,
        receipt_span_s=round(frames[-1]-frames[0],3) if frames else 0,
        first_sensor_timestamp=first_sensor, last_sensor_timestamp=last_sensor,
        sessions=len(sessions), gaps_over_3s=len(intervals),
        longest_gap_s=round(max((b-a for a,b in intervals), default=0),3),
        gaps=[dict(start=a,end=b,seconds=round(b-a,3)) for a,b in intervals],
        object_classes=dict(types), diagnostics=dict(counts), archive_issues=dict(issues),
        fragments=len(completed))
    return completed, quality


def generate(directory, calibration_path=None):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text())
    if manifest['state'] in {'checking_reception', 'recording'}:
        raise ValueError('Wait until the capture has closed its archives')
    config = json.loads((directory/'config.json').read_text())
    # Keep each raw capture configuration as recorded; refresh the derived
    # view from the current reference catalog by UDID.
    catalog = {s['id']: s for s in json.loads(CONFIG.read_text())['sites']}
    config['sites'] = sorted(({**s, **catalog.get(s['id'], {})} for s in config['sites']),
                             key=lambda s:s['station_m'])
    custom = json.loads(Path(calibration_path).read_text()) if calibration_path else {}
    out = directory/'observed'
    out.mkdir(exist_ok=True)
    start, end = manifest['start'], manifest['end']
    index = dict(start=start, end=end, capture_id=directory.name,
                 timezone=config['timezone'], sites=[], classes=CLASSES, vehicles=sorted(VEHICLES))
    for site in config['sites']:
        code = site['id']
        issues = Counter()
        entry = custom.get(code)
        tracks, stats = extract(events(directory, code, issues), site, start, end, issues, calibration(entry))
        index['sites'].append({**site, **stats, 'calibrated_projection': entry is not None,
                               'calibration_source': entry.get('source') if entry else None})
        # gzip is served as HTTP Content-Encoding, reducing loopback transfer.
        target = out/(code+'.json.gz')
        tmp = target.with_suffix('.tmp')
        with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=3) as f:
            json.dump(tracks,f,separators=(',',':'),allow_nan=False)
        tmp.replace(target)
        print(f"{code}: {stats['frames']:,} saved frames, {stats['receipt_span_s']:.1f}s span, "
              f"{stats['gaps_over_3s']} gaps over 3s, {stats['fragments']:,} fragments",flush=True)
    index['state'] = manifest['state']
    index['unavailable'] = manifest.get('unavailable',{})
    atomic(out/'index.json', index)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path)
    p.add_argument('--calibration',type=Path)
    a=p.parse_args()
    directory=a.capture or BASE/json.loads((BASE/'latest.json').read_text())['capture_id']
    generate(directory,a.calibration)
