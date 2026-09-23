"""Run a read-only stream recorder with the provided BlueCity SDK.

python -m dashboard.collector --site SENSOR_UDID
Credentials come from environment variables or an interactive password prompt.
"""
import argparse
from datetime import datetime, timezone
import getpass
import os
import time
from .storage import Store

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', required=True)
    args = parser.parse_args()
    from realtime_subscriber.Realtime_subscriber_api import BCTWSConnection
    from google.protobuf.json_format import MessageToDict
    username = os.getenv('BLUECITY_USERNAME') or input('BlueCity username: ')
    password = os.getenv('BLUECITY_PASSWORD') or getpass.getpass('BlueCity password: ')
    db = Store(os.getenv('OUSTER_DB','data/ouster.sqlite3'))
    stream = BCTWSConnection(UDID=args.site,username=username,password=password,singleton=True,
        subscriptions=[BCTWSConnection.subscriptionOption.FRAME,BCTWSConnection.subscriptionOption.PHASE_CHANGE,BCTWSConnection.subscriptionOption.LOOP_CHANGE],semantic_abs=False)
    print('Recording read-only frames and phase events. Ctrl+C stops collection.')
    try:
        while True:
            event = MessageToDict(stream.get_hyperparameter())
            stamp = event.get('frame',{}).get('timestamp') or event.get('timestamp')
            if not stamp:
                continue  # Receipt time must not masquerade as sensor time.
            timestamp = datetime.fromisoformat(stamp.replace('Z','+00:00'))
            if timestamp.tzinfo is None:
                continue  # Require a verified timezone instead of assuming one.
            db.save_event(args.site,timestamp.timestamp(),event)
    except KeyboardInterrupt:
        print('\nRecording stopped; local data retained.')

if __name__ == '__main__':
    main()
