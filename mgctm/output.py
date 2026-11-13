"""Create auditable aggregate outputs and interactive local metric map."""
import json
from pathlib import Path
from .geometry import export_cells, write_csv

MAP = """<!doctype html><meta charset="utf-8"><title>MG-CTM cell map</title>
<style>body{font:16px system-ui;margin:2rem;color:#152a3d}svg{width:100%;height:420px;background:#f3f6fa}
line{cursor:help}pre{white-space:pre-wrap}</style><h1 id="name"></h1>
<p>Directed cell geometry · wheel to zoom; drag to pan. L purple, shared blue, through green, R orange.</p>
<svg id="map"></svg><pre id="detail">Hover over a cell.</pre>
<script>
const data=__DATA__, m=document.querySelector('svg'), ns='http://www.w3.org/2000/svg';
document.querySelector('#name').textContent=data.name;
const points=data.cells.flatMap(c=>c.geometry.coordinates);
const xs=points.map(p=>p[0]), ys=points.map(p=>-p[1]);
let view=[Math.min(...xs)-20,Math.min(...ys)-30,Math.max(...xs)-Math.min(...xs)+40,Math.max(...ys)-Math.min(...ys)+60];
function render(){m.setAttribute('viewBox',view.join(' '));}render();
for(const c of data.cells){
 const q=document.createElementNS(ns,'polyline'),p=c.properties;
 const shift=p.movements==='L'?-4:p.movements==='R'?4:0;
 q.setAttribute('points',c.geometry.coordinates.map(([x,y])=>[x,-y+shift].join(',')).join(' '));
 q.setAttribute('fill','none');q.setAttribute('stroke',({L:'#8d3ab0',T:'#197445',R:'#e07d21'})[p.movements]||'#2074ae');
 q.setAttribute('stroke-width','3');q.style.cursor='help';
 q.onpointerenter=()=>document.querySelector('#detail').textContent=JSON.stringify(p,null,2);m.append(q);
 const a=c.geometry.coordinates.at(-2), b=c.geometry.coordinates.at(-1);
 const angle=Math.atan2(a[1]-b[1],b[0]-a[0])*180/Math.PI;
 const arrow=document.createElementNS(ns,'path');arrow.setAttribute('d','M -5 -2 L 0 0 L -5 2');
 arrow.setAttribute('transform','translate('+b[0]+' '+(-b[1]+shift)+') rotate('+angle+')');
 arrow.setAttribute('fill','none');arrow.setAttribute('stroke','#263744');m.append(arrow);
}
for(const stop of data.stops){
 const [x,y]=stop.xy, label=document.createElementNS(ns,'text');
 label.setAttribute('x',x);label.setAttribute('y',-y-12);label.setAttribute('font-size','12');
 label.setAttribute('text-anchor','middle');label.textContent=stop.name;m.append(label);
}
m.addEventListener('wheel',e=>{e.preventDefault();const f=e.deltaY<0?.8:1.25;
 const x=e.offsetX/m.clientWidth,y=e.offsetY/m.clientHeight;
 view=[view[0]+view[2]*(1-f)*x,view[1]+view[3]*(1-f)*y,view[2]*f,view[3]*f];render();},{passive:false});
m.addEventListener('pointerdown',e=>m.setPointerCapture(e.pointerId));
m.addEventListener('pointermove',e=>{if(!e.buttons)return;view[0]-=e.movementX*view[2]/m.clientWidth;view[1]-=e.movementY*view[3]/m.clientHeight;render();});
</script>"""


def simulation(net,rows,meta,densities,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    cells=export_cells(net,out)
    write_csv(out/'predictions.csv',(dict(end_s=t,target=k[0],metric=k[1],value=v)
                                    for t,items in rows.items() for k,v in items.items()))
    (out/'summary.json').write_text(json.dumps(dict(name=net.spec['name'],synthetic=net.spec['synthetic'],
                                                    **meta),indent=2))
    stops={}
    for edge in net.spec['connections']:
        if 'signal' in edge:
            stops.setdefault(edge['intersection'],net.sections[edge['from']].xy[-1])
    payload=json.dumps(dict(name=net.spec['name'],cells=cells,
                            stops=[dict(name=k,xy=v) for k,v in stops.items()])).replace('<','\\u003c')
    (out/'cell-map.html').write_text(MAP.replace('__DATA__',payload))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    t=list(rows); duration=t[-1]/60
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    # Use each parent link's through/shared lane group on the mainline;
    # side bays have separate queue traces rather than a fictitious station.
    main=[i for i,c in enumerate(net.cells) if 'T' in c.section.turns]
    if main:
        station=np.r_[0,np.cumsum(net.length[main])]
        mesh=ax.pcolormesh(np.r_[0,np.array(t)/60],station,densities[:,main].T*1000,shading='flat')
        fig.colorbar(mesh,ax=ax,label='vehicles/km/lane')
    ax.set(xlabel='Minutes from peak start',ylabel='Cumulative length of selected cells (m)',
           title=f"{net.spec['name']} · through-capable cells in configuration order")
    fig.savefig(out/'density.png',dpi=145);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4),layout='constrained')
    for section in net.sections.values():
        if section.bay:
            ax.plot(np.array(t)/60,[v[section.id,'queue_m'] for v in rows.values()],label=section.id)
    ax.set(xlabel='Minutes from peak start',ylabel='Contiguous congested length (m)',
           title=f"{net.spec['name']} · turn-bay queue proxy",xlim=(0,duration))
    if ax.lines: ax.legend(ncols=3,fontsize=8)
    fig.savefig(out/'queues.png',dpi=145);plt.close(fig)
