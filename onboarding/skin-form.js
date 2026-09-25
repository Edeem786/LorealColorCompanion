// Skin samples are measurements in the skin_tone category, not makeup likes.
let skinSavedCount = 0;
let useSkinTone = true;
let skinRequest = 0;

function resetSkinTone() {
  skinRequest++;
  skinSavedCount = 0;
  useSkinTone = true;
  $('skin-saved').replaceChildren();
  $('skin-status').textContent = '';
  $('skin-clear').hidden = true;
}

function displaySavedSkin(colors) {
  skinSavedCount = colors.length;
  $('skin-saved').replaceChildren();
  for (const color of colors) {
    const swatch = document.createElement('span');
    swatch.className = 'mini-swatch';
    swatch.style.background = `oklab(${color[0]} ${color[1]} ${color[2]})`;
    swatch.setAttribute('aria-label', 'Saved skin sample');
    $('skin-saved').append(swatch);
  }
  $('skin-clear').hidden = !colors.length;
  $('skin-status').textContent = colors.length ?
    `${colors.length} saved skin sample(s). Continue to reuse them, or save new samples to replace them.` :
    'No skin samples saved. Add a photo or continue without skin tone.';
  updateButtons();
}

async function loadSkinProfile() {
  const ticket = ++skinRequest;
  const profile = user();
  try {
    const response = await fetch('/api/skin-tone?user_id=' + encodeURIComponent(profile));
    const data = await response.json();
    if (ticket !== skinRequest || profile !== $('user').value.trim()) return;
    if (!response.ok) throw Error(data.error || 'Could not load skin samples.');
    displaySavedSkin(data.colors);
  } catch (error) {
    if (ticket === skinRequest) $('skin-status').textContent = error.message;
  }
}

$('skin-next').onclick = async () => {
  if (saving || loading || sets.skin.some(ref => ref.detecting)) return;
  const colors = selected('skin').map(shade => shade.color);
  if (!colors.length && !skinSavedCount) return;
  skinRequest++;
  locked(true);
  try {
    if (colors.length) {
      const result = await api('/api/skin-tone', {user_id: user(), colors});
      displaySavedSkin(result.colors);
    }
    useSkinTone = true;
    stage('balance');
    status('Skin samples ready. They affect blush suggestions only.');
  } catch (error) {
    $('skin-status').textContent = error.message;
  } finally {
    locked(false);
  }
};
$('skin-back').onclick = () => stage('cvd');
$('skin-skip').onclick = () => {
  skinRequest++;
  useSkinTone = false;
  stage('balance');
  status('Skin tone will not affect these suggestions. Saved samples are kept.');
};
$('skin-clear').onclick = async () => {
  skinRequest++;
  locked(true);
  try {
    const result = await api('/api/skin-tone', {user_id: user(), colors: []});
    displaySavedSkin(result.colors);
    useSkinTone = false;
    clearResults();
  } catch (error) {
    $('skin-status').textContent = error.message;
  } finally {
    locked(false);
  }
};
