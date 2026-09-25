// Lightweight frontend behavior checks; no browser or npm dependencies needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor() {
    this.children = [];
    this.value = '';
    this.dataset = {};
    this.hidden = false;
    this.style = {};
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  insertBefore(child, before) { this.children.splice(this.children.indexOf(before), 0, child); }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
  scrollIntoView() {}
  getContext() { return {drawImage() {}, strokeRect() {}}; }
  querySelectorAll() { return []; }
}

async function main() {
  const html = fs.readFileSync('onboarding/index.html', 'utf8');
  const elements = new Map([...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new Element()]));
  const element = id => {
    assert.ok(elements.has(id), `Missing HTML element: ${id}`);
    return elements.get(id);
  };
  element('user').value = 'frontend-test';
  element('add-aesthetic').value = 'no';
  const requests = [];
  let finishDetection;
  const context = vm.createContext({
    crypto: require('node:crypto').webcrypto,
    FormData: class { constructor() { this.fields = {}; } append(key, value) { this.fields[key] = value; } },
    document: {getElementById: element, createElement: () => new Element(), querySelectorAll: () => []},
    fetch: async (url, options) => {
      if (url === '/api/detect-shades') {
        requests.push({url, body: options.body.fields});
        return new Promise(resolve => { finishDetection = shades => resolve({
          ok: true, json: async () => ({shades})
        }); });
      }
      const body = options ? JSON.parse(options.body) : null;
      requests.push({url, body});
      const data = url.startsWith('/api/skin-tone') ? {colors: body?.colors || []} : url === '/api/catalogs' ? {catalogs: [{category: 'blush', count: 26}]} :
        url === '/api/recommend' ? {cvd: {applied: true, message: 'CVD simulation active'}, personal_weight: 1, environment_weight: 0, results: [{
          name: 'Test product', color: [.6, .1, .04], score: .7,
          personal: {reason: ['Near a liked shade']}, environment: {reason: []}
        }]} : {saved: true};
      return {ok: true, json: async () => data};
    },
  });
  vm.runInContext(fs.readFileSync('onboarding/colors.js', 'utf8'), context);
  vm.runInContext(fs.readFileSync('onboarding/app.js', 'utf8'), context);
  vm.runInContext(fs.readFileSync('onboarding/skin-form.js', 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(element('category').value, 'blush');
  for (const id of ['personal-next', 'aesthetic-next', 'recommend']) assert.equal(typeof element(id).onclick, 'function');

  // Seed a reviewed reference, then exercise the actual event handlers.
  vm.runInContext(`sets.personal.push({
    card: document.createElement('article'), frozen: false,
    shades: [{selected: true, saved: false, color: [.6, .1, .04], event_id: 'one'}]
  });`, context);
  await element('personal-next').onclick();
  assert.equal(element('aesthetic-stage').hidden, false);
  assert.equal(requests.filter(r => r.url === '/api/rating').length, 1);
  assert.equal(requests.find(r => r.url === '/api/rating').body.category, 'blush');
  await element('personal-next').onclick();
  assert.equal(requests.filter(r => r.url === '/api/rating').length, 1, 'Back/continue must not duplicate ratings');
  await element('aesthetic-next').onclick();
  assert.equal(element('cvd-stage').hidden, false);
  assert.equal(element('weight').value, 100);
  assert.equal(element('weight').disabled, true);
  vm.runInContext("stage('balance')", context);
  await element('recommend').onclick();
  const request = requests.find(r => r.url === '/api/recommend');
  assert.equal(request.body.personal_weight, 1);
  assert.equal(request.body.category, 'blush');
  assert.equal(element('results').children[1].children.length, 1);
  assert.equal(element('recommend').disabled, false);
  assert.ok(element('results').children[0].textContent.includes('CVD simulation active'));
  element('balance-back').onclick();
  assert.equal(element('skin-stage').hidden, false);
  await new Promise(resolve => setImmediate(resolve));
  element('skin-back').onclick();
  assert.equal(element('cvd-stage').hidden, false);
  element('category').onchange();
  assert.equal(element('personal-stage').hidden, false);
  assert.equal(vm.runInContext('sets.personal.length', context), 0);
  vm.runInContext(`
    const detectionRef = {
      name: 'photo', shades: [], frozen: false,
      source: {toBlob: callback => callback({})},
      palette: document.createElement('div')
    };
    sets.personal.push(detectionRef);
    const detectionButton = document.createElement('button');
  `, context);
  let pending = vm.runInContext("detectReferenceShades(detectionRef, 'personal', detectionButton)", context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(element('personal-next').disabled, true);
  finishDetection([[180, 80, 100]]);
  await pending;
  assert.equal(vm.runInContext('detectionRef.shades.length', context), 1);
  assert.equal(requests.filter(r => r.url === '/api/rating').length, 1, 'Detection must not save ratings');
  pending = vm.runInContext("detectReferenceShades(detectionRef, 'personal', detectionButton)", context);
  await new Promise(resolve => setImmediate(resolve));
  vm.runInContext('clearExtraction(detectionRef)', context);
  finishDetection([[1, 2, 3]]);
  await pending;
  assert.equal(vm.runInContext('detectionRef.shades.length', context), 0, 'Ignore results after crop changes');
  // Render real reference cards and click the actual category-specific button.
  for (const category of ['lip', 'blush']) {
    element('category').value = category;
    vm.runInContext(`
      detectionRef.box = {left: 25, top: 25, width: 50, height: 50};
      detectionRef.source.width = detectionRef.source.height = 100;
      renderReference(detectionRef, 'personal');
    `, context);
    const card = vm.runInContext('detectionRef.card', context);
    const buttons = card.children.filter(child => typeof child.onclick === 'function' && child.textContent?.startsWith('Auto-detect'));
    assert.equal(buttons.length, 1);
    assert.equal(buttons[0].textContent, `Auto-detect ${category} shades`);
    pending = buttons[0].onclick();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(requests.at(-1).body.category, category);
    finishDetection([[180, 80, 100]]);
    await pending;
    assert.equal(vm.runInContext('detectionRef.shades.length', context), 1);
    pending = buttons[0].onclick();
    await new Promise(resolve => setImmediate(resolve));
    finishDetection([]);
    await pending;
    assert.equal(vm.runInContext('detectionRef.shades.length', context), 1, 'Empty detection preserves review');
  }
  vm.runInContext("sets.skin.push({shades:[{selected:true,color:[.65,.07,.04]}]})", context);
  await element('skin-next').onclick();
  assert.equal(element('balance-stage').hidden, false);
  assert.equal(requests.filter(r => r.url === '/api/skin-tone').at(-1).body.colors.length, 1);
  assert.equal(requests.filter(r => r.url === '/api/rating').length, 1, 'Skin samples are not makeup likes');
  element('skin-skip').onclick();
  await element('recommend').onclick();
  assert.equal(requests.filter(r => r.url === '/api/recommend').at(-1).body.use_skin_tone, false);
  await element('skin-clear').onclick();
  assert.equal(vm.runInContext('skinSavedCount', context), 0);
  console.log('Frontend initialization, navigation, save retries, and recommendation rendering passed.');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
