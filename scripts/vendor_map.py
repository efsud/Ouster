"""Copy the pinned npm Leaflet distribution into the local dashboard."""
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
target=root/'dashboard/static/vendor'
target.mkdir(parents=True,exist_ok=True)
for name in ['leaflet.js','leaflet.css']:
    shutil.copyfile(root/'node_modules/leaflet/dist'/name,target/name)
shutil.copyfile(root/'node_modules/leaflet/LICENSE',target/'LICENSE')
shutil.copytree(root/'node_modules/leaflet/dist/images',target/'images',dirs_exist_ok=True)
print('Copied Leaflet 1.9.4 and its license to dashboard/static/vendor.')
