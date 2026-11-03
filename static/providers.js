'use strict';
document.addEventListener('study-ready',async()=>{
  const form=document.querySelector('#ai-connection-form');if(!form)return;
  const provider=form.querySelector('[name=provider]'),model=form.querySelector('[name=model]'),key=form.querySelector('[name=api_key]');
  const free=form.querySelector('[name=free_only]'),custom=form.querySelector('[name=base_url]');
  let catalog=[],busy=false;
  const say=(message,error=false)=>status('#ai-connection-status',message,error);
  function lock(value){busy=value;form.querySelectorAll('button').forEach(b=>b.disabled=value);}
  function describe(){
    const selected=catalog.find(m=>m.id===model.value);
    document.querySelector('#ai-model-details').textContent=selected?`${selected.price_status==='free'?'Free endpoint':selected.price_status==='paid'?'Paid model':'Pricing unknown'} · ${selected.tested?'Tested with Study Desk':'Untested with Study Desk'} · ${selected.region}${selected.pricing?` · USD ${selected.pricing[0]} input / ${selected.pricing[1]} output per million tokens`:''}`:'Manual model: pricing and compatibility are unverified. Possible charges require acknowledgement.';
  }
  function controls(){form.querySelector('[name=accept_charges]').closest('label').hidden=free.checked;form.querySelector('[name=route]').closest('label').hidden=provider.value!=='openrouter';}
  function applyScope(scope){
    const limited=scope==='brief_only';
    for(const id of ['practice-form','ask-form']){const panel=document.getElementById(id);if(!panel)continue;panel.querySelector('button[type=submit]').disabled=limited;let note=panel.querySelector('[data-provider-scope]');if(!note){note=document.createElement('p');note.className='hint';note.dataset.providerScope='';panel.prepend(note);}note.hidden=!limited;note.textContent='The selected free model supports brief concept explanations only. Choose a suitable paid connection in Settings for question generation or tutoring.';}
    document.querySelector('#start-path').disabled=limited;
    const depth=document.querySelector('#depth');depth.querySelector('option[value=deep]').disabled=limited;if(limited)depth.value='brief';
    let note=document.querySelector('#explain-form [data-provider-scope]');if(!note){note=document.createElement('p');note.className='hint';note.dataset.providerScope='';document.querySelector('#explain-form').prepend(note);}note.hidden=!limited;note.textContent='Free model: brief explanations only. These models performed substantially worse than the tested paid DeepSeek Flash setup for question generation. Explanations still require source and correctness checks.';
  }
  function render(){
    const old=model.value,search=form.querySelector('[name=search]').value.toLowerCase();
    const rows=catalog.filter(m=>(!free.checked||m.price_status==='free')&&(m.id+' '+m.name).toLowerCase().includes(search));
    model.replaceChildren();
    const empty=document.createElement('option');empty.value='';empty.textContent=rows.length?'Choose a model':'Refresh models or adjust the filter';model.append(empty);
    rows.forEach(m=>{const option=document.createElement('option');option.value=m.id;option.textContent=`${m.name} — ${m.price_status==='free'?'Free':m.price_status==='paid'?'Paid':'Price unknown'}${m.tested?' · Tested':''}`;model.append(option);});
    if(rows.some(m=>m.id===old))model.value=old;
    document.querySelector('#ai-model-count').textContent=`${rows.length} text-generating models. Catalog listing does not certify access or quality.`;
    describe();
    controls();
  }
  async function allowance(){try{const result=await api('/local/providers/allowance');document.querySelector('#ai-allowance').textContent=result.source==='provider'?`Provider free allowance: ${result.remaining??'unknown'} remaining of ${result.limit??'unknown'}${result.resets_at?' · resets '+result.resets_at:''}`:result.note||'Allowance unavailable.';}catch(e){document.querySelector('#ai-allowance').textContent=e.message;}}
  function payload(activate){return {provider:provider.value,model:form.querySelector('[name=manual_model]').value.trim()||model.value,base_url:custom.value.trim(),api_key:key.value.trim(),activate,free_only:free.checked,eligible:form.querySelector('[name=eligible]').checked,accept_charges:form.querySelector('[name=accept_charges]').checked,json_mode:form.querySelector('[name=json_mode]').checked,reasoning:form.querySelector('[name=reasoning]').value,route:form.querySelector('[name=route]').value};}
  provider.onchange=()=>{catalog=[];key.value='';custom.closest('label').hidden=provider.value!=='custom';free.checked=provider.value==='openrouter';free.disabled=provider.value!=='openrouter';form.querySelector('[name=manual_model]').value='';form.querySelector('[name=eligible]').checked=false;form.querySelector('[name=accept_charges]').checked=false;render();say('Save a key for this provider, then refresh models. The active connection changes only when you save the connection.');};
  model.onchange=async()=>{describe();const route=form.querySelector('[name=route]');route.replaceChildren();if(provider.value!=='openrouter'||!model.value)return;try{const data=await api('/local/providers/endpoints?'+new URLSearchParams({model:model.value}));for(const e of data.endpoints.filter(e=>!free.checked||e.free)){const option=document.createElement('option');option.value=e.id;option.textContent=e.name+' · '+(e.free?'Free':'Check pricing');route.append(option);}}catch(e){say(e.message,true);}};free.onchange=render;form.querySelector('[name=search]').oninput=render;
  form.querySelector('[data-save-key]').onclick=async()=>{if(busy)return;lock(true);say('Saving key securely…');try{if(!key.value.trim())throw new Error('Enter a key to save.');const r=await post('/local/providers',payload(false));key.value='';say(r.message);}catch(e){say(e.message,true);}finally{lock(false);}};
  form.querySelector('[data-refresh-models]').onclick=async()=>{if(busy)return;lock(true);say('Refreshing model catalog…');try{const r=await api('/local/providers/models?'+new URLSearchParams({provider:provider.value,base_url:custom.value,refresh:'true'}));catalog=r.models;render();say('Catalog refreshed. Confirm location eligibility before selecting a model.');}catch(e){say(e.message,true);}finally{lock(false);}};
  form.onsubmit=async event=>{event.preventDefault();if(busy)return;lock(true);say('Saving connection…');try{const r=await post('/local/providers',payload(true));key.value='';say(r.message);applyScope(r.scope);await allowance();}catch(e){say(e.message,true);}finally{lock(false);}};
  form.querySelector('[data-test-connection]').onclick=async()=>{if(busy)return;if(!form.querySelector('[name=allow_test]').checked){say('Confirm the small test request before testing. It can consume free allowance or incur charges.',true);return;}lock(true);say('Testing the saved connection…');try{const r=await post('/local/providers/test',{allow_request:true});say(r.message);await allowance();}catch(e){say(e.message,true);}finally{lock(false);}};
  try{
    const data=await api('/local/providers');provider.replaceChildren();data.providers.forEach(p=>{const option=document.createElement('option');option.value=p.id;option.textContent=p.name;provider.append(option);});
    const selected=data.selected;provider.value=selected.provider;custom.value=selected.base_url||'';custom.closest('label').hidden=provider.value!=='custom';
    applyScope(data.scope);
    free.checked=selected.free_only??provider.value==='openrouter';free.disabled=provider.value!=='openrouter';form.querySelector('[name=reasoning]').value=selected.reasoning||'auto';
    controls();
    if(selected.model){const option=document.createElement('option');option.value=selected.model;option.textContent=selected.model+' · Saved selection';model.append(option);model.value=selected.model;}
    if(selected.routes?.length){const option=document.createElement('option');option.value=selected.routes[0];option.textContent=selected.routes[0]+' · Saved hosting endpoint';form.querySelector('[name=route]').append(option);}
    document.querySelector('#ai-recommendation').textContent=data.free_recommendation?'Free default: '+data.free_recommendation+'. Free allowance is limited; each verified question uses several requests.':data.recommendation_status;
    say(data.configured?'A key is configured. Leave the key field empty to retain it.':'Add your own provider key to enable AI study tools.');
    if(!data.configured){view('settings');key.focus();}
    await allowance();
  }catch(e){say(e.message,true);}
});
