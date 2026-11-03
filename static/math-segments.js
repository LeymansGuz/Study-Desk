/* One delimiter scanner shared by browser rendering and server-side KaTeX. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.studyMathSegments=api;})(typeof globalThis!=='undefined'?globalThis:this,()=>{
  function scan(input){
    const text=String(input||''),segments=[],issues=[];let i=0,start=0;
    const money=index=>/^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?=$|[\s.,;:!?)}\]])/.test(text.slice(index+1));
    function close(from,delimiter,inline){
      for(let p=from;p<text.length;p++){
        if(inline&&(text[p]==='\n'||text[p]==='\r'))return -1;
        if(inline&&text[p]==='`')return -1;
        if(text.startsWith(delimiter,p)&&(delimiter!=='$'||(text[p-1]!=='$'&&text[p+1]!=='$')))return p;
        if(text[p]==='\\')p++;
      }return -1;
    }
    while(i<text.length){
      if(text[i]==='`'||text.startsWith('~~~',i)){
        const char=text[i];let count=1;while(text[i+count]===char)count++;
        const marker=char.repeat(count),end=text.indexOf(marker,i+count);
        if(end>=0){i=end+count;continue;}if(count>=3){i=text.length;continue;}
      }
      let opening='',ending='',display=false;
      if(text.startsWith('\\(',i)){opening='\\(';ending='\\)';}
      else if(text.startsWith('\\[',i)){opening='\\[';ending='\\]';display=true;}
      else if(text.startsWith('$$',i)){opening='$$';ending='$$';display=true;}
      else if(text[i]==='$'&&i+1<text.length&&!/\s/.test(text[i+1])){opening='$';ending='$';}
      else if(text[i]==='\\'){i+=2;continue;}
      if(!opening){i++;continue;}
      const end=close(i+opening.length,ending,opening==='$');
      // A monetary amount followed by another monetary amount is prose, not math.
      if(opening==='$'&&money(i)&&(end<0||/\d/.test(text[end+1]||'')||/\s/.test(text[end-1]||''))){i++;continue;}
      if(end<0){issues.push('Unclosed mathematical delimiter.');i+=opening.length;continue;}
      if(start<i)segments.push({type:'text',value:text.slice(start,i)});
      segments.push({type:'math',value:text.slice(i+opening.length,end),display,raw:text.slice(i,end+ending.length)});
      i=end+ending.length;start=i;
    }
    if(start<text.length)segments.push({type:'text',value:text.slice(start)});
    return {segments,issues};
  }
  return {scan};
});
