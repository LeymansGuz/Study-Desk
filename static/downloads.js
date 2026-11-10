'use strict';
(()=>{
  let desktop=null;
  const exportPath=path=>/^\/(?:library\/(?:course\/[^/]+\/export|personal\/export|guide\/[^/]+)|study\/(?:cards\/export|sheets\/[^/]+\/export)|session\/[^/]+\/export|bank-exams\/[^/]+\/summary\/export|workspace\/(?:documents\/[^/]+\/download|download-all))(?:\?|$)/.test(path);
  function notice(anchor){
    const actions=anchor.closest('.local-actions')||anchor;
    let p=actions.nextElementSibling;if(!p?.classList.contains('export-status')){p=document.createElement('p');p.className='export-status';p.setAttribute('role','status');p.setAttribute('aria-live','polite');actions.after(p);}return p;
  }
  window.saveStudyExport=async(url,options={},filename='study-export')=>{
    const parsed=new URL(url,location.href);if(parsed.origin!==location.origin)throw Error('Only local study exports can be saved here.');
    if(desktop===null)desktop=(await api('/local/profile')).desktop;
    if(desktop){
      const payload={route:parsed.pathname+parsed.search};if(options.method==='POST')payload.passphrase=JSON.parse(options.body).passphrase;
      const job=await post('/desktop/files/save',payload);
      const deadline=Date.now()+30*60*1000;
      while(Date.now()<deadline){await new Promise(r=>setTimeout(r,500));const state=await api('/desktop/files/status/'+job.id);if(state.state==='error')throw Error(state.message);if(['saved','cancelled'].includes(state.state))return state.message;}
      throw Error('The Save dialog is still pending. Finish or cancel it before starting another export.');
    }
    const response=await fetch(url,{cache:'no-store',...options});
    if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(error.detail||error.error||'Export failed. Your study work is kept.');}
    const suggested=/filename="?([^";]+)"?/.exec(response.headers.get('Content-Disposition')||'')?.[1]||filename;
    const blob=URL.createObjectURL(await response.blob()),link=document.createElement('a');link.href=blob;link.download=suggested;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(blob),60000);
    return 'Download started. Check your browser’s Downloads list for '+suggested+'.';
  };
  document.addEventListener('click',async event=>{
    const link=event.target.closest('a[href]');if(!link)return;
    if(['course-bundle-export','personal-export'].includes(link.id)&&!document.querySelector('#library-course')?.value){event.preventDefault();const p=notice(link);p.textContent='Choose a course before exporting its study material.';p.classList.add('local-error');return;}
    const url=new URL(link.href,location.href);
    if(link.id==='source-download'&&url.origin===location.origin)url.pathname=url.pathname.replace(/\/file$/,'/download');
    if(url.origin!==location.origin||!exportPath(url.pathname+url.search)||url.pathname.startsWith('/library/guide/')&&url.searchParams.get('download')!=='true')return;
    event.preventDefault();if(link.dataset.saving)return;
    link.dataset.saving='true';link.setAttribute('aria-busy','true');const p=notice(link);p.textContent='Preparing export…';p.classList.remove('local-error');
    try{p.textContent=await window.saveStudyExport(url.href);}catch(e){p.textContent=e.message;p.classList.add('local-error');}finally{delete link.dataset.saving;link.removeAttribute('aria-busy');}
  },true);
  document.addEventListener('study-ready',async()=>{desktop=(await api('/local/profile')).desktop;});
})();
