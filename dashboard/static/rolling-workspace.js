'use strict';
if(new URLSearchParams(location.search).get('embed')==='workspace'){
 document.body.classList.add('embedded-figure');
 const figureMain=document.querySelector('main'),figureControls=document.createElement('div');figureControls.className='embedded-controls';
 const figureSites=document.getElementById('sites'),figureChoices=document.createElement('div');figureChoices.className='embedded-choices';
 figureChoices.append(document.getElementById('direction').closest('label'),document.getElementById('objects').closest('label'));
 const figureLayers=document.createElement('div');figureLayers.className='embedded-layers';
 for(const id of ['within-layer','between-layer','color-layer','uncertain-layer']){const input=document.getElementById(id);if(input)figureLayers.append(input.closest('label'));}
 figureControls.append(figureSites,figureChoices,figureLayers);
 const figurePlot=document.createElement('div');figurePlot.className='embedded-plot';figurePlot.append(document.getElementById('plot'));
 const figureFooter=document.createElement('div');figureFooter.className='embedded-footer';
 const figureActions=document.createElement('div');figureActions.className='embedded-actions';
 for(const id of ['zoom-in','zoom-out','reset'])figureActions.append(document.getElementById(id));
 const figureSource=document.createElement('select');figureSource.setAttribute('aria-label','Trajectory recording');
 if(corridor==='florida')figureSource.add(new Option('Frozen hour · Nov 24','frozen'));
 figureSource.add(new Option('Latest rolling hour','rolling'));figureSource.value=frozenId?'frozen':'rolling';
 figureSource.onchange=()=>{const url=new URL(location.href);if(figureSource.value==='frozen')url.searchParams.set('frozen','20261124T194525Z');else url.searchParams.delete('frozen');location.href=url;};
 const figureOpen=document.createElement('a');figureOpen.textContent='Full figures';figureOpen.target='_blank';figureOpen.rel='noopener';
 const fullURL=new URL(location.href);fullURL.searchParams.delete('embed');figureOpen.href=fullURL.href;
 const figureInfoButton=document.createElement('button');figureInfoButton.type='button';figureInfoButton.textContent='Details';
 figureActions.append(figureSource,figureOpen,figureInfoButton);
 const figureNote=document.createElement('p');figureNote.className='embedded-note';figureNote.textContent='Solid: observed · Dashed: estimated · Gray: uncertain. Scroll over the chart to zoom at the pointer.';
 const figureWindow=document.createElement('p');figureWindow.className='embedded-window';figureWindow.setAttribute('role','status');
 function reportFigureWindow(){
  figureWindow.textContent=data&&view?`${regionName} · ${clock(view[0])}–${clock(view[1])} · ${frozenId?'Frozen recording':'Rolling hour'}`:document.getElementById('message').textContent;
  figureWindow.title=document.getElementById('message').textContent;
 }
 const figureDialog=document.createElement('dialog');figureDialog.className='embedded-details';
 const figureClose=document.createElement('button');figureClose.type='button';figureClose.textContent='Close details';
 figureInfoButton.onclick=()=>figureDialog.showModal();figureClose.onclick=()=>figureDialog.close();figureDialog.append(figureClose);
 for(const child of [...figureMain.children])figureDialog.append(child);
 figureFooter.append(figureActions,figureWindow,figureNote);
 figureMain.append(figureControls,figurePlot,figureFooter);document.body.append(figureDialog);
 new MutationObserver(reportFigureWindow).observe(document.getElementById('coverage'),{childList:true,characterData:true,subtree:true});
 new MutationObserver(reportFigureWindow).observe(document.getElementById('message'),{childList:true,characterData:true,subtree:true});
 new ResizeObserver(()=>draw()).observe(figurePlot);
 reportFigureWindow();
}
