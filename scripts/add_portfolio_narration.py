"""Retiming and audio finishing for the user's own portfolio narration.

The source remains private and unchanged. This uses the actual supplied audio,
not voice synthesis. Only long pauses are shortened; atempo preserves pitch.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess
from render_portfolio_video import CUES, stamp, duration

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/portfolio'
OUT=ROOT/'docs/portfolio'
FFMPEG=next((WORK/'runtime/imageio_ffmpeg/binaries').glob('ffmpeg-*'))
TARGET=119.2

def run(args):
    subprocess.run([str(FFMPEG),'-hide_banner','-loglevel','error','-y',*map(str,args)],check=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--audio',type=Path,required=True)
    args=parser.parse_args();source=args.audio.resolve()
    transcript=json.loads((WORK/'narration-transcript.json').read_text())
    words=[w for segment in transcript for w in segment['words']]
    # Boundaries checked against ASR word timing, a second ending transcription,
    # and speech activity detection. A 0.45-second pause remains at each cut.
    first,last=1.45,142.99
    cuts=[]
    for a,b in zip(words,words[1:]):
        if b['start']-a['end']>=.7:
            cuts.append([a['end']+.225,b['start']-.225])
    intervals=[];cursor=first
    for a,b in cuts:
        assert cursor<a<b<last
        intervals.append([cursor,a]);cursor=b
    intervals.append([cursor,last])
    kept=sum(b-a for a,b in intervals)
    leading,trailing=.25,.30
    pace=kept/(TARGET-leading-trailing)
    assert 1<=pace<=1.20,pace
    def new_time(t):
        retained=sum(max(0,min(t,b)-a) for a,b in intervals if t>a)
        return leading+retained/pace
    # Cue boundaries use the middle of inter-paragraph pauses where available.
    starts=[first,5.35,12.96,19.30,30.44,38.66,45.98,50.76,57.50,
            65.24,74.58,81.32,90.38,100.70,110.20,118.90,126.76,135.10]
    boundaries=[0]+[round(new_time(t)*25)/25 for t in starts[1:]]+[TARGET]
    texts=[c[2] for c in CUES]
    texts[15]='Change the green duration and rerun the scenario to compute traffic propagation.'
    texts[16]='The CTM simulation is educational and has not been calibrated for field decisions.'
    texts[17]='Ouster Corridor Observatory—a traffic analytics research project by me.'
    aligned=[(boundaries[i],boundaries[i+1],text) for i,text in enumerate(texts)]
    assert all(a<b for a,b,_ in aligned)

    # Cut in pauses, with very short boundary fades to avoid clicks.
    audio_filter=[]
    for i,(a,b) in enumerate(intervals):
        audio_filter.append(f'[0:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS,'
                            f'afade=t=in:st=0:d=0.006,afade=t=out:st={b-a-.006:.6f}:d=0.006[a{i}]')
    inputs=''.join(f'[a{i}]' for i in range(len(intervals)))
    audio_filter.append(f'{inputs}concat=n={len(intervals)}:v=0:a=1,highpass=f=80,lowpass=f=9000,'
                        f'afftdn=nr=6:nf=-40:tn=1,atempo={pace:.9f},'
                        f'adelay=250:all=1,apad=whole_dur={TARGET},atrim=duration={TARGET},'
                        'loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000[narration]')
    filters=WORK/'narration-audio.filter';filters.write_text(';\n'.join(audio_filter))
    cleaned=WORK/'narration-finished.wav'
    run(['-i',source,'-filter_complex',filters.read_text(),'-map','[narration]','-map_metadata','-1',
         '-ac','1','-c:a','pcm_s24le',cleaned])

    # Retiming the clean screen master keeps original, obsolete subtitles out.
    scene_dir=WORK/'narrated-scenes';scene_dir.mkdir(exist_ok=True)
    pieces=[]
    for i,((old_a,old_b,_),(new_a,new_b,_)) in enumerate(zip(CUES,aligned)):
        p=scene_dir/f'{i:02d}.mp4';span=new_b-new_a;ratio=span/(old_b-old_a)
        run(['-ss',old_a,'-i',WORK/'assembled.mp4','-t',span,'-vf',
             f'trim=duration={old_b-old_a},setpts={ratio:.9f}*(PTS-STARTPTS),fps=25,tpad=stop_mode=clone:stop_duration=0.12',
             '-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-color_range','tv',
             '-threads','2','-video_track_timescale','12800',p]);pieces.append(p)
    listing=WORK/'narrated-concat.txt';listing.write_text('\n'.join("file '"+str(p)+"'" for p in pieces))
    base=WORK/'narrated-assembled.mp4';run(['-f','concat','-safe','0','-i',listing,'-c','copy',base])
    srt=OUT/'Ouster_Corridor_Observatory_Narrated_Subtitles.srt'
    srt.write_text('\n'.join(f'{i+1}\n{stamp(a,True)} --> {stamp(b,True)}\n{text}\n' for i,(a,b,text) in enumerate(aligned)))
    ass=WORK/'narrated-subtitles.ass'
    header=(WORK/'subtitles.ass').read_text().split('Dialogue:')[0]
    lines=[header]+[f'Dialogue: 0,{stamp(a)},{stamp(b)},Subtitle,,0,0,0,,{text}' for a,b,text in aligned]
    lines.append(f'Dialogue: 0,{stamp(boundaries[1])},{stamp(boundaries[-2])},Brand,,0,0,0,,OUSTER / CORRIDOR OBSERVATORY')
    chapters=[(1,3,'01 / SELECT A CORRIDOR'),(3,4,'02 / LIVE ROAD USERS'),(4,5,'03 / API PHASE STATES'),
              (5,7,'04 / RECORDED TRAFFIC'),(7,8,'05 / FILTER + ZOOM'),(8,10,'06 / LOCAL GAP RECONSTRUCTION'),
              (10,12,'07 / CORRIDOR CONNECTIONS'),(12,13,'08 / VISIBLE UNCERTAINTY'),
              (13,14,'09 / CORRIDOR PATTERNS'),(14,17,'10 / EDUCATIONAL CTM EXPLORER')]
    for i,j,label in chapters:lines.append(f'Dialogue: 0,{stamp(boundaries[i])},{stamp(boundaries[j])},Chapter,,0,0,0,,{label}')
    ass.write_text('\n'.join(lines))
    final=OUT/'Ouster_Corridor_Observatory_With_My_Voice.mp4'
    run(['-i',base,'-i',cleaned,'-map','0:v:0','-map','1:a:0','-map_metadata','-1',
         '-vf',f'ass={ass}','-t',TARGET,'-c:v','libx264','-preset','fast','-crf','20',
         '-pix_fmt','yuv420p','-color_range','tv','-threads','2','-c:a','aac','-b:a','192k','-ar','48000',
         '-metadata:s:a:0','language=eng','-movflags','+faststart',final])
    result={'source_audio_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_duration_s':duration(source),'output_duration_s':duration(final),
            'removed_pause_seconds':round(sum(b-a for a,b in cuts),3),
            'pace_factor':round(pace,6),'pitch_preserved':True,'voice_synthesis':False,
            'source_unchanged':True,'resolution':[1920,1080],'fps':25,
            'audio':'User recording; gentle filtering and loudness normalization; AAC mono 48 kHz',
            'subtitle_timing':'Aligned to narration; burned-in; editable SRT sidecar',
            'recording_metadata_removed':True,'cue_boundaries_s':boundaries,'size_bytes':final.stat().st_size}
    (OUT/'Narration_Validation.json').write_text(json.dumps(result,indent=2))
    (WORK/'narration-edit-decisions.json').write_text(json.dumps({'keep_intervals':intervals,'cuts':cuts,'aligned_cues':aligned},indent=2))
    for i in [0,3,4,9,11,12,15,17]:
        t=(boundaries[i]+boundaries[i+1])/2
        run(['-ss',t,'-i',final,'-frames:v','1',WORK/'qa'/f'narrated-{i:02d}.png'])
    print(json.dumps(result))

if __name__=='__main__':main()
