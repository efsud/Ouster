'use strict';
// Keep the live and analytical components intact; arrange them as the supplied
// slide, with the full viewport devoted to the map, phase cards and trajectories.
const workspaceMain=document.querySelector('body > main');
const workspaceLive=document.getElementById('live');
const workspaceMenu=document.querySelector('.sidebar');
workspaceMenu.id='workspace-menu';workspaceMenu.hidden=true;
const workspaceTop=document.createElement('div');workspaceTop.className='workspace-topbar';
const workspaceBrandBox=document.createElement('div');workspaceBrandBox.className='workspace-brand-box';
const workspaceBrand=document.querySelector('.brand');
workspaceBrand.setAttribute('href','#workspace-menu');workspaceBrand.setAttribute('role','button');
workspaceBrand.setAttribute('aria-label','Ouster workspace menu');workspaceBrand.setAttribute('aria-expanded','false');
workspaceBrand.setAttribute('aria-controls','workspace-menu');
workspaceBrandBox.append(workspaceBrand,document.getElementById('approximate-objects').closest('label'));
const workspaceRotation=document.getElementById('preview-rotation').closest('label');workspaceRotation.classList.add('workspace-rotation');
const workspaceRegion=document.getElementById('region').closest('.select-wrap');workspaceRegion.classList.add('workspace-network');
workspaceTop.append(workspaceBrandBox,workspaceRotation,workspaceRegion);
document.body.insertBefore(workspaceTop,workspaceMenu);
function closeWorkspaceMenu(){workspaceMenu.hidden=true;workspaceBrand.setAttribute('aria-expanded','false');}
workspaceBrand.addEventListener('click',event=>{event.preventDefault();workspaceMenu.hidden=!workspaceMenu.hidden;workspaceBrand.setAttribute('aria-expanded',String(!workspaceMenu.hidden));});
workspaceBrand.addEventListener('keydown',event=>{if(event.key===' '){event.preventDefault();workspaceBrand.click();}});
document.addEventListener('click',event=>{if(!workspaceMenu.contains(event.target)&&!workspaceBrand.contains(event.target))closeWorkspaceMenu();});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeWorkspaceMenu();});
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{
 document.body.dataset.view=button.dataset.tab;closeWorkspaceMenu();
 if(workspaceDialog.open)workspaceDialog.close();
 if(button.dataset.tab==='live')requestAnimationFrame(()=>map?.invalidateSize());
}));

const workspaceLeft=document.createElement('div');workspaceLeft.className='workspace-left';
const workspaceNetwork=document.querySelector('.network-grid');
const workspacePhases=document.getElementById('live-phase-panel');
const workspacePhaseHead=document.createElement('div');workspacePhaseHead.className='workspace-phase-head';
workspacePhaseHead.append(document.getElementById('live-phase-title'));
const workspaceDetailsButton=document.createElement('button');workspaceDetailsButton.type='button';workspaceDetailsButton.className='workspace-details-button';workspaceDetailsButton.textContent='Details';
workspaceDetailsButton.setAttribute('aria-label','Open sensor and phase details');workspacePhaseHead.append(workspaceDetailsButton);
workspacePhases.prepend(workspacePhaseHead);
workspaceLeft.append(workspaceNetwork,workspacePhases);

const workspaceHistory=document.createElement('article');workspaceHistory.className='workspace-history';
workspaceHistory.setAttribute('aria-label','Corridor trajectory figures');
const workspaceFrame=document.createElement('iframe');workspaceFrame.id='workspace-trajectories';workspaceFrame.title='Florida corridor trajectories';
workspaceHistory.append(workspaceFrame);
// Diagnostics and existing KPI tools remain reachable, but do not displace the
// panels shown in the reference. They retain their original IDs and handlers.
const workspaceDialog=document.createElement('dialog');workspaceDialog.id='workspace-details';
workspaceDialog.setAttribute('aria-labelledby','workspace-details-heading');
const workspaceDialogHead=document.createElement('div');workspaceDialogHead.className='workspace-dialog-head';
const workspaceDialogTitle=document.createElement('h2');workspaceDialogTitle.id='workspace-details-heading';workspaceDialogTitle.textContent='Sensor & phase details';
const workspaceClose=document.createElement('button');workspaceClose.type='button';workspaceClose.textContent='Close';workspaceClose.className='secondary';
workspaceDialogHead.append(workspaceDialogTitle,workspaceClose);workspaceDialog.append(workspaceDialogHead);
workspaceDetailsButton.onclick=()=>workspaceDialog.showModal();workspaceClose.onclick=()=>workspaceDialog.close();
for(const item of [...workspaceLive.children]){
 if(item.classList.contains('section-intro')||item.classList.contains('filters'))item.hidden=true;
 workspaceDialog.append(item);
}
for(const item of [...workspacePhases.children]){
 if(item.tagName==='DETAILS'||item.id==='phase-direction-evidence'||(item.tagName==='P'&&item.id!=='live-phase-health'))workspaceDialog.append(item);
}
workspaceDialog.append(workspaceNetwork.querySelector('.map-footer'));
workspaceDialog.prepend(document.getElementById('global-notice'));
workspaceLive.append(workspaceLeft,workspaceHistory);
document.body.append(workspaceDialog);
const originalHeader=workspaceMain.querySelector(':scope > header');originalHeader.classList.add('workspace-original-header');

function syncWorkspaceFigures(){
 if(state.publicLive){workspaceFrame.removeAttribute('src');return;}
 const region=document.getElementById('region').value;
 const url=region==='Florida'?'/florida_rolling.html?embed=workspace&frozen=20261124T194525Z&between=1':'/finch_rolling.html?embed=workspace&between=1';
 if(workspaceFrame.getAttribute('src')!==url)workspaceFrame.src=url;
 workspaceFrame.title=region==='Florida'?'Florida corridor trajectories':'Toronto Finch corridor trajectories';
}
document.addEventListener('dashboard:networkchange',syncWorkspaceFigures);
document.getElementById('region').addEventListener('change',syncWorkspaceFigures);
if(new URLSearchParams(location.search).get('region')==='Florida')document.getElementById('region').value='Florida';
syncWorkspaceFigures();
const workspaceResize=new ResizeObserver(()=>{if(typeof map!=='undefined')map?.invalidateSize({pan:true,animate:false});});
workspaceResize.observe(document.getElementById('map'));
