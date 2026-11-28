"""Compile homogeneous lane sections at actual split and stop-line boundaries."""
from dataclasses import dataclass
import math
import numpy as np
from .inputs import Series, number, shares
from .signals import Signal

TURNS=('L','T','R')


@dataclass(frozen=True)
class Section:
    id: str
    link: str
    lanes: tuple
    start_m: float
    end_m: float
    turns: tuple
    vf: float
    wave: float
    jam: float
    bay: bool
    xy: tuple

    @classmethod
    def load(cls,row):
        a,b = (number(row[key],key) for key in ('start_m','end_m'))
        lanes,turns=tuple(row['lane_ids']),tuple(row['turns'])
        if (b<=a or not lanes or len(set(lanes))!=len(lanes) or not turns
                or len(set(turns))!=len(turns) or not set(turns)<=set(TURNS)):
            raise ValueError(f"Invalid geometry/turn permissions: {row['id']}")
        xy=tuple(tuple(map(float,p)) for p in row['xy'])
        if (len(xy)<2 or any(len(p)!=2 or not all(map(math.isfinite,p)) for p in xy)
                or not math.isclose(sum(math.dist(p,q) for p,q in zip(xy,xy[1:])),b-a,
                                    rel_tol=.005,abs_tol=.05)):
            raise ValueError(f"Centerline length does not match station interval: {row['id']}")
        return cls(row['id'],row['link'],lanes,a,b,turns,
                   number(row['vf_mps'],'free-flow speed',1e-6),
                   number(row['wave_mps'],'wave speed',1e-6),
                   number(row['jam_veh_per_m_lane'],'jam density',1e-6),
                   bool(row.get('bay')),xy)


@dataclass(frozen=True)
class Cell:
    id: str
    section: Section
    start_m: float
    end_m: float

    @property
    def length(self):
        return self.end_m-self.start_m


@dataclass(frozen=True)
class Edge:
    id: str
    src: int
    dst: int
    turn: int
    distribution: Series | None = None
    signal: Signal | None = None
    cap_vps: Series | None = None


def ratios(rows, turns):
    return Series.from_rows([(t,shares(p,turns)) for t,p in rows])


class Network:
    def __init__(self, spec):
        self.spec=spec
        ids=spec['intersections']
        if len(set(ids))!=len(ids) or not ids:
            raise ValueError('Intersection identifiers must be nonempty and unique')
        if not spec['synthetic'] and (spec.get('geometry_verified') is not True or
                                     not spec.get('geometry_source') or not spec.get('signal_source')):
            raise ValueError('Field runs require verified geometry and provenance for geometry and signals')
        self.sections={s.id:s for s in map(Section.load,spec['sections'])}
        if len(self.sections)!=len(spec['sections']) or not self.sections:
            raise ValueError('Section IDs must be unique and nonempty')
        sections=list(self.sections.values())
        by_lane={}
        for s in sections:
            for lane in s.lanes:
                by_lane.setdefault((s.link,lane),[]).append((s.start_m,s.end_m))
        for key,ranges in by_lane.items():
            ranges.sort()
            if any(abs(b-c)>1e-6 for (_,b),(c,_) in zip(ranges,ranges[1:])):
                raise ValueError(f'Overlapping or discontinuous physical lane sections: {key}')
        requested=number(spec.get('dt_s',1),'time step',1e-9)
        min_length=number(spec.get('min_cell_m',15),'min cell length',1e-9)
        shortest=min((s.end_m-s.start_m)/max(s.vf,s.wave) for s in sections)
        cells=[]; ends={}
        # Use the LightSim count at a feasible common step, then check both speeds.
        divide=max(1,math.ceil(requested/shortest))
        dt=requested/divide
        counts=[max(1,math.floor((s.end_m-s.start_m)/max(min_length,s.vf*dt))) for s in sections]
        # A faster backward wave can require fewer cells than the nominal rule.
        counts=[min(n,max(1,math.floor((s.end_m-s.start_m)/(max(s.vf,s.wave)*dt)+1e-10)))
                for s,n in zip(sections,counts)]
        self.dt=dt
        edges=[]
        for s,n in zip(sections,counts):
            first=len(cells); dx=(s.end_m-s.start_m)/n
            for j in range(n):
                idx=len(cells)
                cells.append(Cell(f'{s.id}:{j}',s,s.start_m+j*dx,s.start_m+(j+1)*dx))
                if j:
                    edges.extend(Edge(f'{s.id}:{j-1}>{j}:{m}',idx-1,idx,TURNS.index(m)) for m in s.turns)
            ends[s.id]=(first,len(cells)-1)
        signal_ids=set()
        for e in spec['connections']:
            s=self.sections[e['from']]; d=self.sections[e['to']] if e.get('to') else None
            turn=e['turn']
            if turn not in s.turns:
                raise ValueError(f'Turn {turn} not permitted in {s.id}')
            signal=None
            if 'signal' in e:
                if e.get('intersection') not in ids:
                    raise ValueError('Unknown signalized intersection')
                signal_ids.add(e['intersection'])
                signal=Signal.load(e['signal'],turn)
                if signal.cycle_s is None and e['signal'].get('valid_until_s',0)<spec['duration_s']:
                    raise ValueError('Recorded signal coverage does not extend through the peak')
            distribution=None
            if d:
                if signal is None:
                    if s.link != d.link or abs(s.end_m-d.start_m)>1e-6:
                        raise ValueError('Unsignalized physical split must meet on the same link')
                    if turn not in d.turns or 'next_ratios' in e:
                        raise ValueError('A split must preserve assigned turn intent')
                    if s.bay or (len(s.turns)==1 and s.lanes != d.lanes):
                        raise ValueError('No lateral transfer after commitment to a lane group')
                else:
                    distribution=ratios(e['next_ratios'],d.turns)
            if not d and 'next_ratios' in e:
                raise ValueError('A terminal exit cannot reassign a turning ratio')
            edges.append(Edge(e['id'],ends[s.id][1],ends[d.id][0] if d else -1,
                              TURNS.index(turn),distribution,signal,
                              Series.from_rows([(t,number(v,'exit capacity')/3600) for t,v in e['capacity_vph']])
                              if 'capacity_vph' in e else None))
        if signal_ids!=set(ids):
            raise ValueError('Every intersection needs an explicit signalized movement')
        if len({e.id for e in edges})!=len(edges):
            raise ValueError('Duplicate edge ID')
        required={(i,TURNS.index(m)) for i,c in enumerate(cells) for m in c.section.turns}
        assignments=[(e.src,e.turn) for e in edges]
        if set(assignments)!=required or len(set(assignments))!=len(assignments):
            raise ValueError('Every cell/turn needs exactly one path; no ambiguous lane switching')
        self.cells,self.edges,self.ends=cells,edges,ends
        self.sources=[]
        source_ids=set()
        for o in spec['origins']:
            if o['id'] in source_ids:
                raise ValueError('Duplicate origin')
            source_ids.add(o['id'])
            section=self.sections[o['to']]
            self.sources.append((o['id'],ends[section.id][0],
                  Series.from_rows([(t,number(v,'demand')/3600) for t,v in o['demand_vph']]),
                  ratios(o['ratios'],section.turns)))
        self.withdrawals=[]
        for o in spec.get('withdrawals',[]):
            self.withdrawals.append((o['id'], ends[o['from']][1],
                Series.from_rows([(t,number(v,'midblock exit demand')/3600) for t,v in o['rate_vph']])))
        if len({o[0] for o in self.withdrawals})!=len(self.withdrawals):
            raise ValueError('Duplicate midblock sink')
        self.length=np.array([c.length for c in cells])
        self.lanes=np.array([len(c.section.lanes) for c in cells])
        self.v=np.array([c.section.vf for c in cells])
        self.w=np.array([c.section.wave for c in cells])
        self.jam=np.array([c.section.jam for c in cells])
        self.capacity=self.v*self.w*self.jam/(self.v+self.w)*self.lanes
        self.storage=self.jam*self.length*self.lanes
        if np.any(dt*np.maximum(self.v,self.w)>self.length+1e-8):
            raise ValueError('Infeasible CFL discretization')
        def aligned(t):
            return math.isclose(t/dt,round(t/dt),rel_tol=0,abs_tol=1e-7)
        clocks=[spec['duration_s'],spec['output_bin_s']]
        for e in edges:
            for series in (e.distribution,e.cap_vps,e.signal.changes if e.signal else None):
                if series is not None: clocks.extend(series.times)
            if e.signal:
                clocks.append(e.signal.offset_s)
                if e.signal.cycle_s: clocks.append(e.signal.cycle_s)
        for _,_,d,r in self.sources:
            clocks.extend(d.times+r.times)
        for _,_,r in self.withdrawals:
            clocks.extend(r.times)
        if not all(aligned(t) for t in clocks):
            raise ValueError('Input change points and reporting intervals must align with the simulation step')
