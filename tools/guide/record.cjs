// Records one clip per scene of tools/guide/script.yaml on the local demo copy, timed to its narration.
//   node tools/guide/record.cjs [--chapter <id>] [--scene <id>]
// Needs: demo copy up + seeded + logged in (tools/demo), and narration.json from tts.py.
// Output: <GUIDE_OUT>/clips/<scene>.mp4 (1920×1080, 30 fps, exact narration length) + <scene>.json
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const OUT = process.env.GUIDE_OUT || '/tmp/claude-0/-home-user-overthought-studio/9a68d7c5-bc7f-54ea-9349-55c1fc7db717/scratchpad/guide';
const B = 'http://localhost:3000';
const args = process.argv.slice(2);
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };

const script = JSON.parse(execFileSync('python3', ['-c',
  'import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding="utf-8"))))',
  path.join(__dirname, 'script.yaml')]).toString());
const narration = JSON.parse(fs.readFileSync(path.join(OUT, 'narration.json'), 'utf8'));
const redbar = (on) => execFileSync('python3', [path.join(ROOT, 'tools/demo/seed_demo.py'), 'red-bar', on ? 'on' : 'off']);

// cursor dot + highlight ring, re-created on every navigation; the ring follows its element while scrolling
const OVERLAY = () => {
  const mk = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div');
    c.id = '__cur';
    c.style.cssText = 'position:fixed;z-index:2147483647;left:-40px;top:-40px;width:22px;height:22px;margin:-11px 0 0 -11px;' +
      'border-radius:50%;background:rgba(255,214,10,.35);border:2px solid #FFD60A;pointer-events:none;transition:transform .12s';
    const r = document.createElement('div');
    r.id = '__ring';
    r.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;border:4px solid #FFD60A;border-radius:14px;' +
      'box-shadow:0 0 0 6px rgba(255,214,10,.18);opacity:0;transition:opacity .35s';
    document.documentElement.append(c, r);
    addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => { c.style.transform = 'scale(.7)'; }, true);
    addEventListener('mouseup', () => { c.style.transform = ''; }, true);
    const loop = () => {
      const el = window.__hlEl;
      if (el && el.isConnected) {
        const b = el.getBoundingClientRect();
        Object.assign(r.style, { left: b.left - 8 + 'px', top: b.top - 8 + 'px', width: b.width + 16 + 'px', height: b.height + 16 + 'px', opacity: '1' });
      } else r.style.opacity = '0';
      requestAnimationFrame(loop);
    };
    loop();
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', mk); else mk();
};

async function readyId() {
  const env = Object.fromEntries(fs.readFileSync(path.join(ROOT, 'tools/demo/demo.env'), 'utf8').split('\n')
    .filter((l) => l.includes('=')).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]));
  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/videos?select=id&title=eq.Why%20you%20forget%20why%20you%20walked%20into%20a%20room`,
    { headers: { apikey: env.SUPABASE_SERVICE_ROLE_KEY } });
  return (await r.json())[0].id;
}

async function glide(page, loc) {
  const b = await loc.boundingBox();
  if (!b) return;
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 18 });
}

async function tryHighlight(page, sel) {
  if (!sel) return true;
  const loc = page.locator(sel).first();
  if (!(await loc.count()) || !(await loc.isVisible().catch(() => false))) return false;
  await loc.scrollIntoViewIfNeeded().catch(() => {});
  await loc.evaluate((el) => { window.__hlEl = el; });
  return true;
}

async function recordScene(b, scene, ids) {
  const phone = scene.viewport === 'm';
  // record 1280×720 and upscale ×1.5 to 1920×1080: the UI ends up 50% larger, readable on a phone
  // (Playwright's video ignores deviceScaleFactor, so the scaling happens in ffmpeg)
  const vp = phone ? { width: 390, height: 844 } : { width: 1280, height: 720 };
  const dsf = 1;
  const size = vp;
  const dir = path.join(OUT, 'raw', scene.id);
  fs.rmSync(dir, { recursive: true, force: true });
  execFileSync('python3', [path.join(ROOT, 'tools/demo/seed_demo.py'), 'heartbeat']);   // sidebar says 'Worker online'
  if (scene.redbar) redbar(true);
  const ctx = await b.newContext({
    viewport: vp, deviceScaleFactor: dsf, recordVideo: { dir, size },
    storageState: scene.fresh ? undefined : path.join(ROOT, 'tools/demo/.state.json'),
  });
  await ctx.addInitScript(OVERLAY);
  const t0ctx = Date.now();
  const page = await ctx.newPage();
  await page.goto(B + scene.route.replace('@ready', ids.ready), { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  await page.mouse.move(vp.width * 0.55, vp.height * 0.45);
  const start = (Date.now() - t0ctx) / 1000;            // clip starts once the page is ready
  const dur = narration[scene.id].duration;
  const acts = scene.actions || [];
  const step = Math.max(600, (dur * 1000 * 0.8) / Math.max(1, acts.length));
  let lit = await tryHighlight(page, scene.highlight);
  for (const a of acts) {
    const tStep = Date.now();
    if (a.do === 'wait') await page.waitForTimeout(a.ms);
    else if (a.do === 'scroll') await page.mouse.wheel(0, a.px);
    else {
      const loc = page.locator(a.target).first();
      await loc.waitFor({ state: 'visible', timeout: 8000 });
      await glide(page, loc);
      if (a.do === 'click') { await loc.click(); await page.waitForLoadState('networkidle').catch(() => {}); }
      if (a.do === 'type') { await loc.click(); await page.keyboard.type(a.text, { delay: 70 }); }
      if (a.do === 'play') await loc.evaluate((v) => { v.muted = true; v.play(); });
    }
    if (!lit) lit = await tryHighlight(page, scene.highlight);
    const left = step - (Date.now() - tStep);
    if (left > 0) await page.waitForTimeout(left);
  }
  if (!lit) lit = await tryHighlight(page, scene.highlight);
  const box = scene.highlight && lit ? await page.evaluate(() => {
    const r = window.__hlEl?.getBoundingClientRect(); return r ? { x: r.x, y: r.y, w: r.width, h: r.height } : null;
  }) : null;
  const elapsed = (Date.now() - t0ctx) / 1000 - start;
  if (elapsed < dur + 1.5) await page.waitForTimeout((dur + 1.5 - elapsed) * 1000);
  const raw = await page.video().path();
  await ctx.close();
  if (scene.redbar) redbar(false);

  const clip = path.join(OUT, 'clips', `${scene.id}.mp4`);
  fs.mkdirSync(path.dirname(clip), { recursive: true });
  const vf = phone
    ? 'scale=-2:1000:flags=lanczos,unsharp=5:5:0.6,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x111111,fps=30,tpad=stop_mode=clone:stop_duration=3'
    : 'scale=1920:1080:flags=lanczos,unsharp=5:5:0.6,fps=30,tpad=stop_mode=clone:stop_duration=3';
  execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-ss', start.toFixed(2), '-i', raw, '-t', dur.toFixed(3),
    '-vf', vf, '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', clip]);
  const got = parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', clip]).toString());
  fs.writeFileSync(clip.replace(/\.mp4$/, '.json'), JSON.stringify({ duration: got, audio: dur, box, viewport: vp, highlighted: !!lit }));
  return { id: scene.id, got, dur, lit: !!lit || !scene.highlight };
}

(async () => {
  const ids = { ready: await readyId() };
  const b = await chromium.launch();
  let bad = 0;
  for (const ch of script.chapters) {
    if (opt('--chapter') && String(ch.id) !== opt('--chapter')) continue;
    for (const sc of ch.scenes) {
      if (opt('--scene') && sc.id !== opt('--scene')) continue;
      const r = await recordScene(b, sc, ids).catch((e) => ({ id: sc.id, error: e.message.split('\n')[0] }));
      const ok = !r.error && r.got >= r.dur - 0.05 && r.lit;
      if (!ok) bad++;
      console.log(`${ok ? 'OK  ' : 'FAIL'} ${sc.id} ${r.error || `clip ${r.got.toFixed(2)}s / audio ${r.dur.toFixed(2)}s${r.lit ? '' : ' (highlight not found)'}`}`);
    }
  }
  await b.close();
  process.exit(bad ? 1 : 0);
})();
