"""Exogenous signal permissions; no controller or signal optimization."""
from dataclasses import dataclass
from .inputs import Series, number

STATES = {'protected','permissive','rtor','red','yellow','all_red'}


@dataclass(frozen=True)
class Signal:
    changes: Series
    cycle_s: float | None
    offset_s: float
    lost_s: float
    alternate_vps: float

    @classmethod
    def load(cls, spec, turn):
        changes = Series.from_rows(spec['changes'])
        if set(changes.values)-STATES:
            raise ValueError('Unrecognized signal state')
        if ('rtor' in changes.values and
            (turn != 'R' or spec.get('rtor_verified') is not True)):
            raise ValueError('Right-on-red requires explicit permission on a right turn')
        if 'permissive' in changes.values and turn != 'L':
            raise ValueError('Permissive left state requires a left turn')
        cycle = spec.get('cycle_s')
        if cycle is not None:
            cycle = number(cycle,'cycle',1e-9)
            if cycle <= changes.times[-1]:
                raise ValueError('Cycle must extend beyond last phase change')
        offset = number(spec.get('offset_s',0),'offset')
        if cycle is None and offset:
            raise ValueError('Recorded intervals use aligned times, not an offset')
        alternate = number(spec.get('alternate_vph',0),'permissive capacity')/3600
        if set(changes.values)&{'rtor','permissive'} and 'alternate_vph' not in spec:
            raise ValueError('Explicit permissive/RTOR discharge capacity required')
        return cls(changes,cycle,offset,number(spec.get('lost_s',0),'lost time'),alternate)

    def limits(self,t):
        """Sending multiplier and cap in vehicles/second; phase evaluated at step start."""
        from bisect import bisect_right
        x = (t+self.offset_s)%self.cycle_s if self.cycle_s else t
        i = bisect_right(self.changes.times,x+1e-10)-1
        mode = self.changes.values[i]
        if mode in ('permissive','rtor'):
            return 1.,self.alternate_vps
        if mode != 'protected':
            return 0.,0.
        if not self.lost_s:
            return 1.,float('inf')
        j=i
        while j and self.changes.values[j-1]=='protected':
            j-=1
        age=x-self.changes.times[j]
        if j==0 and self.cycle_s:
            if all(v=='protected' for v in self.changes.values):
                return 1.,float('inf')
            k=len(self.changes.values)
            while self.changes.values[k-1]=='protected':
                k-=1
            if k < len(self.changes.values):
                age += self.cycle_s-self.changes.times[k]
        return min(1.,max(0.,age)/self.lost_s),float('inf')
