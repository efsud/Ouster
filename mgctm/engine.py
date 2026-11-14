"""Simultaneous conservative updates using a FIFO node rule per physical lane group."""
import numpy as np


class Simulator:
    def __init__(self, network, seed=42, stochastic=False, infinite_bays=False):
        self.net=network
        if infinite_bays and not network.spec['synthetic']:
            raise ValueError('Infinite bay counterfactual is synthetic only')
        self.infinite=np.array([infinite_bays and c.section.bay for c in network.cells])
        self.n=np.zeros((len(network.cells),3))
        self.reservoir=np.zeros((len(network.sources),3))
        self.rng=np.random.default_rng(seed)
        self.stochastic=stochastic
        self.time=0.
        self.arrived=self.exited=0.
        self.edge_total=np.zeros(len(network.edges))
        self.exit_total=np.zeros(len(network.withdrawals))
        self.residual=0.
        self.src=np.array([e.src for e in network.edges],dtype=int)
        self.dst=np.array([e.dst for e in network.edges],dtype=int)
        self.turn=np.array([e.turn for e in network.edges],dtype=int)
        self.internal=self.dst>=0
        self.in_dest=self.dst[self.internal]
        self.orig=np.array([s[1] for s in network.sources],dtype=int)
        self.sink=np.array([s[1] for s in network.withdrawals],dtype=int)
        self.special=[(i,e) for i,e in enumerate(network.edges) if e.signal or e.cap_vps]
        self.distributions=[(i,e) for i,e in enumerate(network.edges) if e.distribution]

    def step(self):
        net,t,dt=self.net,self.time,self.net.dt
        total=self.n.sum(axis=1)
        density=total/(net.length*net.lanes)
        send=np.minimum(net.v*density*net.lanes,net.capacity)*dt
        receive=np.minimum(net.capacity,net.w*np.maximum(0,net.jam-density)*net.lanes)*dt
        receive[self.infinite]=net.capacity[self.infinite]*dt
        # Explicit mid-block withdrawals consume the same sending budget.
        # They are measured exogenous flows, not extra lanes or demand sinks.
        requested=np.array([r.at(t)*dt for _,_,r in net.withdrawals],dtype=float)
        sums=np.bincount(self.sink,weights=requested,minlength=len(total))
        factor=np.minimum(1,send/np.maximum(sums,1e-30))
        withdrawals=requested*factor[self.sink]
        sent_to_sink=np.bincount(self.sink,weights=withdrawals,minlength=len(total))
        composition=np.divide(self.n,total[:,None],out=np.zeros_like(self.n),where=total[:,None]>0)
        removed=composition*sent_to_sink[:,None]
        requests=(send-sent_to_sink)[self.src]*composition[self.src,self.turn]
        # Requests keep their turn identity. Red requests contribute zero
        # available capacity but still participate in shared-lane FIFO.
        limited=requests.copy()
        for i,e in self.special:
            if e.signal:
                scale,cap=e.signal.limits(t)
                limited[i]=min(limited[i]*scale,cap*dt)
            if e.cap_vps:
                limited[i]=min(limited[i],e.cap_vps.at(t)*dt)
        for i,(_,_,demand,ratio) in enumerate(net.sources):
            rate=demand.at(t)*dt
            mix=ratio.at(t)
            if self.stochastic:
                new=self.rng.multinomial(self.rng.poisson(rate),mix)
            else:
                new=rate*np.asarray(mix)
            self.reservoir[i]+=new
            self.arrived+=sum(new)
        entry=self.reservoir.sum(axis=1)
        # One proportional allocation pass across all competing incoming
        # requests, including reservoirs. FIFO can leave unused supply; no
        # claim of maximizing node throughput or modeling individual queues.
        arrivals=np.bincount(self.in_dest,weights=limited[self.internal],minlength=len(total))
        arrivals+=np.bincount(self.orig,weights=entry,minlength=len(total))
        receive_scale=np.minimum(1,receive/np.maximum(arrivals,1e-30))
        limited[self.internal]*=receive_scale[self.in_dest]
        fraction=np.divide(limited,requests,out=np.ones_like(limited),where=requests>0)
        fifo=np.ones(len(total))
        np.minimum.at(fifo,self.src,fraction)
        flow=requests*fifo[self.src]
        admitted=self.reservoir*receive_scale[self.orig,None]
        self.reservoir-=admitted
        next_n=self.n-removed
        np.add.at(next_n,(self.src,self.turn),-flow)
        np.add.at(next_n,(self.in_dest,self.turn[self.internal]),flow[self.internal])
        for i,e in self.distributions:
            next_n[e.dst,e.turn]-=flow[i]
            next_n[e.dst]+=flow[i]*np.asarray(e.distribution.at(t))
        np.add.at(next_n,self.orig,admitted)
        self.exited+=float(flow[~self.internal].sum()+withdrawals.sum())
        self.edge_total+=flow
        self.exit_total+=withdrawals
        self.residual=float(next_n.sum()+self.reservoir.sum()+self.exited-self.arrived)
        if (np.any(next_n < -1e-8) or np.any(next_n.sum(1)[~self.infinite]>net.storage[~self.infinite]+1e-8)
            or abs(self.residual)>max(1e-7,self.arrived*1e-10)):
            raise ArithmeticError('CTM violated conservation or storage bounds')
        self.n=np.maximum(next_n,0)
        self.time+=dt
        return dict(send=send,receive=receive,flows=flow,withdrawals=withdrawals,admitted=admitted)

    def snapshot(self):
        net=self.net
        density=self.n.sum(1)/(net.length*net.lanes)
        critical=net.capacity/(net.v*net.lanes)
        values={}
        for name,(first,last) in net.ends.items():
            sl=slice(first,last+1)
            values[name,'vehicles']=float(self.n[sl].sum())
            length=0.
            for j in range(last,first-1,-1):
                if density[j]<=critical[j]:
                    break
                length+=net.length[j]
            values[name,'queue_m']=length
            values[name,'spillback']=float(length>=net.length[sl].sum()-1e-8)
            # Fundamental-diagram speed proxy, not a trajectory travel time.
            q=np.minimum(net.v[sl]*density[sl],net.w[sl]*np.maximum(0,net.jam[sl]-density[sl]))
            values[name,'speed_kmh']=float(np.average(np.divide(q,density[sl],out=net.v[sl].copy(),
                where=density[sl]>0),weights=net.length[sl])*3.6)
        return values,density


def run(network, *, seed=42, stochastic=False, infinite_bays=False, history=False):
    sim=Simulator(network,seed,stochastic,infinite_bays)
    duration=float(network.spec['duration_s'])
    bin_s=float(network.spec['output_bin_s'])
    stride=round(bin_s/network.dt)
    if duration<=0 or bin_s<=0 or stride<1 or abs(duration/bin_s-round(duration/bin_s))>1e-9:
        raise ValueError('Peak duration must contain whole positive output bins')
    rows={}; densities=[]; residual=0.; last=np.zeros(len(network.edges))
    vehicle_seconds=origin_wait_seconds=0.
    for i in range(1,round(duration/network.dt)+1):
        sim.time=(i-1)*network.dt
        vehicle_seconds+=float(sim.n.sum())*network.dt
        origin_wait_seconds+=float(sim.reservoir.sum())*network.dt
        sim.step()
        residual=max(residual,abs(sim.residual))
        if i%stride==0:
            values,density=sim.snapshot()
            values.update({(e.id,'count'):float(v) for e,v in zip(network.edges,sim.edge_total-last)})
            rows[round(i*network.dt,8)]=values
            last=sim.edge_total.copy()
            if history:
                densities.append(density)
    return rows,dict(arrivals=sim.arrived,exits=sim.exited,network_vehicles=float(sim.n.sum()),
        origin_backlog=float(sim.reservoir.sum()),max_mass_residual_vehicles=residual,
        vehicle_seconds=vehicle_seconds,origin_wait_vehicle_seconds=origin_wait_seconds,
        state_bytes=sim.n.nbytes+sim.reservoir.nbytes,
        dt_s=network.dt,steps=round(duration/network.dt)),np.asarray(densities)
