'use strict';
document.addEventListener('study-ready',async()=>{
  const form=document.querySelector('#ai-connection-form');if(!form)return;
  const provider=form.querySelector('[name=provider]'),model=form.querySelector('[name=model]'),key=form.querySelector('[name=api_key]');
  const free=form.querySelector('[name=free_only]'),custom=form.querySelector('[name=base_url]');
  let catalog=[],busy=false;
  const say=(message,error=false)=>status('#ai-connection-status',message,error);
  function lock(value){busy=value;form.querySelectorAll('button').forEach(b=>b.disabled=value);}
  function providerLabel(id){return [...provider.options].find(option=>option.value===id)?.textContent||id;}
  function describe(){
    const selected=catalog.find(m=>m.id===model.value);
    document.querySelector('#ai-model-details').textContent=selected?`${selected.price_status==='free'?'Free endpoint':selected.price_status==='paid'?'Paid model':'Pricing unknown'} · ${selected.tested?'Tested with Study Desk':'Untested with Study Desk'} · ${selected.region}${selected.pricing?` · USD ${selected.pricing[0]} input / ${selected.pricing[1]} output per million tokens`:''}`:'Manual model: pricing and compatibility are unverified. Provider charges may apply.';
  }
  function controls(){form.querySelector('[name=route]').closest('label').hidden=provider.value!=='openrouter';}
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
    const empty=document.createElement('option');empty.value='';empty.textContent=rows.length?'Choose a model':'Enter a key and refresh the catalog';model.append(empty);
    rows.forEach(m=>{const option=document.createElement('option');option.value=m.id;option.textContent=`${m.name} — ${m.price_status==='free'?'Free':m.price_status==='paid'?'Paid':'Price unknown'}${m.tested?' · Tested':''}`;model.append(option);});
    if(rows.some(m=>m.id===old))model.value=old;
    document.querySelector('#ai-model-count').textContent=`${rows.length} text-generating models. Catalog listing does not certify access or quality.`;
    describe();controls();
  }
  async function allowance(){
    try{const result=await api('/local/providers/allowance');document.querySelector('#ai-allowance').textContent=result.source==='provider'?`Provider free allowance: ${result.remaining??'unknown'} remaining of ${result.limit??'unknown'}${result.resets_at?' · resets '+result.resets_at:''}`:result.note||'Allowance unavailable.';}
    catch(e){document.querySelector('#ai-allowance').textContent=e.message;}
  }
  async function currentStatus(){
    try{
      const data=await api('/local/providers');const selected=data.selected||{};
      const saved=Boolean(data.configured&&selected.model);
      const note=saved?`Current: ${providerLabel(selected.provider)} · ${selected.model}${data.scope==='brief_only'?' · Brief explanations only':''}`:'No AI connection saved yet.';
      const host=document.querySelector('#ai-current');if(host)host.textContent=note;
    }catch(error){const host=document.querySelector('#ai-current');if(host)host.textContent=error.message;}
  }
  async function loadModels(refresh=true){
    const result=await api('/local/providers/models?'+new URLSearchParams({provider:provider.value,base_url:custom.value,refresh:String(refresh)}));
    catalog=result.models||[];render();return result;
  }
  function payload(activate){return {provider:provider.value,model:form.querySelector('[name=manual_model]').value.trim()||model.value,base_url:custom.value.trim(),api_key:key.value.trim(),activate,free_only:free.checked,json_mode:form.querySelector('[name=json_mode]').checked,reasoning:form.querySelector('[name=reasoning]').value,route:form.querySelector('[name=route]').value};}
  provider.onchange=()=>{
    catalog=[];key.value='';custom.closest('label').hidden=provider.value!=='custom';free.checked=provider.value==='openrouter';free.disabled=provider.value!=='openrouter';form.querySelector('[name=manual_model]').value='';render();
    say('Enter the provider key and click Save and use. The model catalog refreshes automatically.');
  };
  model.onchange=async()=>{
    describe();const route=form.querySelector('[name=route]');route.replaceChildren();
    if(provider.value!=='openrouter'||!model.value)return;
    try{const data=await api('/local/providers/endpoints?'+new URLSearchParams({model:model.value}));for(const e of data.endpoints.filter(e=>!free.checked||e.free)){const option=document.createElement('option');option.value=e.id;option.textContent=e.name+' · '+(e.free?'Free':'Check pricing');route.append(option);}}
    catch(e){say(e.message,true);}
  };
  free.onchange=render;
  form.querySelector('[name=search]').oninput=render;
  form.onsubmit=async event=>{
    event.preventDefault();if(busy)return;lock(true);
    try{
      const chosen=form.querySelector('[name=manual_model]').value.trim()||model.value;
      if(!chosen){
        if(!key.value.trim())throw new Error('Enter an API key, then click Save and use.');
        await post('/local/providers',payload(false));key.value='';
        await loadModels(true);
        say('Key saved. Choose a model, then click Save and use.');
        await currentStatus();
        return;
      }
      const result=await post('/local/providers',payload(true));key.value='';
      say(result.message);applyScope(result.scope);await allowance();await currentStatus();
    }catch(error){say(error.message,true);}
    finally{lock(false);}
  };
  try{
    const data=await api('/local/providers');provider.replaceChildren();data.providers.forEach(p=>{const option=document.createElement('option');option.value=p.id;option.textContent=p.name;provider.append(option);});
    const selected=data.selected;provider.value=selected.provider;custom.value=selected.base_url||'';custom.closest('label').hidden=provider.value!=='custom';
    applyScope(data.scope);
    free.checked=selected.free_only??provider.value==='openrouter';free.disabled=provider.value!=='openrouter';form.querySelector('[name=reasoning]').value=selected.reasoning||'auto';
    controls();
    if(selected.model){const option=document.createElement('option');option.value=selected.model;option.textContent=selected.model+' · Saved selection';model.append(option);model.value=selected.model;}
    if(selected.routes?.length){const option=document.createElement('option');option.value=selected.routes[0];option.textContent=selected.routes[0]+' · Saved hosting endpoint';form.querySelector('[name=route]').append(option);}
    document.querySelector('#ai-recommendation').textContent=data.free_recommendation?'Free default: '+data.free_recommendation+'. Free allowance is limited; each verified question uses several requests.':data.recommendation_status;
    await currentStatus();
    if(data.configured){try{await loadModels(true);}catch(error){say(error.message,true);render();}}else render();
    say(data.configured?'A connection is saved. Enter a new key only when replacing it.':'Enter your provider key to begin.');
    if(!data.configured){view('settings');key.focus();}
    await allowance();
  }catch(e){say(e.message,true);}
});
