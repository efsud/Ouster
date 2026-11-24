"""Browser-independent checks of observed-support envelopes and membership."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node needed for shared canvas helpers')
class RegimeCanvasTests(unittest.TestCase):
    def test_example_switch_clears_conflicting_group_filters(self):
        js = Path(__file__).parent/'static/florida-rolling.js'
        script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.argv[1],'utf8');
const helper=source.slice(source.indexOf('function clearGroupFilters('),source.indexOf('function groupModeUI('));
const elements={'trajectory-group':{value:'old'},'group-mode':{checked:true},'regime-select':{value:'selected-local-group'},'regime-mode':{checked:true}};
const ctx={el:id=>elements[id],groupModeUI:()=>{}};vm.createContext(ctx);vm.runInContext(helper,ctx);
ctx.clearGroupFilters(true);
assert.equal(elements['regime-mode'].checked,false);assert.equal(elements['regime-select'].value,'all');
assert.equal(elements['group-mode'].checked,false);assert.equal(elements['trajectory-group'].value,'all');
// The shared Finch page lacks all these optional controls.
ctx.el=()=>null;ctx.clearGroupFilters(true);
'''
        subprocess.run(['node','-e',script,str(js.resolve())], check=True)

    def test_empty_time_bins_are_not_joined_and_membership_is_segment_local(self):
        js = Path(__file__).parent/'static/regime-groups.js'
        script = r'''
const assert=require('node:assert/strict');
const {regimeEnvelopeRuns,regimeSegmentContains,sameRegimeSnapshot}=require(process.argv[1]);
assert.equal(sameRegimeSnapshot({generated_at:2},{snapshot_generated_at:2,regime_groups:{snapshot_generated_at:1}}),false);
assert.equal(sameRegimeSnapshot({generated_at:2},{snapshot_generated_at:2,regime_groups:{snapshot_generated_at:2}}),true);
assert.equal(sameRegimeSnapshot(null,{}),false);
const occupied=[[.95,1,2,3],[1.99,2,3,3],[3.01,4,5,3],[4.05,5,6,3]];
assert.deepEqual(regimeEnvelopeRuns(occupied),[occupied.slice(0,2),occupied.slice(2)]);
const stopped={start_index:2,end_index:5},moving={start_index:5,end_index:9};
assert.equal(regimeSegmentContains(stopped,5),true);
assert.equal(regimeSegmentContains(moving,5),false);
assert.equal(regimeSegmentContains(moving,6),true);
assert.equal(regimeSegmentContains(stopped,2),false);
assert.equal(regimeSegmentContains(stopped,6),false);
assert.deepEqual(regimeEnvelopeRuns([]),[]);
'''
        subprocess.run(['node','-e',script,str(js.resolve())], check=True)


if __name__ == '__main__':
    unittest.main()
