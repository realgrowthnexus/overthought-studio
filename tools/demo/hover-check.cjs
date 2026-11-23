// Every clickable control on every page: hand cursor + a visible hover change (laptop, light and dark).
//   node tools/demo/hover-check.cjs [--theme light|dark] [--only /settings,/]
// Prints one line per problem; exit 1 when something fails. Needs the demo copy (see README).
const { chromium } = require('playwright');
const path = require('path');

const B = 'http://localhost:3000';
const STATE = path.join(__dirname, '.state.json');
const args = process.argv.slice(2);
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const THEME = opt('--theme') || 'light';
const ROUTES = (opt('--only') || ['/', '/channels', '/channels/overthought', '/channels/overthought/videos',
  '/channels/overthought/ideas', '/channels/overthought/strategy', '/channels/overthought/settings', '/channels/new',
  '/videos', '/analytics', '/reports', '/accounts', '/settings', '/logs'].join(',')).split(',');

const SEL = 'a[href], button, [role=button], [role=switch], [role=tab], summary, select, label[for], ' +
  'input[type=checkbox], input[type=radio], input[type=range], input[type=file]';
// what a hover may change (on the control, its parent row, or a pseudo-element)
const PROPS = ['backgroundColor', 'color', 'borderTopColor', 'borderBottomColor', 'boxShadow', 'textDecorationColor',
  'textDecorationLine', 'textDecorationThickness', 'opacity', 'transform', 'outlineColor', 'filter'];

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ storageState: STATE, viewport: { width: 1280, height: 900 },
    colorScheme: THEME === 'dark' ? 'dark' : 'light', reducedMotion: 'reduce' });
  const p = await ctx.newPage();
  await p.addInitScript((t) => { try { localStorage.setItem('theme', t); } catch {} }, THEME);
  const problems = [];
  let checked = 0;
  for (const route of ROUTES) {
    await p.goto(B + route, { waitUntil: 'networkidle' });
    await p.waitForTimeout(400);
    const n = await p.locator(SEL).count();
    for (let i = 0; i < n; i++) {
      const el = p.locator(SEL).nth(i);
      if (!(await el.isVisible().catch(() => false))) continue;
      const info = await el.evaluate((e, props) => {
        const snap = (x) => { if (!x) return null; const s = getComputedStyle(x); return props.map((k) => s[k]).join('|'); };
        const row = e.closest('li, tr, [data-row], article, .group') || e.parentElement;
        const name = (e.getAttribute('aria-label') || e.textContent || e.getAttribute('name') || e.tagName).trim()
          .replace(/\s+/g, ' ').slice(0, 40);
        const current = ['page', 'step', 'true'].includes(e.getAttribute('aria-current') || '') ||
          e.getAttribute('aria-checked') === 'true' || e.getAttribute('aria-pressed') === 'true' ||
          e.getAttribute('aria-selected') === 'true' || (e.className || '').toString().includes('sr-only') ||
          e.getBoundingClientRect().bottom <= 0;   // off-screen until focused (skip link)
        const disabled = e.disabled || e.getAttribute('aria-disabled') === 'true' || e.closest('fieldset:disabled');
        const covered = (() => { const r = e.getBoundingClientRect(); const top = document.elementFromPoint(
          r.left + r.width / 2, r.top + r.height / 2); return top && !e.contains(top) && !top.contains(e); })();
        return { name, tag: e.tagName.toLowerCase(), disabled: !!disabled, covered, current,
          cursor: getComputedStyle(e).cursor, before: [snap(e), snap(row), snap(e.firstElementChild)] };
      }, PROPS).catch(() => null);
      if (!info || info.covered) continue;
      checked++;
      const label = `${route}  <${info.tag}> "${info.name}"`;
      if (info.disabled) {
        if (!['not-allowed', 'default'].includes(info.cursor)) problems.push(`${label}: disabled but cursor=${info.cursor}`);
        continue;
      }
      const okCursor = info.tag === 'input' || info.tag === 'select' ? ['pointer', 'default', 'auto'] : ['pointer'];
      if (!okCursor.includes(info.cursor) && !(info.tag === 'label')) problems.push(`${label}: cursor=${info.cursor}`);
      if (['input', 'select', 'label'].includes(info.tag)) continue;     // native controls: cursor is enough
      if (info.current) continue;          // the selected / current item may stay still on hover
      await el.hover({ timeout: 2000 }).catch(() => {});
      await p.waitForTimeout(220);
      const after = await el.evaluate((e, props) => {
        const snap = (x) => { if (!x) return null; const s = getComputedStyle(x); return props.map((k) => s[k]).join('|'); };
        const row = e.closest('li, tr, [data-row], article, .group') || e.parentElement;
        return [snap(e), snap(row), snap(e.firstElementChild)];
      }, PROPS).catch(() => null);
      if (after && after.every((v, j) => v === info.before[j])) problems.push(`${label}: no visible hover change`);
      await p.mouse.move(2, 2);
    }
  }
  await b.close();
  console.log(`[${THEME}] checked ${checked} controls on ${ROUTES.length} pages, ${problems.length} problem(s)`);
  for (const x of [...new Set(problems)]) console.log('  - ' + x);
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
