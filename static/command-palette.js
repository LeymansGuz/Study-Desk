'use strict';
(()=>{
  const by=id=>document.getElementById(id);
  let dialog,input,list,active=0,items=[];
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  function build(){
    dialog=document.createElement('dialog');
    dialog.id='command-dialog';
    dialog.className='command-dialog';
    dialog.setAttribute('aria-labelledby','command-title');
    dialog.setAttribute('aria-modal','true');
    dialog.innerHTML='<div class="command-head"><h2 id="command-title">Jump to</h2><kbd>Esc</kbd></div><label class="sr-only" for="command-input">Find a view, course or library section</label><input id="command-input" type="search" placeholder="Search views, courses and library sections" autocomplete="off" spellcheck="false"><div id="command-list" role="listbox" aria-label="Available destinations"></div><p class="command-hint">↑↓ move · Enter open · Esc close</p>';
    document.body.append(dialog);
    input=dialog.querySelector('#command-input');
    list=dialog.querySelector('#command-list');
    input.addEventListener('input',()=>{active=0;render();});
    input.addEventListener('keydown',event=>{
      if(event.key==='ArrowDown'){event.preventDefault();active=Math.min(items.length-1,active+1);paint();}
      else if(event.key==='ArrowUp'){event.preventDefault();active=Math.max(0,active-1);paint();}
      else if(event.key==='Enter'){event.preventDefault();run(active);}
    });
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
  }

  function destinations(){
    const view=name=>({label:{today:'Today',practice:'Study - Practice',explain:'Study - Explain',ask:'Study - Ask',workspace:'Workspace',progress:'Progress',settings:'Settings'}[name]||name,detail:'Open view',run:()=>go(name)});
    const actions=[view('today'),view('practice'),view('explain'),view('ask'),view('workspace'),view('progress'),view('settings')];
    const tabs=[...document.querySelectorAll('#view-learning > .library-tabs [data-library-tab]')];
    tabs.forEach((button,index)=>actions.push({label:'Library - '+button.textContent,detail:'Jump to section',run:()=>{go('learning');button.click();}}));
    (window.studyLocal?.courses||[]).forEach(course=>actions.push({label:course.name,detail:'Switch active course',run:()=>{
      const select=by('active-course');if(!select)return;
      select.value=course.id;select.dispatchEvent(new Event('change',{bubbles:true}));close();
    }}));
    return actions;
  }

  function render(){
    const query=input.value.trim().toLowerCase();
    items=destinations().filter(item=>(item.label+' '+item.detail).toLowerCase().includes(query));
    active=Math.min(active,Math.max(0,items.length-1));
    list.innerHTML=items.map((item,index)=>`<button type="button" role="option" aria-selected="${index===active}" class="command-option ${index===active?'is-active':''}" data-command-index="${index}"><span>${esc(item.label)}</span><small>${esc(item.detail)}</small></button>`).join('')||'<p class="command-empty">No matching destination. Try a course name, view or library section.</p>';
    list.querySelectorAll('[data-command-index]').forEach(button=>button.onclick=()=>run(Number(button.dataset.commandIndex)));
    paint();
  }

  function paint(){
    list.querySelectorAll('[data-command-index]').forEach(button=>{
      const selected=Number(button.dataset.commandIndex)===active;
      button.classList.toggle('is-active',selected);button.setAttribute('aria-selected',String(selected));
    });
    const selected=list.querySelector('[aria-selected="true"]');if(selected)selected.scrollIntoView({block:'nearest'});
  }

  function run(index){
    const item=items[index];if(!item)return;
    close();item.run();
  }

  function go(name){
    if(typeof window.studyView==='function')window.studyView(name);
    close();
  }

  function close(){if(dialog?.open)dialog.close();}

  function open(){
    if(!dialog)build();
    input.value='';active=0;render();
    if(!dialog.open)dialog.showModal();
    requestAnimationFrame(()=>input.focus());
  }

  by('command-open')?.addEventListener('click',open);
  document.addEventListener('keydown',event=>{
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){
      event.preventDefault();open();
    }
  });
})();
