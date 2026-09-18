// Diagnosis entry; the server supplies an ordinal severity_level (1, 2, 3).
let cvdRequest = 0;
async function loadCvdProfile() {
  const ticket = ++cvdRequest;
  const profileUser = $('user').value.trim();
  $('cvd-type').value = $('cvd-severity').value = '';
  $('cvd-status').textContent = '';
  $('cvd-type').disabled = $('cvd-severity').disabled = $('cvd-save').disabled = false;
  if (!profileUser) return;
  $('cvd-type').disabled = $('cvd-severity').disabled = $('cvd-save').disabled = true;
  try {
    const response = await fetch('/api/cvd-profile?user_id=' + encodeURIComponent(profileUser));
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'Could not load color vision profile.');
    if (ticket !== cvdRequest) return;
    if (data.profile) {
      $('cvd-type').value = data.profile.type;
      $('cvd-severity').value = data.profile.severity;
      $('cvd-status').textContent = 'Saved diagnosis details loaded. You can update them here.';
    }
  } catch (error) {
    if (ticket === cvdRequest) $('cvd-status').textContent = error.message;
  } finally {
    if (ticket === cvdRequest) $('cvd-type').disabled = $('cvd-severity').disabled = $('cvd-save').disabled = false;
  }
}
$('user').addEventListener('input', loadCvdProfile);
$('cvd-form').onsubmit = async event => {
  event.preventDefault();
  const ticket = ++cvdRequest;
  $('cvd-save').disabled = $('cvd-back').disabled = true;
  const stageRevision = revision;
  try {
    await api('/api/cvd-profile', {user_id: user(), type: $('cvd-type').value, severity: $('cvd-severity').value});
    if (ticket === cvdRequest) {
      $('cvd-status').textContent = 'Color vision profile saved. New suggestions will use the available simulation for your personal matches.';
      if (stageRevision === revision) {
        stage('balance');
        status('Choose your balance, then reveal your suggested products.');
      }
    }
  } catch (error) {
    if (ticket === cvdRequest) $('cvd-status').textContent = error.message;
  } finally {
    $('cvd-back').disabled = false;
    if (ticket === cvdRequest) $('cvd-save').disabled = false;
  }
};
$('cvd-back').onclick = () => stage('aesthetic');
loadCvdProfile();
