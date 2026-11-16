"""Conditional checks against saved vendor definitions, not a verified ID join."""
import json
from pathlib import Path
from functools import lru_cache
ROOT=Path(__file__).resolve().parent.parent

@lru_cache(maxsize=32)
def saved_definitions(site):
    paths=sorted((ROOT/'data/cloud').glob(f'phases-{site}-*.json'))
    if not paths:return {}
    try:
        value=json.loads(paths[-1].read_text())
        rows=value.get('data',[])
        if not isinstance(rows,list):return {}
        return {'retrieved_at':value.get('retrieved_at'),'rows':rows}
    except (OSError,ValueError):return {}

def check_definition(site,numbers,movement,definitions=None):
    value=saved_definitions(site) if definitions is None else definitions
    matches=[]
    for number in numbers:
        rows=[r for r in value.get('rows',[]) if r.get('active') is True and str(r.get('phase_label'))==str(number)]
        movements=set()
        for r in rows:
            allowed=r.get('allowed_movements',[])
            if isinstance(allowed,str):movements.update(x.strip().upper() for x in allowed.split(','))
            elif isinstance(allowed,list):
                for item in allowed:
                    if isinstance(item,dict) and str(item.get('trafficLightStatus','')).lower()=='green':
                        movements.add(str(item.get('turningMovement','')).upper())
        if movements:matches.append({'phase_number':str(number),'green_movements_if_label_matches':sorted(movements),'conflict':movement not in movements})
    return {'join_verified':False,'retrieved_at':value.get('retrieved_at'),'matches':matches,
            'conflict':any(m['conflict'] for m in matches),
            'note':'Conditional on phase_label matching phaseNumber; saved definitions may be outdated. Agreement does not verify the join.'}
