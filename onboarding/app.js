// Shared page state and helpers
const $ = id => document.getElementById(id);
const sets = {
  personal: [],
  aesthetic: [],
  skin: []
};
let revision = 0,
  loading = false,
  saving = false,
  rankingRequest = 0,
  confirmedEnvironment = null;

function status(message) {
  $('status').textContent = message;
}

function user() {
  const id = $('user').value.trim();
  if (!id) throw Error('Enter your profile ID first.');
  return id;
}
async function api(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Request failed.');
  return data;
}

function clearResults() {
  rankingRequest++;
  $('results').replaceChildren();
}

function stage(name) {
  if (name === 'skin') loadSkinProfile();
  for (const key of ['personal', 'aesthetic', 'cvd', 'skin', 'balance']) {
    $(key + '-stage').hidden = key !== name;
    if (key === name) $('step-' + key).setAttribute('aria-current', 'step');
    else $('step-' + key).removeAttribute('aria-current');
  }
  clearResults();
  $('skip-content').setAttribute('href', '#' + name + '-stage');
  $(name + '-stage').setAttribute('tabindex', '-1');
  $(name + '-stage').focus?.({preventScroll: true});
  $(name + '-stage').scrollIntoView({
    behavior: 'auto',
    block: 'start'
  });
}

function selected(kind) {
  return sets[kind].flatMap(ref => ref.shades.filter(s => s.selected));
}
// Enable/disable controls during uploads and saves.
function updateButtons() {
  const count = selected('personal').length;
  $('personal-count').textContent = count ? `${count} shade${count === 1 ? '' : 's'} selected` : 'Select shades to get started';
  const detecting = [...sets.personal, ...sets.aesthetic, ...sets.skin].some(ref => ref.detecting);
  $('skin-next').disabled = loading || saving || detecting ||
    !(selected('skin').length || (typeof skinSavedCount !== 'undefined' && skinSavedCount > 0));
  for (const id of ['skin-skip', 'skin-back', 'skin-clear']) $(id).disabled = saving || loading || detecting;
  $('personal-next').disabled = loading || saving || detecting || !selected('personal').length || sets.personal
    .some(r => !r.shades.length);
  $('aesthetic-next').disabled = loading || saving || detecting || ($('add-aesthetic').value === 'yes' && (!
    selected('aesthetic').length || sets.aesthetic.some(r => !r.shades.length)));
  $('aesthetic-next').textContent = $('add-aesthetic').value === 'yes' ?
    'Use these aesthetic shades & continue' : 'Continue with just my preferences';
}

function locked(value) {
  saving = value;
  for (const id of ['user', 'category', 'personal-upload', 'aesthetic-upload', 'environment',
      'add-aesthetic', 'aesthetic-back', 'skin-upload'
    ]) $(id).disabled = value;
  document.querySelectorAll('.references input,.references button').forEach(e => e.disabled =
    value || e.dataset.saved === 'true');
  updateButtons();
}
// Manual cropping and RGB shade review
function preview(ref) {
  const c = ref.canvas,
    ctx = c.getContext('2d'),
    b = ref.box;
  ctx.drawImage(ref.source, 0, 0);
  const rect = [b.left * c.width / 100, b.top * c.height / 100, b.width * c.width / 100, b.height *
    c.height / 100
  ];
  ctx.strokeStyle = 'black';
  ctx.lineWidth = 5;
  ctx.strokeRect(...rect);
  ctx.strokeStyle = 'white';
  ctx.lineWidth = 2;
  ctx.strokeRect(...rect);
}

function clearExtraction(ref) {
  ref.extractionVersion = (ref.extractionVersion || 0) + 1;
  ref.shades = [];
  ref.palette.replaceChildren();
  updateButtons();
  clearResults();
}

function extract(ref) {
  ref.extractionVersion = (ref.extractionVersion || 0) + 1;
  const b = ref.box,
    crop = document.createElement('canvas'),
    x = Math.floor(b.left * ref.source.width / 100),
    y = Math.floor(b.top * ref.source.height / 100),
    w = Math.max(1, Math.floor(b.width * ref.source.width / 100)),
    h = Math.max(1, Math.floor(b.height * ref.source.height / 100));
  crop.width = Math.min(w, 160);
  crop.height = Math.min(h, 160);
  crop.getContext('2d').drawImage(ref.source, x, y, w, h, 0, 0, crop.width, crop.height);
  const extracted = palette(crop.getContext('2d').getImageData(0, 0, crop.width, crop.height).data);
  showReferenceShades(ref, extracted.map(s => s.rgb));
}
// Send the full resized photo only when automatic detection is requested.
async function detectReferenceShades(ref, kind, button) {
  if (saving || ref.frozen || ref.detecting) return;
  const pageVersion = revision;
  const extractionVersion = ref.extractionVersion = (ref.extractionVersion || 0) + 1;
  const category = kind === 'skin' ? 'skin_tone' : $('category').value;
  const isCurrent = () => pageVersion === revision && sets[kind].includes(ref) &&
    extractionVersion === ref.extractionVersion && !ref.frozen && !saving;
  ref.detecting = true;
  button.disabled = true;
  updateButtons();
  status('Detecting shades in ' + ref.name + '…');
  try {
    const blob = await new Promise(resolve => ref.source.toBlob(resolve, 'image/png'));
    if (!isCurrent()) return;
    if (!blob) throw Error('Could not prepare the image. Try manual extraction.');
    const body = new FormData();
    body.append('image', blob, 'reference.png');
    body.append('category', category);
    const response = await fetch('/api/detect-shades', {method: 'POST', body});
    const data = await response.json();
    if (!isCurrent()) return;
    if (!response.ok) throw Error(data.error || 'Detection failed. Try manual extraction.');
    if (Array.isArray(data.shades) && data.shades.length === 0) {
      status('No usable shades found. Use a clear photo of one face or extract shades manually.');
      return;
    }
    showReferenceShades(ref, data.shades);
  } catch (error) {
    if (isCurrent()) status(error.message);
  } finally {
    ref.detecting = false;
    button.disabled = saving || ref.frozen;
    updateButtons();
  }
}

// This only populates the review UI. Continue is still required to save likes.
function showReferenceShades(ref, rgbColors) {
  if (ref.frozen || saving) return;
  const shades = shadesFromRgb(rgbColors); // Validate before changing existing review.
  ref.shades = shades.map(s => ({
    ...s,
    selected: true,
    event_id: crypto.randomUUID(),
    saved: false
  }));
  ref.palette.replaceChildren();
  clearResults();
  ref.shades.forEach((s, i) => {
    const label = document.createElement('label');
    label.className = 'palette-option';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = true;
    input.onchange = () => {
      s.selected = input.checked;
      updateButtons();
      clearResults();
    };
    const swatch = document.createElement('span');
    swatch.className = 'mini-swatch';
    swatch.style.background = s.hex;
    const text = document.createElement('span');
    text.textContent =
      `Shade ${i+1} · ${s.hex.toUpperCase()} · lightness ${Math.round(s.color[0]*100)}/100`;
    label.append(input, swatch, text);
    ref.palette.append(label);
  });
  status(ref.shades.length ? (ref.kind === 'skin' ? 'Keep the samples that represent your skin. Save to replace your previous skin samples.' : 'Review the checked shades. Nothing is saved until you continue.') :
    'No opaque shades found. Adjust the crop or remove this image.');
  updateButtons();
}
// Build one reference card: image, crop controls, shade checkboxes.
function renderReference(ref, kind) {
  ref.kind = kind;
  const category = kind === 'skin' ? 'skin_tone' : $('category').value;
  const card = document.createElement('article');
  card.className = 'reference';
  ref.card = card;
  const heading = document.createElement('h3');
  heading.textContent = ref.name;
  const canvas = document.createElement('canvas');
  ref.canvas = canvas;
  canvas.width = ref.source.width;
  canvas.height = ref.source.height;
  canvas.setAttribute('aria-label', ref.name + ' makeup region selection');
  canvas.className = 'reference-photo';
  const controls = document.createElement('div');
  controls.className = 'sliders';
  ref.inputs = {};
  ref.outputs = {};
  const sync = () => {
    ref.box.width = Math.min(ref.box.width, 100 - ref.box.left);
    ref.box.height = Math.min(ref.box.height, 100 - ref.box.top);
    for (const key of Object.keys(ref.box)) {
      ref.inputs[key].value = ref.box[key];
      ref.outputs[key].textContent = Math.round(ref.box[key]) + '%';
    }
    preview(ref);
  };
  for (const key of ['left', 'top', 'width', 'height']) {
    const label = document.createElement('label');
    label.textContent = key[0].toUpperCase() + key.slice(1) + ' ';
    const input = document.createElement('input');
    input.type = 'range';
    input.min = ['left', 'top'].includes(key) ? 0 : 1;
    input.max = ['left', 'top'].includes(key) ? 99 : 100;
    input.value = ref.box[key];
    input.setAttribute('aria-label', `${ref.name} crop ${key}`);
    const output = document.createElement('output');
    ref.inputs[key] = input;
    ref.outputs[key] = output;
    input.oninput = () => {
      ref.box[key] = Number(input.value);
      clearExtraction(ref);
      sync();
    };
    label.append(input, output);
    controls.append(label);
  }
  let start = null;
  const point = e => {
    const r = canvas.getBoundingClientRect();
    return [Math.max(0, Math.min(99, (e.clientX - r.left) / r.width * 100)), Math.max(0, Math.min(
      99, (e.clientY - r.top) / r.height * 100))];
  };
  canvas.onpointerdown = e => {
    if (saving || ref.frozen) return;
    start = point(e);
    canvas.setPointerCapture(e.pointerId);
    clearExtraction(ref);
  };
  canvas.onpointermove = e => {
    if (!start) return;
    const end = point(e);
    ref.box = {
      left: Math.min(start[0], end[0]),
      top: Math.min(start[1], end[1]),
      width: Math.max(1, Math.abs(start[0] - end[0])),
      height: Math.max(1, Math.abs(start[1] - end[1]))
    };
    sync();
  };
  canvas.onpointerup = canvas.onpointercancel = () => {
    start = null;
  };
  const extractButton = document.createElement('button');
  extractButton.textContent = kind === 'skin' ? 'Extract skin samples' : 'Extract makeup shades';
  extractButton.setAttribute('aria-label', extractButton.textContent + ' from ' + ref.name);
  extractButton.onclick = () => extract(ref);
  const detectButton = document.createElement('button');
  detectButton.textContent = 'Auto-detect ' + (kind === 'skin' ? 'skin' : category) + ' shades';
  detectButton.disabled = !['lip', 'blush', 'skin_tone'].includes(category);
  if (detectButton.disabled) detectButton.dataset.saved = 'true';
  detectButton.setAttribute('aria-label', detectButton.textContent + ' for ' + ref.name);
  detectButton.onclick = () => detectReferenceShades(ref, kind, detectButton);
  const remove = document.createElement('button');
  remove.textContent = 'Remove reference';
  remove.className = 'secondary';
  remove.onclick = () => {
    sets[kind] = sets[kind].filter(r => r !== ref);
    card.remove();
    updateButtons();
  };
  ref.palette = document.createElement('div');
  ref.palette.className = 'palette';
  const hint = document.createElement('p');
  hint.className = 'hint';
  hint.textContent = kind === 'skin' ?
    'Drag over bare skin or adjust the crop sliders, then extract samples.' :
    'Drag over the selected makeup or adjust the crop sliders, then extract shades.';
  const privacy = document.createElement('p');
  privacy.className = 'hint';
  privacy.textContent =
    'Auto-detection sends this resized photo to the app server for processing. Photos are not saved. ' +
    (category === 'blush' ? 'Cheek shades include skin and makeup; review the results.' :
      (kind === 'skin' ? 'Review the detected skin samples before saving.' : 'Review the detected lip shades before continuing.'));
  card.append(heading, canvas, hint, controls, detectButton, privacy, extractButton, remove, ref
  .palette);
  $(kind + '-gallery').append(card);
  sync();
}
// Decode uploaded photos in the browser. No image is sent to Flask.
async function loadFiles(kind, files) {
  if (loading || saving) return;
  loading = true;
  const ticket = revision;
  updateButtons();
  const errors = [];
  try {
    for (const file of files) {
      if (sets[kind].length >= (kind === 'skin' ? 1 : 6)) {
        errors.push(kind === 'skin' ? 'Remove the current skin photo before adding another.' : 'Each set supports up to 6 images.');
        break;
      }
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 *
        1024 * 1024) {
        errors.push(file.name + ': choose JPEG, PNG or WebP up to 10 MB.');
        continue;
      }
      const url = URL.createObjectURL(file);
      try {
        const image = new Image();
        image.src = url;
        await image.decode();
        if (ticket !== revision) return;
        if (image.naturalWidth * image.naturalHeight > 40_000_000) throw Error(
          'Image exceeds 40 megapixels.');
        const scale = Math.min(1, 800 / Math.max(image.naturalWidth, image.naturalHeight)),
          source = document.createElement('canvas');
        source.width = Math.max(1, Math.round(image.naturalWidth * scale));
        source.height = Math.max(1, Math.round(image.naturalHeight * scale));
        source.getContext('2d').drawImage(image, 0, 0, source.width, source.height);
        const ref = {
          name: file.name,
          source,
          box: {
            left: 25,
            top: 25,
            width: 50,
            height: 50
          },
          shades: [],
          frozen: false
        };
        sets[kind].push(ref);
        renderReference(ref, kind);
      } catch (error) {
        errors.push(file.name + ': ' + error.message);
      } finally {
        URL.revokeObjectURL(url);
      }
    }
    status(errors.length ? errors.join(' ') :
      'References added. Select the makeup region in each photo.');
  } finally {
    loading = false;
    $(kind + '-upload').value = '';
    updateButtons();
  }
}
for (const kind of ['personal', 'aesthetic', 'skin']) $(kind + '-upload').onchange = e => loadFiles(kind, [
  ...e.target.files
]);
// Save confirmed shades, retaining event IDs so retries do not duplicate likes.
function freeze(ref) {
  ref.frozen = true;
  ref.card.querySelectorAll('input,button').forEach(e => {
    e.disabled = true;
    e.dataset.saved = 'true';
  });
}
async function saveSet(kind) {
  const profile = user(),
    destination = kind === 'personal' ? 'personal' : 'environment:' + ($('environment').value
      .trim());
  if (kind === 'aesthetic' && !$('environment').value.trim()) throw Error(
    'Name your aesthetic inspiration first.');
  if (!selected(kind).length) throw Error('Keep at least one extracted shade checked.');
  // Stable IDs and frozen cards allow retries after partial network failures.
  sets[kind].forEach(freeze);
  locked(true);
  try {
    for (const shade of selected(kind))
      if (!shade.saved) {
        await api('/api/rating', {
          user_id: profile,
          preference_profile_id: destination,
          category: $('category').value,
          color: shade.color,
          rating: 1,
          event_id: shade.event_id
        });
        shade.saved = true;
      } if (kind === 'aesthetic') confirmedEnvironment = destination;
  } finally {
    locked(false);
  }
}
// Guided navigation: personal → aesthetic → CVD → balance
async function continuePersonalReferences() {
  try {
    await saveSet('personal');
    status('Your reference shades are saved.');
    stage('aesthetic');
  } catch (e) {
    status(e.message + ' Continue again to retry; saved shades will not be duplicated.');
  }
};
$('add-aesthetic').onchange = () => {
  $('aesthetic-inputs').hidden = $('add-aesthetic').value !== 'yes';
  updateButtons();
  clearResults();
};
$('environment').onchange = () => {
  if (sets.aesthetic.some(r => r.frozen)) {
    sets.aesthetic = [];
    $('aesthetic-gallery').replaceChildren();
    confirmedEnvironment = null;
    status(
      'New environment name. Add its own reference set. Previously saved ratings are retained.');
  }
  updateButtons();
};
$('aesthetic-back').onclick = () => stage('personal');
async function continueAestheticReferences() {
  try {
    if ($('add-aesthetic').value === 'yes') {
      await saveSet('aesthetic');
      $('weight').value = 60;
      $('weight').disabled = false;
    } else {
      $('weight').value = 100;
      $('weight').disabled = true;
    }
    $('balance-description').textContent = hasAesthetic() ?
      `Choose how much your taste and ${$('environment').value.trim()} (your estimate) should influence the result.` :
      'No second reference set selected. Recommendations use 100% your own taste.';
    weightLabel();
    stage('cvd');
    status('Enter the type and severity stated in your diagnosis.');
  } catch (e) {
    status(e.message + ' Continue again to retry.');
  }
};

function hasAesthetic() {
  return $('add-aesthetic').value === 'yes' && confirmedEnvironment !== null && selected(
    'aesthetic').some(s => s.saved);
}

function weightLabel() {
  const self = hasAesthetic() ? Number($('weight').value) : 100;
  $('weight-output').textContent = `${self}% my taste · ${100-self}% aesthetic inspiration`;
  $('weight').setAttribute('aria-valuetext', $('weight-output').textContent);
  clearResults();
}
$('weight').oninput = weightLabel;
$('balance-back').onclick = () => stage('skin');
// Request catalog recommendations using the selected category and balance.
async function requestRecommendations() {
  const ticket = ++rankingRequest;
  try {
    $('recommend').disabled = true;
    status('Finding your closest catalog shades…');
    const data = await api('/api/recommend', {
      user_id: user(),
      category: $('category').value,
      use_skin_tone: useSkinTone,
      personal_weight: hasAesthetic() ? Number($('weight').value) / 100 : 1,
      ...(hasAesthetic() ? {
        environment_profile_id: confirmedEnvironment
      } : {})
    });
    if (ticket !== rankingRequest) return;
    renderRecommendations(data);
    status('Suggestions ready. Change the slider and suggest again to compare balances.');
  } catch (e) {
    status(e.message);
  } finally {
    $('recommend').disabled = false;
  }
};
// Start a fresh reference session when the user or makeup category changes.
function resetReferences() {
  resetSkinTone();
  revision++;
  confirmedEnvironment = null;
  for (const kind of ['personal', 'aesthetic', 'skin']) {
    sets[kind] = [];
    $(kind + '-gallery').replaceChildren();
    $(kind + '-upload').value = '';
  }
  $('add-aesthetic').value = 'no';
  $('aesthetic-inputs').hidden = true;
  stage('personal');
  updateButtons();
  status('Profile changed. Add references for this user.');
};

$('user').onchange = resetReferences;
$('category').onchange = resetReferences;
fetch('/api/catalogs').then(async response => {
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Could not load catalogs.');
  $('category').replaceChildren();
  for (const catalog of data.catalogs) {
    const option = document.createElement('option');
    option.value = catalog.category;
    option.textContent = `${catalog.category} (${catalog.count} products)`;
    option.disabled = !catalog.count;
    $('category').append(option);
  }
  const active = data.catalogs.find(c => c.count > 0);
  if (!active) throw Error('Add products to the catalogs folder first.');
  $('category').value = active.category;
}).catch(error => {
  status(error.message);
  $('personal-upload').disabled = true;
});

// Build product cards and their preference explanations.
function renderRecommendations(data) {
  const note = document.createElement('p');
  note.textContent =
    `${Math.round(data.personal_weight*100)}% my taste · ${Math.round(data.environment_weight*100)}% aesthetic inspiration. Scores express similarity-based preferences, not probabilities.`;
  const grid = document.createElement('div');
  grid.className = 'cards';
  if (data.skin_tone_count) note.textContent += ' Blush scores include your skin-tone color-coherence factor.';
  if (data.cvd) note.textContent += ' ' + data.cvd.message;
  $('results').replaceChildren(note, grid);
  if (!data.results.some(r => r.score !== null && r.score > 0)) {
    const message = document.createElement('p');
    message.textContent =
      'No confident positive product match yet. These catalog products may need more reference evidence.';
    $('results').insertBefore(message, grid);
  }
  for (const [i, item] of data.results.slice(0, 12).entries()) {
    const card = document.createElement('article');
    card.className = 'card';
    const swatch = document.createElement('div');
    swatch.className = 'swatch';
    swatch.style.background = `oklab(${item.color[0]} ${item.color[1]} ${item.color[2]})`;
    const title = document.createElement('h3');
    title.textContent = `${i+1}. ${item.name}`;
    const summary = document.createElement('p');
    summary.textContent = item.score === null ? 'Not enough nearby evidence' :
      `Preference score: ${item.score.toFixed(2)}${hasAesthetic()&&item.shared_match?' · Positive evidence in both profiles':''}`;
    const detail = document.createElement('details'),
      label = document.createElement('summary'),
      reason = document.createElement('p');
    label.textContent = 'Why this shade';
    reason.textContent =
      `My taste: ${item.personal.reason.join(' ')}${hasAesthetic()?' Aesthetic estimate: '+item.environment.reason.join(' '):''}`;
    if (item.skin_factor !== null && item.skin_factor !== undefined) {
      reason.textContent += ` Skin-tone coherence: ${item.skin_factor.toFixed(2)}; preference score before adjustment: ${item.preference_score === null ? 'unknown' : item.preference_score.toFixed(2)}.`;
    }
    detail.append(label, reason);
    card.append(swatch, title, summary, detail);
    grid.append(card);
  }
}

// Page actions. The separate cvd-form.js owns the color-vision step.
$('personal-next').onclick = continuePersonalReferences;
$('aesthetic-next').onclick = continueAestheticReferences;
$('recommend').onclick = requestRecommendations;
