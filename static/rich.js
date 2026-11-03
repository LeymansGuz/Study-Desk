/* Safe Markdown and mathematical notation rendering. */
window.studyRich=value=>{
  const math=[],prefix='STUDYMATH'+(crypto.randomUUID?.()||String(Math.random()).slice(2)).replaceAll('-','');
  // Model answers sometimes indent prose by four spaces. Marked turns that into
  // a code block, leaving **markdown** literal. Preserve fenced code, but treat
  // indented prose as prose so the whole answer uses one formatting system.
  let fenced=false;
  const normalized=String(value||'').slice(0,60000).replace(/\r\n?/g,'\n').split('\n').map(line=>{
    if(/^\s*(?:```|~~~)/.test(line)){fenced=!fenced;return line;}
    if(!fenced&&/^ {4,}\S/.test(line))return line.slice(4);
    return line;
  }).join('\n');
  const text=window.studyMathSegments.scan(normalized).segments.map(part=>{
    if(part.type!=='math')return part.value;
    const token=prefix+math.length+'END';let rendered;
    try{rendered=katex.renderToString(part.value,{displayMode:part.display,throwOnError:false,trust:false,maxExpand:300,maxSize:20,output:'htmlAndMathml'});}catch(_){rendered=part.raw.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');}
    math.push([token,rendered]);return token;
  }).join('');
  let html=DOMPurify.sanitize(marked.parse(text,{breaks:true,gfm:true}),{ALLOWED_TAGS:['p','br','strong','em','del','code','pre','ul','ol','li','table','thead','tbody','tr','th','td','blockquote','h2','h3','h4'],ALLOWED_ATTR:[]});
  for(const [token,rendered] of math)html=html.replaceAll(token,rendered);
  return html;
};
