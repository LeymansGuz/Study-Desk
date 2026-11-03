const katex = require('../static/vendor/katex/katex.min.js');
const scanner = require('../static/math-segments.js');
let input='';
process.stdin.setEncoding('utf8');
process.stdin.on('data',chunk=>{input+=chunk;if(input.length>100000)process.exit(2);});
process.stdin.on('end',()=>{
  try{
    let count=0,size=0;const seen=new Set();
    for(const text of JSON.parse(input)){
      const parsed=scanner.scan(text);if(parsed.issues.length)throw Error(parsed.issues[0]);
      for(const part of parsed.segments){if(part.type!=='math')continue;const key=JSON.stringify([part.value,part.display]);if(seen.has(key))continue;seen.add(key);count++;size+=part.value.length;if(count>256||size>24000)throw Error('Mathematical formatting exceeds the validation budget.');katex.renderToString(part.value,{displayMode:part.display,throwOnError:true,strict:'error',trust:false,maxExpand:300,maxSize:20});}
    }
  }
  catch(error){process.stderr.write(String(error.message).slice(0,350));process.exitCode=1;}
});
