"""Build the Word reference from locally saved Phase Details responses."""
from collections import Counter
import json
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT

ROOT=Path(__file__).resolve().parents[1]
sites=[s for s in json.loads((ROOT/'config/sites.json').read_text())['sites'] if s['region']=='Toronto']
records={}; sources={}
for s in sites:
    path=sorted((ROOT/'data/cloud').glob(f'phases-{s["id"]}-*.json'))[-1]
    sources[s['id']]=path.name
    data=json.loads(path.read_text())
    records[s['id']]={int(p['phase_label']):p for p in data['data'] if p.get('active')}

def signature(p):
    return (p['approach'],tuple(sorted((m['turningMovement'],m['trafficLightStatus']) for m in p['allowed_movements']))) if p else None

# The modal definition among present active records is a comparison aid only.
baseline={}
for n in range(1,15):
    present=[p[n] for p in records.values() if n in p]
    if present:
        common=Counter(signature(p) for p in present).most_common(1)[0][0]
        baseline[n]=next(p for p in present if signature(p)==common)

names={'N':'North','S':'South','E':'East','W':'West'}
def flows(p):
    if not p:return 'Not returned'
    return '; '.join(names[m[0]]+' to '+names[m[1]] for m in sorted({x['turningMovement'] for x in p['allowed_movements']}))
def codes(p):
    if not p:return 'Not returned'
    by={}
    for x in p['allowed_movements']:by.setdefault(x['turningMovement'],set()).add(x['trafficLightStatus'][0].upper())
    return '; '.join(k+' ['+'/'.join(sorted(v))+']' for k,v in sorted(by.items()))

doc=Document();sec=doc.sections[0]
sec.top_margin=sec.bottom_margin=Inches(.65);sec.left_margin=sec.right_margin=Inches(.7)
sec.page_width=Inches(8.5);sec.page_height=Inches(11)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2']:
    st=doc.styles[name];st.font.name='Calibri';st.font.color.rgb=RGBColor(0,0,0)
for st in doc.styles:
    for border in st.element.xpath('.//w:pBdr'):
        border.getparent().remove(border)
doc.styles['Normal'].font.size=Pt(10)
doc.styles['Normal'].paragraph_format.space_after=Pt(7)
doc.styles['Title'].font.size=Pt(25)
doc.styles['Heading 1'].font.size=Pt(16)
doc.styles['Heading 2'].font.size=Pt(12)
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('Toronto signal decoder  |  ')
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)

def para(t):doc.add_paragraph(t)
def heading(t):doc.add_heading(t,1)
def table(headers,rows,widths,size=9):
    t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    for c,w in zip(t.columns,widths):c.width=Inches(w)
    for cell,h in zip(t.rows[0].cells,headers):cell.text=h
    for row in rows:
        for c,v in zip(t.add_row().cells,row):c.text=str(v)
    borders=OxmlElement('w:tblBorders')
    for edge in ['top','left','bottom','right','insideH','insideV']:
        e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
    t._tbl.tblPr.append(borders)
    for i,row in enumerate(t.rows):
        cant=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(cant)
        if i==0:row._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
        for j,cell in enumerate(row.cells):
            cell.width=Inches(widths[j]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr=cell._tc.get_or_add_tcPr();shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'DCE6F1' if i==0 else ('F4F6F8' if i%2==0 else 'FFFFFF'));pr.append(shade)
            margins=OxmlElement('w:tcMar')
            for edge,value in [('top','45'),('bottom','45'),('left','75'),('right','75')]:
                e=OxmlElement('w:'+edge);e.set(qn('w:w'),value);e.set(qn('w:type'),'dxa');margins.append(e)
            pr.append(margins)
            for p in cell.paragraphs:
                p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1
                if j==0:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:run.font.size=Pt(size);run.bold=i==0
    return t

doc.add_heading('Toronto intersection signal decoder',0)
para('Unified reference and intersection exceptions')
para('Configuration snapshot 2 October 2026  |  Prepared 5 October 2026')
para('This guide translates the configured phase labels for ten Finch Avenue West intersections into vehicle entry and exit directions. A common pattern describes many records, but intersection-specific exceptions must always override it. The pattern is a reference for this snapshot, not a universal BlueCity numbering standard.')
heading('How to read a movement')
para('The first letter is the side from which a vehicle enters; the second is the side toward which it leaves. WE means west to east. WN means west to north. The approach identifies the entry leg. These compass labels describe the configured approaches, not surveyed signal-head positions or an exact vehicle bearing.')
table(['Code','Entry side','Exit side'],[(c,names[c[0]],names[c[1]]) for c in ['NS','SN','EW','WE','NE','NW','SE','SW','EN','ES','WN','WS']],[1,3,3.1])
heading('Configuration and live colour are separate')
para('phase_label names a configured phase; phase_id identifies its configuration record. Neither is a verified join to the live phaseNumber. active means the configuration is in effect, not that the signal is green. Missing active records do not prove a road movement or physical light is absent.')
para('The API returned trafficLightStatus text inside allowed_movements. Its meaning in this endpoint is undocumented. G and R in this guide preserve that green or red text without treating it as a current colour or a verified permission to move. A live colour requires a timestamped PhaseChange and a verified phase mapping.')

doc.add_page_break();heading('Common phase label pattern')
para('For each label, the baseline below is the most frequent approach and movement/status configuration among intersections where that label was returned as active. Missing labels are not filled in. The match count is out of all ten intersections and includes the nested G/R entries, not just directions.')
table(['Label','Typical configured flows','Matching sites'],[(n,flows(baseline.get(n)),f"{sum(signature(r.get(n))==signature(baseline[n]) for r in records.values())}/10" if n in baseline else 'Absent in 10/10') for n in range(1,15)],[.6,5.3,1.2],10)
heading('Apply the decoder in this order')
for t in ['1. Select the exact intersection UDID and the applicable configuration version.',
          '2. Look up the returned active record for the phase label. If absent, report not returned; do not substitute the baseline.',
          '3. Decode each movement code as entry side to exit side. Preserve its attached status text separately.',
          '4. Use the intersection tables and exceptions on the following pages. They take precedence over the common pattern.',
          '5. Add a live colour only after independently verifying the configuration-to-live identifier relationship.']:
    para(t)
para('Labels 1 and 11, and labels 5 and 12, often have matching configuration associations. They remain separate records. Equal configured movements do not imply identical live states or the same physical light.')

doc.add_page_break();heading('Exceptions for each intersection')
para('Every difference from the common pattern is listed below. Status-only changes are included because collapsing them would lose information from the actual response. Labels 9 and 13 are absent from all ten active configurations, so they are not repeated as site exceptions.')
exception_rows=[]
for s in sites:
    rs=records[s['id']];missing=[str(n) for n in baseline if n not in rs]
    changed=[n for n in baseline if n in rs and signature(rs[n])!=signature(baseline[n])]
    desc=[]
    if missing:desc.append('Not returned: '+', '.join(missing)+'.')
    for n in changed:desc.append(f"Label {n}: {codes(rs[n])}.")
    exception_rows.append((s['name'].replace('Finch W & ','').replace(' (LRT)',''), ' '.join(desc) or 'No differences from the common pattern.'))
table(['Intersection','Exceptions or replacement entries'],exception_rows,[1.15,5.95],9)
heading('What the recording confirms')
para('The 5 October Driftwood sample showed a repeating pattern near 130 seconds and matching observed live pairs 1/5, 2/6, 4/8, 9/11, 10/12 and 13/14. These pairs differ from the repeated configuration associations. Live channels 9 and 13 were present even though those configuration labels were absent. This supports keeping the configuration lookup and live decoder separate.')
para('Some channels reported long yellow intervals. Channel type and the phase_type codes remain unverified; this document does not identify pedestrian channels, physical heads or controller permissions from those values.')

for i,s in enumerate(sites):
    if i%2==0:doc.add_page_break()
    heading(s['name'].replace(' (LRT)','').replace('&','and'))
    para(s['id']+'  |  Active records from the 2 October 2026 response')
    rs=records[s['id']]
    table(['Label','From','To','Raw movement and status entries'],[(n,names[rs[n]['approach']] if n in rs else '—',', '.join(names[c] for c in sorted({m['turningMovement'][1] for m in rs[n]['allowed_movements']})) if n in rs else 'Not returned',codes(rs.get(n))) for n in range(1,15)],[.5,.65,1.35,4.6],9)
    p=doc.add_paragraph('G = green text; R = red text in configuration. These are not live colours.');p.paragraph_format.space_after=Pt(10)
    for r in p.runs:r.font.size=Pt(8)

doc.add_page_break();heading('Evidence and validation')
para('Source definitions: Ouster BlueCity Traffic Data API Manual, section 2.3 Movement Codes and section 3.4.1 Phase Details. The actual endpoint responses differ from the manual example: allowed_movements is a list of movement/status objects, not a comma-separated string. The nested trafficLightStatus semantics and phase_type codes are not defined in that section.')
para('All ten source responses were retrieved on 2 October 2026 with active_only=false; this guide filters to active=true. The underlying requests are read-only. This is a dated configuration reference, not a new API query or verification of today’s settings.')
table(['Intersection','UDID','Active labels'],[(s['name'].replace('Finch W & ','').replace(' (LRT)',''),s['id'],', '.join(map(str,sorted(records[s['id']])))) for s in sites],[1.2,2.2,3.7],9)
heading('Reproducibility')
para('The source files are retained locally under data/cloud/phases-<UDID>-<retrieval timestamp>.json. The guide generator reads the latest saved response for each UDID. It computes the common pattern from complete approach and movement/status signatures, then derives every exception from the same records. All 140 label slots are represented in the intersection tables.')
para('Validation checks: ten unique sites; no duplicate active labels per site; labels 1–14 represented for every site; each movement’s entry letter agrees with its approach; every exception differs from the common signature. No default movement is inserted for missing labels. The document is also rendered and visually reviewed before delivery.')
heading('Information still needed for live directional decoding')
para('Confirm how phase_label or phase_id maps to live phaseNumber; explain nested trafficLightStatus and phase_type; resolve live channels without matching active labels; and verify physical signal locations separately. Until then, this guide decodes configured flow associations only. Corridor coordination additionally requires synchronized recordings from multiple intersections.')

for s in sites:
    raw=json.loads((ROOT/'data/cloud'/sources[s['id']]).read_text())['data']
    active=[p for p in raw if p.get('active')]
    assert len(active)==len(records[s['id']])
    assert all(m['turningMovement'][0]==p['approach'] for p in active for m in p['allowed_movements'])
assert len(sites)==len(records)==10
assert sum(len(t.rows)-1 for t in doc.tables[3:13])==140
out=ROOT/'docs/Toronto_signal_decoder.docx';doc.save(out)
print(out)
