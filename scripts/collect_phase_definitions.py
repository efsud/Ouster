"""Fetch read-only phase definitions with a private terminal credential prompt."""
import getpass
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.bluecity import BlueCity

def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run in an interactive Terminal for private credential entry.')
    print('Read-only Toronto phase definitions. No sensor configuration changes.')
    os.environ['BLUECITY_USERNAME'] = input('BlueCity API username: ').strip()
    os.environ['BLUECITY_PASSWORD'] = getpass.getpass('BlueCity API password (hidden): ')
    client = BlueCity()
    destination = ROOT / 'data/cloud'
    destination.mkdir(parents=True, exist_ok=True)
    sites = json.loads((ROOT / 'config/sites.json').read_text())['sites']
    for site in (s for s in sites if s.get('region') == 'Toronto'):
        params = {'UDID': site['id'], 'active_only': 'false'}
        try:
            result = client.query('phases', params)
            path = destination / f'phases-{site["id"]}-{time.time_ns()}.json'
            path.write_text(json.dumps({'site': site['id'], 'retrieved_at': time.time(),
                                       'params': params, 'data': result,
                                       'realtime_identifier_mapping_verified': False}, indent=2))
            print(f'{site["name"]}: definitions saved; live identifier relationship remains unverified.', flush=True)
        except HTTPError as exc:
            print(f'{site["name"]}: HTTP {exc.code}.', flush=True)
            if exc.code in (401, 403):
                print('Stopped: check API credentials or permissions.');break
        except (URLError, TimeoutError):
            print('Network request failed; no definitions saved for this site. Retry when access is restored.');break
        except (ValueError, KeyError):
            print('Unexpected API response; definitions were not interpreted.');break
    os.environ.pop('BLUECITY_USERNAME', None)
    os.environ.pop('BLUECITY_PASSWORD', None)

if __name__ == '__main__':
    main()
