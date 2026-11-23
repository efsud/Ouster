"""Visible endpoint context independent of acquisition cadence.

Keep the legacy five points at low rates. At higher rates expand only on the
observed side until at least one second is available; never cross a gap.
"""
def select(points,exit_side,minimum_seconds=1.,minimum_samples=5):
    if len(points)<=minimum_samples:return points
    count=minimum_samples
    anchor=points[-1][0] if exit_side else points[0][0]
    while count<len(points):
        edge=points[-count][0] if exit_side else points[count-1][0]
        if abs(anchor-edge)>=minimum_seconds:break
        count+=1
    return points[-count:] if exit_side else points[:count]
