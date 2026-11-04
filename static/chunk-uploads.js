/* Bounded retryable transport. Validation and indexing remain server-authoritative. */
(()=>{
  let pending=null;
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  window.cancelCourseUpload=async()=>{
    if(!pending?.id)return;
    const response=await fetch(`/workspace/uploads/${pending.id}`,{method:'DELETE'});
    if(!response.ok&&response.status!==404){const body=await response.json().catch(()=>({}));throw Error(body.detail||'Wait for document saving to finish before changing this selection.');}
    pending=null;
  };
  const transient=error=>!error.status||[408,409,425,429].includes(error.status)||error.status>=500;
  async function json(url,options={}){
    const response=await fetch(url,{...options,signal:AbortSignal.timeout(20000)});
    const body=await response.json().catch(()=>null);
    if(!response.ok){const error=new Error(typeof body?.detail==='string'?body.detail:`Upload request failed (${response.status}).`);error.status=response.status;throw error;}
    return body;
  }
  async function retry(fn,notify){
    for(let attempt=0;;attempt++){
      try{return await fn(attempt);}catch(error){
        if(!transient(error)||attempt>=3)throw error;
        notify?.(`Connection interrupted. Retrying (${attempt+1}/3)…`);
        await pause(Math.min(4000,750*2**attempt));
      }
    }
  }
  function put(url,blob,digest,onProgress){
    return new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest();xhr.open('PUT',url);xhr.timeout=90000;
      xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.setRequestHeader('X-Chunk-SHA256',digest);
      xhr.upload.onprogress=event=>onProgress(event.loaded);
      xhr.onload=()=>{let body;try{body=JSON.parse(xhr.responseText);}catch(_){}
        if(xhr.status>=200&&xhr.status<300)resolve(body);
        else{const error=new Error(typeof body?.detail==='string'?body.detail:`Chunk transfer failed (${xhr.status}).`);error.status=xhr.status;reject(error);}};
      xhr.onerror=xhr.ontimeout=()=>reject(new Error('The connection was interrupted. Confirmed chunks are preserved.'));
      xhr.send(blob);
    });
  }
  window.uploadCourseBatch=async({courseId,docType,files,onProgress})=>{
    const total=files.reduce((sum,file)=>sum+file.size,0);
    const report=(text,bytes=0,phase='transfer')=>onProgress({text,percent:total?Math.min(100,Math.floor(bytes/total*100)):0,phase});
    const same=pending&&pending.courseId===courseId&&pending.docType===docType&&files.length===pending.files.length&&files.every((file,index)=>file===pending.files[index]);
    if(!same){
      if(pending?.id)fetch(`/workspace/uploads/${pending.id}`,{method:'DELETE'}).catch(()=>{});
      pending=null;
    }
    let batch;
    if(pending?.id){try{batch=await retry(()=>json(`/workspace/uploads/${pending.id}`));}catch(error){if(error.status!==404)throw error;pending=null;}}
    if(!pending?.id){
      pending ||= {courseId,docType,files:[...files],requestKey:crypto.randomUUID().replaceAll('-','')};
      report('Preparing secure upload…');
      batch=await retry(()=>json('/workspace/uploads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({course_id:courseId,doc_type:docType,files:files.map(file=>({name:file.name,size:file.size})),request_key:pending.requestKey})}));
      pending.id=batch.id;
    }
    const base=`/workspace/uploads/${batch.id}`;
    if(batch.status==='receiving'){
      for(let index=0;index<files.length;index++){
        while(batch.offsets[index]<files[index].size){
          const offset=batch.offsets[index],blob=files[index].slice(offset,offset+batch.chunk_bytes);
          const hash=await crypto.subtle.digest('SHA-256',await blob.arrayBuffer());
          const digest=Array.from(new Uint8Array(hash),byte=>byte.toString(16).padStart(2,'0')).join('');
          const confirmed=batch.offsets.reduce((sum,value)=>sum+value,0);
          batch=await retry(async attempt=>{
            if(attempt){
              const remote=await json(base);
              if(remote.offsets[index]>=offset+blob.size)return remote;
            }
            return put(`${base}/files/${index}?offset=${offset}`,blob,digest,bytes=>report(`Uploading ${index+1}/${files.length}: ${files[index].name}`,confirmed+bytes));
          },message=>report(message,confirmed));
          report(`${batch.offsets[index]===files[index].size?"Transferred":"Uploading"} ${index+1}/${files.length}: ${files[index].name}`,batch.offsets.reduce((sum,value)=>sum+value,0));
        }
      }
      batch=await retry(()=>json(base+'/complete',{method:'POST'}),message=>report(message,total));
    }
    report('Transfer complete. Verifying and saving files in the background…',total,'verify');
    // Each poll is short. Large PDF validation never holds a Cloudflare request open.
    const deadline=Date.now()+30*60*1000;
    let recoveries=0;
    while(['processing','receiving'].includes(batch.status)&&Date.now()<deadline){
      if(batch.status==='receiving'){
        if(++recoveries>3||batch.offsets.some((offset,index)=>offset!==files[index].size))break;
        report('Reconnecting to saved upload after a server restart…',total,'verify');
        batch=await retry(()=>json(base+'/complete',{method:'POST'}));
      }
      await pause(1500);batch=await retry(()=>json(base),message=>report(message,total,'verify'));
    }
    if(batch.status==='failed'){
      pending=null;const error=new Error(batch.error||'File validation failed.');error.status=batch.error_status;throw error;
    }
    if(batch.status!=='complete')throw new Error('Verification is still pending. Keep these files selected and click Upload and index to reconnect.');
    if(!batch.result||batch.result.uploaded?.length!==files.length||files.some(file=>
      !batch.result.uploaded.some(saved=>saved.size===file.size&&saved.course_id===courseId))){
      throw new Error('The server has not confirmed every saved document. Refresh Workspace before retrying.');
    }
    pending=null;report('Files verified and saved.',total,'complete');return batch.result;
  };
})();
