const $ = id => document.getElementById(id);
let report = null, activeIndex = null, filter = 'all', busy = false;
const choices = {};
const labels = {matched:'Metadata match',needs_review:'Needs review',not_found:'Not found',incomplete_search:'Search incomplete'};
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function safeLink(url,label){try{const u=new URL(url);if(u.protocol!=='https:')return el('span',label);const a=el('a',label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{return el('span',label);}}
function count(){const n=Object.keys(choices).length;$('selection-count').textContent=`${n} correction${n===1?'':'s'} selected · others unchanged`;}
function filteredRows(){const query=$('search').value.trim().toLowerCase();return (report?.results||[]).filter(row=>(filter==='all'||row.status===filter||(filter==='unresolved'&&['not_found','incomplete_search'].includes(row.status)))&&row.input.raw.toLowerCase().includes(query));}
function renderList(){
 const rows=filteredRows();$('reference-list').replaceChildren();$('list-total').textContent=rows.length;
 if(!rows.some(r=>r.index===activeIndex))activeIndex=rows[0]?.index??null;
 for(const row of rows){
  const b=el('button',undefined,'reference-row'+(row.index===activeIndex?' selected':''));b.type='button';b.setAttribute('aria-pressed',String(row.index===activeIndex));
  const top=el('div',undefined,'row-top');top.append(el('span',undefined,'status-dot '+row.status),el('span',labels[row.status]),el('span',String(row.index+1).padStart(2,'0'),'row-num'));
  b.append(top,el('div',row.input.title||row.input.raw,'row-title'),el('div',[row.input.authors.join(', '),row.input.year].filter(Boolean).join(' · ')||'Bibliographic details unavailable','row-meta'));
  if(choices[row.index]!==undefined)b.append(el('div','Correction selected','row-selected'));
  b.onclick=()=>{activeIndex=row.index;renderList();renderDetail();};$('reference-list').append(b);
 }
 if(!rows.length)$('reference-list').append(el('div','No references in this view.','list-empty'));
}
function renderDetail(){
 const row=report?.results.find(r=>r.index===activeIndex);$('results').replaceChildren();$('position').textContent=row?`${row.index+1} of ${report.results.length}`:'';
 if(!row){$('results').append(el('div','Select a reference from the list to inspect its metadata.','list-empty'));return;}
 const page=el('article',undefined,'detail-content');const badge=el('div',undefined,'detail-status');badge.append(el('span',undefined,'status-dot '+row.status),el('span',labels[row.status]));
 page.append(badge,el('h2',row.input.title||'Untitled reference','detail-title'),el('p',[row.input.authors.join(', '),row.input.year].filter(Boolean).join(' · ')||'Review the original reference below.','detail-meta'));
 page.append(el('h3','ORIGINAL REFERENCE','section-label'),el('p',row.input.raw,'original'),el('h3','SOURCE LOOKUP','section-label'));
 const sources=el('div',undefined,'sources');for(const s of row.sources)sources.append(el('span',`${s.name} · ${s.state==='ok'?s.count+' found':'unavailable'}`,'source-pill '+s.state));page.append(sources);
 for(const warning of row.input.warnings)page.append(el('p',warning,'review-note'));
 if(row.candidates.length){
  page.append(el('h3','COMPARE & SELECT','section-label'));
  const keep=el('label',undefined,'keep-original');const none=el('input');none.type='radio';none.name=`row-${row.index}`;none.checked=choices[row.index]===undefined;none.onchange=()=>{delete choices[row.index];count();renderList();};keep.append(none,el('span','Keep original reference'));page.append(keep);
  for(const candidate of row.candidates){
   const c=el('div',undefined,'candidate'),heading=el('div',undefined,'candidate-heading'),label=el('label'),radio=el('input');radio.type='radio';radio.name=`row-${row.index}`;radio.checked=choices[row.index]===candidate.id;radio.onchange=()=>{choices[row.index]=candidate.id;count();renderList();};label.append(radio,el('span',candidate.record.title));heading.append(label,el('p',[candidate.record.venue,candidate.record.year].filter(Boolean).join(' · ')));c.append(heading);
   const links=el('div',undefined,'source-links');for(const s of candidate.record.sources)links.append(safeLink(s.url,s.name+' ↗'));c.append(links);
   const wrap=el('div',undefined,'table-scroll'),table=el('table'),thead=el('thead'),head=el('tr');for(const t of ['Field','Your reference','Source record'])head.append(el('th',t));thead.append(head);table.append(thead);const body=el('tbody');
   for(const d of candidate.differences){if(d.state==='not_supplied'&&!d.candidate)continue;const tr=el('tr');tr.append(el('td',d.field),el('td',d.input||'Not supplied',d.input?'':'missing'),el('td',d.candidate||'Unavailable',d.state==='different'?'different':d.candidate?'':'missing'));body.append(tr);}table.append(body);wrap.append(table);c.append(wrap);
   const notes=el('div',undefined,'candidate-notes');for(const reason of [...candidate.reasons,...candidate.record.conflicts])notes.append(el('p',reason));c.append(notes);page.append(c);
  }
 }else page.append(el('p','No candidate is available to compare. Try a fuller title or a DOI, or retry live lookup if a source is unavailable.','unresolved-note'));
 page.append(el('p',row.note,'review-note'));$('results').append(page);
}
function render(data){
 report=data;for(const k of Object.keys(choices))delete choices[k];activeIndex=data.results.find(r=>r.status==='needs_review')?.index??data.results[0]?.index;filter='all';$('search').value='';
 $('count-all').textContent=data.results.length;for(const key of ['matched','needs_review'])$('count-'+key).textContent=data.summary[key];$('count-unresolved').textContent=data.summary.not_found+data.summary.incomplete_search;
 $('mode-tag').textContent=data.mode==='demo'?'Offline example':'Live metadata';$('exports').hidden=false;$('report').href=`/api/report/${data.id}`;
 setFilter('all');count();$('feedback').textContent=`${data.results.length} references checked in ${data.elapsed_seconds}s. Corrections require your selection.`;
}
function setFilter(value){filter=value;const names={all:'All references',needs_review:'Needs review',matched:'Metadata matches',unresolved:'Unresolved'};$('list-title').textContent=names[value];document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('active',b.dataset.filter===value);b.setAttribute('aria-pressed',String(b.dataset.filter===value));});renderList();renderDetail();}
function openImport(){if(!$('import-dialog').open)$('import-dialog').showModal();}
$('new-list').onclick=openImport;$('start').onclick=openImport;$('close-dialog').onclick=()=>$('import-dialog').close();
$('search').oninput=()=>{renderList();renderDetail();};document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>setFilter(b.dataset.filter));
document.addEventListener('keydown',e=>{if(e.key.toLowerCase()==='n'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!$('import-dialog').open){e.preventDefault();openImport();}});
$('sample').onclick=async()=>{try{const r=await fetch('/api/demo');if(!r.ok)throw new Error('Could not load example.');$('references').value=(await r.json()).text;$('file').value='';document.querySelector('input[name="mode"][value="demo"]').checked=true;$('ai').checked=false;await runCheck();}catch(err){$('feedback').textContent=err.message;}};
$('clear-file').onclick=()=>{$('file').value='';};
async function runCheck(){
 if(busy)return;busy=true;$('check').disabled=true;if($('sample'))$('sample').disabled=true;$('import-error').textContent='';$('feedback').textContent='Checking references… Live source lookups may take a minute or more.';
 try{const form=new FormData($('check-form'));form.set('ai',$('ai').checked?'true':'false');const response=await fetch('/api/check',{method:'POST',body:form});const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Request failed');render(data);$('import-dialog').close();}catch(err){$('feedback').textContent=err.message;$('import-error').textContent=err.message;}finally{busy=false;$('check').disabled=false;if($('sample'))$('sample').disabled=false;}
}
$('check-form').onsubmit=e=>{e.preventDefault();runCheck();};
async function download(kind){if(!report)return;try{const r=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({report_id:report.id,selections:choices,format:kind})});if(!r.ok){const d=await r.json();throw new Error(d.detail||'Export failed');}const url=URL.createObjectURL(await r.blob());const a=el('a');a.href=url;a.download=`reviewed-references.${kind}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){$('feedback').textContent=e.message;}}
$('docx').onclick=()=>download('docx');$('txt').onclick=()=>download('txt');
