'use strict';
window.studyAttachments=window.studyAttachments||{};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rich=s=>window.studyRich(String(s??''));
const fileSize=bytes=>bytes<1024?`${bytes} B`:bytes<1048576?`${(bytes/1024).toFixed(1)} KB`:`${(bytes/1048576).toFixed(1)} MB`;
const local={view:'practice',courses:[],files:[],filePage:0,jobs:[],rebuildPending:false,practice:null,ask:null,path:null,settings:{},busy:new Set()};
window.studyLocal=local;
window.studyView=view;
window.studyApi=api;
window.studyResume=resume;
const types={};
// Text dates avoid operating-system locale placeholders such as dd/月/yyyy.
const studyDates={
 display(value){return value?String(value).split('-').reverse().join('/'):'';},
 iso(value){
  if(!value.trim())return null;
  const match=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim());
  if(!match)throw Error('Enter the exam date as dd/mm/yyyy.');
  const [,d,m,y]=match,date=new Date(Date.UTC(+y,+m-1,+d));
  if(date.getUTCFullYear()!==+y||date.getUTCMonth()!==+m-1||date.getUTCDate()!==+d)throw Error('Enter a valid exam date as dd/mm/yyyy.');
  return `${y}-${m}-${d}`;
 }
};


async function api(path,options={}) {
  const headers={...options.headers};
  if(options.body&&!(options.body instanceof FormData))headers['Content-Type']='application/json';
  if(options.method==='POST'&&/^\/(ask|answer|explain|bank-exams|study\/recall)/.test(path))headers['Idempotency-Key']=crypto.randomUUID();
  let response;try{response=await fetch(path,{cache:'no-store',...options,headers});}catch(_){throw Error('Study Desk cannot be reached. Reopen your workspace; your input has been kept.');}
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(typeof data.error==='string'?data.error:typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(x=>x.msg).join('; '):'The request could not be completed.');
  return data;
}
const post=(path,body={})=>api(path,{method:'POST',body:JSON.stringify(body)});
function status(selector,text,error=false){const el=typeof selector==='string'?$(selector):selector;if(!el)return;el.textContent=text;el.classList.toggle('local-error',error);}
function fail(error){$('#global-error').hidden=false;$('#global-error').textContent=error.message;}
async function task(name,form,selector,fn){
  if(local.busy.has(name))return;
  local.busy.add(name);const controls=[...form.querySelectorAll('button')];
  controls.forEach(x=>x.disabled=true);let seconds=0;status(selector,'Preparing and checking…');
  const timer=setInterval(()=>status(selector,`Preparing and checking… ${++seconds}s`),1000);
  try{const result=await fn();clearInterval(timer);status(selector,typeof result==='string'?result:'Ready.');}
  catch(error){clearInterval(timer);status(selector,error.message,true);}
  finally{controls.forEach(x=>x.disabled=false);local.busy.delete(name);pathControls();}
}
function view(name){
  local.scrollPositions||={};local.scrollPositions[local.view]=$('.app-main').scrollTop;
  if(!$('#view-'+name))name='practice';
  if(name!=='workspace')clearTimeout(local.jobsTimer);
  local.view=name;$$('.local-view').forEach(el=>el.hidden=el.id!=='view-'+name);
  $$('[data-view]').forEach(el=>el.classList.toggle('is-active',el.dataset.view===name));
  const navLabel=$(`[data-view="${name}"]`);
  $('#page-label').textContent=navLabel?navLabel.textContent.replace(/^\d+\s*/,'').trim():({explain:'Study - Explain',ask:'Study - Ask'}[name]||name);
  history.replaceState(null,'','#'+name);$('#global-error').hidden=true;
  if(name==='workspace')workspace().catch(fail);
  if(name==='progress')progress().catch(fail);
  if(name==='learning')learning().catch(fail);
  if(name==='settings')statistics().catch(fail);
  document.dispatchEvent(new CustomEvent('study-view',{detail:name}));requestAnimationFrame(()=>$('.app-main').scrollTo({top:local.scrollPositions[name]||0,behavior:'instant'}));
}
function theme(value){document.documentElement.dataset.theme=value;localStorage.setItem('study-theme',value);$('#setting-theme').value=value;}
async function courses(){
  const result=await api('/workspace/courses');local.courses=result.courses||[];
  $$('.course-select').forEach(el=>{const selected=el.value;el.innerHTML='<option value="">Choose a course</option>'+local.courses.map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');if(local.courses.some(c=>c.id===selected))el.value=selected;else if(local.courses.length===1)el.value=local.courses[0].id;});
  $('#coverage-open').disabled=!$('#workspace-course').value;$('#delete-course').disabled=!$('#workspace-course').value;
  renderMaintenance();document.dispatchEvent(new Event('study-courses-updated'));
}
function request(){return {topic:$('#scope').value==='syllabus'?'Any syllabus topic':$('#topic').value,scope:$('#scope').value,difficulty:$('#difficulty').value,question_types:[$('#question-type').value],course_ids:[$('#practice-course').value],doc_types:$$('#source-types input:checked').map(x=>x.value),figure_mode:'auto',client_request_id:crypto.randomUUID()};}
function figure(data){
  if(!data?.svg)return '';
  return `<section><h3>${esc(data.title||'Mathematical figure')}</h3>${DOMPurify.sanitize(data.svg,{USE_PROFILES:{svg:true,svgFilters:false},FORBID_TAGS:['foreignObject','script','image','use','a','animate','set'],FORBID_ATTR:['href','xlink:href','style']})}<details><summary>Text description</summary><p>${esc(data.alt||'')}</p></details></section>`;
}
function evidenceButton(data){return data.sources?.length?'<button type="button" class="quiet-button" data-evidence>View source evidence</button>':'';}
function renderQuestion(mode,data,restored=false){
  local[mode]=data;const host=$('#'+mode+'-result');host.hidden=false;
  const metadata=data.verification||{};
  host.innerHTML=`${local.path&&mode==='practice'?`<p>Concept mastery path · stage ${Number(local.path.index||0)+1} / 3</p>`:''}<p class="hint">${esc(data.difficulty||'')} · ${esc((data.question_type||'').replaceAll('_',' '))}</p><div class="rich-text">${rich(data.question)}</div>${figure(data.figure)}<details class="check-details"><summary>${metadata.solver_passed===true&&metadata.opa_passed===true?'Automated checks completed':'Available check details'}</summary><p class="hint">${metadata.premise_passed===true?'Setup: Checked · ':''}${metadata.solver_passed===true?'Solver: Passed · ':''}${metadata.opa_passed===true?'OPA: Passed · ':''}${Number.isFinite(metadata.latency)?`Time: ${metadata.latency}s`:''}</p></details><div class="local-actions">${evidenceButton(data)}<a class="quiet-button" href="/session/${encodeURIComponent(data.thread_id)}/export">Download transcript</a></div><div class="rich-text">${rich(data.opening_hint||'')}</div><div class="local-history"></div><form class="answer-form"><fieldset class="local-choices" ${data.options?.length?'':'hidden'}><legend>Choose an answer</legend>${(data.options||[]).map((option,i)=>`<label class="local-option"><input type="radio" name="choice-${mode}" value="${i}"><span><strong>${String.fromCharCode(65+i)}.</strong><div class="rich-text">${rich(option.replace(/^[A-D][.)]\s*/,''))}</div></span></label>`).join('')}</fieldset><label ${data.options?.length?'hidden':''}>Your attempt<textarea class="attempt" rows="5" maxlength="20000"></textarea></label><button class="primary-button" type="submit">Submit attempt</button><p class="answer-status" role="status"></p></form><div class="rich-text answer-feedback">${rich(restored?data.last_feedback||'':'')}</div><div class="path-next"></div>`;
  host.querySelector('[data-evidence]')?.addEventListener('click',()=>sources(data));
  if(restored)host.querySelector('.local-history').innerHTML=(data.history||[]).slice(-10).map(item=>`<div class="local-item rich-text">${rich(item.answer||item.feedback||item.content||'')}</div>`).join('');
  if(['correct','revealed','blocked'].includes(data.status))host.querySelector('.answer-form').hidden=true;
  host.querySelector('.answer-form').onsubmit=event=>{
    event.preventDefault();const form=event.currentTarget,selected=form.querySelector('input:checked');
    const answer=data.options?.length?(selected?`${String.fromCharCode(65+Number(selected.value))}. ${data.options[Number(selected.value)]}`:''):form.querySelector('.attempt').value;
    if(!answer.trim()){form.querySelector('.answer-status').textContent='Enter an answer first.';return;}
    task('answer-'+mode,form,'#'+mode+'-result .answer-status',async()=>{
      const result=await post('/answer',{thread_id:data.thread_id,answer});
      host.querySelector('.local-history').insertAdjacentHTML('beforeend',`<div class="local-item rich-text"><strong>Your attempt</strong>${rich(answer)}${rich(result.feedback)}${result.solution?rich(result.solution):''}</div>`);
      form.querySelector('.attempt').value='';
      if(result.status!=='awaiting_answer')form.hidden=true;
      data.status=result.status;
      if(mode==='exam'&&result.status!=='awaiting_answer'){renderExam(await api('/bank-exams/'+local.exam.id));}
      if(mode==='exam'&&result.status==='awaiting_answer')examNext({completed:local.exam.index===local.exam.count-1&&result.status!=='awaiting_answer',can_advance:result.status!=='awaiting_answer'});
      if(local.path&&mode==='practice'&&result.is_correct&&local.path.index===2){host.querySelector('.path-next').textContent='Mastery path completed.';}
      else if(local.path&&mode==='practice'&&result.is_correct){host.querySelector('.path-next').innerHTML='<button class="primary-button" id="path-next">Continue mastery path</button>';$('#path-next').onclick=()=>task('path-next',host.querySelector('.path-next'),'#practice-status',nextPath);}
    });
  };
}
async function nextPath(){
  const data=await post('/ask/path/'+local.path.id+'/next');
  local.path=data;
  if(data.completed||data.status==='completed'){ $('#practice-result .path-next').textContent='Mastery path completed.';local.path=null;return; }
  renderPath(data);
}
function renderPath(data){local.path=data;const q=data.question;if(q&&typeof q==='object')renderQuestion('practice',{...q,status:data.current_status||q.status,history:data.history||[]},true);if(data.can_advance){const h=$('#practice-result .path-next');h.innerHTML='<button class="primary-button" id="path-next">Continue mastery path</button>';$('#path-next').onclick=()=>task('path-next',h,'#practice-status',nextPath);}if(data.completed)$('#practice-result .path-next').textContent='Mastery path completed.';if(!q)throw Error('The learning path could not be displayed. Resume it from Learning tools.');}
async function explanation(data){
  const host=$('#explain-result');host.hidden=false;host.innerHTML=`<div class="rich-text">${rich(data.markdown)}</div><div class="local-actions"><button id="test-understanding" class="primary-button">Test my understanding</button>${evidenceButton(data)}</div>`;
  host.querySelector('[data-evidence]')?.addEventListener('click',()=>sources({...data,question:data.markdown}));
  $('#test-understanding').onclick=()=>{
    if(local.practice&&!(window.confirm('Your current practice remains in saved sessions. Prepare practice for this concept?')))return;
    $('#topic').value=data.topic;$('#scope').value='topic';$('#topic-field').hidden=false;$('#topic').required=true;$('#difficulty').value='medium';$('#practice-course').value=data.course_ids[0];pathControls();view('practice');
  };
  document.dispatchEvent(new CustomEvent('study-explanation',{detail:data}));
}
async function sources(data){
  data={...data,sources:(data.sources||[]).map(s=>({...s,source_file:s.source_file||s.file}))};
  const dialog=$('#source-dialog');dialog.classList.remove('document-only');$('#source-question').innerHTML=rich(data.question);$('#source-select').innerHTML=(data.sources||[]).map((s,i)=>`<option value="${i}">${esc(s.ref)} · ${esc(s.source_file)} · p. ${esc(s.page)}</option>`).join('');
  const files=(await api('/workspace/files')).files||[];
  const update=()=>{
    const source=data.sources[Number($('#source-select').value)];$('#source-excerpt').textContent=source.excerpt||source.text||'';
    const file=files.find(f=>f.filename===source.source_file&&f.course_id===source.course_id);
    $('#source-pdf').hidden=!file||!file.filename.toLowerCase().endsWith('.pdf');$('#source-download').hidden=!file;
    window.studyBookmark?.(file||null,Number(source.page)||1);if(file){const url=`/workspace/documents/${encodeURIComponent(file.id)}/file#page=${Number(source.page)||1}`;$('#source-pdf').src=file.filename.toLowerCase().endsWith('.pdf')?url:'about:blank';$('#source-download').href=url;}
  };$('#source-select').onchange=update;update();dialog.showModal();
}
async function jobs(){
  clearTimeout(local.jobsTimer);
  const previous=local.jobs;const data=await api('/workspace/jobs');const rows=local.jobs=data.jobs||[];
  if(local.view==='workspace'&&rows.some(j=>j.status==='done'&&previous.some(old=>old.id===j.id&&old.status!=='done'))){
    const course=$('#workspace-course').value;const fresh=(await api('/workspace/files'+(course?'?course_id='+encodeURIComponent(course):''))).files||[];
    if(course===$('#workspace-course').value){local.files=fresh;$$('[data-preview]').forEach(b=>{const file=fresh.find(f=>f.id===b.dataset.preview);const label=b.closest('.local-item')?.querySelector('.local-file-meta span:last-child');if(file&&label)label.textContent=file.indexed?file.chunks+' chunks':'Waiting for indexing';});}
  }
  $('#jobs').innerHTML=rows.slice(0,8).map(j=>`<p>${esc(local.courses.find(c=>c.id===j.course_id)?.name||'Indexing')} · ${esc(j.status)} ${Number(j.progress)||0}% ${esc(j.message||j.error||'')}${j.status==='failed'?` <button type="button" class="quiet-button" data-retry="${esc(j.id)}">Retry</button>`:''}</p>`).join('');
  renderMaintenance();
  $$('[data-retry]').forEach(b=>b.onclick=async()=>{try{await post('/workspace/jobs/'+b.dataset.retry+'/retry');await jobs();}catch(e){status('#upload-status',e.message,true);}});
  if(local.view==='workspace'&&rows.some(j=>['queued','running'].includes(j.status)))local.jobsTimer=setTimeout(()=>jobs().catch(fail),2000);
}
function renderMaintenance(){
  const course=$('#workspace-course').value;
  const active=local.jobs.find(j=>j.course_id===course&&['queued','running'].includes(j.status));
  const hasFiles=local.files.some(f=>f.course_id===course);
  $('#reindex').disabled=!course||!hasFiles||!!active||local.rebuildPending;
  $('#reindex-hint').textContent=!course?'Choose a course to manage its index.':!hasFiles?'Upload course material before rebuilding its index.':active?'This course is being indexed. Wait for it to finish.':'Rebuild only this course. Existing documents and course settings are kept. This makes no AI generation calls.';
  const job=local.jobs.find(j=>j.course_id===course&&j.doc_type==='rebuild');
  $('#rebuild-progress').innerHTML=job?`<p>${esc(({queued:'Rebuild queued',running:'Rebuilding course index',done:'Course index rebuilt',failed:'Rebuild failed'})[job.status]||job.status)} · ${Number(job.progress)||0}% ${esc(job.message||'')}</p>${['queued','running'].includes(job.status)?`<progress aria-label="Course index rebuild progress" max="100" value="${Number(job.progress)||0}"></progress>`:''}`:'';
}
async function workspace(){
  const course=$('#workspace-course').value;
  local.files=(await api('/workspace/files'+(course?'?course_id='+encodeURIComponent(course):''))).files||[];local.filePage=0;renderFiles();await jobs();
  $('#coverage-open').disabled=!course;$('#delete-course').disabled=!course;
}
function renderFiles(){
  const query=$('#file-search').value.trim().toLowerCase(),rows=local.files.filter(f=>f.filename.toLowerCase().includes(query)),size=10;
  local.filePage=Math.min(local.filePage,Math.max(0,Math.ceil(rows.length/size)-1));
  $('#files').innerHTML=rows.slice(local.filePage*size,(local.filePage+1)*size).map(f=>`<article class="local-item"><label class="file-select-label"><input type="checkbox" class="file-choice" data-file-select="${esc(f.id)}" aria-label="Select ${esc(f.filename)}"><strong>${esc(f.filename)}</strong></label><p class="local-file-meta"><span data-file-type-label>${esc(types[f.doc_type]||f.doc_type)}</span><span>${fileSize(f.size)}</span><span>${f.indexed?`${Number(f.chunks)} chunks`:'Waiting for indexing'}</span></p><div class="local-actions"><button class="quiet-button" data-preview="${esc(f.id)}">Preview</button><a class="quiet-button" href="/workspace/documents/${encodeURIComponent(f.id)}/download">Download</a><button class="quiet-button" data-syllabus="${esc(f.id)}" data-enabled="${Boolean(f.syllabus_enabled)}">${Boolean(f.syllabus_enabled)?'Included in':'Excluded from'} any syllabus topic</button><label>Document type<select data-type="${esc(f.id)}">${Object.entries(types).map(([v,t])=>`<option value="${v}" ${v===f.doc_type?'selected':''}>${t}</option>`).join('')}</select></label><button class="quiet-button" data-delete="${esc(f.id)}">Delete</button></div></article>`).join('')||'<p class="hint">No documents found. Add your course material above.</p>';
  $('#file-pages').innerHTML=`<button class="quiet-button" id="file-prev" ${local.filePage===0?'disabled':''}>Previous</button><span>${rows.length?local.filePage+1:0} / ${Math.ceil(rows.length/size)} · ${rows.length} documents</span><button class="quiet-button" id="file-next" ${(local.filePage+1)*size>=rows.length?'disabled':''}>Next</button>`;
  $('#file-prev').onclick=()=>{local.filePage--;renderFiles();};$('#file-next').onclick=()=>{local.filePage++;renderFiles();};
  $$('[data-preview]').forEach(b=>b.onclick=async()=>{try{const f=local.files.find(x=>x.id===b.dataset.preview);const result=await api('/workspace/documents/'+f.id+'/preview');$('#source-dialog').classList.toggle('document-only',result.mode==='pdf');$('#source-question').innerHTML=rich(result.content||f.filename);if(result.mode==='image'){const image=document.createElement('img');image.src=result.file_url;image.alt=f.filename;image.className='source-image';$('#source-question').append(image);}$('#source-select').innerHTML='<option>Original document</option>';$('#source-excerpt').textContent='';$('#source-pdf').hidden=result.mode!=='pdf';window.studyBookmark?.(f,1);$('#source-pdf').src=result.mode==='pdf'?result.file_url:'about:blank';$('#source-download').href=result.file_url;$('#source-download').hidden=false;$('#source-select').onchange=null;$('#source-dialog').showModal();}catch(e){fail(e);}});
  $$('[data-syllabus]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api('/workspace/documents/'+b.dataset.syllabus+'/syllabus',{method:'PUT',body:JSON.stringify({enabled:b.dataset.enabled!=='true'})});await workspace();}catch(e){fail(e);b.disabled=false;}});
  async function saveType(select,value){
    const file=local.files.find(f=>f.id===select.dataset.type),previous=file.doc_type;
    select.disabled=true;
    try{
      const result=await api('/workspace/files/'+file.id+'/type',{method:'PUT',body:JSON.stringify({doc_type:value})});
      file.doc_type=result.doc_type;select.value=result.doc_type;
      select.closest('article').querySelector('[data-file-type-label]').textContent=types[result.doc_type];
      status('#file-type-status','Document type saved.');
    }catch(e){select.value=previous;throw e;}finally{select.disabled=false;}
  }
  $$('[data-type]').forEach(b=>b.onchange=async()=>{try{await saveType(b,b.value);}catch(e){status('#file-type-status',e.message,true);}});
  const choices=$$('[data-file-select]');
  function selection(){const count=choices.filter(c=>c.checked).length;$('#file-type-tools').hidden=!count;$('#file-type-count').textContent=`${count} selected`;}
  choices.forEach(c=>c.onchange=selection);selection();
  $('#file-select-page').disabled=!choices.length;
  $('#file-select-page').onclick=()=>{const checked=!choices.every(c=>c.checked);choices.forEach(c=>c.checked=checked);selection();};
  $('#file-type-apply').onclick=async()=>{
    const selected=choices.filter(c=>c.checked),button=$('#file-type-apply'),value=$('#file-bulk-type').value;
    const locked=$$('#files select,#files button,#file-pages button,#file-search,#workspace-course,#file-bulk-type');
    const disabled=locked.map(el=>el.disabled);locked.forEach(el=>el.disabled=true);
    button.disabled=true;$('#file-select-page').disabled=true;choices.forEach(c=>c.disabled=true);
    let saved=0;
    try{for(const choice of selected){await saveType($$('[data-type]').find(s=>s.dataset.type===choice.dataset.fileSelect),value);choice.checked=false;saved++;$$('[data-type]').forEach(el=>el.disabled=true);}
      status('#file-type-status',`${saved} document types saved.`);
    }catch(e){status('#file-type-status',`${saved} saved. ${e.message} Remaining files stay selected.`,true);}
    finally{locked.forEach((el,i)=>el.disabled=disabled[i]);button.disabled=false;$('#file-select-page').disabled=false;choices.forEach(c=>c.disabled=false);selection();}
  };
  $$('[data-delete]').forEach(b=>b.onclick=async()=>{if(!confirm('Delete this document and its indexed content?'))return;try{await api('/workspace/files/'+b.dataset.delete,{method:'DELETE'});await workspace();}catch(e){fail(e);}});
}
async function coverage(){const id=$('#workspace-course').value;if(!id)return;const data=await api('/workspace/courses/'+id+'/coverage');$('#coverage').hidden=false;$('#coverage-summary').textContent='Index summary: '+Number(data.eligible_sections??data.sections?.length??0)+' extracted sections available for practice. This is not a check of complete syllabus coverage.';$('#scope-rules').value=typeof data.scope_rules==='string'?data.scope_rules:(data.scope_rules?.[0]?.scope_notes||'');}
async function learning(){const data=await api('/learning/dashboard');$('#saved-sessions').innerHTML=(data.sessions||[]).map((s,i)=>`<div class="local-item" data-history-row ${i>=3?'hidden':''}><p>${esc(s.question)}</p><p class="hint">${esc((s.course_ids||[]).map(id=>local.courses.find(c=>c.id===id)?.name||'Course unavailable').join(', '))} · ${esc(({awaiting_answer:'In progress',correct:'Completed',revealed:'Answer reviewed'})[s.status]||s.status||'Saved')}</p><button class="quiet-button" data-resume="${esc(s.id)}" data-kind="${esc(s.kind)}">Resume ${esc(({tutor:"session",explain:"explanation",path:"mastery path",exam:"bank exam"})[s.kind]||"session")}</button></div>`).join('')||'<p class="hint">Your study sessions will appear here. <button type="button" class="quiet-button" data-empty-go="practice">Start practising</button></p>';$$('[data-resume]').forEach(b=>b.onclick=()=>resume(b.dataset.kind,b.dataset.resume).catch(fail));const old=$('#saved-history-toggle');if(old)old.remove();if(data.sessions.length>3){const toggle=document.createElement('button');toggle.id='saved-history-toggle';toggle.type='button';toggle.className='quiet-button';toggle.textContent='Show all '+data.sessions.length+' saved sessions';toggle.setAttribute('aria-expanded','false');toggle.onclick=()=>{const expanded=toggle.getAttribute('aria-expanded')!=='true';toggle.setAttribute('aria-expanded',String(expanded));$$('[data-history-row]').forEach((r,i)=>r.hidden=!expanded&&i>=3);toggle.textContent=expanded?'Show recent sessions':'Show all '+data.sessions.length+' saved sessions';};$('#saved-sessions').after(toggle);}await bank();}
async function resume(kind,id){
  if(kind==='tutor'){const data=await api('/session/'+id);const mode=data.mode==='question'?'ask':'practice';view(mode);local.path=null;renderQuestion(mode,data,true);}
  else if(kind==='explain'){const data=await api('/explain/'+id);view('explain');await explanation(data);}
  else if(kind==='exam'){view('learning');renderExam(await api('/bank-exams/'+id));}
  else if(kind==='path'){view('practice');renderPath(await api('/ask/path/'+id));}
}
const questionLabels={};
async function bank(){const course=$('#bank-course').value;if(!course){local.bankData=null;$('#bank-counts').innerHTML='<p class="hint">Choose a course to view verified counts. <button type="button" class="quiet-button" data-empty-go="workspace">Manage material</button></p>';examAvailable();return;}const data=await api('/learning/courses/'+course+'/bank');if(course!==$('#bank-course').value)return;local.bankData={...data,course_id:course};const counts=data.counts||[];const levels=[...new Set(counts.map(r=>r.difficulty))];const kinds=[...new Set(counts.map(r=>r.question_type))];$('#bank-counts').innerHTML=levels.length?table(levels.map(d=>Object.fromEntries([['Difficulty',d],...kinds.map(t=>[questionLabels[t]||t,counts.find(r=>r.difficulty===d&&r.question_type===t)?.count||0])]))):'<p class="hint">No verified questions in this course yet. <button type="button" class="quiet-button" data-empty-go="practice">Practise a topic</button></p>';examAvailable();}
function examAvailable(){const data=local.bankData;if(!data||data.course_id!==$('#exam-course').value){$('#exam-available').textContent='Choose a course to see available verified questions.';return;}const count=(data.counts||[]).filter(r=>($('#exam-difficulty').value==='any'||r.difficulty===$('#exam-difficulty').value)&&($('#exam-type').value==='any'||r.question_type===$('#exam-type').value)).reduce((n,r)=>n+r.count,0);$('#exam-available').textContent=`${count} verified question${count===1?'':'s'} match these filters. Up to 10 can be used per exam.`;}

function table(rows){if(!Array.isArray(rows))return `<pre>${esc(JSON.stringify(rows,null,2))}</pre>`;if(!rows.length)return '<p class="hint">No entries yet.</p>';const keys=Object.keys(rows[0]);return `<div class="local-table-wrap"><table class="local-table"><thead><tr>${keys.map(k=>`<th>${esc(k.replaceAll('_',' '))}</th>`).join('')}</tr></thead><tbody>${rows.slice(0,40).map(r=>`<tr>${keys.map(k=>`<td>${esc(r[k]===null?'—':typeof r[k]==='number'&&/cost|usd|rate/.test(k)?r[k].toFixed(5):typeof r[k]==='object'?JSON.stringify(r[k]):typeof r[k]==='string'?r[k].replaceAll('_',' '):r[k])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;}
async function progress(){
  const data=await api('/progress');const totals=data.dashboard?.totals||data.dashboard||{};
  $('#progress-summary').innerHTML='<p class="hint">First attempt measures independent practice. Solved eventually includes later attempts. Cards, bank exams and deliberate retries do not increase these totals.</p><div class="local-metrics">'+Object.entries(totals).filter(([k,v])=>['total','first_attempt_accuracy','accuracy','mistakes','streak_days'].includes(k)&&typeof v==='number').map(([k,v])=>'<div><strong>'+esc(k==='accuracy'?'Solved eventually (%)':k==='first_attempt_accuracy'?'First attempt (%)':k.replaceAll('_',' '))+'</strong><span>'+esc(v)+'</span></div>').join('')+'</div>';
  $('#mistakes').innerHTML=(data.mistakes||[]).map(r=>`<article class="local-item rich-text">${rich(r.question)}<div class="local-actions"><button class="quiet-button" data-mistake-retry="${esc(r.id)}">Try again</button><button class="quiet-button" data-review-concept="${esc(r.id)}">Explain this concept</button><button class="quiet-button" data-resolve="${esc(r.id)}">Mark resolved</button></div></article>`).join('')||'<p class="hint">No open mistakes. <button type="button" class="quiet-button" data-empty-go="practice">Start practising</button></p>';
  $$('[data-mistake-retry]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const result=await post('/progress/mistakes/'+b.dataset.mistakeRetry+'/retry');view('learning');renderExam(result);$('#exam-result').scrollIntoView({block:'start'});}catch(e){fail(e);}finally{b.disabled=false;}});
  $$('[data-review-concept]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const context=await api('/library/review-context/'+encodeURIComponent(b.dataset.reviewConcept));if(local.providerScope==='brief_only')throw Error('Choose a suitable paid connection to explain a mistake in depth.');$('#explain-course').value=context.course_id;$('#explain-topic').value=context.topic;$('#depth').value='deep';view('explain');$('#explain-form').requestSubmit();}catch(e){fail(e);}finally{b.disabled=false;}});
  $$('[data-resolve]').forEach(b=>b.onclick=async()=>{await post('/progress/mistakes/'+b.dataset.resolve+'/resolve');await progress();});
  const card=data.flashcards?.[0];$('#review-cards').innerHTML=card?`<article class="local-item"><h3>${card.front?.split(/\s+/).length>25?'Practice question review':'Due recall card'}</h3><div class="rich-text">${rich(card.front||card.question)}</div><details><summary>Show answer</summary><div class="rich-text">${rich(card.back||card.answer)}</div><p class="hint">Again: could not recall · Hard: recalled with effort · Good: recalled correctly · Easy: recalled immediately. Your rating sets the next review date.</p><div class="local-actions">${['again','hard','good','easy'].map(r=>`<button class="quiet-button" data-rating="${r}">${r}</button>`).join('')}</div></details></article>`:'<p class="hint">No review cards due.</p>';
  $$('[data-rating]').forEach(b=>b.onclick=async()=>{try{await post('/progress/flashcards/'+card.id+'/review',{rating:b.dataset.rating});await progress();}catch(e){fail(e);}});
  document.dispatchEvent(new Event('study-progress-updated'));
}
async function statistics(){const data=await api('/local/statistics');const metrics={...(data.period||{})};if(metrics.missing_usage)metrics.cost_usd=null;$('#statistics').innerHTML='<h3>Last 30 days</h3>'+table([metrics])+'<p class="hint">Cached input is included in input tokens. Cached counts and per-question details cover retained provider traces. Costs are estimates in USD; — means usage is unknown.</p><h3>Recent question operations</h3>'+table((data.operations||[]).map(r=>({kind:r.kind,outcome:r.failures?'Failed':'Completed',input:r.input_tokens,cached_input:r.cached_input_tokens,output:r.output_tokens,cost_usd:r.missing_usage?null:r.cost_usd,seconds:Math.round(Number(r.latency_ms||0)/100)/10})));
  const timing=data.pipeline;if(timing)$('#statistics').insertAdjacentHTML('beforeend','<details class="library-panel"><summary>Processing timings</summary><p class="hint">'+esc(timing.note)+'</p>'+table([{workflows:timing.workflows,queue_seconds:Number((timing.mean_queue_ms/1000).toFixed(2)),processing_seconds:Number((timing.mean_processing_ms/1000).toFixed(2))}])+table(timing.stages.map(s=>({stage:s.stage,observations:s.observations,seconds:Number((s.mean_ms/1000).toFixed(2))})))+'</details>');
}
function pathControls(){const any=$('#scope').value==='syllabus',limited=local.providerScope==='brief_only';$('#start-path').disabled=any||limited;for(const [id,name] of [['practice-form','practice'],['ask-form','ask']])$('#'+id+' button[type=submit]').disabled=limited||local.busy.has(name);$('#path-guidance').textContent=limited?'Choose a suitable paid connection in Settings for question generation and mastery paths.':any?'Choose Specific topic to start a mastery path.':'Mastery path uses the topic and question type above: Foundation → Application → Synthesis. Each checked question is prepared only when you reach it.';}
function examNext(data){const host=$('#exam-result .path-next');if(data.completed){const summary=data.summary;if(!summary){host.textContent='Bank exam completed.';return;}host.innerHTML=`<section aria-label="Paper summary"><h2>Paper summary</h2><p><strong>${summary.solved} / ${summary.total} solved (${summary.solved_percent}%)</strong> · ${summary.first_attempt_correct} correct on the first attempt · ${summary.needs_review} to revisit</p><p class="hint">${esc(summary.scoring_note)}</p>${table(summary.questions.map(q=>({Question:q.number,Difficulty:q.difficulty,Type:questionLabels[q.question_type]||q.question_type,Result:q.status==='correct'?'Solved':q.status==='revealed'?'Solution shown':'Not solved',Attempts:q.attempts}))) }<div class="local-actions">${summary.questions.map(q=>`<button type="button" class="quiet-button" data-exam-review="${esc(q.thread_id)}">Review Q${q.number}</button>`).join('')}<a class="quiet-button" href="/bank-exams/${encodeURIComponent(data.id)}/summary/export">Download paper summary</a></div><div id="exam-review"></div></section>`;host.querySelectorAll('[data-exam-review]').forEach(b=>b.onclick=async()=>{try{const q=await api('/session/'+b.dataset.examReview);$('#exam-review').innerHTML='<h3>Question review</h3><div class="rich-text">'+rich(q.question)+rich(q.last_feedback||'')+'</div>';}catch(e){fail(e);}});return;}if(data.can_advance){host.innerHTML='<button class="primary-button" id="exam-next">Next bank question</button>';$('#exam-next').onclick=()=>task('exam-next',host,'#exam-status',async()=>renderExam(await post('/bank-exams/'+local.exam.id+'/next')));}}
function renderExam(data){renderQuestion('exam',{...data.question,status:data.current_status||data.question.status,history:data.history||[]},true);local.exam=data;$('#exam-result').insertAdjacentHTML('afterbegin',`<p>Verified bank exam · question ${data.index+1} / ${data.count}</p>`);examNext(data);}

async function init(){
  $$('[data-view]').forEach(b=>b.onclick=()=>view(b.dataset.view));
  const catalog=await api('/local/catalog');Object.assign(types,catalog.document_types);Object.assign(questionLabels,catalog.question_types);$('#file-bulk-type').innerHTML=Object.entries(types).map(([v,t])=>`<option value="${v}">${t}</option>`).join('');
  $('#doc-type').innerHTML=Object.entries(types).map(([v,t])=>`<option value="${v}" ${v==='notes'?'selected':''}>${t}</option>`).join('');
  $('#source-types').innerHTML=Object.entries(types).map(([v,t])=>`<label><input type="checkbox" value="${v}">${t}</label>`).join('');
  $('#theme-toggle').onclick=async()=>{const value=document.documentElement.dataset.theme==='dark'?'light':'dark';theme(value);local.settings.theme=value;try{local.settings=await api('/settings',{method:'PUT',body:JSON.stringify(local.settings)});}catch(error){fail(error);}};
  $('#scope').onchange=()=>{$('#topic-field').hidden=$('#scope').value==='syllabus';$('#topic').required=$('#scope').value!=='syllabus';pathControls();};
  $('#practice-form').onsubmit=e=>{e.preventDefault();task('practice',e.currentTarget,'#practice-status',async()=>{local.path=null;const data=await post('/ask',request());renderQuestion('practice',data);});};
  $('#start-path').onclick=()=>{if($('#scope').value!=='topic'||!$('#topic').value.trim()){status('#practice-status','Enter a specific topic first.',true);return;}if(!$('#practice-form').reportValidity())return;task('path',$('#practice-form'),'#practice-status',async()=>{const r=request();renderPath(await post('/ask/path',{topic:r.topic,course_ids:r.course_ids,question_type:r.question_types[0],doc_types:r.doc_types}));});};
  $('#explain-form').onsubmit=e=>{e.preventDefault();task('explain',e.currentTarget,'#explain-status',async()=>{await explanation(await post('/explain',{topic:$('#explain-topic').value,course_ids:[$('#explain-course').value],depth:$('#depth').value}));});};
  $('#ask-form').onsubmit=e=>{e.preventDefault();task('ask',e.currentTarget,'#ask-status',async()=>{const queue=studyAttachments.ask;if(!queue)throw Error('Attachment controls are still loading. Try again.');const attachment=await queue.question();if($('#own-question').value.length+attachment.attachment_text.length+200>queue.limits.question_chars)throw Error('The combined question is too long. Remove unrelated text or pages.');if(!$('#own-question').value.trim()&&!attachment.attachment_text.trim())throw Error('Enter a question or attach readable question text.');queue.lock(true);try{renderQuestion('ask',await post('/ask/question',{question:$('#own-question').value,...attachment,client_request_id:crypto.randomUUID()}));}finally{queue.lock(false);}});};
  $('#course-form').onsubmit=e=>{e.preventDefault();task('course',e.currentTarget,'#course-status',async()=>{const c=await post('/workspace/courses',{name:$('#course-name').value});await courses();$('#workspace-course').value=c.id;$('#course-name').value='';await workspace();});};
  $('#upload-form').onsubmit=e=>{e.preventDefault();task('upload',e.currentTarget,'#upload-status',async()=>{const queue=studyAttachments.workspace;if(!queue||!queue.files.length)throw Error('Select files to upload first.');queue.lock(true);try{const receipt=await window.uploadCourseBatch({courseId:$('#workspace-course').value,docType:$('#doc-type').value,files:[...queue.files],onProgress:p=>{status('#upload-status',p.text);queue.message(p.text);}});const failed=(receipt.outcomes||[]).filter(x=>x.status==='failed');queue.files=failed.map(x=>queue.files[x.index]);queue.invalidate();$('#documents').value='';await courses();await workspace();queue.message((receipt.outcomes||[]).map(x=>x.filename+': '+x.status+(x.error?' — '+x.error:'')).join(' · '),failed.length>0);if(failed.length)throw Error(failed.length+' file(s) failed. Successful files are saved; click Upload and index to retry only the remaining files.');}finally{queue.lock(false);}});};
  $('#workspace-course').onchange=()=>{$('#coverage').hidden=true;workspace().catch(fail);};$('#file-search').oninput=()=>{local.filePage=0;renderFiles();};
  $('#coverage-open').onclick=()=>coverage().catch(fail);$('#coverage-close').onclick=()=>$('#coverage').hidden=true;
  $('#scope-save').onclick=async()=>{try{await api('/workspace/courses/'+$('#workspace-course').value+'/scope',{method:'PUT',body:JSON.stringify({scope_notes:$('#scope-rules').value})});status('#coverage-status','Scope saved.');}catch(e){status('#coverage-status',e.message,true);}};
  $('#delete-course').onclick=async()=>{if(!confirm('Delete this course and all its documents?'))return;try{await api('/workspace/courses/'+$('#workspace-course').value,{method:'DELETE'});await courses();await workspace();}catch(e){fail(e);}};
  $('#reindex').onclick=async()=>{if($('#reindex').disabled)return;local.rebuildPending=true;renderMaintenance();status('#reindex-status','Requesting a course index rebuild…');try{await post('/workspace/reindex',{course_id:$('#workspace-course').value});status('#reindex-status','Rebuild requested. Progress appears below.');await jobs();}catch(e){status('#reindex-status',e.message,true);}finally{local.rebuildPending=false;renderMaintenance();}};
  $('#source-close').onclick=()=>$('#source-dialog').close();
  $('#source-dialog').addEventListener('close',()=>$('#source-pdf').src='about:blank');
  $('#source-download').removeAttribute('target');
  $('#source-download').onclick=()=>{const link=$('#source-download'),url=new URL(link.href,location.href);if(url.origin===location.origin&&/^\/workspace\/documents\/[^/]+\/file$/.test(url.pathname)){link.href=url.pathname.replace(/\/file$/,'/download');link.setAttribute('download','');}};
  $('#exam-form').onsubmit=e=>{e.preventDefault();task('exam',e.currentTarget,'#exam-status',async()=>renderExam(await post('/bank-exams',{course_id:$('#exam-course').value,count:Number($('#exam-count').value),difficulty:$('#exam-difficulty').value,question_type:$('#exam-type').value})));};
  pathControls();
  $('#bank-course').onchange=()=>{$('#exam-course').value=$('#bank-course').value;bank().catch(fail);};
  $('#exam-course').onchange=()=>{$('#bank-course').value=$('#exam-course').value;bank().catch(fail);};
  $('#exam-difficulty').onchange=examAvailable;$('#exam-type').onchange=examAvailable;
  $('#settings-form').onsubmit=e=>{e.preventDefault();task('settings',e.currentTarget,'#settings-status',async()=>{local.settings=await api('/settings',{method:'PUT',body:JSON.stringify({...local.settings,theme:$('#setting-theme').value,attempts_before_reveal:Number($('#attempt-limit').value)})});theme(local.settings.theme);});};
  $('#backup').onclick=async()=>{try{await post('/local/backup');status('#maintenance-status','Backup saved in the local backup folder.');}catch(e){status('#maintenance-status',e.message,true);}};
  $('#verify-backup').onclick=async()=>{try{await api('/local/backup/verify');status('#maintenance-status','Latest backup verified: archive and SQLite integrity checks passed.');}catch(e){status('#maintenance-status',e.message,true);}};
  $('#statistics-refresh').onclick=()=>statistics().catch(fail);
  await courses();local.settings=await api('/settings');$('#attempt-limit').value=local.settings.attempts_before_reveal||3;theme(local.settings.theme||'light');
  view(location.hash.slice(1)||'today');
  document.dispatchEvent(new Event('study-ready'));
}
document.addEventListener('DOMContentLoaded',()=>init().catch(fail));
