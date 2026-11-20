// UI checks for the demo copy at 375 px (phone) and 1280 px (laptop). Each case: null = pass, string = what failed.
//   node tools/demo/ui-check.cjs [--only a,b] [--login-only] [--shots <dir>]
// Needs: bash tools/demo/up.sh, python tools/demo/seed_demo.py, node tools/demo/login.cjs
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const B = 'http://localhost:3000';
const STATE = path.join(__dirname, '.state.json');
const VP = { m: { width: 375, height: 812 }, d: { width: 1280, height: 800 } };
const args = process.argv.slice(2);
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const ONLY = (opt('--only') || '').split(',').filter(Boolean);
const SHOTS = opt('--shots');

const ROUTES = ['/', '/channels', '/channels/overthought', '/channels/overthought/videos', '/channels/overthought/ideas',
  '/channels/overthought/strategy', '/channels/overthought/settings', '/channels/new', '/channels/money-brain',
  '/videos', '/videos/@ready', '/analytics', '/reports', '/accounts', '/settings', '/logs'];

// ---------------------------------------------------------------- cases
const CASES = [
  {
    name: 'no-h-overflow', routes: ROUTES, viewports: ['m', 'd'],
    check: async (p) => p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1
      ? `page is ${document.documentElement.scrollWidth}px wide` : null),
  },
  {
    name: 'scrollers-show-fade', routes: ROUTES, viewports: ['m'],
    check: async (p) => p.evaluate(() => {
      const bad = [...document.querySelectorAll('main *')].filter((el) => {
        const s = getComputedStyle(el);
        return ['auto', 'scroll'].includes(s.overflowX) && el.scrollWidth > el.clientWidth + 2 &&
          el.clientHeight > 0 && !el.classList.contains('scroll-fade-x') && el.tagName !== 'TEXTAREA';
      });
      return bad.length ? `${bad.length} scroller(s) without scroll-fade-x: ` +
        bad.slice(0, 3).map((e) => (e.className || e.tagName).toString().slice(0, 60)).join(' | ') : null;
    }),
  },
  {
    name: 'controls-not-clipped', routes: ROUTES, viewports: ['m'],
    check: async (p) => p.evaluate(() => {
      const out = [];
      for (const c of document.querySelectorAll('main button, main a, main [role=radio], main input, main select')) {
        const r = c.getBoundingClientRect();
        if (!r.width || !r.height) continue;
        for (let a = c.parentElement; a && a !== document.body; a = a.parentElement) {
          const s = getComputedStyle(a);
          if (!['hidden', 'clip', 'auto', 'scroll'].includes(s.overflowX)) continue;
          const ar = a.getBoundingClientRect();
          const scrolls = ['auto', 'scroll'].includes(s.overflowX);
          if (r.right > ar.right + 1 || r.left < ar.left - 1) {
            if (!scrolls) out.push(`clipped "${(c.textContent || c.getAttribute('aria-label') || c.tagName).trim().slice(0, 30)}"`);
          }
          break;
        }
      }
      return out.length ? out.slice(0, 4).join(', ') : null;
    }),
  },
  {
    name: 'controls-inside-cards', routes: ROUTES, viewports: ['m'],
    check: async (p) => p.evaluate(() => {
      const out = [];
      for (const c of document.querySelectorAll('main button, main a, main [role=radio], main input, main select')) {
        const r = c.getBoundingClientRect();
        if (!r.width || !r.height) continue;
        let card = c.parentElement;
        while (card && card !== document.body) {
          const s = getComputedStyle(card);
          if (parseFloat(s.borderLeftWidth) > 0 && parseFloat(s.borderRightWidth) > 0 && parseFloat(s.borderRadius) >= 10) break;
          card = card.parentElement;
        }
        if (!card || card === document.body) continue;
        let a = c.parentElement, scrolled = false;
        for (; a && a !== card; a = a.parentElement) if (['auto', 'scroll'].includes(getComputedStyle(a).overflowX)) scrolled = true;
        const cr = card.getBoundingClientRect();
        if (!scrolled && (r.right > cr.right + 1 || r.left < cr.left - 1))
          out.push(`"${(c.textContent || c.getAttribute('aria-label') || c.tagName).trim().slice(0, 24)}" sticks out of its card`);
      }
      return out.length ? [...new Set(out)].slice(0, 4).join(', ') : null;
    }),
  },
  {
    name: 'empty-chart-no-axes', routes: ['/channels/money-brain'], viewports: ['m', 'd'],
    check: async (p) => {
      const msg = p.getByText('numbers appear after the first posts get views', { exact: false }).first();
      if (!(await msg.isVisible())) return 'empty message not shown';
      const ticks = await p.locator('.recharts-cartesian-axis-tick').count();
      return ticks ? `${ticks} axis ticks drawn under the empty message` : null;
    },
  },
  {
    name: 'idea-title-width', routes: ['/channels/overthought/ideas'], viewports: ['m'],
    check: async (p) => p.evaluate(() => {
      const w = [...document.querySelectorAll('main ol > li > div.min-w-0')].map((d) => d.getBoundingClientRect().width);
      if (!w.length) return 'no idea rows';
      const narrow = w.filter((x) => x < 180);
      return narrow.length ? `${narrow.length} idea titles narrower than 180px (min ${Math.round(Math.min(...w))})` : null;
    }),
  },
  {
    name: 'csp-ws-scheme', routes: ['/login'], viewports: ['d'], public: true,
    check: async (p, res) => {
      const csp = (res && (await res.headers())['content-security-policy']) || '';
      return /connect-src[^;]*ws:\/\/127\.0\.0\.1:54321/.test(csp) ? null : 'connect-src lacks ws://127.0.0.1:54321';
    },
  },
];

// ---------------------------------------------------------------- runner
async function readyVideoId() {
  const env = Object.fromEntries(fs.readFileSync(path.join(__dirname, 'demo.env'), 'utf8').split('\n')
    .filter((l) => l.includes('=')).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]));
  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/videos?select=id&status=eq.ready&limit=1`,
    { headers: { apikey: env.SUPABASE_SERVICE_ROLE_KEY } });
  return (await r.json())[0]?.id;
}

(async () => {
  const b = await chromium.launch();
  const ready = await readyVideoId();
  let fails = 0;
  const cases = CASES.filter((c) => !ONLY.length || ONLY.includes(c.name));
  for (const vpName of ['m', 'd']) {
    const ctx = await b.newContext({ viewport: VP[vpName], storageState: fs.existsSync(STATE) ? STATE : undefined });
    const page = await ctx.newPage();
    const errors = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
    page.on('pageerror', (e) => errors.push(e.message.slice(0, 160)));
    if (args.includes('--login-only')) {
      const r = await page.goto(B + '/videos');
      console.log(`${new URL(page.url()).pathname === '/videos' ? 'PASS' : 'FAIL'} login ${vpName} /videos ${r.status()}`);
      await ctx.close(); continue;
    }
    const routes = [...new Set(cases.filter((c) => c.viewports.includes(vpName)).flatMap((c) => c.routes))];
    for (const route of routes) {
      const url = B + route.replace('@ready', ready);
      errors.length = 0;
      const res = await page.goto(url, { waitUntil: 'networkidle' });
      await page.waitForTimeout(250);
      if (SHOTS) {
        fs.mkdirSync(SHOTS, { recursive: true });
        await page.screenshot({ path: path.join(SHOTS, `${vpName}${route.replace(/[/@]/g, '_') || '_'}.png`), fullPage: true });
      }
      for (const c of cases.filter((c) => c.viewports.includes(vpName) && c.routes.includes(route))) {
        const r = await c.check(page, res).catch((e) => `threw: ${e.message.slice(0, 120)}`);
        if (r) fails++;
        console.log(`${r ? 'FAIL' : 'PASS'} ${c.name} ${vpName} ${route}${r ? ' ' + r : ''}`);
      }
      if (!ONLY.length || ONLY.includes('no-console-errors')) {
        if (errors.length) fails++;
        console.log(`${errors.length ? 'FAIL' : 'PASS'} no-console-errors ${vpName} ${route}${errors.length ? ' ' + errors[0] : ''}`);
      }
    }
    await ctx.close();
  }
  await b.close();
  console.log(fails ? `${fails} check(s) failed` : 'all checks passed');
  process.exit(fails ? 1 : 0);
})();

module.exports = { CASES };
