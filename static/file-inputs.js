'use strict';
(()=>{
  function enhance(input){
    if(input.dataset.fileUi==='true'||input.classList.contains('attachment-picker'))return;
    input.dataset.fileUi='true';input.classList.add('file-native');
    const wrap=document.createElement('span');wrap.className='file-picker';
    const button=document.createElement('button');button.type='button';button.className='quiet-button';button.textContent=input.multiple?'Choose files':'Choose file';
    const status=document.createElement('span');status.className='file-picker-name';status.setAttribute('aria-live','polite');
    wrap.append(button,status);input.after(wrap);
    const update=()=>{
      const files=[...(input.files||[])];
      status.textContent=files.length?(files.length===1?files[0].name:`${files.length} files selected`):(input.multiple?'No files selected':'No file selected');
      status.title=files.map(file=>file.name).join(', ');
    };
    button.onclick=event=>{event.preventDefault();event.stopPropagation();if(!input.disabled)input.click();};
    input.addEventListener('change',update);
    input.form?.addEventListener('reset',()=>setTimeout(update,0));
    update();
  }
  const scan=root=>root.querySelectorAll('input[type=file]').forEach(enhance);
  document.addEventListener('study-ready',()=>{
    scan(document);
    new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(node=>{
      if(node.nodeType!==1)return;
      if(node.matches?.('input[type=file]'))enhance(node);
      scan(node);
    }))).observe(document.body,{childList:true,subtree:true});
  });
})();
