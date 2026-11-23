// Records a captioned product walkthrough of the demo copy (made-up data) → tools/demo/out/walkthrough.mp4
//   node tools/demo/record-walkthrough.cjs     (needs the demo copy up + seeded, see README)
// This is a PRODUCT walkthrough only. TikTok's app review needs a real sandbox recording of the live site
// (connect a sandbox account + send a draft) — record that by hand once the sandbox keys are in Settings.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const B = 'http://localhost:3000';
const OUT = path.join(__dirname, 'out');
const W = 1280, H = 720;

const card = (title, sub, note) => `data:text/html,${encodeURIComponent(`<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;height:100vh;display:grid;place-items:center;background:#111;color:#f6f1e6;font-family:system-ui,sans-serif">
<div style="text-align:center;max-width:900px;padding:0 40px"><div style="font-size:52px;font-weight:700;letter-spacing:-.02em">${title}</div>
<div style="margin-top:18px;font-size:24px;color:#ffd60a">${sub}</div><div style="margin-top:28px;font-size:18px;color:#a19a8d;line-height:1.5">${note}</div></div></body></html>`)}`;

async function caption(p, text) {
  await p.evaluate((t) => {
    let el = document.getElementById('__cap');
    if (!el) {
      el = document.createElement('div'); el.id = '__cap';
      el.style.cssText = 'position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;max-width:1000px;' +
        'padding:12px 20px;border-radius:12px;background:rgba(17,17,17,.92);color:#f6f1e6;font:600 18px/1.4 system-ui,sans-serif;' +
        'box-shadow:0 8px 30px rgba(0,0,0,.35);border:1px solid #ffd60a;text-align:center;pointer-events:none';
      document.body.appendChild(el);
    }
    el.textContent = t;
  }, text);
}
const go = async (p, url, text, wait = 3200) => { await p.goto(B + url, { waitUntil: 'networkidle' }); await caption(p, text); await p.waitForTimeout(wait); };
const glide = async (p, loc) => { const b = await loc.boundingBox(); if (b) await p.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 18 }); await p.waitForTimeout(350); };

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  for (const f of fs.readdirSync(OUT)) if (f.endsWith('.webm')) fs.unlinkSync(path.join(OUT, f));
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: W, height: H }, colorScheme: 'dark', recordVideo: { dir: OUT, size: { width: W, height: H } } });
  const p = await ctx.newPage();

  await p.goto(card('Overthought Studio', 'studio.getgrowthnexus.com', 'Product walkthrough · demo data<br>A private dashboard where the owner makes short educational videos and sends them to their own TikTok accounts.'));
  await p.waitForTimeout(3500);

  // 1) owner logs in
  await p.goto(B + '/login', { waitUntil: 'networkidle' });
  await caption(p, '1 · The owner signs in to their private dashboard');
  await p.waitForTimeout(1200);
  await p.locator('input[type=email]').pressSequentially('owner@demo.local', { delay: 45 });
  await p.locator('input[type=password]').pressSequentially('DemoPass!2026x', { delay: 45 });
  await glide(p, p.locator('button[type=submit]'));
  await p.locator('button[type=submit]').click();
  await p.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 15000 });
  await p.waitForLoadState('networkidle');
  await caption(p, 'Overview: every channel, what is being made, and what is waiting for approval');
  await p.waitForTimeout(3500);

  // 2) TikTok accounts (Login Kit)
  await go(p, '/accounts', '2 · TikTok accounts: each channel connects its own TikTok account with Login Kit (user.info.basic, user.info.profile)', 4500);
  await p.mouse.wheel(0, 380); await p.waitForTimeout(2200);

  // 3) channel + delivery mode
  await go(p, '/channels/overthought', '3 · A channel: its topics, schedule and videos', 3000);
  await go(p, '/channels/overthought/settings', 'Channel settings', 1200);
  const mode = p.getByText('How videos reach TikTok');
  await mode.scrollIntoViewIfNeeded(); await p.mouse.wheel(0, -120);
  await caption(p, 'Delivery: "TikTok drafts". Approved videos go to the TikTok inbox; the owner posts them in the TikTok app (video.upload)');
  await p.waitForTimeout(4500);

  // 4) review a video, approve, send to drafts
  await go(p, '/videos', '4 · Videos: every video with its status', 2200);
  const ready = p.getByText('Why you forget why you walked into a room').locator('visible=true').first();
  await glide(p, ready); await ready.click();
  await p.waitForLoadState('networkidle');
  await caption(p, 'The owner watches the finished video and checks the script and caption');
  const vid = p.locator('video').first();
  if (await vid.count()) { await vid.evaluate((v) => { v.muted = true; v.play().catch(() => {}); }); }
  await p.waitForTimeout(5000);
  const approve = p.getByRole('button', { name: 'Approve' });
  if (await approve.count()) { await glide(p, approve); await caption(p, 'Approve: nothing reaches TikTok without the owner\'s OK'); await p.waitForTimeout(1200); await approve.click(); await p.waitForTimeout(2500); }
  const pub = p.getByRole('button', { name: 'Publish now' }).first();
  if (await pub.count()) {
    await glide(p, pub); await pub.click(); await p.waitForTimeout(800);
    await caption(p, 'Publish now → uploads the video to the connected account\'s TikTok drafts (Content Posting API · video.upload)');
    await p.waitForTimeout(3500);
    const confirm = p.getByRole('dialog').getByRole('button', { name: 'Publish now' });
    await glide(p, confirm); await confirm.click(); await p.waitForTimeout(2500);
  }

  // 5) analytics (user.info.stats + video.list)
  await go(p, '/analytics', '5 · Analytics: followers and likes (user.info.stats) and each posted video\'s views, likes, comments and shares (video.list)', 5000);
  await p.mouse.wheel(0, 420); await p.waitForTimeout(2500);

  await p.goto(card('Overthought Studio', 'Login Kit · Content Posting API (upload to drafts)', 'Scopes: user.info.basic · user.info.profile · user.info.stats · video.list · video.upload'));
  await p.waitForTimeout(3500);

  const raw = await p.video().path();
  await ctx.close(); await b.close();
  const mp4 = path.join(OUT, 'walkthrough.mp4');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', raw, '-c:v', 'libx264', '-preset', 'medium', '-crf', '24', '-pix_fmt', 'yuv420p',
    '-r', '30', '-movflags', '+faststart', '-an', mp4]);
  console.log(mp4, (fs.statSync(mp4).size / 1e6).toFixed(1) + ' MB');
})().catch((e) => { console.error(e); process.exit(1); });
