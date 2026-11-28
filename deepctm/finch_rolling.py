"""Finch rolling figures using the shared bounded trajectory pipeline."""
from .florida_rolling import ROOT, main, read_snapshot as shared_snapshot
FOLDER = ROOT / 'data/finch-rolling'
def read_snapshot(now=None):
    return shared_snapshot(now, folder=FOLDER)
if __name__ == '__main__':
    main(region='Toronto', folder=FOLDER, source_name='finch-live.sqlite3')
