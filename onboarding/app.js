const $ = id => document.getElementById(id);
const sets = {personal: [], aesthetic: []};
let revision=0, loading=false, saving=false, rankingRequest=0, confirmedEnvironment=null;
function status(message){$('status').textContent=message;}
function user(){const id=$('user').value.trim();if(!id)throw Error('Enter your profile ID first.');return id;}
async function api(path,body){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(data.error||'Request failed.');return data;}
function clearResults(){rankingRequest++;$('results').replaceChildren();}
function stage(name){for(const key of ['personal','aesthetic','balance']){$(key+'-stage').hidden=key!==name;if(key===name)$('step-'+key).setAttribute('aria-current','step');else $('step-'+key).removeAttribute('aria-current');}clearResults();$(name+'-stage').scrollIntoView({behavior:'smooth',block:'start'});}
function selected(kind){return sets[kind].flatMap(ref=>ref.shades.filter(s=>s.selected));}
function updateButtons(){
  $('personal-next').disabled=loading||saving||!selected('personal').length||sets.personal.some(r=>!r.shades.length);
  $('aesthetic-next').disabled=loading||saving||($('add-aesthetic').value==='yes'&&(!selected('aesthetic').length||sets.aesthetic.some(r=>!r.shades.length)));
  $('aesthetic-next').textContent=$('add-aesthetic').value==='yes'?'Use these aesthetic shades & continue':'Continue with just my preferences';
}
function locked(value){saving=value;for(const id of ['user','category','personal-upload','aesthetic-upload','environment','add-aesthetic','aesthetic-back'])$(id).disabled=value;document.querySelectorAll('.references input,.references button').forEach(e=>e.disabled=value||e.dataset.saved==='true');updateButtons();}
function preview(ref){const c=ref.canvas,ctx=c.getContext('2d'),b=ref.box;ctx.drawImage(ref.source,0,0);const rect=[b.left*c.width/100,b.top*c.height/100,b.width*c.width/100,b.height*c.height/100];ctx.strokeStyle='black';ctx.lineWidth=5;ctx.strokeRect(...rect);ctx.strokeStyle='white';ctx.lineWidth=2;ctx.strokeRect(...rect);}
function clearExtraction(ref){ref.shades=[];ref.palette.replaceChildren();updateButtons();clearResults();}
function extract(ref){
  const b=ref.box,crop=document.createElement('canvas'),x=Math.floor(b.left*ref.source.width/100),y=Math.floor(b.top*ref.source.height/100),w=Math.max(1,Math.floor(b.width*ref.source.width/100)),h=Math.max(1,Math.floor(b.height*ref.source.height/100));
  crop.width=Math.min(w,160);crop.height=Math.min(h,160);crop.getContext('2d').drawImage(ref.source,x,y,w,h,0,0,crop.width,crop.height);
  const extracted=palette(crop.getContext('2d').getImageData(0,0,crop.width,crop.height).data);
  showReferenceShades(ref, extracted.map(s=>s.rgb));
}
// Future detector response: showReferenceShades(ref, response.shades).
// This only populates the review UI. Continue is still required to save likes.
function showReferenceShades(ref, rgbColors){
  if(ref.frozen||saving)return;
  const shades=shadesFromRgb(rgbColors); // Validate before changing existing review.
  ref.shades=shades.map(s=>({...s,selected:true,event_id:crypto.randomUUID(),saved:false}));
  ref.palette.replaceChildren();clearResults();
  ref.shades.forEach((s,i)=>{const label=document.createElement('label');label.className='palette-option';const input=document.createElement('input');input.type='checkbox';input.checked=true;input.onchange=()=>{s.selected=input.checked;updateButtons();clearResults();};const swatch=document.createElement('span');swatch.className='mini-swatch';swatch.style.background=s.hex;const text=document.createElement('span');text.textContent=`Shade ${i+1} · ${s.hex.toUpperCase()} · lightness ${Math.round(s.color[0]*100)}/100`;label.append(input,swatch,text);ref.palette.append(label);});
  status(ref.shades.length?'Review the checked shades. Nothing is saved until you continue.':'No opaque shades found. Adjust the crop or remove this image.');updateButtons();
}
function renderReference(ref,kind){
  const card=document.createElement('article');card.className='reference';ref.card=card;const heading=document.createElement('h3');heading.textContent=ref.name;
  const canvas=document.createElement('canvas');ref.canvas=canvas;canvas.width=ref.source.width;canvas.height=ref.source.height;canvas.setAttribute('aria-label',ref.name+' makeup region selection');canvas.className='reference-photo';
  const controls=document.createElement('div');controls.className='sliders';ref.inputs={};ref.outputs={};
  const sync=()=>{ref.box.width=Math.min(ref.box.width,100-ref.box.left);ref.box.height=Math.min(ref.box.height,100-ref.box.top);for(const key of Object.keys(ref.box)){ref.inputs[key].value=ref.box[key];ref.outputs[key].textContent=Math.round(ref.box[key])+'%';}preview(ref);};
  for(const key of ['left','top','width','height']){const label=document.createElement('label');label.textContent=key[0].toUpperCase()+key.slice(1)+' ';const input=document.createElement('input');input.type='range';input.min=['left','top'].includes(key)?0:1;input.max=['left','top'].includes(key)?99:100;input.value=ref.box[key];input.setAttribute('aria-label',`${ref.name} crop ${key}`);const output=document.createElement('output');ref.inputs[key]=input;ref.outputs[key]=output;input.oninput=()=>{ref.box[key]=Number(input.value);clearExtraction(ref);sync();};label.append(input,output);controls.append(label);}
  let start=null;const point=e=>{const r=canvas.getBoundingClientRect();return [Math.max(0,Math.min(99,(e.clientX-r.left)/r.width*100)),Math.max(0,Math.min(99,(e.clientY-r.top)/r.height*100))];};
  canvas.onpointerdown=e=>{if(saving||ref.frozen)return;start=point(e);canvas.setPointerCapture(e.pointerId);clearExtraction(ref);};canvas.onpointermove=e=>{if(!start)return;const end=point(e);ref.box={left:Math.min(start[0],end[0]),top:Math.min(start[1],end[1]),width:Math.max(1,Math.abs(start[0]-end[0])),height:Math.max(1,Math.abs(start[1]-end[1]))};sync();};canvas.onpointerup=canvas.onpointercancel=()=>{start=null;};
  const extractButton=document.createElement('button');extractButton.textContent='Extract makeup shades';extractButton.setAttribute('aria-label','Extract makeup shades from '+ref.name);extractButton.onclick=()=>extract(ref);
  // Placeholder only: no handler, image upload, or automatic ratings.
  const detectButton=document.createElement('button');
  detectButton.textContent='Auto-detect lip shades';
  detectButton.disabled=true;
  detectButton.dataset.saved='true'; // Keep disabled when save controls unlock.
  detectButton.setAttribute('aria-label','Auto-detect lip shades for '+ref.name+' (coming soon)');
  const remove=document.createElement('button');remove.textContent='Remove reference';remove.className='secondary';remove.onclick=()=>{sets[kind]=sets[kind].filter(r=>r!==ref);card.remove();updateButtons();};
  ref.palette=document.createElement('div');ref.palette.className='palette';const hint=document.createElement('p');hint.className='hint';hint.textContent='Drag over the selected makeup or adjust the crop sliders, then extract shades.';
  const privacy=document.createElement('p');privacy.className='hint';
  privacy.textContent='Auto-detection is coming soon. For now, select a rectangle and extract lip shades manually.';
  card.append(heading,canvas,hint,controls,detectButton,privacy,extractButton,remove,ref.palette);$(kind+'-gallery').append(card);sync();
}
async function loadFiles(kind,files){
  if(loading||saving)return;loading=true;const ticket=revision;updateButtons();const errors=[];
  try{for(const file of files){
    if(sets[kind].length>=6){errors.push('Each set supports up to 6 images.');break;}
    if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>10*1024*1024){errors.push(file.name+': choose JPEG, PNG or WebP up to 10 MB.');continue;}
    const url=URL.createObjectURL(file);
    try{const image=new Image();image.src=url;await image.decode();if(ticket!==revision)return;if(image.naturalWidth*image.naturalHeight>40_000_000)throw Error('Image exceeds 40 megapixels.');const scale=Math.min(1,800/Math.max(image.naturalWidth,image.naturalHeight)),source=document.createElement('canvas');source.width=Math.max(1,Math.round(image.naturalWidth*scale));source.height=Math.max(1,Math.round(image.naturalHeight*scale));source.getContext('2d').drawImage(image,0,0,source.width,source.height);const ref={name:file.name,source,box:{left:25,top:25,width:50,height:50},shades:[],frozen:false};sets[kind].push(ref);renderReference(ref,kind);}catch(error){errors.push(file.name+': '+error.message);}finally{URL.revokeObjectURL(url);}
  }status(errors.length?errors.join(' '):'References added. Select the makeup region in each photo.');}finally{loading=false;$(kind+'-upload').value='';updateButtons();}
}
for(const kind of ['personal','aesthetic'])$(kind+'-upload').onchange=e=>loadFiles(kind,[...e.target.files]);
function freeze(ref){ref.frozen=true;ref.card.querySelectorAll('input,button').forEach(e=>{e.disabled=true;e.dataset.saved='true';});}
async function saveSet(kind){
  const profile=user(),destination=kind==='personal'?'personal':'environment:'+($('environment').value.trim());
  if(kind==='aesthetic'&&!$('environment').value.trim())throw Error('Name your aesthetic inspiration first.');if(!selected(kind).length)throw Error('Keep at least one extracted shade checked.');
  // Stable IDs and frozen cards allow retries after partial network failures.
  sets[kind].forEach(freeze);locked(true);
  try{for(const shade of selected(kind))if(!shade.saved){await api('/api/rating',{user_id:profile,preference_profile_id:destination,category:$('category').value,color:shade.color,rating:1,event_id:shade.event_id});shade.saved=true;}if(kind==='aesthetic')confirmedEnvironment=destination;}finally{locked(false);}
}
$('personal-next').onclick=async()=>{try{await saveSet('personal');status('Your reference shades are saved.');stage('aesthetic');}catch(e){status(e.message+' Continue again to retry; saved shades will not be duplicated.');}};
$('add-aesthetic').onchange=()=>{$('aesthetic-inputs').hidden=$('add-aesthetic').value!=='yes';updateButtons();clearResults();};
$('environment').onchange=()=>{if(sets.aesthetic.some(r=>r.frozen)){sets.aesthetic=[];$('aesthetic-gallery').replaceChildren();confirmedEnvironment=null;status('New environment name. Add its own reference set. Previously saved ratings are retained.');}updateButtons();};
$('aesthetic-back').onclick=()=>stage('personal');
$('aesthetic-next').onclick=async()=>{try{if($('add-aesthetic').value==='yes'){await saveSet('aesthetic');$('weight').value=60;$('weight').disabled=false;}else{$('weight').value=100;$('weight').disabled=true;}$('balance-description').textContent=hasAesthetic()?`Choose how much your taste and ${$('environment').value.trim()} (your estimate) should influence the result.`:'No second reference set selected. Recommendations use 100% your own taste.';weightLabel();stage('balance');status('Choose your balance, then reveal your suggested shades.');}catch(e){status(e.message+' Continue again to retry.');}};
function hasAesthetic(){return $('add-aesthetic').value==='yes'&&confirmedEnvironment!==null&&selected('aesthetic').some(s=>s.saved);}
function weightLabel(){const self=hasAesthetic()?Number($('weight').value):100;$('weight-output').textContent=`${self}% my taste · ${100-self}% aesthetic inspiration`;$('weight').setAttribute('aria-valuetext',$('weight-output').textContent);clearResults();}
$('weight').oninput=weightLabel;$('balance-back').onclick=()=>stage('aesthetic');
$('recommend').onclick=async()=>{
  const ticket=++rankingRequest;
  try{$('recommend').disabled=true;const data=await api('/api/recommend',{user_id:user(),category:$('category').value,mode:'weighted',personal_weight:hasAesthetic()?Number($('weight').value)/100:1,...(hasAesthetic()?{environment_profile_id:confirmedEnvironment}:{})});if(ticket!==rankingRequest)return;
    const note=document.createElement('p');note.textContent=`${Math.round(data.personal_weight*100)}% my taste · ${Math.round(data.environment_weight*100)}% aesthetic inspiration. Scores express similarity-based preferences, not probabilities.`;
    const grid=document.createElement('div');grid.className='cards';$('results').replaceChildren(note,grid);
    if(!data.results.some(r=>r.score!==null&&r.score>0)){const message=document.createElement('p');message.textContent='No confident positive product match yet. These catalog products may need more reference evidence.';$('results').insertBefore(message,grid);}
    for(const [i,item] of data.results.slice(0,12).entries()){const card=document.createElement('article');card.className='card';const swatch=document.createElement('div');swatch.className='swatch';swatch.style.background=`oklab(${item.color[0]} ${item.color[1]} ${item.color[2]})`;const title=document.createElement('h3');title.textContent=`${i+1}. ${item.name}`;const summary=document.createElement('p');summary.textContent=item.score===null?'Not enough nearby evidence':`Preference score: ${item.score.toFixed(2)}${hasAesthetic()&&item.shared_match?' · Positive evidence in both profiles':''}`;const detail=document.createElement('details'),label=document.createElement('summary'),reason=document.createElement('p');label.textContent='Why this shade';reason.textContent=`My taste: ${item.personal.reason.join(' ')}${hasAesthetic()?' Aesthetic estimate: '+item.environment.reason.join(' '):''}`;detail.append(label,reason);const code=document.createElement('p');code.textContent=`Color source: ${item.color_source||'unspecified'} · Approximate preview`;card.append(swatch,title,code,summary,detail);
      if(item.accessibility){
        const accessibility=document.createElement('p');
        accessibility.textContent=`Accessibility: ${item.accessibility.score.toFixed(2)} / 1. ${item.accessibility.reason}`;
        card.append(accessibility);
      }else if(item.accessibility_error){
        const unavailable=document.createElement('p');unavailable.textContent=item.accessibility_error;card.append(unavailable);
      }
      grid.append(card);}status('Suggestions ready. Change the slider and suggest again to compare balances.');
  }catch(e){status(e.message);}finally{$('recommend').disabled=false;}
};
function resetReferences(){revision++;confirmedEnvironment=null;for(const kind of ['personal','aesthetic']){sets[kind]=[];$(kind+'-gallery').replaceChildren();$(kind+'-upload').value='';}$('add-aesthetic').value='no';$('aesthetic-inputs').hidden=true;stage('personal');updateButtons();status('Profile changed. Add references for this user.');};

$('user').onchange=resetReferences;
$('category').onchange=resetReferences;
fetch('/api/catalogs').then(async response=>{
  const data=await response.json();if(!response.ok)throw Error(data.error||'Could not load catalogs.');
  $('category').replaceChildren();
  for(const catalog of data.catalogs){const option=document.createElement('option');option.value=catalog.category;option.textContent=`${catalog.category} (${catalog.count} products)`;option.disabled=!catalog.count;$('category').append(option);}
  const active=data.catalogs.find(c=>c.count>0);if(!active)throw Error('Add products to the catalogs folder first.');
  $('category').value=active.category;
}).catch(error=>{status(error.message);$('personal-upload').disabled=true;});
