'use strict';
document.addEventListener('study-ready',async()=>{
  try {
    const profile=await api('/local/profile');
    if(!profile.desktop)return;
    const form=document.querySelector('#desktop-provider-form');
    form.hidden=false;
    document.querySelector('#local-run-help').textContent='Your documents and study progress are stored on this computer. Closing Study Desk stops its private services. AI requests send relevant document excerpts to DeepSeek.';
    const connection=await api('/desktop/provider');
    status('#desktop-provider-status',connection.configured?'API key saved. Enter a new key only to replace it.':'Add your API key to enable AI study tools.');
    if(!connection.configured){view('settings');document.querySelector('#desktop-api-key').focus();}
    form.onsubmit=async event=>{
      event.preventDefault();
      const button=form.querySelector('button');
      if(button.disabled)return;
      button.disabled=true;status('#desktop-provider-status','Saving securely…');
      try {
        const input=document.querySelector('#desktop-api-key');
        const result=await post('/desktop/provider',{api_key:input.value});
        input.value='';status('#desktop-provider-status',result.message);
      } catch(error) {status('#desktop-provider-status',error.message,true);}
      finally {button.disabled=false;}
    };
  } catch(error) {fail(error);}
});
