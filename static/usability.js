/* Shared navigation and source actions; no additional model requests. */
'use strict';
(()=>{
  const by=id=>document.getElementById(id);
  let bookmark=null;
  window.studyBookmark=(document,page)=>{
    bookmark=document?{document,page}:null;
    const form=by('source-bookmark');if(!form)return;form.hidden=!document;if(!document)return;
    form.elements.page.value=page;form.elements.label.value='';form.elements.text.value='';
    by('source-bookmark-status').textContent='';
    by('source-bookmark-hint').textContent=`${document.filename} · page ${page}. If you navigate within the PDF, enter the new page number here.`;
  };
  document.addEventListener('study-ready',()=>{
    const sourceForm=document.createElement('form');sourceForm.id='source-bookmark';sourceForm.innerHTML='<details class="library-panel"><summary>Bookmark this page</summary><p id="source-bookmark-hint" class="hint"></p><div class="local-grid"><label>Page<input name="page" type="number" min="1" required></label><label>Label (optional)<input name="label" maxlength="120"></label></div><label>Personal note (optional)<textarea name="text" rows="2" maxlength="4000"></textarea></label><button class="quiet-button" type="submit">Save bookmark</button><p id="source-bookmark-status" role="status"></p></details>';
    by('source-download').after(sourceForm);
    sourceForm.onsubmit=e=>{e.preventDefault();if(!bookmark)return;task('source-bookmark',sourceForm,'#source-bookmark-status',()=>post('/library/annotations',{document_id:bookmark.document.id,page:Number(sourceForm.elements.page.value),label:sourceForm.elements.label.value,text:sourceForm.elements.text.value}));};
    // One search entry point, with independently labelled results and errors.
    const search=by('study-search'),panel=document.createElement('section');panel.className='card local-card';panel.id='unified-search';panel.innerHTML='<h2>Find your study work</h2>';
    const courseLabel=by('course-library').querySelector('[data-library-course]').parentElement;courseLabel.querySelector('select').id='library-course';panel.append(courseLabel,search,by('study-search-results'));
    const documentPanel=by('document-search').closest('details');
    by('document-search').hidden=true;
    const heading=document.createElement('h3');heading.textContent='Course documents';
    panel.append(heading,by('document-search-status'),by('document-search-results'),documentPanel.querySelector('.library-jobs'));
    documentPanel.hidden=true;
    by('course-library').before(panel);
    // Resume is the first action in Learning tools; history remains bounded at ten.
    by('revision-sheets').closest('section').querySelector('h2').textContent='Personal revision sheets';
    const saved=by('saved-sessions').closest('section');saved.querySelector('h2').textContent='Continue studying';
    const learning=by('view-learning'),title=learning.querySelector('h1');learning.prepend(title);title.after(saved);saved.after(panel);panel.after(by('course-library'));
    const bankSection=by('bank-course').closest('section'),exam=by('exam-form').closest('section');
    const details=document.createElement('details');details.className='library-panel';details.innerHTML='<summary>Practise from the verified question bank</summary>';
    bankSection.before(details);details.append(bankSection,exam);
    // The bank and exam share one visible course choice and availability refresh.
    by('exam-course').parentElement.hidden=true;
    by('exam-course').disabled=true;by('bank-course').parentElement.hidden=true;
    const syncBank=()=>{const course=by('library-course').value;by('bank-course').value=course;by('exam-course').value=course;bank().catch(fail);};
    document.addEventListener('study-library-course',syncBank);document.addEventListener('study-view',e=>{if(e.detail==='learning')syncBank();});syncBank();
    const utilities=by('cards-import').closest('details');utilities.querySelector('summary').textContent='Import, export and manage personal study work';
    const anki=document.querySelector('a[href="/study/cards/export"]');utilities.append(anki.parentElement);
    const guidePanel=by('guide-load').closest('details');by('guide-load').hidden=true;
    guidePanel.addEventListener('toggle',()=>{if(guidePanel.open&&!by('guide-load').disabled)by('guide-load').click();});
    const bookmarkTools=by('annotation-form'),manual=document.createElement('details');manual.className='library-panel';manual.innerHTML='<summary>Add a bookmark manually</summary><p class="hint">You can also bookmark directly from an original document or source preview.</p>';bookmarkTools.before(manual);manual.append(bookmarkTools);
    by('adaptive-load').hidden=true;
    const recommendations=by('adaptive-items').closest('details');recommendations.open=true;
    const plan=by('schedule-form'),time=plan.elements.minutes.parentElement;
    const advanced=document.createElement('details');advanced.className='library-panel';advanced.innerHTML='<summary>Adjust time for this course (optional)</summary><p class="hint">Uses your daily study time from Today’s study queue unless you set an override.</p>';advanced.append(time);plan.querySelector('.local-grid').after(advanced);
    // Do not recreate the sidebar during workspace polling. Keep a reserved scrollbar
    // and preserve each view's scroll position when navigating between activities.
  });
})();
