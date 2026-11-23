// Functional checks on the demo copy: settings save (incl. the API-key fallback switch) and a channel voice change.
//   node tools/demo/flow-check.cjs      (needs the demo copy + login, see README)
const { chromium } = require('playwright');
const path = require('path');
const B = 'http://localhost:3000';

const results = [];
const check = (name, ok, extra = '') => results.push(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ' — ' + extra : ''}`);

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ storageState: path.join(__dirname, '.state.json'), viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(e.message));

  // 1) settings: fallback switch + cap persist after reload
  await p.goto(B + '/settings', { waitUntil: 'networkidle' });
  const sw = p.getByRole('switch', { name: 'Continue on the API key' });
  if ((await sw.getAttribute('aria-checked')) !== 'true') await sw.click();
  await p.locator('#fbcap').fill('3.5');
  await p.getByRole('button', { name: 'Save settings' }).click();
  await p.getByText('Settings saved.').first().waitFor({ timeout: 10000 }).then(() => check('settings save toast', true))
    .catch(() => check('settings save toast', false));
  await p.reload({ waitUntil: 'networkidle' });
  check('fallback switch persisted', (await sw.getAttribute('aria-checked')) === 'true');
  check('fallback cap persisted', (await p.locator('#fbcap').inputValue()) === '3.5');
  // switch back off (leave the demo as it was)
  await sw.click();
  await p.getByRole('button', { name: 'Save settings' }).click();
  await p.waitForTimeout(1500);

  // 2) channel voice: change, save, reload, sample player follows the choice
  await p.goto(B + '/channels/overthought/settings', { waitUntil: 'networkidle' });
  const sel = p.locator('select#voice');
  const before = await sel.inputValue();
  const target = before === 'bm_george' ? 'af_heart' : 'bm_george';
  await sel.selectOption(target);
  const src = await p.locator('audio').getAttribute('src');
  check('voice sample follows the picker', src === `/voices/${target}.mp3`, src);
  const sample = await p.request.get(B + src);
  check('voice sample file is served', sample.ok() && (sample.headers()['content-type'] || '').includes('audio'), String(sample.status()));
  await p.getByRole('button', { name: 'Save changes' }).click();
  await p.waitForTimeout(2000);
  await p.reload({ waitUntil: 'networkidle' });
  check('channel voice persisted', (await sel.inputValue()) === target);
  await sel.selectOption(before);
  await p.getByRole('button', { name: 'Save changes' }).click();
  await p.waitForTimeout(1500);

  // 3) wizard: later steps cannot be clicked before the first is filled
  await p.goto(B + '/channels/new', { waitUntil: 'networkidle' });
  check('wizard future steps disabled', await p.getByRole('button', { name: /Schedule & posting/ }).isDisabled());

  check('no page errors', errors.length === 0, errors.slice(0, 2).join(' | '));
  await b.close();
  console.log(results.join('\n'));
  process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
