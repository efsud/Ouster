"""Generate the portable live-map setup guide with the bundled document runtime."""
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
d=Document();s=d.sections[0]
s.top_margin=s.bottom_margin=Inches(.7)
s.left_margin=s.right_margin=Inches(.75)
for name in ['Normal','Title','Heading 1','Heading 2']:
    style=d.styles[name];style.font.name='Calibri';style.font.color.rgb=RGBColor(0,0,0)
for style in d.styles:
    for e in style.element.xpath('.//w:pBdr'):e.getparent().remove(e)
d.styles['Normal'].font.size=Pt(11)
d.styles['Normal'].paragraph_format.space_after=Pt(8)
d.styles['Title'].font.size=Pt(25)
d.styles['Heading 1'].font.size=Pt(17)
def p(t):d.add_paragraph(t)
def h(t):d.add_heading(t,1)
def code(t):
    par=d.add_paragraph();par.paragraph_format.space_after=Pt(10)
    for i,line in enumerate(t.splitlines()):
        r=par.add_run(('\n' if i else '')+line);r.font.name='Consolas';r.font.size=Pt(9)
def table(headers,rows):
    t=d.add_table(rows=1,cols=len(headers));t.style='Table Grid'
    for c,x in zip(t.rows[0].cells,headers):c.text=x
    for row in rows:
        for c,x in zip(t.add_row().cells,row):c.text=x
    for i,row in enumerate(t.rows):
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        if i==0:row._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
        for c in row.cells:
            pr=c._tc.get_or_add_tcPr();b=OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');b.append(e)
            pr.append(b)
            if i==0:
                sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'DCE6F1');pr.append(sh)
            for par in c.paragraphs:
                par.paragraph_format.space_after=Pt(5);par.paragraph_format.space_before=Pt(5)
                for r in par.runs:r.font.size=Pt(10);r.bold=i==0

d.add_heading('Run the Ouster live map on another computer',0)
p('Toronto dashboard transfer and setup guide\nPrepared 16 October 2026')
p('Copy the application and its configuration, create a fresh Python environment, and sign in privately to BlueCity. The connected launcher starts both the local dashboard and the ten Toronto sensor recorders. Historical recordings are optional for a new live map.')
h('1 Prepare the destination computer')
p('Use Python 3.11, a modern browser, internet access and a BlueCity API account authorized for the requested sensors. These commands target macOS or Linux. On Windows, run them inside a Linux environment such as WSL; the current launcher uses Unix process controls and is not a native PowerShell launcher. Windows and Linux operation has not been validated in this session.')
h('2 Copy the project files')
p('Create an Ouster folder on the destination computer. Preserve the folder names and their relative structure.')
table(['Copy','Purpose'],[
('dashboard/ — entire folder','Python application and webpage assets, including static/vendor/.'),
('config/ — entire folder','Sensor inventory, coordinates, rotations and supporting configuration.'),
('scripts/ — entire folder','Connected launcher and maintenance tools.'),
('Data API/Realtime SDK/ wheel file','Install bctRealtimeSDK_Subscriber-3.1.0-py3-none-any.whl. Preserve its path.'),
('README.md and docs/','Recommended instructions, learning material and project documentation.')])
p('The current positions and per-intersection rotations are in config/sites.json. If config/sites.local.json exists, review and copy it only when its local overrides are intended for the destination; those overrides take precedence.')
p('Do not copy .venv/, node_modules/, __pycache__/, .DS_Store or .git/ for a simple runtime transfer. Recreate .venv on the new computer. Node.js is not required to run the bundled map. Do not transfer credentials or activation links as configuration.')

d.add_page_break();h('3 Install the Python environment')
p('Open Terminal on the destination computer. Replace /path/to/Ouster with the actual copied folder. Run these commands in order. If python3.11 is not found, install Python 3.11 first and reopen Terminal.')
code('cd "/path/to/Ouster"\npython3.11 --version\npython3.11 -m venv .venv\n.venv/bin/python -m pip install \\\n  "Data API/Realtime SDK/bctRealtimeSDK_Subscriber-3.1.0-py3-none-any.whl" \\\n  certifi')
p('The local SDK wheel installs its declared dependencies. Internet access may be needed to download them. No environment activation is required because every command uses the environment’s Python explicitly.')
h('4 Start the map and live recorders')
p('From the Ouster folder, run the following commands. The certificate setting enables verified HTTPS using the installed trusted certificate bundle.')
code('export SSL_CERT_FILE="$(\n  .venv/bin/python -c \'import certifi; print(certifi.where())\'\n)"\n\n.venv/bin/python scripts/start_connected.py --port 8766 --toronto')
p('Enter the BlueCity API username and password when prompted. The password is hidden while typing. The launcher keeps credentials in process memory and child-process environments; do not place them in source files or command arguments.')
p('This command starts both the server and all Toronto collectors. Do not also start open_dashboard.command on port 8766. The .command launchers are macOS conveniences and can use different ports; use the explicit command above for this setup.')
h('5 Open and verify the map')
p('Open this address in a browser on the destination computer:')
code('http://127.0.0.1:8766/')
for t in ['Select Live network and Toronto.', 'Leave Approximate live objects enabled.', 'Leave Per-intersection settings selected to preserve the configured site rotations.', 'Click a receiving intersection and zoom to level 17 or higher.', 'Check that receipt times advance and objects move. A reachable page alone does not prove live reception.']:
    d.add_paragraph(t,style='List Bullet')
p('Keep the Terminal open and the computer awake. Live objects older than five seconds are hidden. Sensor placement remains approximate; the display adjustments are not independently verified field calibration.')

d.add_page_break();h('6 Stop and restart later')
p('Press Ctrl+C in the connected launcher Terminal to stop the server and recorders. To start again, open Terminal, change to the Ouster folder, and repeat the certificate setting and launch command in step 4. Enter credentials again. Installation is only needed once per environment.')
h('7 Transfer historical data if needed')
p('For a fresh live map, omit data/. The application creates its database and recording files automatically. To carry existing history, stop every recorder and dashboard process that uses the source database, then copy the entire data/ folder. Keep the destination stopped during replacement. Do not overwrite an existing destination database unless you intend to replace that history.')
p('The data folder can be large. The application normally expires raw events 30 days after receipt; derived KPI and anomaly records remain. Copying old raw data does not disable that retention policy. Use a local writable folder with sufficient disk space rather than actively running the SQLite database inside a synchronized cloud folder.')
h('8 Troubleshoot startup and missing objects')
table(['Symptom','What to check'],[
('Page is not reachable','Keep the launcher running; read its Terminal error. Open the same port used in the launch command.'),
('Port 8766 is occupied','Stop the existing server, or launch with --port 8768 and open http://127.0.0.1:8768/.'),
('No objects on the map','Enable approximate objects, zoom to 17+, check fresh receipts and confirm internet access. Stale recordings are not replayed as live.'),
('Authentication or routing failure','Check the API account and sensor authorization. A sensor returning grpc_unauthenticated or beacon_http_404 may require Ouster assistance.'),
('Certificate verification fails','Repeat the SSL_CERT_FILE command after installing certifi. Do not disable certificate verification. Managed networks may require an approved CA bundle.'),
('Map tiles are blank','Check access to OpenStreetMap tile services. Background tiles need internet even though Leaflet itself is bundled.')])
p('127.0.0.1 means the computer opening the address. This server binds to that computer only; the link is not a public website or a link to your original Mac. A shared or hosted deployment requires a separate setup.')
p('Project references: scripts/start_connected.py; dashboard/server.py; dashboard/sdk_client.py; config/sites.json. Commands were checked against the project source. The destination machine still needs its own installation and live reception check.')
out=ROOT/'docs/Live_map_transfer_instructions.docx';d.save(out);print(out)
