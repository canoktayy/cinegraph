/* MovieGraph demo. All titles, scores, paths and statistics come from the API. */
'use strict';
const $ = selector => document.querySelector(selector);
const state = {view:'recommendations', offset:0, limit:8, rows:[], loading:false};
const palettes = [
  ['#c4cfc3','#718b7b','#213f37'],['#e3cbb1','#be7858','#4f3529'],
  ['#b8c5cd','#587582','#203d4b'],['#c5c1cf','#79718b','#39334c'],
  ['#ddd8b4','#a6a16b','#4b4a29'],['#d5bcb4','#a36c66','#542f30'],
  ['#bacdca','#558c86','#1c4945'],['#d4cdbf','#9a8b6c','#484034']
];
const copy = {
  recommendations:['For you','A few stories for you','Follow your taste.<br><em>Find your next story.</em>'],
  discover:['Taste communities','People like you. Films beyond you.','Shared tastes.<br><em>Unexpected discoveries.</em>'],
  trending:['The long view','Stories that made a connection','Great stories linger.<br><em>See the long view.</em>'],
  catalog:['Explore the catalog','A whole world of stories','Every film, a doorway.<br><em>Where will you go?</em>']
};
function escapeText(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function api(path, options={}){
  const response=await fetch(path,options);let result;
  try{result=await response.json();}catch{throw new Error('The service returned an unreadable response.');}
  if(!response.ok){const detail=result.detail??result.message??'Request failed';throw new Error(typeof detail==='string'?detail:JSON.stringify(detail));}
  return result;
}
function notice(text){$('#notice').textContent=text;$('#notice').hidden=!text;}
function setView(view){
  state.view=view;state.offset=0;
  document.querySelectorAll('.nav-item').forEach(button=>button.classList.toggle('active',button.dataset.view===view));
  $('#breadcrumb').textContent=copy[view][0];$('#collection-title').textContent=copy[view][1].replace(/\.$/,'')+'.';
  $('#hero-title').innerHTML=copy[view][2];$('#show-more').hidden=view!=='catalog';
  $('#genre').disabled=!['catalog','recommendations'].includes(view);if($('#genre').disabled)$('#genre').value='';loadFilms();
}
function card(movie,index){
  const palette=palettes[Math.abs(movie.movie_id)%palettes.length];
  const title=movie.title.replace(/\s*\(\d{4}\)\s*$/,'');
  const score=Number.isFinite(movie.score)?movie.score.toFixed(2):null;
  const activeGenre=$('#genre').value;const genres=[...(movie.genres||[])].sort((a,b)=>a===activeGenre?-1:b===activeGenre?1:a.localeCompare(b)).slice(0,2).join(' / ')||'Unclassified';
  return `<article class="movie-card"><button class="movie-art variant-${movie.movie_id%5}" data-detail="${movie.movie_id}" aria-label="Explore ${escapeText(movie.title)}" style="--poster-bg:${palette[0]};--poster-color:${palette[1]};--poster-ink:${palette[2]}"><span class="art-stripes"></span><span class="film-number">FRAME / ${String(index+1+state.offset).padStart(2,'0')}</span><span class="film-year">${movie.year||'—'}</span><span class="poster-type ${title.length>50?'long-title':''}"><span class="poster-caption">A MOVIEGRAPH SELECTION</span>${escapeText(title)}</span></button><div class="movie-meta"><div><span class="movie-title">${escapeText(title)}</span><span class="movie-genre">${escapeText(genres)}</span></div>${score?`<span class="movie-score">✧ ${score}</span>`:''}</div><div class="movie-bottom"><button class="why-button" ${state.view==='recommendations'?'data-evidence':'data-detail'}="${movie.movie_id}">${state.view==='recommendations'?'Why this film?':'Follow the connection'} ↗</button><span class="support-label">${movie.support?escapeText(movie.support)+' signals':'CATALOG'}</span></div></article>`;
}
async function loadFilms(){
  if(state.loading)return;state.loading=true;$('#movie-grid').classList.add('loading');notice('');
  try{
    const user=Number($('#user-id').value);const genre=$('#genre').value;const q=$('#search').value.trim();
    let path;
    if(state.view==='catalog')path=`/api/movies?limit=${state.limit}&offset=${state.offset}&q=${encodeURIComponent(q)}&genre=${encodeURIComponent(genre)}`;
    else if(state.view==='trending')path=`/api/movies/trending?limit=${state.limit}&window_days=365`;
    else if(state.view==='discover')path=`/api/users/${user}/discover?limit=${state.limit}`;
    else path=`/api/users/${user}/recommendations?limit=${state.limit}${genre?'&genre='+encodeURIComponent(genre):''}`;
    // An absent filter must remain absent, rather than the empty string genre.
    path=path.replace(/&genre=$/,'');
    const result=await api(path);state.rows=result.items;$('#show-more').hidden=state.view!=='catalog'||result.items.length<state.limit;$('#show-previous').hidden=state.view!=='catalog'||state.offset===0;
    $('#movie-grid').innerHTML=result.items.length?result.items.map(card).join(''):'<div class="empty-state">No matching stories yet. Try another genre or user.</div>';
    const method=(result.method||'catalog').replaceAll('_',' ');
    $('#method-note').textContent=method.charAt(0).toUpperCase()+method.slice(1);
    $('#result-note').textContent=`${result.items.length} films · ${state.view==='catalog'?'catalog snapshot':state.view==='trending'?'historical snapshot':'user '+user+' · '+method}`;
    if(result.fallback_reason)notice('Fallback: '+result.fallback_reason);
  }catch(error){notice(error.message);$('#movie-grid').innerHTML='<div class="empty-state">We couldn’t follow that connection.<br><small>Check the graph service or try another user.</small></div>';$('#result-note').textContent='Request could not be completed';}
  finally{state.loading=false;$('#movie-grid').classList.remove('loading');}
}
async function loadStats(){
  try{
    const stats=await api('/api/system/status');
    for(const field of ['movies','ratings','users'])$('#stat-'+field).textContent=new Intl.NumberFormat('en-US').format(stats[field]);
    $('#snapshot-date').textContent=stats.as_of?new Date(stats.as_of*1000).toLocaleDateString('en-US',{month:'short',year:'numeric'}):'Not seeded';
    document.querySelector('.health-dot').classList.add('ready');
    const genres=await api('/api/genres');
    genres.forEach(genre=>{const option=document.createElement('option');option.value=genre;option.textContent=genre;$('#genre').append(option);});
  }catch(error){notice(error.message);$('#snapshot-date').textContent='Graph unavailable';}
}
function openDetail(html){$('#detail-content').innerHTML=html;$('#detail-dialog').showModal();}
async function showSimilar(movieId){
  const film=state.rows.find(row=>row.movie_id===movieId);
  openDetail(`<div class="detail-label">FOLLOW THE CONNECTION</div><h2 class="detail-heading">${escapeText(film?.title||'Movie '+movieId)}</h2><p class="detail-copy">Finding films with overlapping positive raters…</p>`);
  try{
    const result=await api(`/api/movies/${movieId}/similar?limit=6`);
    $('#detail-content').insertAdjacentHTML('beforeend',`<div class="similar-list">${result.items.map(row=>`<div class="similar-item">${escapeText(row.title)}<small>Similarity ${row.score.toFixed(3)} · ${row.support} shared positive raters</small></div>`).join('')||'<p>No supported similarity neighbors in this snapshot.</p>'}</div><p class="detail-copy">Shrunk Jaccard similarity · scores are not probabilities.</p><button class="primary-link" data-evidence="${movieId}">Why for user ${escapeText($('#user-id').value)}? ↗</button>`);
  }catch(error){$('#detail-content').insertAdjacentHTML('beforeend',`<p class="error-text">${escapeText(error.message)}</p>`);}
}
async function showEvidence(movieId){
  const user=Number($('#user-id').value);openDetail('<div class="detail-label">VISIBLE REASONS</div><h2 class="detail-heading">Every recommendation has a path.</h2><p class="detail-copy">Following the graph…</p>');
  try{
    const result=await api(`/api/users/${user}/recommendations/${movieId}/explanation`);
    $('#detail-content').innerHTML=`<div class="detail-label">EVIDENCE / USER ${user} → FILM ${movieId}</div><h2 class="detail-heading">A reason, not a guess.</h2><p class="detail-copy">${escapeText(result.explanation)}</p>${result.evidence.map(evidence=>`<div class="evidence-path"><h4>${escapeText(evidence.path[2].title)}</h4><div class="path-nodes"><span class="path-node">User ${user}</span><span class="path-arrow">RATED →</span><span class="path-node">Movie ${evidence.path[2].movie_id}</span><span class="path-arrow">SIMILAR_TO →</span><span class="path-node">Movie ${movieId}</span></div><div class="evidence-stats"><span>Rating ${evidence.source_rating}</span><span>Similarity ${evidence.similarity.toFixed(3)}</span><span>${evidence.support} shared raters</span><span>Contribution ${evidence.contribution.toFixed(3)}</span></div></div>`).join('')}<p class="detail-copy">Observed ratings + derived similarity. ${escapeText(result.note)}<br>Run: ${escapeText(result.analytics_run_id||'none')}</p>`;
  }catch(error){$('#detail-content').innerHTML=`<h2 class="detail-heading">Connection unavailable.</h2><p class="error-text">${escapeText(error.message)}</p>`;}
}
async function askGraph(){
  const question=$('#question').value.trim();const key=$('#api-key').value.trim();
  if(!question||!key){$('#ask-result').hidden=false;$('#ask-result').textContent='Add your local access key and a question first.';return;}
  const button=$('#ask-button');button.disabled=true;button.textContent='Following the graph…';$('#ask-result').hidden=false;$('#ask-result').textContent='The local model is interpreting your question. No model-generated query will run unchecked.';
  try{
    const result=await api('/api/ask',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':key},body:JSON.stringify({question,user_id:Number($('#user-id').value),limit:10})});
    $('#ask-result').innerHTML=`<strong>${escapeText(result.explanation)}</strong><br>${escapeText(result.warnings.join(' '))}<details><summary>View the validated Cypher and graph evidence ↗</summary><pre>${escapeText(result.compiled_cypher)}</pre><pre>${escapeText(JSON.stringify(result.rows,null,2))}</pre></details>`;
  }catch(error){$('#ask-result').innerHTML=`<span class="error-text">${escapeText(error.message)}</span>`;}
  finally{button.disabled=false;button.innerHTML='Follow the evidence <span>↗</span>';}
}
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>setView(button.dataset.view)));
$('#filter-form').addEventListener('submit',event=>{event.preventDefault();state.offset=0;if($('#search').value.trim()&&state.view!=='catalog')setView('catalog');else loadFilms();});
$('#show-previous').addEventListener('click',()=>{state.offset=Math.max(0,state.offset-state.limit);loadFilms();});
$('#show-more').addEventListener('click',()=>{state.offset+=state.limit;if(state.offset>1000)state.offset=0;loadFilms();});
document.addEventListener('click',event=>{const evidence=event.target.closest('[data-evidence]');const detail=event.target.closest('[data-detail]');if(evidence)showEvidence(Number(evidence.dataset.evidence));else if(detail)showSimilar(Number(detail.dataset.detail));});
$('#close-detail').addEventListener('click',()=>$('#detail-dialog').close());
$('#detail-dialog').addEventListener('click',event=>{if(event.target===$('#detail-dialog'))$('#detail-dialog').close();});
$('#ask-button').addEventListener('click',askGraph);
document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>{$('#question').value=button.dataset.question;$('#question').focus();}));
loadStats();loadFilms();
