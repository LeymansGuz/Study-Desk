'use strict';
window.studyAttachments={};
class AttachmentQueue {
  constructor(input,kind,limits){
    this.input=input;this.kind=kind;this.limits=limits;this.files=[];this.roles=new Map();this.urls=new Map();this.page=0;this.busy=false;this.extracted=null;
    input.multiple=true;input.required=false;input.classList.add('attachment-picker');
    this.zone=document.createElement('section');this.zone.className='attachment-zone';this.zone.tabIndex=0;this.zone.setAttribute('aria-label',`${kind==='ask'?'Question':'Workspace'} attachments: drop files or paste a screenshot`);
    input.parentElement.insertAdjacentElement('afterend',this.zone);
    this.zone.innerHTML='<p class="hint">Drop files here or focus this area and paste a screenshot.</p><div class="local-actions"><button type="button" class="quiet-button" data-choose>Choose files</button><button type="button" class="quiet-button" data-paste>Paste screenshot</button><button type="button" class="quiet-button" data-clear>Clear selected files</button></div><p data-summary class="hint"></p><div data-files></div><div data-pages class="local-actions"></div><p data-message role="status" aria-live="polite"></p>';
    input.onchange=()=>{this.add([...input.files]);input.value='';};
    this.zone.ondragover=e=>{e.preventDefault();this.zone.classList.add('drag-over');};
    this.zone.ondragleave=()=>this.zone.classList.remove('drag-over');
    this.zone.ondrop=e=>{e.preventDefault();this.zone.classList.remove('drag-over');this.add([...e.dataTransfer.files]);};
    this.zone.onpaste=e=>{const files=[...e.clipboardData.files];if(files.length){e.preventDefault();this.add(this.namedImages(files));}};
    input.form.addEventListener('paste',e=>{if(!this.zone.contains(e.target)&&e.clipboardData.files.length){e.preventDefault();this.add(this.namedImages([...e.clipboardData.files]));}});
    this.zone.querySelector('[data-paste]').onclick=()=>this.paste();
    this.zone.querySelector('[data-choose]').onclick=()=>{if(!this.busy)this.input.click();};
    this.zone.querySelector('[data-clear]').onclick=()=>this.change(()=>this.files=[]);
    if(kind==='ask'){
      this.review=document.querySelector('#attachment-review');this.text=document.querySelector('#attachment-text');
      document.querySelector('#read-attachments').onclick=async()=>{try{await this.read();}catch(error){this.message(error.message,true);}};
    }
    this.render();
  }
  namedImages(files){return files.map((file,index)=>!file.name||file.name==='image.png'?new File([file],`Screenshot-${new Date().toISOString().replace(/[:.]/g,'-')}-${index+1}.${file.type==='image/jpeg'?'jpg':file.type==='image/webp'?'webp':'png'}`,{type:file.type||'image/png'}):file);}
  message(text,error=false){const host=this.zone.querySelector('[data-message]');host.textContent=text;host.classList.toggle('error-text',error);}
  invalidate(){this.extracted=null;if(this.review){this.review.hidden=true;this.text.value='';}for(const url of this.urls.values())URL.revokeObjectURL(url);this.urls.clear();}
  async change(action){
    if(this.busy)return;const submit=this.input.form.querySelector('button[type=submit]'),wasDisabled=submit?.disabled;if(submit)submit.disabled=true;this.lock(true);
    try{if(this.kind==='workspace')await window.cancelCourseUpload();action();this.invalidate();this.message('Selection updated.');}
    catch(error){this.message(error.message,true);}finally{this.lock(false);if(submit)submit.disabled=wasDisabled;}
  }
  add(incoming){
    if(this.busy)return;
    const allowed=this.input.accept.split(',');let next=[...this.files],duplicates=0;
    try{
      for(const file of incoming){
        const extension='.'+file.name.split('.').pop().toLowerCase();
        if(!allowed.includes(extension))throw Error(`${file.name}: unsupported file type.`);
        const image=/^\.(png|jpe?g|webp)$/.test(extension),cap=this.kind==='ask'?this.limits.question_file_bytes:image?this.limits.image_bytes:this.limits.document_bytes;
        if(!file.size||file.size>cap)throw Error(`${file.name}: use a non-empty file within ${fileSize(cap)}.`);
        if(next.some(old=>old.name===file.name&&old.size===file.size&&old.lastModified===file.lastModified)){duplicates++;continue;}
        if(next.some(old=>old.name===file.name))throw Error(`${file.name}: another selected file has this name. Rename one first.`);
        next.push(file);
      }
      const count=this.kind==='ask'?this.limits.question_files:this.limits.workspace_files,cap=this.kind==='ask'?this.limits.question_bytes:this.limits.workspace_bytes;
      if(next.length>count||next.reduce((n,f)=>n+f.size,0)>cap)throw Error(`Select at most ${count} files and ${fileSize(cap)} total.`);
      this.files=next;this.invalidate();this.page=Math.floor(Math.max(0,next.length-1)/10);this.render();
      this.message(duplicates?`${duplicates} duplicate selection(s) skipped.`:this.kind==='ask'?'Files selected. Reading starts only when you choose Read attachments or submit.':'Files selected. Choose Upload and index when ready.');
    }catch(error){this.message(error.message,true);}
  }
  async paste(){
    if(this.busy)return;
    try{
      if(!navigator.clipboard?.read)throw Error('Use the keyboard shortcut');
      const items=await navigator.clipboard.read(),files=[];
      for(const item of items){const type=item.types.find(t=>['image/png','image/jpeg','image/webp'].includes(t));if(type){const blob=await item.getType(type);files.push(new File([blob],`Screenshot-${Date.now()}-${files.length+1}.${type==='image/jpeg'?'jpg':type.split('/')[1]}`,{type}));}}
      if(!files.length)throw Error('No screenshot found');this.add(files);
    }catch(_){this.zone.focus();this.message(`Copy a screenshot, then press ${/Mac/.test(navigator.platform)?'⌘V':'Ctrl+V'} in this attachment area. Clipboard permissions differ between systems.`);}
  }
  render(){
    for(const file of this.roles.keys())if(!this.files.includes(file))this.roles.delete(file);
    const host=this.zone.querySelector('[data-files]');host.innerHTML='';
    this.page=Math.min(this.page,Math.max(0,Math.ceil(this.files.length/10)-1));
    this.files.slice(this.page*10,this.page*10+10).forEach((file,offset)=>{
      const index=this.page*10+offset,row=document.createElement('article');row.className='attachment-row';
      if(file.type.startsWith('image/')){const img=document.createElement('img');if(!this.urls.has(file))this.urls.set(file,URL.createObjectURL(file));img.src=this.urls.get(file);img.alt='Screenshot preview';img.loading='lazy';row.append(img);}
      const info=document.createElement('div'),name=document.createElement('strong'),meta=document.createElement('p');name.textContent=file.name;name.title=file.name;meta.className='hint';meta.dataset.fileIndex=index;meta.textContent=`${file.name.split('.').pop().toUpperCase()} · ${fileSize(file.size)} · ${this.extracted?.[index]?'Read':'Selected'}`;info.append(name,meta);row.append(info);
      if(this.kind==='workspace'){
        const label=document.createElement('label');label.textContent='Document type';
        const select=document.createElement('select');select.innerHTML=document.querySelector('#doc-type').innerHTML;
        select.value=this.roles.get(file)||document.querySelector('#doc-type').value;select.disabled=this.busy;
        select.setAttribute('aria-label',file.name+' document type');select.onchange=()=>this.change(()=>this.roles.set(file,select.value));
        label.append(select);info.append(label);
      }
      const remove=document.createElement('button');remove.type='button';remove.className='quiet-button';remove.textContent='Remove';remove.disabled=this.busy;remove.setAttribute('aria-label','Remove '+file.name);remove.onclick=()=>this.change(()=>this.files.splice(index,1));row.append(remove);host.append(row);
    });
    this.zone.querySelector('[data-summary]').textContent=`${this.files.length} file${this.files.length===1?'':'s'} selected · ${fileSize(this.files.reduce((n,f)=>n+f.size,0))} total`;
    const pages=this.zone.querySelector('[data-pages]');pages.innerHTML='';
    if(this.files.length>10)for(const [label,delta] of [['Previous',-1],['Next',1]]){const b=document.createElement('button');b.type='button';b.className='quiet-button';b.textContent=label;b.disabled=this.page+delta<0||(this.page+delta)*10>=this.files.length;b.onclick=()=>{this.page+=delta;this.render();};pages.append(b);}
    this.zone.querySelector('[data-clear]').disabled=this.busy||!this.files.length;
    this.zone.querySelector('[data-paste]').disabled=this.busy;
    this.zone.querySelector('[data-choose]').disabled=this.busy;
  }
  lock(value){this.busy=value;this.input.disabled=value;this.input.form.querySelectorAll('select').forEach(select=>select.disabled=value);this.render();}
  async read(){
    if(this.busy)throw Error('Wait for attachment reading to finish.');
    if(!this.files.length)throw Error('Select at least one question attachment.');
    if(this.extracted){this.review.hidden=false;this.review.open=true;return this.extracted;}
    this.lock(true);const body=new FormData();this.files.forEach(f=>body.append('files',f));
    this.message('Reading locally. Text-based pages bypass OCR; screenshots use local OCR.');
    try{
      const response=await fetch('/api/extract/batch',{method:'POST',body});
      if(!response.ok){const error=await response.json();throw Error(typeof error.detail==='string'?error.detail:'Could not read these attachments.');}
      const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',result=null;
      while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let split;
        while((split=buffer.indexOf('\n\n'))>=0){const line=buffer.slice(0,split);buffer=buffer.slice(split+2);if(!line.startsWith('data: '))continue;const event=JSON.parse(line.slice(6));
          if(event.stage==='error')throw Error(event.message);
          if(event.stage==='reading')this.message(`Reading ${event.index+1}/${this.files.length}: ${event.filename} locally…`);
          if(event.stage==='ready'){const meta=this.zone.querySelector(`[data-file-index="${event.index}"]`);if(meta)meta.textContent=`${fileSize(this.files[event.index].size)} · ${event.cached?'Reused extraction':'Read'} · ${event.chars} characters`;}
          if(event.stage==='complete')result=event.files;
        }
      }
      if(!result)throw Error('Attachment reading was interrupted. Retry to reuse completed extractions.');
      this.extracted=result;this.text.value=result.map(r=>`### ${r.filename}\n${r.text}`).join('\n\n');this.review.hidden=false;
      const warnings=[...new Set(result.flatMap(r=>r.warnings||[]))];this.needsReview=warnings.length>0;
document.querySelector('#attachment-warnings').textContent=warnings.join(' ');
      this.review.open=this.needsReview;this.message('Attachments read. Review or edit the extracted question text below. No AI request has been sent.');return result;
    }finally{this.lock(false);}
  }
  async question(){
    if(!this.files.length)return {attachment_text:'',attachment_name:''};
    await this.read();
        return {attachment_text:this.text.value,attachment_name:`${this.files.length} attachment${this.files.length===1?'':'s'}`};
  }
}
document.addEventListener('study-ready',async()=>{
  try{
    const limits=await api('/local/upload-limits');
    studyAttachments.ask=new AttachmentQueue(document.querySelector('#question-file'),'ask',limits);
    studyAttachments.workspace=new AttachmentQueue(document.querySelector('#documents'),'workspace',limits);
    const bulk=document.createElement('button');bulk.type='button';bulk.className='quiet-button';bulk.textContent='Apply this type to selected files';
    bulk.onclick=()=>{const q=studyAttachments.workspace;q.change(()=>q.files.forEach(f=>q.roles.set(f,document.querySelector('#doc-type').value)));};
    document.querySelector('#doc-type').parentElement.after(bulk);
    document.querySelector('#workspace-upload-limits').textContent=`Up to ${limits.workspace_files} files / ${fileSize(limits.workspace_bytes)} per batch; documents up to ${fileSize(limits.document_bytes)}, screenshots up to ${fileSize(limits.image_bytes)}. Background indexing keeps the app usable.`;
    document.querySelector('#question-upload-limits').textContent=`Up to ${limits.question_files} attachments for one question, ${fileSize(limits.question_bytes)} total, ${fileSize(limits.question_file_bytes)} per file and ${limits.question_pages} relevant pages. Combined question text stays within ${limits.question_chars.toLocaleString()} characters.`;
    document.querySelector('#own-question').required=false;
  }catch(error){fail(error);}
});

window.reviewCourseFiles=async(courseId,files)=>{
  const existing=(await api('/workspace/files?'+new URLSearchParams({course_id:courseId}))).files;
  const conflicts=files.map((file,index)=>({file,index,old:existing.find(d=>d.filename===file.name)})).filter(x=>x.old);
  const metadata=files.map(file=>({doc_type:studyAttachments.workspace.roles.get(file)||document.querySelector('#doc-type').value}));
  if(!conflicts.length)return metadata;
  const dialog=document.createElement('dialog');dialog.className='local-card upload-review-dialog';dialog.setAttribute('aria-labelledby','upload-review-title');
  dialog.innerHTML='<h2 id="upload-review-title">Review existing filenames</h2><p>Replace keeps the old document usable until the new index is ready. Identical files are skipped automatically. Existing document types are preserved when replacing.</p><label>Apply to all conflicts<select data-all><option value="">Choose individually</option><option value="replace">Replace</option><option value="keep">Keep both</option><option value="skip">Skip</option></select></label><div data-conflicts></div><div class="local-actions"><button type="button" class="quiet-button" data-cancel>Cancel</button><button type="button" class="primary-button" data-confirm>Upload selected files</button></div>';
  conflicts.forEach(x=>{const label=document.createElement('label');label.textContent=x.file.name;const select=document.createElement('select');select.dataset.index=x.index;select.innerHTML='<option value="keep">Keep both</option><option value="replace">Replace</option><option value="skip">Skip</option>';label.append(select);dialog.querySelector('[data-conflicts]').append(label);});
  dialog.querySelector('[data-all]').onchange=e=>{if(e.target.value)dialog.querySelectorAll('[data-index]').forEach(s=>s.value=e.target.value);};
  document.body.append(dialog);dialog.showModal();
  return new Promise((resolve,reject)=>{
    let accepted=false;
    dialog.querySelector('[data-cancel]').onclick=()=>dialog.close();
    dialog.querySelector('[data-confirm]').onclick=()=>{accepted=true;conflicts.forEach(x=>Object.assign(metadata[x.index],{conflict:dialog.querySelector(`[data-index="${x.index}"]`).value,expected_sha:x.old.sha256}));dialog.close();};
    dialog.addEventListener('close',()=>{dialog.remove();accepted?resolve(metadata):reject(Error('Upload cancelled. Your selected files are kept.'));},{once:true});
  });
};
