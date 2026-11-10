'use strict';
(()=>{
  let ready=false,scope='full',sheet=null,sheets=[],page=0,queue=[],sheetFetch=0,queueFetch=0;
  const drafts=new Map();
  const form=()=>document.querySelector('#sheet-editor');
  const dirty=()=>sheet&&(form().elements.markdown.value!==sheet.markdown||form().elements.notes.value!==sheet.notes);
  const list=(items)=>'<ul>'+items.map(t=>'<li>'+rich(t)+'</li>').join('')+'</ul>';
  function recallScope(){document.querySelectorAll('[data-recall-submit]').forEach(b=>b.disabled=scope==='brief_only'||local.busy.has('recall')||b.dataset.historical==='true');document.querySelectorAll('[data-recall-scope]').forEach(p=>p.hidden=scope!=='brief_only');}
  document.addEventListener('study-provider-scope',e=>{scope=e.detail;recallScope();});
  async function today(){
    const ticket=++queueFetch,data=await api('/study/today');if(ticket!==queueFetch)return;queue=data.items;
    document.querySelector('#today-summary').textContent=queue.length?`${queue.length} suggested ${queue.length===1?'activity':'activities'} · about ${data.planned_minutes} minutes${data.days_to_exam!==null?' · '+(data.days_to_exam>=0?data.days_to_exam+' days until your exam':'Exam date passed; update your plan'):''}`:'Your queue is clear. Start a practice question or save a concept explanation to build your study history.';
    const host=document.querySelector('#today-items');host.innerHTML=queue.map((q,i)=>`<article class="study-queue-row"><div><strong>${esc(q.title)}</strong><p class="hint">${esc(q.detail)}</p></div><button class="${i?'quiet-button':'primary-button'}" type="button" data-today="${i}">${i?'Open':'Start next'}</button></article>`).join('');
    host.querySelectorAll('[data-today]').forEach(button=>button.onclick=async()=>{
      button.disabled=true;
      try{
        const q=queue[Number(button.dataset.today)];
        if(q.kind==='planned_topic')window.libraryPractice(q.topic,q.course_id,q.difficulty||'medium');
        if(q.kind==='review'){document.querySelector('#review-cards').scrollIntoView({behavior:'smooth',block:'center'});document.querySelector('#review-cards summary')?.focus();}
        if(q.kind==='resume')await resume('tutor',q.id);
        if(q.kind==='bank'){const exam=await post('/bank-exams',{course_id:q.id,count:1,difficulty:'any',question_type:'any'});view('learning');renderExam(exam);document.querySelector('#exam-result').scrollIntoView({behavior:'smooth',block:'start'});}
        if(q.kind==='sheet')await openSheet(q.id);
        if(q.kind==='workspace')view('workspace');
        if(q.kind==='practice'){document.querySelector('#practice-course').value=q.id;view('practice');}
      }catch(e){status('#today-status',e.message,true);}finally{button.disabled=false;}
    });
    const plan=document.querySelector('#study-plan');if(!plan.contains(document.activeElement)){plan.elements.minutes.value=data.preferences.minutes;plan.elements.exam_date.value=studyDates.display(data.preferences.exam_date);}
  }
  function renderSheets(){
    const shown=sheets.slice(page*5,page*5+5);
    document.querySelector('#revision-sheets').innerHTML=shown.map(s=>`<article class="study-queue-row"><div><strong>${esc(s.topic)}</strong><p class="hint">${s.historical?'Needs a fresh source and correctness check':s.edited?'Locally edited · edits not independently checked':'Saved from a checked explanation'}</p></div><button type="button" class="quiet-button" data-sheet="${esc(s.id)}">Open</button></article>`).join('')||'<p class="hint">Save a checked explanation as a revision sheet. It stays available without another AI call. <button type="button" class="quiet-button" data-empty-go="explain">Explain a concept</button></p>';
    document.querySelectorAll('[data-sheet]').forEach(b=>b.onclick=()=>openSheet(b.dataset.sheet).catch(fail));
    const pages=document.querySelector('#sheet-pages');pages.hidden=sheets.length<=5;pages.querySelector('[data-page-label]').textContent=`${page+1} / ${Math.max(1,Math.ceil(sheets.length/5))}`;pages.querySelector('[data-prev]').disabled=page===0;pages.querySelector('[data-next]').disabled=(page+1)*5>=sheets.length;
  }
  async function loadSheets(){const ticket=++sheetFetch,data=await api('/study/sheets');if(ticket!==sheetFetch)return;sheets=data.items;page=Math.min(page,Math.max(0,Math.ceil(sheets.length/5)-1));renderSheets();}
  async function openSheet(id){
    if(local.busy.has('sheet'))throw new Error('Wait for your sheet to finish saving.');
    if(dirty()&&!await window.appConfirm('Your sheet has unsaved edits. Discard those edits and open another sheet?',{title:'Unsaved sheet',confirmText:'Discard edits'}))return;
    sheet=await api('/study/sheets/'+encodeURIComponent(id));view('learning');
    const editor=form();editor.hidden=false;editor.elements.markdown.value=sheet.markdown;editor.elements.notes.value=sheet.notes;
    document.querySelector('#sheet-title').textContent=sheet.topic;
    document.querySelector('#sheet-label').textContent=sheet.historical?'This saved sheet needs a fresh source and correctness check before you rely on it.':sheet.edited?'This sheet has local edits. They have not been independently checked.':'Saved from a checked explanation. Personal edits are labelled separately.';
    document.querySelector('#sheet-render').innerHTML=rich(sheet.markdown);
    document.querySelector('#sheet-export').href='/study/sheets/'+encodeURIComponent(id)+'/export';
    status('#sheet-status','');editor.scrollIntoView({behavior:'smooth',block:'start'});
  }
  function recallResult(data,root=document){
    const feedback=data.feedback;
    root.querySelector('#recall-feedback').innerHTML=`<h3>${esc(({understood:'Understanding demonstrated',developing:'Good start — a few gaps',needs_work:'Review these ideas'})[feedback.verdict])}</h3>${feedback.correct.length?'<h4>What you explained correctly</h4>'+list(feedback.correct):''}${feedback.improve.length?'<h4>What to improve</h4>'+list(feedback.improve):''}<div class="rich-text">${rich(feedback.next_step)}</div>`;
  }
  document.addEventListener('study-explanation',e=>{
    const data=e.detail;
    const actions=document.querySelector('#explain-result .local-actions');
    const save=document.createElement('button');save.type='button';save.className='quiet-button';save.textContent='Save revision sheet';actions.append(save);
    const note=document.createElement('p');note.className='hint';note.setAttribute('role','status');actions.after(note);
    save.onclick=async()=>{save.disabled=true;try{
      let saved=await post('/study/sheets/from/'+encodeURIComponent(data.id));
      if(saved.refresh_available){
        if(!await window.appConfirm('Replace your edited sheet with this newly checked explanation? Your personal notes will be kept.',{title:'Refresh revision sheet?',confirmText:'Replace checked text'})){await openSheet(saved.id);return;}
        saved=await post('/study/sheets/from/'+encodeURIComponent(data.id)+'?replace=true&revision='+saved.revision);
      }
      note.textContent='Revision sheet saved in Learning tools. No additional AI call.';save.textContent='Open revision sheet';save.onclick=()=>openSheet(saved.id).catch(fail);
    }catch(error){note.textContent=error.message;}finally{save.disabled=false;}};
    const details=document.createElement('details');details.className='recall-checkpoint';details.innerHTML='<summary>Recall checkpoint — explain it in your own words</summary><p class="hint">Describe the core idea and when it applies. Your answer is checked against the course evidence; you do not need to repeat the worked example. Checking uses your selected AI connection.</p><form id="recall-form"><label>Your explanation<textarea name="answer" rows="5" minlength="10" maxlength="6000" required></textarea></label><button type="submit" class="primary-button" data-recall-submit>Check my understanding</button><p class="hint" data-recall-scope hidden>Choose a suitable paid connection in Settings for recall assessment.</p><p id="recall-status" role="status" aria-live="polite"></p><div id="recall-feedback" class="rich-text"></div></form>';
    document.querySelector('#explain-result').append(details);
    const recall=details.querySelector('form'),prior=drafts.get(data.id);if(prior){recall.elements.answer.value=prior.answer;if(prior.result)recallResult(prior.result,recall);}
    recall.querySelector('[data-recall-submit]').dataset.historical=String(Boolean(data.historical));
    if(data.historical){const p=document.createElement('p');p.className='hint';p.textContent='Refresh this explanation before checking recall.';recall.prepend(p);}
    if(!prior)api('/study/recall/history/'+encodeURIComponent(data.id)).then(history=>{const saved=history.items?.[0];if(saved&&details.isConnected&&!recall.elements.answer.value){recall.elements.answer.value=saved.answer;drafts.set(data.id,{answer:saved.answer,result:saved});recallResult(saved,recall);}}).catch(()=>{});
    recall.elements.answer.oninput=()=>{const previous=drafts.get(data.id)||{};drafts.set(data.id,{...previous,answer:recall.elements.answer.value});if(drafts.size>10)drafts.delete(drafts.keys().next().value);};
    recall.onsubmit=event=>{event.preventDefault();task('recall',recall,recall.querySelector('#recall-status'),async()=>{const result=await post('/study/recall',{explanation_id:data.id,answer:recall.elements.answer.value});drafts.set(data.id,{answer:recall.elements.answer.value,result});recallResult(result,recall);}).finally(recallScope);};recallScope();
  });
  document.addEventListener('study-view',event=>{
    if(!ready)return;
    if(event.detail==='learning')loadSheets().catch(fail);
    if(event.detail==='today')today().catch(fail);
  });
  document.addEventListener('study-progress-updated',()=>{if(ready)today().catch(e=>status('#today-status',e.message,true));});
  document.addEventListener('study-ready',()=>{
    ready=true;
    const plan=document.querySelector('#study-plan');plan.onsubmit=event=>{event.preventDefault();task('study-plan',plan,'#today-status',async()=>{await api('/study/plan',{method:'PUT',body:JSON.stringify({minutes:Number(plan.elements.minutes.value),exam_date:studyDates.iso(plan.elements.exam_date.value)})});await today();});};
    document.querySelector('[data-prev]').onclick=()=>{page=Math.max(0,page-1);renderSheets();};document.querySelector('[data-next]').onclick=()=>{page++;renderSheets();};
    const editor=form();let previewTimer;editor.elements.markdown.oninput=()=>{clearTimeout(previewTimer);previewTimer=setTimeout(()=>document.querySelector('#sheet-render').innerHTML=rich(editor.elements.markdown.value),180);};
    editor.onsubmit=event=>{event.preventDefault();task('sheet',editor,'#sheet-status',async()=>{
      sheet=await api('/study/sheets/'+encodeURIComponent(sheet.id),{method:'PUT',body:JSON.stringify({revision:sheet.revision,markdown:editor.elements.markdown.value,notes:editor.elements.notes.value})});
      document.querySelector('#sheet-label').textContent=sheet.edited?'Saved with local edits; these edits have not been independently checked.':'Saved from the checked explanation.';await loadSheets();
    });};
    document.querySelector('#sheet-close').onclick=async()=>{if(dirty()&&!await window.appConfirm('Discard unsaved sheet edits?',{title:'Unsaved sheet',confirmText:'Discard edits'}))return;editor.hidden=true;sheet=null;};
    document.querySelector('#sheet-delete').onclick=async()=>{if(!sheet||!await window.appConfirm('Delete this local revision sheet? Export it first if you want a copy.',{title:'Delete revision sheet?',confirmText:'Delete sheet'}))return;await api('/study/sheets/'+encodeURIComponent(sheet.id),{method:'DELETE'});editor.hidden=true;sheet=null;await loadSheets();};
    const actions=editor.querySelector('button[type=submit]').parentElement;
    actions.classList.add('sheet-actions');editor.insertBefore(actions,editor.querySelector('.sheet-grid'));actions.after(document.querySelector('#sheet-status'));
    const evidence=document.createElement('button');evidence.type='button';evidence.className='quiet-button';evidence.textContent='View source evidence';evidence.onclick=()=>sources({...sheet,question:sheet.markdown}).catch(fail);actions.append(evidence);
    const practise=document.createElement('button');practise.type='button';practise.className='quiet-button';practise.textContent='Practise this concept';practise.onclick=async()=>{if(local.practice&&!await window.appConfirm('Your current practice remains saved. Prepare practice for this concept?',{title:'Practise this concept?',confirmText:'Continue'}))return;document.querySelector('#topic').value=sheet.topic;document.querySelector('#scope').value='topic';document.querySelector('#topic-field').hidden=false;document.querySelector('#topic').required=true;document.querySelector('#practice-course').value=sheet.course_ids[0];document.querySelector('#difficulty').value='medium';pathControls();view('practice');};actions.append(practise);
    const search=document.querySelector('#study-search');search.onsubmit=event=>{event.preventDefault();task('study-search',search,'#study-search-status',async()=>{
      const q=search.elements.q.value;const [saved,documents]=await Promise.allSettled([api('/study/search?'+new URLSearchParams({q})),window.searchCourseDocuments(q)]);if(saved.status==='rejected')throw saved.reason;const data=saved.value;if(documents.status==='rejected')status('#document-search-status',documents.reason.message,true);const host=document.querySelector('#study-search-results');host.innerHTML='<h3>Saved study work</h3>'+(data.items.length?data.items.map((item,i)=>`<button type="button" class="quiet-button" data-search-result="${i}">${esc(({revision_sheet:'Revision sheet',explain:'Explanation',tutor:'Practice',path:'Mastery path',exam:'Bank exam'})[item.kind]||'Saved work')}: ${esc(item.title)}</button>`).join(''):'<p class="hint">No saved study work matches. <button type="button" class="quiet-button" data-empty-go="practice">Start a practice question</button></p>');
      host.querySelectorAll('[data-search-result]').forEach(b=>b.onclick=async()=>{const item=data.items[Number(b.dataset.searchResult)];if(item.kind==='revision_sheet')await openSheet(item.id);else await resume(item.kind,item.id);});
    });};
    window.addEventListener('beforeunload',event=>{if(dirty()){event.preventDefault();event.returnValue='';}});
    if(['progress','today'].includes(local.view))today().catch(fail);if(local.view==='learning')loadSheets().catch(fail);
  });
})();
