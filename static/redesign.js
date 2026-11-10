/* Course-first information architecture for the local workspace. */
'use strict';
(()=>{
  const by=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const modes=[['practice','Practice'],['explain','Explain'],['ask','Ask']];
  const labels={today:'Today',practice:'Study - Practice',explain:'Study - Explain',ask:'Study - Ask',workspace:'Workspace',progress:'Progress',learning:'Library',settings:'Settings'};

  function wrapFeedback(){
    const button=by('send-feedback');
    if(!button||button.parentElement?.classList.contains('sidebar-feedback'))return;
    const footer=document.createElement('div');footer.className='sidebar-feedback';
    button.before(footer);footer.append(button);
    button.setAttribute('aria-haspopup','dialog');
    button.setAttribute('aria-controls','feedback-dialog');
  }

  function buildStudyTabs(){
    modes.forEach(([name,label])=>{
      const host=by('view-'+name);if(!host)return;
      const tabs=document.createElement('nav');tabs.className='study-mode-tabs';tabs.setAttribute('aria-label','Study mode');
      tabs.innerHTML=modes.map(([value,text])=>`<button type="button" data-study-mode="${value}" ${value===name?'class="is-active"':''}>${text}</button>`).join('');
      host.querySelector('h1')?.after(tabs);
      tabs.querySelectorAll('[data-study-mode]').forEach(button=>{
        button.onclick=()=>window.studyView(button.dataset.studyMode);
      });
    });
  }

  function setupCourseContext(){
    const label=by('page-label');if(!label)return;
    let left=document.querySelector('.topbar-left');
    if(!left){left=document.createElement('div');left.className='topbar-left';label.before(left);left.append(label);}
    let context=left.querySelector('.course-context');
    if(!context){
      context=document.createElement('div');context.className='course-context';
      context.innerHTML='<label for="active-course">Course</label><select id="active-course" aria-label="Active course"></select><button class="context-manage" type="button" id="context-manage">Manage material</button>';
      left.append(context);
    }
    by('context-manage').onclick=()=>window.studyView('workspace');
    by('active-course').onchange=event=>{
      const id=event.target.value;
      localStorage.setItem('study-active-course',id);
      document.querySelectorAll('.course-select').forEach(select=>{
        if([...select.options].some(option=>option.value===id))select.value=id;
      });
      const library=document.querySelector('#course-library [data-library-course]');
      if(library&&library.value!==id){library.value=id;if(window.studyLocal?.view==='learning')library.dispatchEvent(new Event('change',{bubbles:true}));}
      updateTodayCourse();
    };
    document.addEventListener('change',event=>{
      if(!event.target.matches('.course-select')||event.target.id==='active-course')return;
      const active=by('active-course');if(active&&[...active.options].some(option=>option.value===event.target.value))active.value=event.target.value;
    });
    document.addEventListener('study-courses-updated',renderCourseContext);
    renderCourseContext();
  }

  function renderCourseContext(){
    const select=by('active-course');if(!select)return;
    const courses=window.studyLocal?.courses||[];
    const previous=select.value||localStorage.getItem('study-active-course')||'';
    select.innerHTML='<option value="">All courses</option>'+courses.map(course=>`<option value="${esc(course.id)}">${esc(course.name)}</option>`).join('');
    select.value=courses.some(course=>course.id===previous)?previous:(courses.length===1?courses[0].id:'');
    localStorage.setItem('study-active-course',select.value);
    updateTodayCourse();
  }

  function updateTodayCourse(){
    const name=by('today-course-name');if(!name)return;
    const id=by('active-course')?.value||'';
    const course=(window.studyLocal?.courses||[]).find(item=>item.id===id);
    name.textContent=course?course.name:'All courses';
  }

  function buildLibraryTabs(){
    const view=by('view-learning');if(!view)return;
    const saved=by('saved-sessions')?.closest('section');
    const search=by('unified-search');
    const guide=by('course-library');
    const sheets=by('revision-sheets')?.closest('section');
    const exam=by('exam-form')?.closest('details')||by('exam-form')?.closest('section');
    const transfer=by('cards-import')?.closest('details');
    const targets=[['Continue',saved],['Find',search],['Guide',guide],['Sheets',sheets],['Exam',exam],['Transfer',transfer]].filter(([,target])=>target);
    if(!targets.length)return;
    const tabs=document.createElement('nav');tabs.className='library-tabs';tabs.setAttribute('aria-label','Library sections');
    tabs.innerHTML=targets.map(([label],index)=>`<button type="button" data-library-tab="${index}" ${index===0?'class="is-active"':''}>${label}</button>`).join('');
    view.querySelector('h1')?.after(tabs);
    tabs.querySelectorAll('[data-library-tab]').forEach((button,index)=>{
      button.onclick=()=>{
        tabs.querySelectorAll('button').forEach(item=>item.classList.toggle('is-active',item===button));
        const target=targets[index][1];
        if(target.tagName==='DETAILS')target.open=true;
        target.scrollIntoView({block:'start',behavior:'smooth'});
      };
    });
  }

  function buildToday(){
    const today=by('view-today');if(!today)return;
    const queue=by('today-queue');const slot=by('today-primary-slot');
    if(queue&&slot)slot.append(queue);
    today.querySelectorAll('[data-today-go]').forEach(button=>button.onclick=()=>window.studyView(button.dataset.todayGo));
    loadToday();
  }

  async function loadToday(){
    const summary=by('today-stats');if(!summary)return;
    try{
      const [data,dashboard]=await Promise.all([window.studyApi('/study/today'),window.studyApi('/learning/dashboard').catch(()=>null)]);
      const course=(window.studyLocal?.courses||[]).find(item=>item.id===(window.studyLocal?.view==='today'?by('active-course')?.value:''))||null;
      const due=Number(data.items?.filter(item=>item.kind==='review').length||0);
      const sessions=Number(dashboard?.sessions?.length||0);
      const days=data.days_to_exam;
      summary.innerHTML=`<div class="today-summary-line"><div><strong>${data.items?.length||0}</strong><span>next steps</span><small>${data.planned_minutes||0} min suggested</small></div><div><strong>${days===null||days===undefined?'No date':Math.max(0,days)}</strong><span>${days===null||days===undefined?'exam date not set':'days to exam'}</span></div><div><strong>${sessions}</strong><span>recent sessions</span></div></div><p class="today-note">${course?`Active course: ${esc(course.name)}. `:''}${due?`${due} review activity is waiting. `:''}Suggestions use existing work and make no AI calls.</p>`;
      const recent=by('today-recent');
      if(recent){
        const rows=(dashboard?.sessions||[]).slice(0,3);
        recent.innerHTML=rows.map((item,index)=>{
          const kind={tutor:'Session',explain:'Explanation',path:'Mastery path',exam:'Bank exam'}[item.kind]||'Study work';
          const status={awaiting_answer:'In progress',correct:'Completed',revealed:'Reviewed'}[item.status]||item.status||'Saved';
          return `<article class="study-queue-row"><div><strong>${esc(item.question||item.topic||kind)}</strong><p class="hint">${esc(kind)} · ${esc(status)}</p></div><button type="button" class="quiet-button" data-today-resume="${index}">Resume</button></article>`;
        }).join('')||'<p class="today-empty">Your latest study sessions will appear here after you start one.</p>';
        recent.querySelectorAll('[data-today-resume]').forEach(button=>button.onclick=()=>{
          const item=rows[Number(button.dataset.todayResume)];
          if(item)window.studyResume(item.kind,item.id);
        });
      }
      updateTodayCourse();
    }catch(error){
      summary.innerHTML='<p class="today-empty">Today’s summary is unavailable. You can still open Study, Library or Workspace.</p>';
    }
  }

  function setLabels(name){
    const label=by('page-label');
    if(label)label.textContent=labels[name]||name;
    document.querySelectorAll('.side-link').forEach(button=>{
      const active=button.dataset.view===name||(button.dataset.view==='practice'&&['practice','explain','ask'].includes(name));
      button.classList.toggle('is-active',active);
    });
    document.querySelectorAll('.study-mode-tabs [data-study-mode]').forEach(button=>button.classList.toggle('is-active',button.dataset.studyMode===name));
  }

  document.addEventListener('study-ready',()=>{
    wrapFeedback();
    setupCourseContext();
    buildStudyTabs();
    buildLibraryTabs();
    buildToday();
    setLabels(window.studyLocal?.view||'today');
  });

  document.addEventListener('study-view',event=>{
    setLabels(event.detail);
    if(event.detail==='today')loadToday();
    if(event.detail==='learning')renderCourseContext();
  });
})();


