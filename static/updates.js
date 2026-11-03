'use strict';
document.addEventListener('study-ready',async()=>{
  if(!(await api('/local/profile')).desktop)return;
  const panel=document.querySelector('#desktop-updates');panel.hidden=false;
  const buttons=[...panel.querySelectorAll('[data-update]')];
  let pending=false;
  async function refresh(){
    try{
      const state=await api('/desktop/update/status');
      panel.querySelector('[data-version]').textContent='Installed version: '+state.current_version+(state.version?' · Available: '+state.version:'');
      panel.querySelector('[data-status]').textContent=state.message;
      const progress=panel.querySelector('progress');progress.hidden=state.state!=='downloading';
      if(state.total>0){progress.max=state.total;progress.value=state.received;}else progress.removeAttribute('value');
      const allowed={check:['idle','current','available','downloaded','error'],download:['available'],install:['downloaded']};
      buttons.forEach(button=>button.disabled=pending||!allowed[button.dataset.update].includes(state.state));
      panel.querySelector('[data-transfer]').textContent=state.state==='downloading'&&state.received?`${(state.received/1048576).toFixed(1)} MB${state.total?' / '+(state.total/1048576).toFixed(1)+' MB':''}`:'';
    }catch(error){panel.querySelector('[data-status]').textContent='The app may be restarting. If it does not reopen, start Study Desk again.';}
  }
  buttons.forEach(button=>button.onclick=async()=>{
    if(pending)return;
    if(button.dataset.update==='install'&&!await window.appConfirm('Finish your current study work first. Study Desk will verify a backup, close and install the signed update. Your documents and saved progress stay in the app data folder.',{title:'Install and restart?',confirmText:'Install and restart'}))return;
    pending=true;buttons.forEach(b=>b.disabled=true);
    try{await post('/desktop/update/'+button.dataset.update,{});}catch(error){panel.querySelector('[data-status]').textContent=error.message;pending=false;buttons.forEach(b=>b.disabled=false);return;}
    pending=false;await refresh();
  });
  await refresh();setInterval(()=>{if(!document.hidden)refresh();},1500);
});
