// Creates the demo owner on a fresh demo copy (via /setup) and saves a logged-in browser state.
//   node tools/demo/login.cjs   → tools/demo/.state.json
const { chromium } = require('playwright');
const path = require('path');
const B = 'http://localhost:3000';
const EMAIL = 'owner@demo.local', PASS = 'DemoPass!2026x';
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext();
  const p = await ctx.newPage();
  await p.goto(B + '/setup');
  if (await p.locator('input[name=token]').count()) {
    await p.fill('input[name=token]', 'demo-setup-token');
    await p.fill('input[type=email]', EMAIL);
    await p.fill('input[name=password]', PASS);
    await p.locator('button[type=submit]').click();
    await p.waitForTimeout(2500);
  }
  if (!(new URL(p.url())).pathname.match(/^\/$|^\/(channels|videos)/)) {
    await p.goto(B + '/login');
    await p.fill('input[type=email]', EMAIL);
    await p.fill('input[type=password]', PASS);
    await p.locator('button[type=submit]').click();
    await p.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 });
  }
  await ctx.storageState({ path: path.join(__dirname, '.state.json') });
  console.log('logged in:', p.url());
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
