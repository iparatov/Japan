// Поведенческие тесты приложения. Запуск: node tests/e2e.mjs <путь к index.html>
import pw from '/home/claude/.npm-global/lib/node_modules/playwright/index.js';
import assert from 'node:assert/strict';
import path from 'node:path';
const { chromium } = pw;
const FILE = 'file://' + path.resolve(process.argv[2] || 'dist/index.html');
const ONLY = process.env.ONLY;
const b = await chromium.launch();
let fail = 0;

async function open(iso, { ctx } = {}) {
  const c = ctx || await b.newContext({ viewport: { width: 390, height: 844 }, timezoneId: 'Asia/Tokyo' });
  const p = await c.newPage();
  await p.addInitScript(`(()=>{const T=new Date('${iso}').getTime();const s=Date.now();const R=Date;class D extends R{constructor(...a){a.length?super(...a):super(T+(R.now()-s))}static now(){return T+(R.now()-s)}};window.Date=D;})()`);
  await p.goto(FILE); await p.waitForTimeout(5000);
  await p.getByText('Скрыть подсказку', { exact: true }).first().click({ timeout: 1500 }).catch(() => {});
  return { p, c };
}
const text = p => p.evaluate(() => document.body.innerText);
const nowCard = p => p.evaluate(() => { const el = [...document.querySelectorAll('[data-id]')].find(e => /(сейчас|скоро) ·/.test(e.innerText)); return el ? el.innerText.split('\n').slice(0, 4).join(' | ') : null; });

async function t(name, fn) {
  if (ONLY && !name.includes(ONLY)) return;
  try { await fn(); console.log('ok   ', name); } catch (e) { fail++; console.log('FAIL ', name, '\n     ', e.message.split('\n')[0]); }
}

await t('ночью 01.11 03:00 текущим считается сон 31.10', async () => {
  const { p, c } = await open('2026-11-01T03:00:00+09:00');
  const card = await nowCard(p);
  assert.ok(card && /Сон/.test(card), 'нет подсвеченного сна, получили: ' + card);
  await c.close();
});

await t('в паузе 05.11 07:26 подсвечен следующий пункт', async () => {
  const { p, c } = await open('2026-11-05T07:26:00+09:00');
  const card = await nowCard(p);
  assert.ok(card && /Kiyomizu|Киёмидзу/i.test(card), 'получили: ' + card);
  await c.close();
});

await t('«Вся поездка» 04.11 без отметок = 0', async () => {
  const { p, c } = await open('2026-11-04T12:00:00+09:00');
  const m = (await text(p)).match(/Вся поездка: (\d+) из (\d+)/) || (await text(p)).match(/(\d+) из (\d+)[^\n]*поездк/);
  assert.ok(m, 'нет строки прогресса поездки');
  assert.equal(m[1], '0');
  await c.close();
});

await t('отметка «Сделано» сохраняется после перезагрузки', async () => {
  const { p, c } = await open('2026-10-31T11:20:00+09:00');
  const btn = p.locator('[aria-label^="Отметить «"]').first();
  const label = await btn.getAttribute('aria-label');
  await btn.click(); await p.waitForTimeout(400);
  await p.reload(); await p.waitForTimeout(5000);
  const after = await p.locator(`[aria-label="${label}"]`).count();
  assert.equal(after, 0, 'кнопка «Отметить» снова на месте — отметка потерялась');
  await c.close();
});

await t('31.10 ужин — MASUMI, запасные Kagari и Soranoiro', async () => {
  const { p, c } = await open('2026-10-31T11:20:00+09:00');
  const card = p.getByText(/MASUMI/).first();
  assert.ok(await card.count(), 'нет MASUMI в маршруте');
  const all = await text(p);
  assert.ok(!/Yakiuo/.test(all), 'Yakiuo ещё в маршруте');
  await p.getByText(/^Ужин — MASUMI|^Ужин в MASUMI/).first().click(); await p.waitForTimeout(700);
  const t2 = await text(p);
  assert.match(t2, /Ginza Kagari/);
  assert.match(t2, /Soranoiro/);
  await c.close();
});

await t('30.10 у Kuramu видно время пешком от ICHIRAN', async () => {
  const { p, c } = await open('2026-10-30T20:55:00+09:00');
  await p.getByText(/^Ужин в ICHIRAN/).first().click(); await p.waitForTimeout(700);
  assert.match(await text(p), /Kuramu Kabukicho\s*Бронь онлайн · 1\s*мин пешком/);
  await c.close();
});


const bookings = async p => { await p.getByText('Брони', { exact: false }).last().click(); await p.waitForTimeout(800); };

await t('брони 04.11: прошедшие свёрнуты внизу, сначала текущие', async () => {
  const { p, c } = await open('2026-11-04T12:00:00+09:00');
  await bookings(p);
  const tx = await text(p);
  assert.ok(/Прошедшие · \d+/.test(tx), 'нет строки «Прошедшие · N»');
  assert.ok(!tx.includes('Shibuya Sky'), 'прошедшая бронь Shibuya Sky видна без раскрытия');
  assert.ok(tx.indexOf('Kawaguchiko → Mishima') < tx.indexOf('Прошедшие'), 'текущие брони не выше прошедших');
  await p.getByText(/Прошедшие · \d+/).click(); await p.waitForTimeout(500);
  assert.ok((await text(p)).includes('Shibuya Sky'), 'после раскрытия прошедших Shibuya Sky не видна');
  await c.close();
});

await t('брони: «КУПЛЕНО» и «Куплено N из N» не показываются, когда всё куплено', async () => {
  const { p, c } = await open('2026-10-25T12:00:00+09:00');
  await bookings(p);
  const tx = await text(p);
  assert.ok(!/КУПЛЕНО/.test(tx), 'метка «КУПЛЕНО» на карточках');
  assert.ok(!/Куплено \d+ из \d+/.test(tx), 'строка «Куплено N из N»');
  await c.close();
});

await t('брони: перелёт туда — сегменты и багаж', async () => {
  const { p, c } = await open('2026-10-25T12:00:00+09:00');
  await bookings(p);
  const tx = await text(p);
  assert.ok(tx.includes('ЧТ, 29.10 → ПТ, 30.10'), 'нет подписи группы перелёта');
  assert.ok(/CZ342/.test(tx) && /CZ647/.test(tx) && /Багаж/.test(tx), 'нет сегментов или багажа');
  await c.close();
});


await t('брони: подписи кнопок не обрезаются', async () => {
  const { p, c } = await open('2026-10-25T12:00:00+09:00');
  await bookings(p);
  const cut = await p.evaluate(() => [...document.querySelectorAll('button')].filter(b => /Открыть|На карте/.test(b.innerText) && b.getBoundingClientRect().width > 0)
    .filter(b => b.scrollWidth > b.clientWidth + 1 || [...b.querySelectorAll('*')].some(x => { const r = x.getBoundingClientRect(), o = b.getBoundingClientRect(); return r.width && (r.left < o.left - 1 || r.right > o.right + 1); }))
    .map(b => b.innerText.trim()));
  assert.deepEqual(cut, [], 'обрезаны: ' + cut.join(', '));
  await c.close();
});


await t('брони: кнопка копирует отправителя письма', async () => {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, timezoneId: 'Asia/Tokyo', permissions: ['clipboard-read', 'clipboard-write'] });
  const { p, c } = await open('2026-10-25T12:00:00+09:00', { ctx });
  await bookings(p);
  await p.locator('[aria-label="Скопировать отправителя: Webket"]').click(); await p.waitForTimeout(300);
  assert.equal(await p.evaluate(() => navigator.clipboard.readText()), 'Webket');
  await c.close();
});

await t('офлайн: после первого открытия работает без сети', async () => {
  const http = await import('node:http'); const fs = await import('node:fs');
  const dir = path.dirname(path.resolve(process.argv[2] || 'dist/index.html'));
  const srv = http.createServer((q, r) => { const f = path.join(dir, decodeURIComponent(q.url.split('?')[0]) === '/' ? 'index.html' : decodeURIComponent(q.url.split('?')[0]));
    if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.statusCode = 404; return r.end(); }
    const ext = path.extname(f); r.setHeader('content-type', { '.html': 'text/html', '.js': 'text/javascript', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.svg': 'image/svg+xml' }[ext] || 'application/octet-stream'); r.end(fs.readFileSync(f)); }).listen(8799);
  const c = await b.newContext({ viewport: { width: 390, height: 844 }, timezoneId: 'Asia/Tokyo' });
  const p = await c.newPage(); await p.goto('http://localhost:8799/'); await p.waitForTimeout(5000);
  const sw = await p.evaluate(() => navigator.serviceWorker ? Promise.race([navigator.serviceWorker.ready.then(() => true), new Promise(r => setTimeout(() => r(false), 8000))]) : false);
  assert.ok(sw, 'service worker не активен');
  await c.setOffline(true); await p.reload(); await p.waitForTimeout(5000);
  assert.match(await text(p), /Маршрут/);
  srv.close(); await c.close();
});

await b.close();
console.log(fail ? `\n${fail} упало` : '\nвсё зелёное');
process.exit(fail ? 1 : 0);
