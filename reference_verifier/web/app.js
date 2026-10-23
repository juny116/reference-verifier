const $ = id => document.getElementById(id);
let report = null;
const choices = {};
const labels = {matched:'Metadata match',needs_review:'Review needed',not_found:'Not found',incomplete_search:'Search incomplete'};
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function count(){ $('selection-count').textContent=`${Object.keys(choices).length} corrections selected. Other entries stay unchanged.`; }
function safeLink(url,label){try{const u=new URL(url);if(u.protocol!=='https:')return el('span',label);const a=el('a',label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{return el('span',label);}}
function render(data){
  report=data;for(const k of Object.keys(choices))delete choices[k];count();$('results').replaceChildren();$('summary').replaceChildren();
  $('mode-tag').textContent=data.mode==='demo'?'Offline fixtures':'Live metadata';
  for(const [key,n] of Object.entries(data.summary))if(n)$('summary').append(el('span',`${n} ${labels[key]}`));
  for(const row of data.results){
    const card=el('article',undefined,`result ${row.status}`);card.append(el('span',`${row.index+1} / ${labels[row.status]}`,'badge'),el('h3',row.input.raw));
    card.append(el('p',row.sources.map(s=>`${s.name}: ${s.state==='ok'?`${s.count} candidates`:'unavailable'}`).join(' · '),'source-status'));
    for(const w of row.input.warnings)card.append(el('p',w,'muted'));
    card.append(el('p',row.note,'muted'));
    if(row.candidates.length){
      const details=el('details');details.open=true;details.append(el('summary',`Compare ${row.candidates.length} candidate${row.candidates.length===1?'':'s'}`));
      const keep=el('label','Keep original (default)');const none=el('input');none.type='radio';none.name=`row-${row.index}`;none.checked=true;none.onchange=()=>{delete choices[row.index];count();};keep.prepend(none);details.append(keep);
      for(const candidate of row.candidates){const c=el('div',undefined,'candidate');const lab=el('label',candidate.record.title);const radio=el('input');radio.type='radio';radio.name=`row-${row.index}`;radio.onchange=()=>{choices[row.index]=candidate.id;count();};lab.prepend(radio);c.append(lab);
        c.append(el('p',`${candidate.record.year||'Year unavailable'} · ${candidate.record.venue||'Venue unavailable'}`));
        for(const s of candidate.record.sources)c.append(safeLink(s.url,s.name+' ↗'));
        const table=el('table');const head=el('tr');for(const t of ['Field','Input','Source'])head.append(el('th',t));const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody');
        for(const d of candidate.differences){if(d.state==='not_supplied'&&!d.candidate)continue;const tr=el('tr');tr.append(el('td',d.field),el('td',d.input||'Not supplied'),el('td',d.candidate||'Unavailable',d.state==='different'?'different':''));body.append(tr);}table.append(body);c.append(table);
        for(const reason of [...candidate.reasons,...candidate.record.conflicts])c.append(el('p',reason));details.append(c);
      }card.append(details);
    }$('results').append(card);
  }
  $('exports').hidden=false;$('report').href=`/api/report/${data.id}`;$('feedback').textContent=`Checked ${data.results.length} references in ${data.elapsed_seconds}s. Review and explicitly select any corrections.`;
}
$('sample').onclick=async()=>{try{const r=await fetch('/api/demo');$('references').value=(await r.json()).text;$('file').value='';}catch{$('feedback').textContent='Could not load example.';}};
$('clear-file').onclick=()=>{$('file').value='';};
$('check-form').onsubmit=async e=>{e.preventDefault();$('check').disabled=true;$('exports').hidden=true;report=null;$('feedback').textContent='Looking up sources… Live lookups may take a minute or more for a list. Provider failures will be shown.';
  try{const form=new FormData(e.target);form.set('ai',$('ai').checked?'true':'false');const response=await fetch('/api/check',{method:'POST',body:form});const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Request failed');render(data);}catch(err){$('feedback').textContent=err.message;$('results').replaceChildren();$('summary').replaceChildren();}finally{$('check').disabled=false;}
};
async function download(kind){if(!report)return;try{const r=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({report_id:report.id,selections:choices,format:kind})});if(!r.ok){const d=await r.json();throw new Error(d.detail||'Export failed');}const url=URL.createObjectURL(await r.blob());const a=el('a');a.href=url;a.download=`reviewed-references.${kind}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){$('feedback').textContent=e.message;}}
$('docx').onclick=()=>download('docx');$('txt').onclick=()=>download('txt');
