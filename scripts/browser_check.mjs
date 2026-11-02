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

const failures = [];

async function metrics(cdp) {
  const { metrics: list } = await cdp.send('Performance.getMetrics');
  return Object.fromEntries(list.map(m => [m.name, m.value]));
}

async function checkPage(page, cdp, path) {
  const firstParty = new Map();
  const problems = [];
  let navigations = 0;

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
  const onError = error => problems.push(`exception: ${error.message.slice(0, 160)}`);
  const onNavigate = frame => {
    if (frame === page.mainFrame()) navigations += 1;
  };

  page.on('request', onRequest);
  page.on('response', onResponse);
  page.on('requestfailed', onFailed);
  page.on('console', onConsole);
  page.on('pageerror', onError);
  page.on('framenavigated', onNavigate);

  await page.goto(BASE_URL + path, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(1500);
  const before = await metrics(cdp);
  await page.waitForTimeout(3000);
  const after = await metrics(cdp);
  const idle = Math.round(((after.TaskDuration - before.TaskDuration) / 3) * 1000);

  page.off('request', onRequest);
  page.off('response', onResponse);
  page.off('requestfailed', onFailed);
  page.off('console', onConsole);
  page.off('pageerror', onError);
  page.off('framenavigated', onNavigate);

  if (navigations !== 1) problems.push(`loaded ${navigations} times`);
  for (const [call, count] of firstParty) {
    if (count > 1) problems.push(`called ${count} times: ${call}`);
  }
  if (idle > IDLE_BUDGET_MS_PER_S) {
    problems.push(`idle main thread ${idle} ms/s (budget ${IDLE_BUDGET_MS_PER_S})`);
  }

  console.log(`${problems.length ? 'FAIL' : 'ok  '} ${path}  idle ${idle} ms/s`);
  for (const problem of problems) {
    console.log(`     ${problem}`);
    failures.push(`${path}: ${problem}`);
  }
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
  console.log(`${calls.length ? 'FAIL' : 'ok  '} favorites list reused between pages`);
  if (calls.length) failures.push(`favorites list fetched ${calls.length} more times`);
}

await browser.close();
if (failures.length) {
  console.error(`\n${failures.length} problem(s) found.`);
  process.exit(1);
}
console.log('\nAll pages clean.');
