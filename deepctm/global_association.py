"""Partial min-cost matching with explicit unmatched endpoints and alternatives.

No FIFO assumption, hidden identity, or confidence-probability interpretation.
Edge exclusion compares the entire competing assignment, including unmatched
options. Independent candidate components keep the repeated solves bounded.
"""
import numpy as np
from scipy.optimize import linear_sum_assignment
from .spatial_bridges import pair_cost, curve


def solve_edges(nleft, nright, edges, unmatched_cost=.75, margin=.25):
    if unmatched_cost <= 0 or margin < 0:
        raise ValueError('Positive unmatched cost and nonnegative margin required')
    if not edges:
        return []
    adjacency = {}
    for i, j in edges:
        if not (0 <= i < nleft and 0 <= j < nright):
            raise ValueError('Endpoint index outside input')
        adjacency.setdefault(('a', i), set()).add(('b', j))
        adjacency.setdefault(('b', j), set()).add(('a', i))
    remaining = set(adjacency); result = []
    while remaining:
        pending = [min(remaining)]; component = set()
        while pending:
            node = pending.pop()
            if node in component:
                continue
            component.add(node); pending.extend(adjacency[node] - component)
        remaining -= component
        aa = sorted(i for side, i in component if side == 'a')
        bb = sorted(i for side, i in component if side == 'b')
        n, m = len(aa), len(bb)
        # Real rows/columns plus one dedicated unmatched choice per endpoint.
        matrix = np.full((n+m, m+n), np.inf)
        for row, i in enumerate(aa):
            for col, j in enumerate(bb):
                if (i, j) in edges:
                    cost = edges[i, j]
                    if not np.isfinite(cost) or cost < 0:
                        raise ValueError('Finite nonnegative edge costs required')
                    matrix[row, col] = cost
            matrix[row, m+row] = unmatched_cost
        for col in range(m):
            matrix[n+col, col] = unmatched_cost
        matrix[n:, m:] = 0
        rows, cols = linear_sum_assignment(matrix)
        optimum = float(matrix[rows, cols].sum())
        for row, col in zip(rows, cols):
            if row >= n or col >= m:
                continue
            cost = matrix[row, col]; matrix[row, col] = np.inf
            r, c = linear_sum_assignment(matrix)
            alternative = float(matrix[r, c].sum())
            matrix[row, col] = cost
            gap = max(0., alternative-optimum)
            # A tie is ambiguous even when the requested numerical margin is zero.
            if gap <= 1e-9 or gap+1e-9 < margin:
                continue
            result.append(dict(left=aa[row], right=bb[col], cost=float(cost),
                               margin=gap, alternative_objective=alternative,
                               component_objective=optimum,
                               identity='unverified_assignment_hypothesis'))
    return sorted(result, key=lambda r: (r['left'], r['right']))


def associate_global(left, right, threshold=1.5, margin=.25):
    edges = {}; paths = {}
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            if a.get('class_type') != b.get('class_type'):
                continue
            cost = pair_cost(a, b)
            if cost is None or cost > threshold:
                continue
            points = curve(a, b)
            if points is not None:
                edges[i, j] = cost; paths[i, j] = points
    matches = solve_edges(len(left), len(right), edges,
                          unmatched_cost=threshold/2, margin=margin)
    for match in matches:
        match['points'] = paths[match['left'], match['right']]
    return matches
