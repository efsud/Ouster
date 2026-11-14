"""Clearly synthetic arterial network for software and synthetic recovery tests."""


def make(n=2, peak='AM', duration=1200):
    sections=[]; links=[]; origins=[]
    def section(name,link,lanes,a,b,turns,xy,bay=False):
        sections.append(dict(id=name,link=link,lane_ids=lanes,start_m=a,end_m=b,turns=list(turns),
            vf_mps=15,wave_mps=5,jam_veh_per_m_lane=.15,xy=xy,bay=bay))
    def phases(offset, left=False):
        green=25 if left else 0
        return dict(cycle_s=60,offset_s=offset,lost_s=2,changes=(
            [[0,'red'],[green,'protected'],[40,'yellow'],[43,'all_red'],[45,'red']]
            if left else [[0,'protected'],[40,'yellow'],[43,'all_red'],[45,'red']]))
    for i in range(n):
        name=f'S{i+1}'
        a=i*180; b=a+135; c=a+180
        section(name+'-approach',name,['a','b'],0,135,'LTR',[[a,0],[b,0]])
        section(name+'-left',name,['b'],135,180,'L',[[b,0],[c,0]],True)
        section(name+'-shared',name,['a'],135,180,'TR',[[b,0],[c,0]])
        for turn in 'LTR':
            group='left' if turn=='L' else 'shared'
            links.append(dict(id=f'{name}-split-{turn}',**{'from':name+'-approach','to':name+'-'+group,'turn':turn}))
            e=dict(id=f'{name}-{turn}',**{'from':name+'-'+group,'to':None,'turn':turn},
                   intersection=name,signal=phases((i*8)%60,turn=='L'))
            if turn=='T' and i+1<n:
                e.update(to=f'S{i+2}-approach',next_ratios=[[0,{'L':.16,'T':.76,'R':.08}],
                                                          [300,{'L':.24,'T':.69,'R':.07}]])
            links.append(e)
    rates=[1100,1450,1325,950] if peak=='AM' else [1150,1500,1475,1100]
    origins.append(dict(id='west',to='S1-approach',demand_vph=[[300*i,r] for i,r in enumerate(rates)],
                        ratios=[[0,{'L':.22,'T':.70,'R':.08}],[300,{'L':.30,'T':.62,'R':.08}]]))
    return dict(name=f'SYNTHETIC {n}-intersection arterial',synthetic=True,peak=peak,
        intersections=[f'S{i+1}' for i in range(n)],dt_s=1,min_cell_m=15,duration_s=duration,
        output_bin_s=60,sections=sections,connections=links,origins=origins,
        withdrawals=[],timezone='America/New_York',driving_side='right',units='SI',
        study_dates=[],seed=42)
