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
    const utilities=by('cards-import')?.closest('details');
    const examGroup=by('exam-form')?.closest('details')||by('exam-form')?.closest('section');
    if(utilities&&examGroup&&utilities!==examGroup)examGroup.after(utilities);
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
    const setActive=index=>tabs.querySelectorAll('button').forEach((item,itemIndex)=>item.classList.toggle('is-active',itemIndex===index));
    tabs.querySelectorAll('[data-library-tab]').forEach((button,index)=>{
      button.onclick=()=>{
        setActive(index);
        const target=targets[index][1];
        if(target.tagName==='DETAILS')target.open=true;
        target.scrollIntoView({block:'start',behavior:'smooth'});
      };
    });
    const main=document.querySelector('.app-main');
    if(main){
      let scheduled=false;
      const update=()=>{
        scheduled=false;
        if(!by('view-learning')||by('view-learning').hidden)return;
        let current=0;const threshold=Math.min(360,window.innerHeight*0.5);
        targets.forEach(([,target],index)=>{if(target.getBoundingClientRect().top<=threshold)current=index;});
        setActive(current);
      };
      let settle;
      main.addEventListener('scroll',()=>{if(!scheduled){scheduled=true;requestAnimationFrame(update);}clearTimeout(settle);settle=setTimeout(update,120);},{passive:true});
      if('IntersectionObserver' in window){
        const observer=new IntersectionObserver(()=>{clearTimeout(settle);settle=setTimeout(update,120);},{root:main,rootMargin:'-100px 0px -55% 0px',threshold:0});
        targets.forEach(([,target])=>observer.observe(target));
      }
      update();
    }
  }

  function buildProgressShortcut(){
    const view=by('view-progress');if(!view||by('progress-today'))return;
    const row=document.createElement('div');row.id='progress-today';row.className='progress-today';
    row.innerHTML='<p>Your next action lives on Today.</p><button type="button" class="quiet-button" data-empty-go="today">Open Today</button>';
    view.querySelector('h1')?.after(row);
  }

  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-empty-go]');
    if(button)window.studyView(button.dataset.emptyGo);
  });

  function buildToday(){
    const today=by('view-today');if(!today)return;
    const queue=by('today-queue');const slot=by('today-primary-slot');
    if(queue&&slot)slot.append(queue);
    today.querySelectorAll('[data-today-go]').forEach(button=>button.onclick=()=>window.studyView(button.dataset.todayGo));
    renderSetup();
    loadToday();
  }

  function renderSetup(){
    const today=by('view-today');if(!today)return;
    let host=by('today-setup');
    if(!host){
      host=document.createElement('section');host.id='today-setup';host.className='card local-card';
      today.querySelector('.today-grid')?.before(host);
    }
    if((window.studyLocal?.courses||[]).length){host.hidden=true;host.innerHTML='';return;}
    host.hidden=false;
    host.innerHTML='<p class="today-kicker">First run</p><h2>Set up your study desk</h2><p class="hint">Three short steps. Nothing is sent to an AI provider until you request a study action.</p><div class="setup-steps"><div><strong>1. Add a course</strong><span>Create the course you are studying.</span><button type="button" class="quiet-button" data-empty-go="workspace">Add course</button></div><div><strong>2. Add material</strong><span>Upload notes, slides or past papers. Indexing is local.</span><button type="button" class="quiet-button" data-empty-go="workspace">Upload material</button></div><div><strong>3. Connect a provider</strong><span>Add your own API key in Settings when you are ready.</span><button type="button" class="quiet-button" data-empty-go="settings">Open Settings</button></div></div><button type="button" class="primary-button" data-empty-go="practice">Start studying</button>';
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

  let lastStudyMode=null;
  function syncStudyContext(target){
    const source=lastStudyMode;if(!source||source===target)return;
    if(source==='practice'&&target==='explain'){
      const topic=by('topic')?.value.trim();
      if(topic&&!by('explain-topic')?.value.trim())by('explain-topic').value=topic;
    }
    if(source==='explain'&&target==='practice'){
      const topic=by('explain-topic')?.value.trim();
      if(topic&&!by('topic')?.value.trim()){
        by('topic').value=topic;by('scope').value='topic';by('topic-field').hidden=false;by('topic').required=true;
      }
    }
  }

  document.addEventListener('study-courses-updated',()=>renderSetup());

  document.addEventListener('study-ready',()=>{
    wrapFeedback();
    setupCourseContext();
    buildStudyTabs();
    buildLibraryTabs();
    buildProgressShortcut();
    buildToday();
    lastStudyMode=['practice','explain','ask'].includes(window.studyLocal?.view)?window.studyLocal.view:null;
    setLabels(window.studyLocal?.view||'today');
  });

  document.addEventListener('study-view',event=>{
    setLabels(event.detail);
    if(['practice','explain','ask'].includes(event.detail)){syncStudyContext(event.detail);lastStudyMode=event.detail;}
    if(event.detail==='today')loadToday();
    if(event.detail==='learning')renderCourseContext();
  });
})();


