'use strict';
document.addEventListener('study-ready',async()=>{
  try {const profile=await api('/local/profile');if(profile.desktop)document.querySelector('#local-run-help').textContent='Your documents and study progress are stored on this computer. Closing Study Desk stops its private services. Configure your AI connection above.';}
  catch(error){fail(error);}
});
