from copy import deepcopy
import unittest
import numpy as np
from .cells import Network
from .demo import make
from .engine import Simulator, run
from .signals import Signal
from .experiments import variant
from .evaluation import paired_summary,select
from .trajectory_counts import bin_counts, crosses
from datetime import datetime, timezone


def config():
    c=make(2,duration=120)
    c['origins'][0]['demand_vph']=[[0,0]]
    return c


class Physics(unittest.TestCase):
    def test_empty(self):
        net=Network(config())
        rows,meta,_=run(net)
        self.assertEqual(meta['arrivals'],0)
        self.assertEqual(meta['network_vehicles'],0)
        self.assertEqual(meta['exits'],0)

    def test_free_flow_cfl_propagation(self):
        sim=Simulator(Network(config()))
        sim.n[0,1]=sim.arrived=1
        sim.step()
        self.assertAlmostEqual(sim.n[1,1],1)
        self.assertAlmostEqual(sim.n[0].sum(),0)

    def test_red_builds_and_green_discharges(self):
        net=Network(config())
        sim=Simulator(net)
        start,last=net.ends['S1-left']
        sim.n[start,0]=sim.arrived=1
        for _ in range(20):sim.step()
        self.assertAlmostEqual(sim.n[last,0],1)
        self.assertEqual(sim.exited,0)
        for _ in range(20):sim.step()
        self.assertGreater(sim.exited,.99)

    def test_lost_time_and_wraparound(self):
        s=Signal.load(dict(changes=[[0,'protected'],[10,'red'],[15,'protected']],cycle_s=20,lost_s=8),'T')
        self.assertEqual(s.limits(15)[0],0)
        self.assertAlmostEqual(s.limits(0)[0],5/8)
        self.assertEqual(s.limits(3)[0],1)
        with self.assertRaises(ValueError):
            Signal.load(dict(changes=[[0,'rtor']],alternate_vph=50),'R')

    def test_turn_bay_spillback_preserves_independent_group(self):
        net=Network(config());sim=Simulator(net)
        _,a=net.ends['S1-approach']; b,c=net.ends['S1-left'];_,d=net.ends['S1-shared']
        sim.n[b:c+1,0]=net.storage[b:c+1]
        sim.n[a]=[1,1,0];sim.n[d,1]=1;sim.arrived=sim.n.sum()
        q=sim.step()['flows']
        amounts={e.id:v for e,v in zip(net.edges,q)}
        self.assertEqual(amounts['S1-split-L'],0)
        self.assertEqual(amounts['S1-split-T'],0)
        sim.time=3
        q=sim.step()['flows']
        self.assertGreater(dict(zip((e.id for e in net.edges),q))['S1-T'],0)
        self.assertFalse(sim.n[b:c+1,1:].any())

    def test_shared_lane_capacity_and_terminal_sending(self):
        net=Network(config());sim=Simulator(net)
        _,i=net.ends['S2-shared']
        sim.n[i]=[0,1,1];sim.arrived=2;sim.time=4
        flow=dict(zip((e.id for e in net.edges),sim.step()['flows']))
        self.assertGreater(flow['S2-T'],0)
        self.assertGreater(flow['S2-R'],0)
        self.assertLessEqual(flow['S2-T']+flow['S2-R'],net.capacity[i]*net.dt+1e-9)

    def test_cannot_double_count_physical_lane(self):
        c=config()
        c['sections'][2]['lane_ids']=['b']
        with self.assertRaisesRegex(ValueError,'Overlapping'):
            Network(c)

    def test_midblock_entry_exit_and_reservoir(self):
        c=config()
        c['origins'][0]['demand_vph']=[[0,16000]]
        c['origins'].append(dict(id='mid',to='S1-shared',demand_vph=[[0,500]],ratios=[[0,{'T':.9,'R':.1}]]))
        c['withdrawals']=[dict(id='driveway',**{'from':'S1-approach'},rate_vph=[[0,200]])]
        net=Network(c); sim=Simulator(net)
        for _ in range(120): sim.step()
        self.assertGreater(sim.reservoir.sum(),0)
        self.assertGreater(sim.exit_total.sum(),0)
        self.assertAlmostEqual(sim.arrived,sim.n.sum()+sim.reservoir.sum()+sim.exited)

    def test_short_section_uses_smaller_time_step(self):
        c=config()
        for s in c['sections'][:3]:
            s['start_m']/=10;s['end_m']/=10
            s['xy']=[[x/10,y] for x,y in s['xy']]
        net=Network(c)
        self.assertLess(net.dt,1)
        self.assertTrue(np.all(net.dt*np.maximum(net.v,net.w)<=net.length+1e-8))
        self.assertTrue(np.all(net.v==15))

    def test_poisson_reproducible(self):
        c=config();c['origins'][0]['demand_vph']=[[0,1100]]
        net=Network(c)
        self.assertEqual(run(net,seed=10,stochastic=True)[0],run(net,seed=10,stochastic=True)[0])
        self.assertNotEqual(run(net,seed=10,stochastic=True)[0],run(net,seed=11,stochastic=True)[0])

    def test_real_geometry_gate_and_e8_required(self):
        c=config();c['synthetic']=False
        with self.assertRaisesRegex(ValueError,'verified geometry'):Network(c)
        with self.assertRaisesRegex(ValueError,'alternative plan'):variant(config(),['alternate_signals'])

    def test_verified_gate_count_uses_car_only_and_never_bridges_gap(self):
        gate=dict(target='T',p=[0,1],q=[0,-1])
        self.assertIsNotNone(crosses([-1,0],[1,0],gate['p'],gate['q']))
        self.assertIsNone(crosses([-1,3],[1,3],gate['p'],gate['q']))
        def event(t,x,session='a'):
            return dict(received_at=t,session=session,payload={'frame':{
                'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),
                'objects':[dict(id='car',classType='2',centerX=x,centerY=0),
                           dict(id='truck',classType='4',centerX=x,centerY=0)]}})
        counts,valid,_=bin_counts([event(0,-1),event(1,1),event(2,-1),event(3,1,'b')],
                                   [gate],0,3,3)
        self.assertEqual(counts['T',0],1)
        self.assertEqual(valid,{0})
        _,valid,_=bin_counts([event(0,-1),event(3,1)],[gate],0,3,3)
        self.assertEqual(valid,set())

    def test_no_single_day_model_selection(self):
        self.assertIsNone(select({'E0':{('date','AM'):1}}, {'E0':0})['selected'])
        self.assertIsNone(paired_summary({1:.3},{1:.2})['ci95'])


if __name__=='__main__':
    unittest.main()
