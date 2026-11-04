'use strict';
document.addEventListener('study-ready', async()=>{
  const host=document.querySelector('#data-use-settings');
  const legal=await api('/local/legal');
  const render=()=>{host.querySelector('[data-legal-state]').textContent=legal.accepted?'AI data use acknowledged. You can withdraw to block future AI requests.':'Review the notice before using AI study tools. Workspace remains available.';host.querySelector('[data-withdraw]').hidden=!legal.accepted;};
  async function open(documentName='privacy'){
    const previous=document.activeElement;
    const dialog=document.createElement('dialog');dialog.className='study-legal-dialog';
    dialog.innerHTML='<div class="local-actions"><h2>Data use and study terms</h2><button class="quiet-button" data-close>Close</button></div><nav class="local-actions" aria-label="Notice sections"><button class="quiet-button" data-document="privacy">Data use</button><button class="quiet-button" data-document="terms">Usage terms</button><button class="quiet-button" data-document="licenses">Licences</button></nav><div class="rich-text legal-copy"></div><p class="hint">For AI features, relevant excerpts, your questions and attempts are sent to your selected provider and, for OpenRouter, its selected hosting provider. Requests consume allowance and may incur charges. Avoid personal or confidential data. Automated verification can miss mistakes.</p><div class="local-actions"><button class="primary-button" data-accept>Accept and enable AI</button><button class="quiet-button" data-later>Use Workspace for now</button></div><p role="status" data-message></p>';
    document.body.append(dialog);
    const close=()=>{dialog.close();dialog.remove();previous?.focus();};
    dialog.querySelector('[data-close]').onclick=close;dialog.querySelector('[data-later]').onclick=()=>{close();if(!legal.accepted)view('workspace');};
    dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
    const load=async name=>{try{dialog.querySelector('.legal-copy').innerHTML=rich((await api('/local/legal/'+name)).markdown);}catch(error){dialog.querySelector('[data-message]').textContent=error.message;}};
    dialog.querySelectorAll('[data-document]').forEach(button=>button.onclick=()=>load(button.dataset.document));
    const accept=dialog.querySelector('[data-accept]');
    accept.onclick=async()=>{accept.disabled=true;try{Object.assign(legal,await post('/local/legal',{version:legal.version,accepted:true}));render();close();}catch(error){dialog.querySelector('[data-message]').textContent=error.message;accept.disabled=false;}};
    dialog.showModal();await load(documentName);
  }
  host.querySelectorAll('[data-review]').forEach(button=>button.onclick=()=>open(button.dataset.review));
  host.querySelector('[data-withdraw]').onclick=async()=>{try{Object.assign(legal,await post('/local/legal',{version:legal.version,accepted:false}));render();}catch(error){fail(error);}};
  render();if(!legal.accepted)await open();
});
