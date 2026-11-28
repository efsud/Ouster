import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description='Passenger-car movement-group CTM')
    commands=p.add_subparsers(dest='command',required=True)
    for name in ('simulate','geometry','experiment'):
        cmd=commands.add_parser(name)
        cmd.add_argument('config',type=Path)
        cmd.add_argument('output',type=Path)
    profile=commands.add_parser('profiles')
    for key in ('network','profile_csv','output'):
        profile.add_argument(key,type=Path)
    audit=commands.add_parser('audit-recordings')
    audit.add_argument('root',type=Path)
    car=commands.add_parser('car-counts')
    for key in ('capture','gate_config','output'):
        car.add_argument(key,type=Path)
    a=p.parse_args()
    if a.command=='audit-recordings':
        from .observations import archive_audit
        report=archive_audit(a.root)
    elif a.command=='car-counts':
        from .trajectory_counts import convert
        report=convert(a.capture,a.gate_config,a.output)
    elif a.command=='profiles':
        from .profiles import overlay
        from .cells import Network
        spec=overlay(json.loads(a.network.read_text()),a.profile_csv)
        Network(spec)
        a.output.write_text(json.dumps(spec,indent=2))
        report={'validated_profile_config':str(a.output)}
    elif a.command=='geometry':
        from .geometry import download
        report=download(json.loads(a.config.read_text()),a.output)
    elif a.command=='experiment':
        from .experiments import execute
        report=execute(a.config,a.output)
    else:
        from .cells import Network
        from .engine import run
        from .output import simulation
        spec=json.loads(a.config.read_text())
        net=Network(spec)
        rows,report,density=run(net,seed=spec.get('seed',42),history=True)
        simulation(net,rows,report,density,a.output)
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
