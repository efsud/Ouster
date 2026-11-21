"""Deterministic synthetic fixtures for learning; never attributed to real sites."""
from .analytics import calculate

def generate():
    start = 1789992000  # A fixed UTC time makes tests and examples reproducible.
    windows = []
    for bucket in range(36):
        s = start+bucket*300
        tracks = []
        for i in range(25+(bucket%8)):
            delay = 12+(bucket%9)*2+(i%5)
            entry = s+i*6
            tracks.append({'id':f'demo-{bucket}-{i}', 'vehicle':True,'entry':entry,'arrival':entry+10+delay,'exit':entry+12+delay,'complete':True,'max_gap_s':.1,'stopped_s':delay*.7,'green':i%4!=0,'departed_from_queue_on_green':i%4!=0})
        w = {'site':'DEMO-001','approach':'NB','source':'synthetic','start':s,'end':s+300,'length_m':100,'free_speed_mps':10,'lanes':1,'coverage':.96,'signal_synchronized':True,'entry_observation_complete':True,'departure_observation_complete':True,'green_seconds':150,'tracks':tracks,'queue_samples':[{'time':s+j*5,'length_m':(j%9)*5+bucket%8,'visible':True} for j in range(60)],'cycles':[{'start':s+j*90,'end':s+(j+1)*90,'residual_queue_m':10 if (j+bucket)%3==0 else 0,'visible':True} for j in range(3)]}
        windows.append((w,calculate(w)))
    return windows
