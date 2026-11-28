"""Explicit piecewise constant inputs. Times are seconds from the peak start."""
from bisect import bisect_right
import csv
from dataclasses import dataclass
from datetime import date
import math


def number(value, name, lower=0):
    value = float(value)
    if not math.isfinite(value) or value < lower:
        raise ValueError(f'{name} must be finite and >= {lower}')
    return value


@dataclass(frozen=True)
class Series:
    times: tuple
    values: tuple

    @classmethod
    def from_rows(cls, rows):
        times, values = zip(*rows)
        times = tuple(number(t, 'profile time') for t in times)
        if times[0] != 0 or any(a >= b for a,b in zip(times,times[1:])):
            raise ValueError('Profiles must start at zero and be strictly increasing')
        return cls(times, tuple(values))

    def at(self, t):
        return self.values[bisect_right(self.times, t + 1e-10) - 1]


def shares(row, movements):
    if set(row) != set(movements):
        raise ValueError(f'Turning ratios must cover {sorted(movements)}')
    row = {k:number(v, 'turn ratio') for k,v in row.items()}
    if not math.isclose(sum(row.values()),1,abs_tol=1e-9):
        raise ValueError('Turning ratios must sum to one')
    return [row.get(m,0.) for m in ('L','T','R')]


def load_observations(path):
    """Standardized independent observations, not raw trajectory estimates."""
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    seen = set()
    for row in rows:
        row['date'] = date.fromisoformat(row['date']).isoformat()
        if row['peak'] not in ('AM','PM'):
            raise ValueError('peak must be AM or PM')
        row['end_s'] = number(row['end_s'],'observation bin end')
        row['value'] = number(row['value'],'observed value')
        if not row['source'].strip():
            raise ValueError('Observation provenance is required')
        key = tuple(row[k] for k in ('date','peak','end_s','target','metric'))
        if key in seen:
            raise ValueError(f'Duplicate observation {key}')
        seen.add(key)
    return rows
