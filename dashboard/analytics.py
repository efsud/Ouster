"""Explicit, unit-aware calculations from the supplied LaTeX specification.

Inputs are annotated observations, not unvalidated raw detections. None means
unavailable. Half-open reporting windows prevent counting a boundary twice.
"""
import math
from statistics import mean

METRICS = {
    'control_delay': ('Control delay', 's/veh'),
    'stopped_delay': ('Stopped delay', 's/veh'),
    'queue_p95': ('Queue length · P95', 'm'),
    'aog': ('Arrivals on green', '%'),
    'split_failure': ('Split failure', '% cycles'),
    'volume': ('Approach volume', 'veh/h'),
    'discharge': ('Discharge rate', 'veh/h/lane'),
}

def finite(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name} must be >= {minimum}')
    return value

def percentile(values, p):
    if not values:
        return None
    a = sorted(values)
    pos = (len(a)-1)*p
    lo, hi = math.floor(pos), math.ceil(pos)
    return a[lo] + (a[hi]-a[lo])*(pos-lo)

def calculate(window):
    """Calculate one site/approach window; see docs/data-contract.md."""
    if not isinstance(window,dict): raise ValueError('Each window must be an object')
    for key in ['tracks','queue_samples','cycles']:
        if not isinstance(window.get(key,[]),list) or any(not isinstance(item,dict) for item in window.get(key,[])):
            raise ValueError(f'{key} must be an array of objects')
    start = finite(window['start'], 'start')
    end = finite(window['end'], 'end')
    if end <= start:
        raise ValueError('end must follow start')
    coverage = finite(window.get('coverage', 0), 'coverage', 0)
    if coverage > 1:
        raise ValueError('coverage must be a fraction from 0 to 1')
    length = finite(window['length_m'], 'length_m', 0.001)
    free_speed = finite(window['free_speed_mps'], 'free_speed_mps', 0.001)
    lanes = finite(window['lanes'], 'lanes', 1)
    if int(lanes) != lanes:
        raise ValueError('lanes must be an integer')
    tracks, seen = [], set()
    for track in window.get('tracks', []):
        tid = track['id']
        if not isinstance(tid,str) or not tid:
            raise ValueError('Trajectory id must be a nonempty string')
        if tid in seen:
            raise ValueError('Duplicate physical trajectory id; deduplicate before import')
        seen.add(tid)
        gap = finite(track['max_gap_s'], 'max_gap_s', 0)
        for key in ['entry', 'arrival', 'exit']:
            if track.get(key) is not None:
                finite(track[key], key)
        if track.get('entry') is not None and track.get('arrival') is not None and track['arrival'] < track['entry']:
            raise ValueError('arrival precedes entry')
        if track.get('exit') is not None and track.get('arrival') is not None and track['exit'] < track['arrival']:
            raise ValueError('exit precedes arrival')
        if track.get('stopped_s') is not None:
            finite(track['stopped_s'], 'stopped_s', 0)
            if track.get('entry') is not None and track.get('exit') is not None and track['stopped_s'] > track['exit']-track['entry']:
                raise ValueError('Stopped time exceeds observed traversal duration')
        if track.get('vehicle') is True and gap <= 3:
            tracks.append(track)
    arrivals = [t for t in tracks if t.get('arrival') is not None and start <= t['arrival'] < end]
    complete = [t for t in arrivals if t.get('entry') is not None and t.get('complete') is True]
    stopped = [t['stopped_s'] for t in complete if t.get('exit') is not None and t.get('stopped_s') is not None]
    delays = [t['arrival']-t['entry']-length/free_speed for t in complete]
    entries = [t for t in tracks if t.get('entry') is not None and start <= t['entry'] < end]
    queue = []
    queue_times = []
    for q in window.get('queue_samples', []):
        finite(q['time'], 'queue time')
        finite(q['length_m'], 'queue length', 0)
        if start <= q['time'] < end and q.get('visible') is True:
            queue.append(q['length_m'])
        queue_times.append(q['time'])
    if len(set(queue_times)) != len(queue_times):
        raise ValueError('Duplicate queue sample times')
    if len(queue_times)>2:
        ordered=sorted(queue_times)
        spacing=ordered[1]-ordered[0]
        if any(not math.isclose(b-a,spacing,rel_tol=1e-5,abs_tol=1e-6) for a,b in zip(ordered,ordered[1:])):
            raise ValueError('Queue samples must use a regular time grid; mark missing visibility explicitly')
    synchronized = window.get('signal_synchronized') is True
    signal_arrivals = [t for t in arrivals if isinstance(t.get('green'), bool)]
    cycles = []
    for c in window.get('cycles', []):
        finite(c['start'], 'cycle start'); finite(c['end'], 'cycle end')
        finite(c['residual_queue_m'], 'residual queue', 0)
        if c['end'] <= c['start']:
            raise ValueError('cycle end must follow cycle start')
        if start <= c['start'] and c['end'] <= end and c.get('visible') is True:
            cycles.append(c)
    ordered_cycles=sorted(cycles,key=lambda c:c['start'])
    if any(a['end']>b['start'] for a,b in zip(ordered_cycles,ordered_cycles[1:])):
        raise ValueError('Complete cycles cannot overlap')
    green_seconds = window.get('green_seconds')
    if green_seconds is not None:
        finite(green_seconds, 'green_seconds', 0)
        if green_seconds > end-start:
            raise ValueError('green_seconds exceeds reporting window')
    departures = [t for t in tracks if t.get('exit') is not None and start <= t['exit'] < end and t.get('departed_from_queue_on_green') is True]
    values = {
        'control_delay': mean(delays) if delays else None,
        'stopped_delay': mean(stopped) if stopped else None,
        'queue_p95': percentile(queue, .95),
        'aog': 100*sum(t['green'] for t in signal_arrivals)/len(arrivals) if synchronized and arrivals and len(signal_arrivals) == len(arrivals) else None,
        'split_failure': 100*sum(c['residual_queue_m'] > 0 for c in cycles)/len(cycles) if synchronized and cycles else None,
        'volume': len(entries)*3600/(end-start) if window.get('entry_observation_complete') is True else None,
        'discharge': len(departures)*3600/green_seconds/lanes if synchronized and green_seconds and window.get('departure_observation_complete') is True else None,
    }
    flags = []
    if coverage < .8: flags.append('Coverage below 80%')
    if len(complete) < 15: flags.append('Fewer than 15 valid traversals')
    if not synchronized: flags.append('Signal clocks not verified')
    if any(d < 0 for d in delays): flags.append('Negative delay: review free-flow calibration')
    if not queue: flags.append('No visible queue samples')
    return {'values': values, 'quality': {'valid_tracks':len(complete), 'coverage':coverage, 'complete_cycles':len(cycles), 'visible_queue_samples':len(queue), 'excluded_tracks':len(window.get('tracks', []))-len(tracks), 'status':'provisional' if flags else 'passes-input-checks', 'flags':flags}}

def local_to_geo(x, y, latitude, longitude, rotation_deg):
    """Local tangent-plane approximation: x east, y north, CCW rotation.

    For intersection footprints only; origin/rotation must be field validated.
    This is an independent implementation pending the user's original script.
    """
    for name, v in locals().copy().items(): finite(v, name)
    if not -85 < latitude < 85 or not -180 <= longitude <= 180:
        raise ValueError('Origin outside supported coordinate range')
    if math.hypot(x, y) > 5000:
        raise ValueError('Local tangent approximation limited to 5 km')
    theta = math.radians(rotation_deg)
    east, north = x*math.cos(theta)-y*math.sin(theta), x*math.sin(theta)+y*math.cos(theta)
    return [latitude + math.degrees(north/6378137), longitude + math.degrees(east/(6378137*math.cos(math.radians(latitude))))]

def simulate(params):
    """Single lane, triangular-FD CTM; no claim of calibrated field prediction."""
    demand = finite(params.get('demand', 900), 'demand', 0)
    green = finite(params.get('green', 45), 'green', 0)
    cycle = finite(params.get('cycle', 90), 'cycle', 1)
    offset = finite(params.get('offset', 15), 'offset', 0)
    count = params.get('intersections', 3)
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 7:
        raise ValueError('intersections must be an integer from 1 to 7')
    if demand > 3000 or cycle > 180 or green > cycle:
        raise ValueError('Use demand <= 3000 veh/h, cycle <= 180 s, green <= cycle')
    # dx >= max(v,w)*dt is the CFL condition. n is vehicles per cell.
    dx, dt, v, w, jam = 50., 2., 13.89, 5., .15
    capacity = v*w*jam/(v+w)
    n = [0.]*(count*6)
    history, admitted, departed, backlog = [], 0., 0., 0.
    total_time, excess_time = 0., 0.
    for step in range(450):
        t = step*dt
        send = [min(v*a/dx, capacity)*dt for a in n]
        receive = [min(capacity, w*(jam-a/dx))*dt for a in n]
        backlog += demand/3600*dt
        inflow = min(backlog, receive[0]); backlog -= inflow
        flows = [inflow]
        for j in range(len(n)):
            f = min(send[j], receive[j+1]) if j+1 < len(n) else send[j]
            if (j+1)%6 == 0 and (t-(j//6)*offset)%cycle >= green:
                f = 0.
            flows.append(f)
        admitted += inflow; departed += flows[-1]
        total_time += sum(n)*dt
        # Macroscopic excess time against free-flow movement within cells.
        excess_time += sum(max(0, n[j]-flows[j+1]*dx/(v*dt))*dt for j in range(len(n)))
        n = [n[j]+flows[j]-flows[j+1] for j in range(len(n))]
        if step%5 == 0:
            history.append({'time':t+dt,'density':[round(a/dx*1000,2) for a in n], 'queue_m':sum(dx for j,a in enumerate(n) if a/dx > capacity/v), 'backlog':round(backlog,3)})
    return {'history':history, 'admitted':admitted, 'departed':departed, 'remaining':sum(n), 'backlog':backlog, 'conservation_error':admitted-departed-sum(n), 'vehicle_hours':total_time/3600, 'excess_vehicle_hours':excess_time/3600, 'cell_length_m':dx, 'capacity_veh_h':capacity*3600, 'jam_density':jam*1000, 'source':'Uncalibrated CTM simulation', 'duration_s':900}
