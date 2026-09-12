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
    FormData: class { append() {} },
    document: {getElementById: element, createElement: () => new Element(), querySelectorAll: () => []},
    fetch: async (url, options) => {
      if (url === '/api/detect-shades') {
        return new Promise(resolve => { finishDetection = shades => resolve({
          ok: true, json: async () => ({shades})
        }); });
      }
      const body = options ? JSON.parse(options.body) : null;
      requests.push({url, body});
      const data = url === '/api/catalogs' ? {catalogs: [{category: 'blush', count: 26}]} :
        url === '/api/recommend' ? {personal_weight: 1, environment_weight: 0, results: [{
          name: 'Test product', color: [.6, .1, .04], score: .7,
          personal: {reason: ['Near a liked shade']}, environment: {reason: []}
        }]} : {saved: true};
      return {ok: true, json: async () => data};
    },
  });
  vm.runInContext(fs.readFileSync('onboarding/colors.js', 'utf8'), context);
  vm.runInContext(fs.readFileSync('onboarding/app.js', 'utf8'), context);
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
  element('balance-back').onclick();
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
  console.log('Frontend initialization, navigation, save retries, and recommendation rendering passed.');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
