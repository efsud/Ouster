"""Compose the portfolio screen recordings, readable subtitles and title cards."""
from pathlib import Path
import json, re, subprocess, textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/portfolio'
OUT=ROOT/'docs/portfolio'
FFMPEG=next((WORK/'runtime/imageio_ffmpeg/binaries').glob('ffmpeg-*'))
FONT=Path('/System/Library/Fonts/Supplemental/Arial.ttf')
BOLD=Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf')
OUT.mkdir(parents=True,exist_ok=True)

CUES=[
 (0,4,'From LiDAR observations to corridor insight.'),
 (4,11,'Choose Florida or Toronto. This demonstration uses Florida’s active data feed.'),
 (11,16,'Select an intersection, then zoom in to see moving road users.'),
 (16,27,'Road users update from the BlueCity stream. Map positions and alignment are approximate.'),
 (27,36,'Read received phase colors. A phase ID does not establish a verified movement direction.'),
 (36,42,'Explore a saved one-hour recording. The rolling view also refreshes every 30 minutes.'),
 (42,48,'Filter trajectories by travel direction and object type.'),
 (48,57,'Choose intersections, then zoom around the pointer to inspect a specific time window.'),
 (57,61,'Within one intersection, interrupted observations leave gaps.'),
 (61,67,'Enable local estimates: compatible same-session object IDs are connected with constrained curves.'),
 (67,72,'Between intersections, sections of roadway are not observed by LiDAR.'),
 (72,80,'Timing and motion help match candidate tracks. Dashed connections remain estimates.'),
 (80,87,'Gray dashed lines show weaker hypotheses. Uncertain matches are excluded from measured KPIs.'),
 (87,94,'Compare corridor traffic patterns: solid lines are observations; speed colors run from red to green.'),
 (94,99,'The CTM explorer shows how demand and signal timing affect traffic queues.'),
 (99,105,'Change the green duration and rerun the scenario to compare traffic propagation.'),
 (105,110,'This CTM simulation is educational and has not been calibrated for field decisions.'),
 (110,114,'Ouster Corridor Observatory—a traffic analytics research project by Fatemeh Sadeghi.')
]
CHAPTERS=[(0,4,'PORTFOLIO WALKTHROUGH'),(4,16,'01 / SELECT A CORRIDOR'),(16,27,'02 / LIVE ROAD USERS'),(27,36,'03 / API PHASE STATES'),(36,48,'04 / RECORDED TRAFFIC'),(48,57,'05 / FILTER + ZOOM'),(57,67,'06 / LOCAL GAP RECONSTRUCTION'),(67,80,'07 / CORRIDOR CONNECTIONS'),(80,87,'08 / VISIBLE UNCERTAINTY'),(87,94,'09 / CORRIDOR PATTERNS'),(94,110,'10 / EDUCATIONAL CTM EXPLORER'),(110,114,'FATEMEH SADEGHI / RESEARCH PORTFOLIO')]

def run(args):
    subprocess.run([str(FFMPEG),'-hide_banner','-loglevel','error','-y',*map(str,args)],check=True)

def duration(path):
    result=subprocess.run([str(FFMPEG),'-hide_banner','-i',str(path)],capture_output=True,text=True)
    m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',result.stderr)
    if not m:raise RuntimeError('Could not determine video duration')
    h,mn,s=m.groups();return int(h)*3600+int(mn)*60+float(s)

def card(name,heading,subheading,pills):
    im=Image.new('RGB',(1920,1080),'#102e35');draw=ImageDraw.Draw(im)
    draw.rectangle((0,0,1920,7),fill='#65cbb7')
    for x,y in [(1520,170),(1710,390),(1570,630),(1800,820)]:
        draw.line([(x-80,y+190),(x+90,y-190)],fill='#235056',width=3)
    draw.ellipse((138,160,182,204),outline='#81dbca',width=3)
    draw.ellipse((146,168,174,196),fill='#70ccba')
    draw.text((205,158),'OUSTER  /  CORRIDOR OBSERVATORY',font=ImageFont.truetype(str(BOLD),27),fill='#d6eee8')
    y=290
    for line in heading.split('\n'):
        draw.text((140,y),line,font=ImageFont.truetype(str(BOLD),86),fill='white');y+=103
    draw.text((145,y+28),subheading,font=ImageFont.truetype(str(FONT),30),fill='#c1d8da')
    x=145;y=785
    for label in pills:
        font=ImageFont.truetype(str(BOLD),19);w=int(draw.textlength(label,font=font))+44
        draw.rounded_rectangle((x,y,x+w,y+56),radius=28,outline='#568c8c',width=2)
        draw.text((x+22,y+17),label,font=font,fill='#dceee9');x+=w+18
    p=WORK/(name+'.png');im.save(p);return p

def stamp(s,srt=False):
    if srt:
        n=round(s*1000);return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'
    n=round(s*100);return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'

def main():
    log=json.loads((WORK/'capture-log.json').read_text())
    assert [c['name'] for c in log['clips']]==['live','history','ctm'], 'All scenes must finish'
    assert not log['errors'],log['errors']
    intro=card('intro','From LiDAR to\ncorridor insight.','Live observation. Interactive history. Transparent reconstruction.', ['LIVE DATA','TRAJECTORY ANALYTICS','RESEARCH PROTOTYPE'])
    outro=card('outro','Observe. Reconstruct.\nUnderstand.','A traffic analytics research project by Fatemeh Sadeghi.', ['PYTHON + SQLITE','LEAFLET','CONSTRAINED ESTIMATION'])
    common=['-an','-r','25','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-color_range','tv','-threads','2','-video_track_timescale','12800']
    pieces=[]
    p=WORK/'intro.mp4';run(['-loop','1','-i',intro,'-t','4',*common,p]);pieces.append(p)
    timing=[]
    for clip in log['clips']:
        full=duration(clip['path']);lead=max(0,full-clip['duration'])
        target=clip['target_duration'];p=WORK/(clip['name']+'-trim.mp4')
        # Playwright's JPEG-derived VP8 pixels are full-range; declare this
        # explicitly to avoid clipping the dashboard's pale backgrounds.
        run(['-ss',lead,'-i',clip['path'],'-t',target,'-vf','scale=1920:912:flags=lanczos:in_range=full:out_range=tv,pad=1920:1080:0:48:color=0x102e35',*common,p]);pieces.append(p)
        timing.append({'clip':clip['name'],'raw_duration_s':full,'trim_start_s':lead,'output_duration_s':duration(p)})
    p=WORK/'outro.mp4';run(['-loop','1','-i',outro,'-t','4',*common,p]);pieces.append(p)
    listing=WORK/'concat.txt';listing.write_text('\n'.join("file '"+str(p)+"'" for p in pieces))
    base=WORK/'assembled.mp4';run(['-f','concat','-safe','0','-i',listing,'-c','copy',base])
    srt=OUT/'Ouster_Corridor_Observatory_Subtitles.srt'
    srt.write_text('\n'.join(f'{i+1}\n{stamp(a,True)} --> {stamp(b,True)}\n{text}\n' for i,(a,b,text) in enumerate(CUES)))
    ass=WORK/'subtitles.ass'
    head='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Subtitle,Arial,31,&H00FFFFFF,&H00FFFFFF,&H00102E35,&H00102E35,0,0,0,0,100,100,0,0,1,0,0,2,110,110,34,1\nStyle: Brand,Arial,18,&H00FFFFFF,&H00FFFFFF,&H00102E35,&H00102E35,-1,0,0,0,100,100,1,0,1,0,0,7,32,32,14,1\nStyle: Chapter,Arial,17,&H00CFD6A8,&H00CFD6A8,&H00102E35,&H00102E35,0,0,0,0,100,100,1,0,1,0,0,9,32,32,14,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    lines=[head]
    for a,b,text in CUES:
        lines.append(f'Dialogue: 0,{stamp(a)},{stamp(b)},Subtitle,,0,0,0,,{text}')
    lines.append(f'Dialogue: 0,{stamp(4)},{stamp(110)},Brand,,0,0,0,,OUSTER / CORRIDOR OBSERVATORY')
    for a,b,text in CHAPTERS:
        if a>=4 and b<=110:lines.append(f'Dialogue: 0,{stamp(a)},{stamp(b)},Chapter,,0,0,0,,{text}')
    ass.write_text('\n'.join(lines))
    final=OUT/'Ouster_Corridor_Observatory_Walkthrough.mp4'
    run(['-i',base,'-vf',f'ass={ass}',*common,'-movflags','+faststart',final])
    total=duration(final);assert 90<=total<=120,total
    (WORK/'render-validation.json').write_text(json.dumps({'duration_s':total,'resolution':[1920,1080],'fps':25,'subtitles_burned_in':True,'audio':'none','timing':timing,'size_bytes':final.stat().st_size},indent=2))
    for label,t in [('intro',1),('live',22),('phase',32),('filters',45),('local',64),('between',76),('uncertain',84),('ctm',102),('outro',112)]:
        run(['-ss',t,'-i',final,'-frames:v','1',WORK/'qa'/('final-'+label+'.png')])
    print(json.dumps({'output':str(final),'duration_s':total,'size_bytes':final.stat().st_size}))

if __name__=='__main__':main()
