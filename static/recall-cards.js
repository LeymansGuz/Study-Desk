'use strict';
document.addEventListener('study-ready',()=>{
  const container=document.createElement('section');container.id='recall-editor';container.innerHTML='<details class="library-panel"><summary>Create a short personal recall card</summary><p class="hint">One idea per card. Aim for a short prompt and answer; keep any essential formula conditions. Personal cards are not independently checked.</p><form id="recall-card-form"><label>Prompt (up to 25 words)<textarea name="front" maxlength="250" rows="2" required></textarea></label><label>Answer (up to 50 words)<textarea name="back" maxlength="650" rows="3" required></textarea></label><button type="submit" class="quiet-button">Save personal card</button><p id="recall-card-status" role="status"></p></form></details><div id="recall-card-preview"></div>';
  document.querySelector('#cards-manage').after(container);
  const shortcut=document.createElement('button');shortcut.type='button';shortcut.className='quiet-button';shortcut.textContent='Create a short recall card';
  document.querySelector('#review-cards').after(shortcut);
  shortcut.onclick=()=>{view('learning');for(let p=container.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;container.querySelector('details').open=true;requestAnimationFrame(()=>{container.scrollIntoView({block:'start',behavior:'instant'});container.querySelector('[name=front]').focus({preventScroll:true});});};
  const form=container.querySelector('form');form.onsubmit=e=>{e.preventDefault();task('card-save',form,'#recall-card-status',async()=>{const result=await post('/study/cards/save',{cards:[{front:form.elements.front.value,back:form.elements.back.value}]});form.reset();document.dispatchEvent(new Event('study-progress-updated'));return result.saved?'Card saved. Review in Progress or export to Anki.':'This recall card is already saved.';});};
  window.studyRecallCard=async(cardId,button)=>{
    const host=document.querySelector('#recall-card-preview');host.innerHTML='';
    button.closest('article').after(host);
    const message=document.createElement('p');message.setAttribute('role','status');host.append(message);
    host.scrollIntoView({block:'nearest'});
    if(local.providerScope==='brief_only'){message.textContent='Choose a suitable paid model to propose checked cards, or use the manual editor above.';return;}
    await task('card-proposal',button.closest('article'),message,async()=>{
      const proposal=await post('/study/cards/propose',{card_id:cardId});
      const preview=document.createElement('section');preview.className='local-item';preview.innerHTML='<h3>Review proposed recall cards</h3><p class="hint">Checked against the completed question and solution. The original question and its review history are kept. Saving starts separate recall schedules.</p>'+proposal.cards.map(c=>'<article class="local-item rich-text"><strong>Prompt</strong>'+rich(c.front)+'<strong>Answer</strong>'+rich(c.back)+'</article>').join('');
      const save=document.createElement('button');save.type='button';save.className='primary-button';save.textContent='Save these recall cards';preview.append(save);host.append(preview);
      preview.scrollIntoView({block:'nearest'});
      save.onclick=()=>task('card-save',preview,message,async()=>{const result=await post('/study/cards/save',{cards:proposal.cards,proposal_id:proposal.id});save.hidden=true;message.textContent=result.saved+' card(s) saved. Original review history is unchanged.';document.dispatchEvent(new Event('study-progress-updated'));}).then(()=>{if(save.hidden)status(message,'Recall cards saved. Original questions and their review history are kept.');});
    });
  };
});
