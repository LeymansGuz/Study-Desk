'use strict';
document.addEventListener('study-ready',async()=>{
  const form=document.querySelector('#ai-connection-form');if(!form)return;
  const provider=form.querySelector('[name=provider]'),model=form.querySelector('[name=model]'),key=form.querySelector('[name=api_key]');
  const free=form.querySelector('[name=free_only]'),custom=form.querySelector('[name=base_url]');
  let catalog=[],busy=false,savedKey=false,routeReady=false;
  const route=form.querySelector('[name=route]'),manual=form.querySelector('[name=manual_model]');
  const say=(message,error=false)=>status('#ai-connection-status',message,error);
  function sync(){
    form.querySelector('button[type=submit]').disabled=busy||(provider.value==='openrouter'&&Boolean(manual.value.trim()||model.value)&&!routeReady);
    free.disabled=busy||provider.value!=='openrouter';
    form.setAttribute('aria-busy',String(busy));
  }
  function lock(value){busy=value;form.querySelectorAll('input,select,button').forEach(b=>b.disabled=value);sync();}
  function providerLabel(id){return [...provider.options].find(option=>option.value===id)?.textContent||id;}
  function describe(){
    const selected=catalog.find(m=>m.id===model.value);
    document.querySelector('#ai-model-details').textContent=selected?`${selected.price_status==='free'?'Free endpoint':selected.price_status==='paid'?'Paid model':'Provider rates not provided'} · ${selected.tested?'Tested with Study Desk':'Untested with Study Desk'} · ${selected.region}${selected.price_note?' · '+selected.price_note:selected.pricing?` · USD ${selected.pricing[0]} input / ${selected.pricing[1]} output / ${selected.pricing[2]} cached input per million tokens`:selected.price_status==='paid'?' · Rates not provided by this catalog. Check the provider’s pricing.':''}`:'Select a model to see its pricing and compatibility.';
  }
  function controls(){
    route.closest('label').hidden=provider.value!=='openrouter';
    const link=form.querySelector('[data-openrouter]');
    const links={deepseek:['https://platform.deepseek.com/api_keys','Get a DeepSeek key'],openrouter:['https://openrouter.ai/keys','Get an OpenRouter key'],openai:['https://platform.openai.com/api-keys','Get an OpenAI API key'],anthropic:['https://platform.claude.com/settings/keys','Get a Claude API key']};
    link.hidden=!links[provider.value];if(links[provider.value]){link.href=links[provider.value][0];link.textContent=links[provider.value][1];}
  }
  function applyScope(scope){
    const limited=scope==='brief_only';
    local.providerScope=scope;
    document.dispatchEvent(new CustomEvent('study-provider-scope',{detail:scope}));
    for(const id of ['practice-form','ask-form']){const panel=document.getElementById(id);if(!panel)continue;panel.querySelector('button[type=submit]').disabled=limited;let note=panel.querySelector('[data-provider-scope]');if(!note){note=document.createElement('p');note.className='hint';note.dataset.providerScope='';panel.prepend(note);}note.hidden=!limited;note.textContent='The selected free model supports brief concept explanations only. Choose a suitable paid connection in Settings for question generation or tutoring.';}
    pathControls();
    const depth=document.querySelector('#depth');depth.querySelector('option[value=deep]').disabled=limited;if(limited)depth.value='brief';
    let note=document.querySelector('#explain-form [data-provider-scope]');if(!note){note=document.createElement('p');note.className='hint';note.dataset.providerScope='';document.querySelector('#explain-form').prepend(note);}note.hidden=!limited;note.textContent='Free model: brief explanations only. These models performed substantially worse than the tested paid DeepSeek Flash setup for question generation. Explanations still require source and correctness checks.';
  }
  function render(){
    const old=model.value,search=form.querySelector('[name=search]').value.toLowerCase();
    const rows=catalog.filter(m=>(!free.checked||m.price_status==='free')&&(m.id+' '+m.name).toLowerCase().includes(search));
    model.replaceChildren();
    const empty=document.createElement('option');empty.value='';empty.textContent=rows.length?'Choose a model':'Enter a key and refresh the catalog';model.append(empty);
    rows.forEach(m=>{const option=document.createElement('option');option.value=m.id;option.textContent=`${m.name} — ${m.price_status==='free'?'Free':m.price_status==='paid'?'Paid':'Rates not provided'}${m.tested?' · Tested':''}`;model.append(option);});
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
  async function loadRoutes(preferred=''){
    routeReady=false;route.replaceChildren();sync();
    const chosen=manual.value.trim()||model.value;
    if(provider.value!=='openrouter'||!chosen){sync();return;}
    const loading=document.createElement('option');loading.value='';loading.textContent='Loading eligible hosting endpoints…';route.append(loading);
    say('Checking hosting endpoints…');
    let data;
    try{data=await api('/local/providers/endpoints?'+new URLSearchParams({model:chosen}));}
    catch(error){route.replaceChildren();const option=document.createElement('option');option.value='';option.textContent='Could not load hosts — refresh the model list to retry';route.append(option);throw error;}
    route.replaceChildren();
    for(const e of data.endpoints.filter(e=>!free.checked||e.free)){const option=document.createElement('option');option.value=e.id;option.textContent=e.name+' · '+(e.free?'Free':'Paid or provider rates');route.append(option);}
    if([...route.options].some(e=>e.value===preferred))route.value=preferred;
    routeReady=Boolean(route.value);sync();
    if(!routeReady)throw new Error('No eligible hosting endpoint found. Choose another model or change the price filter.');
  }
  function restore(profile){
    free.checked=profile.free_only??provider.value==='openrouter';
    form.querySelector('[name=reasoning]').value=profile.reasoning||'auto';
    form.querySelector('[name=json_mode]').checked=profile.json_mode??true;
    if(profile.model){const option=document.createElement('option');option.value=profile.model;option.textContent=profile.model+' · Saved selection';model.append(option);model.value=profile.model;}
  }
  async function switchProvider(){
    if(busy)return;lock(true);catalog=[];key.value='';savedKey=false;routeReady=false;route.replaceChildren();manual.value='';form.querySelector('[name=search]').value='';
    custom.closest('label').hidden=provider.value!=='custom';render();
    try{
      say('Checking saved connection…');
      const data=await api('/local/providers?'+new URLSearchParams({provider:provider.value,base_url:custom.value}));
      savedKey=data.key_saved;restore(data.profile||{});
      key.placeholder=savedKey?'Key saved securely — leave blank to keep it':'Enter this provider’s API key';
      if(savedKey){await loadModels(false);await loadRoutes(data.profile?.routes?.[0]);}
      say(savedKey?'Saved key available. Choose a model or use the restored selection; no need to enter the key again.':'Enter this provider’s API key, then click Save and use.');
    }catch(e){say(e.message,true);}finally{lock(false);}
  }
  provider.onchange=switchProvider;custom.onchange=switchProvider;
  async function selectionChanged(){if(busy)return;lock(true);try{describe();await loadRoutes();say('Model ready. Click Save and use to activate it.');}catch(e){say(e.message,true);}finally{lock(false);}}
  model.onchange=selectionChanged;manual.onchange=selectionChanged;
  manual.oninput=()=>{if(provider.value==='openrouter'){routeReady=false;route.replaceChildren();sync();}};
  free.onchange=()=>{render();selectionChanged();};
  form.querySelector('[name=search]').oninput=()=>{const old=model.value;render();if(old!==model.value){routeReady=false;route.replaceChildren();sync();}};
  form.querySelector('[data-refresh-models]').onclick=async()=>{
    if(busy)return;lock(true);routeReady=false;
    try{say('Refreshing model list…');await loadModels(true);await loadRoutes();say('Model list refreshed. Choose a model, then Save and use.');}catch(e){say(e.message,true);}finally{lock(false);}
  };
  form.onsubmit=async event=>{
    event.preventDefault();if(busy)return;lock(true);
    try{
      const chosen=form.querySelector('[name=manual_model]').value.trim()||model.value;
      if(!chosen){
        if(!key.value.trim()&&!savedKey)throw new Error('Enter an API key, then click Save and use.');
        if(key.value.trim()){await post('/local/providers',payload(false));key.value='';savedKey=true;}
        await loadModels(true);
        say('Key saved. Choose a model, then click Save and use.');
        await currentStatus();
        return;
      }
      if(provider.value==='openrouter'&&!routeReady)throw new Error('Wait for hosting endpoints to finish loading and choose an eligible host.');
      if(key.value.trim()){
        const host=route.value;
        await post('/local/providers',payload(false));key.value='';savedKey=true;
        await loadModels(true);await loadRoutes(host);
      }
      const result=await post('/local/providers',payload(true));key.value='';savedKey=true;key.placeholder='Key saved securely — leave blank to keep it';
      say(result.message);applyScope(result.scope);await allowance();await currentStatus();
    }catch(error){say(error.message,true);}
    finally{lock(false);}
  };
  lock(true);
  try{
    const data=await api('/local/providers');provider.replaceChildren();data.providers.forEach(p=>{const option=document.createElement('option');option.value=p.id;option.textContent=p.name;provider.append(option);});
    const selected=data.selected;provider.value=selected.provider;custom.value=selected.base_url||'';custom.closest('label').hidden=provider.value!=='custom';
    applyScope(data.scope);
    restore(selected);
    controls();
    if(selected.routes?.length){const option=document.createElement('option');option.value=selected.routes[0];option.textContent=selected.routes[0]+' · Saved hosting endpoint';form.querySelector('[name=route]').append(option);}
    document.querySelector('#ai-recommendation').textContent=data.free_recommendation?'Free default: '+data.free_recommendation+'. Free allowance is limited; each verified question uses several requests.':data.recommendation_status;
    await currentStatus();
    savedKey=data.configured;
    if(data.configured){await loadModels(false);await loadRoutes(selected.routes?.[0]);}else render();
    say(data.configured?'A connection is saved. Enter a new key only when replacing it.':'Enter your provider key to begin.');
    if(!data.configured){view('settings');key.focus();}
    await allowance();
  }catch(e){say(e.message,true);}finally{lock(false);}
});
