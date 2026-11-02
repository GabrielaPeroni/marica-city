// Opens the site in a real browser and checks what Django tests can't see: which calls
// each page makes, failures, console errors, reload loops and idle main-thread work.
//
//   BASE_URL=http://localhost:8000 node scripts/browser_check.mjs
//   CHECK_USER=x CHECK_PASSWORD=y also covers the pages behind login (staff account).

import { chromium } from 'playwright';

const BASE_URL = (process.env.BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const { CHECK_USER, CHECK_PASSWORD } = process.env;

const IDLE_BUDGET_MS_PER_S = 500;
const ASSET = /\/(static|media)\/|\.(png|webp|jpe?g|svg|woff2?|css|ico)(\?|$)/;
// Google's own probes and sign-in frame: origin rules and ad blockers fail these outside prod
const IGNORED_FAILURES = /accounts\.google\.com|gstatic\.com|mapsjs\/gen_204/;
// A wrong-password 401 is expected; the rest are Google's sign-in frame outside prod
const IGNORED_CONSOLE = /origin is not allowed|status of 401/;

const IS_LOCAL = /^https?:\/\/(localhost|127\.0\.0\.1)(:|$)/.test(BASE_URL);
const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64'
);

const failures = [];

async function metrics(cdp) {
  const { metrics: list } = await cdp.send('Performance.getMetrics');
  return Object.fromEntries(list.map(m => [m.name, m.value]));
}

function report(name, problems) {
  console.log(`${problems.length ? 'FAIL' : 'ok  '} ${name}`);
  for (const problem of problems) {
    console.log(`     ${problem}`);
    failures.push(`${name}: ${problem}`);
  }
}

function watch(page) {
  const firstParty = new Map();
  const problems = [];
  const state = { firstParty, problems, navigations: 0 };

  const onRequest = request => {
    const url = request.url();
    if (url.startsWith(BASE_URL) && !ASSET.test(url)) {
      const key = `${request.method()} ${url.slice(BASE_URL.length)}`;
      firstParty.set(key, (firstParty.get(key) || 0) + 1);
    }
  };
  const onResponse = response => {
    if (response.status() >= 400 && !IGNORED_FAILURES.test(response.url())) {
      problems.push(`${response.status()} ${response.url()}`);
    }
  };
  const onFailed = request => {
    const reason = request.failure()?.errorText || '';
    if (reason !== 'net::ERR_ABORTED' && !IGNORED_FAILURES.test(request.url())) {
      problems.push(`failed (${reason}) ${request.url()}`);
    }
  };
  const onConsole = message => {
    const fromGoogle = IGNORED_FAILURES.test(message.location().url || '');
    if (
      message.type() === 'error' &&
      !fromGoogle &&
      !IGNORED_CONSOLE.test(message.text())
    ) {
      problems.push(`console: ${message.text().slice(0, 160)}`);
    }
  };
  // The browser giving up on a page-change animation: the page itself is unaffected
  const onError = error => {
    if (!/Transition was aborted/.test(error.message)) {
      problems.push(`exception: ${error.message.slice(0, 160)}`);
    }
  };
  const onNavigate = frame => {
    if (frame === page.mainFrame()) state.navigations += 1;
  };

  page.on('request', onRequest);
  page.on('response', onResponse);
  page.on('requestfailed', onFailed);
  page.on('console', onConsole);
  page.on('pageerror', onError);
  page.on('framenavigated', onNavigate);

  state.stop = () => {
    page.off('request', onRequest);
    page.off('response', onResponse);
    page.off('requestfailed', onFailed);
    page.off('console', onConsole);
    page.off('pageerror', onError);
    page.off('framenavigated', onNavigate);
  };
  return state;
}

async function checkPage(page, cdp, path) {
  const seen = watch(page);
  await page.goto(BASE_URL + path, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(1500);
  const before = await metrics(cdp);
  await page.waitForTimeout(3000);
  const after = await metrics(cdp);
  const idle = Math.round(((after.TaskDuration - before.TaskDuration) / 3) * 1000);
  seen.stop();

  const { firstParty, problems, navigations } = seen;
  if (navigations !== 1) problems.push(`loaded ${navigations} times`);
  for (const [call, count] of firstParty) {
    if (count > 1) problems.push(`called ${count} times: ${call}`);
  }
  if (idle > IDLE_BUDGET_MS_PER_S) {
    problems.push(`idle main thread ${idle} ms/s (budget ${IDLE_BUDGET_MS_PER_S})`);
  }
  report(`${path}  idle ${idle} ms/s`, problems);
}

async function addPhoto(page) {
  const [chooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    page.locator('#add-image-btn').click(),
  ]);
  await chooser.setFiles({ name: 'foto.png', mimeType: 'image/png', buffer: TINY_PNG });
  await page.locator('[data-image-card]').waitFor();
}

// Submits a place the way a person does, then deletes it. Creates data, so local only.
async function checkPlaceSubmit(page) {
  const create = '/explore/place/create/';
  const seen = watch(page);
  const { problems, firstParty } = seen;

  await page.goto(BASE_URL + create, { waitUntil: 'load' });
  await page.locator('#id_name').fill('Lugar do teste de navegador');
  await page.locator('#id_description').fill('Criado e removido pela verificação.');
  const search = page.locator('#id_address_search');
  const hasSearch = (await search.count()) > 0;
  await (hasSearch ? search : page.locator('#id_address')).fill('Rua do Teste, 1');
  await addPhoto(page);

  // No category yet: the server refuses and shows the error on the same page
  await Promise.all([
    page.waitForNavigation(),
    page.locator('#place-form [type=submit]').click(),
  ]);
  if (!(await page.locator('fieldset [role=alert]').count())) {
    problems.push('no error shown for a missing category');
  }
  if ((await page.locator('#id_name').inputValue()) === '') {
    problems.push('typed text lost after a refused submit');
  }
  if (await page.locator('[data-image-card]').count()) {
    problems.push('preview shown for a photo the server did not keep');
  }
  if (!(await page.locator('[data-photos-lost]').count())) {
    problems.push('nothing asks to choose the photos again');
  }
  if (hasSearch && (await search.inputValue()) !== 'Rua do Teste, 1') {
    problems.push('address lost after a refused submit');
  }

  // A double click must still send one request
  await page.locator('input[name="categories"]').first().check();
  await addPhoto(page);
  await Promise.all([
    page.waitForURL(/\/explore\/place\/\d+\/$/),
    page.locator('#place-form [type=submit]').dblclick(),
  ]);
  const posts = firstParty.get(`POST ${create}`) || 0;
  if (posts !== 2) problems.push(`expected 2 submits, sent ${posts}`);

  const detail = new URL(page.url()).pathname;
  await page.goto(`${BASE_URL}${detail}edit/`, { waitUntil: 'load' });
  const photos = await page.locator('[data-image-card]').count();
  if (photos !== 1)
    problems.push(`expected the saved photo in the form, found ${photos}`);

  await page.locator('[data-dialog-open="deleteModal"]').click();
  await Promise.all([
    page.waitForNavigation(),
    page.locator('#deleteModal form [type=submit]').click(),
  ]);
  seen.stop();

  // Pages repeat GETs between them, so only repeated writes count here
  firstParty.delete(`POST ${create}`);
  for (const [call, count] of firstParty) {
    if (count > 1 && !call.startsWith('GET ')) {
      problems.push(`sent ${count} times: ${call}`);
    }
  }
  report('submit, fix, save and delete a place', problems);
}

// Stands in for Google so the check never spends the key or depends on Google being up
const FAKE_MAPS = `
  window.google = { maps: { places: { Autocomplete: class {
    addListener(_, handler) {
      window.pickPlace = place => { this.place = place; handler(); };
    }
    getPlace() { return this.place; }
  } } } };
  window.initAutocomplete();
`;

async function checkAddressField(page) {
  const create = '/explore/place/create/';
  await page.goto(BASE_URL + create, { waitUntil: 'load' });
  const search = page.locator('#id_address_search');
  if (!(await search.count())) {
    console.log('skip address autocomplete (no GOOGLE_MAPS_API_KEY on this server)');
    return;
  }
  const seen = watch(page);
  const { problems, firstParty } = seen;
  const acceptLeaving = dialog => dialog.accept();
  page.on('dialog', acceptLeaving);
  const textarea = page.locator('#id_address');
  const focused = () => page.evaluate(() => document.activeElement.id);

  // Empty address: the browser must point at the visible field, not block in silence
  await page.locator('#id_name').fill('Teste de endereço');
  await page.locator('#id_description').fill('Descrição');
  await page.locator('#place-form [type=submit]').click();
  await page.waitForTimeout(300);
  if ((await focused()) !== 'id_address_search') {
    problems.push('submitting with no address gives no feedback');
  }

  await search.fill('Rua A');
  if ((await textarea.inputValue()) !== 'Rua A') problems.push('typing is not saved');
  await search.press('Enter');
  await page.waitForTimeout(300);
  if (firstParty.get(`POST ${create}`)) problems.push('Enter in the address submitted');

  await page.evaluate(() =>
    window.pickPlace({
      formatted_address: 'Rua B, Maricá',
      geometry: { location: { lat: () => -22.9, lng: () => -42.8 } },
    })
  );
  const picked = await page.evaluate(() => [
    document.getElementById('id_address').value,
    document.getElementById('id_latitude').value,
    document.getElementById('id_longitude').value,
  ]);
  if (picked.join() !== 'Rua B, Maricá,-22.900000,-42.800000') {
    problems.push(`picking an address filled ${picked.join(' | ')}`);
  }

  // Google refuses the key (billing, restrictions): the plain field must come back
  await page.evaluate(() => window.gm_authFailure?.());
  if (await search.count()) problems.push('broken autocomplete stays on screen');
  if (!(await textarea.isVisible())) problems.push('address field stays hidden');
  if ((await textarea.inputValue()) !== 'Rua B, Maricá') {
    problems.push('address text lost when autocomplete fails');
  }

  await page.goto(`${BASE_URL}/sobre/`, { waitUntil: 'load' });
  page.off('dialog', acceptLeaving);
  seen.stop();
  report('address autocomplete', problems);
}

async function discover(page, listPath, selector) {
  await page.goto(BASE_URL + listPath, { waitUntil: 'load', timeout: 60000 });
  return page
    .locator(selector)
    .first()
    .getAttribute('href', { timeout: 3000 })
    .catch(() => null);
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
if (IS_LOCAL) {
  await context.route(/maps\.googleapis\.com/, route =>
    route.fulfill({ contentType: 'text/javascript', body: FAKE_MAPS })
  );
}
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send('Performance.enable');

const place = await discover(page, '/explore/', 'a[href*="/explore/place/"]');
const event = await discover(
  page,
  '/eventos/',
  'a[href^="/eventos/"]:not([href="/eventos/"])'
);
const publicPages = [
  '/',
  '/explore/',
  place,
  '/eventos/',
  event,
  '/sobre/',
  '/accounts/register/',
];
for (const path of publicPages.filter(Boolean)) await checkPage(page, cdp, path);

if (CHECK_USER && CHECK_PASSWORD) {
  const status = await page.evaluate(
    async ({ username, password }) => {
      const token = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const response = await fetch('/accounts/login/', {
        method: 'POST',
        body: new URLSearchParams({ username, password }),
        headers: { 'X-CSRFToken': token, 'X-Requested-With': 'XMLHttpRequest' },
      });
      return response.status;
    },
    { username: CHECK_USER, password: CHECK_PASSWORD }
  );
  if (status !== 200) failures.push(`login answered ${status}`);
  const privatePages = [
    '/',
    place,
    '/explore/favorites/',
    '/explore/place/create/',
    '/painel-admin/',
    '/explore/admin/backlog/',
    '/accounts/usuarios/',
  ];
  for (const path of privatePages.filter(Boolean)) await checkPage(page, cdp, path);

  // The favorites list is fetched once and then reused between pages
  const calls = [];
  const count = request => {
    if (request.url().includes('/explore/favorites/list/')) calls.push(request.url());
  };
  page.on('request', count);
  await page.goto(`${BASE_URL}/explore/`, { waitUntil: 'load' });
  await page.goto(`${BASE_URL}/sobre/`, { waitUntil: 'load' });
  await page.waitForTimeout(500);
  page.off('request', count);
  report(
    'favorites list reused between pages',
    calls.length ? [`fetched ${calls.length} more times`] : []
  );

  if (IS_LOCAL) {
    await checkAddressField(page);
    await checkPlaceSubmit(page);
  }
}

await browser.close();
if (failures.length) {
  console.error(`\n${failures.length} problem(s) found.`);
  process.exit(1);
}
console.log('\nAll pages clean.');
