// TikTok art drawn in code (no image model): the developer-app icon + one profile picture per channel.
//   node tools/brand/make_tiktok_art.cjs      -> assets/brand/tiktok/*.png (+ _preview.png)
// Style = the video style: charcoal #111, thin white hand-drawn stick figure, one accent colour per channel.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const OUT = path.join(ROOT, 'assets/brand/tiktok');
const FONT = path.join(ROOT, 'apps/web/app/fonts/Kalam-Bold.ttf');
const INK = '#f6f1e6';

function rng(seed) { return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

// smooth path through points (Catmull-Rom -> cubic Bézier)
function smooth(pts, closed = false) {
  const p = closed ? [pts[pts.length - 1], ...pts, pts[0], pts[1]] : [pts[0], ...pts, pts[pts.length - 1]];
  let d = `M${p[1][0].toFixed(1)},${p[1][1].toFixed(1)}`;
  for (let i = 1; i < p.length - 2; i++) {
    const [a, b, c, e] = [p[i - 1], p[i], p[i + 1], p[i + 2]];
    d += ` C${(b[0] + (c[0] - a[0]) / 6).toFixed(1)},${(b[1] + (c[1] - a[1]) / 6).toFixed(1)} ` +
      `${(c[0] - (e[0] - b[0]) / 6).toFixed(1)},${(c[1] - (e[1] - b[1]) / 6).toFixed(1)} ${c[0].toFixed(1)},${c[1].toFixed(1)}`;
  }
  return d + (closed ? ' Z' : '');
}
// hand-drawn line: a few wobbly points between two ends
function wline(r, x1, y1, x2, y2, wob = 2.2, n = 5) {
  const pts = [];
  for (let i = 0; i <= n; i++) { const t = i / n; const j = i === 0 || i === n ? 0.4 : 1;
    pts.push([x1 + (x2 - x1) * t + (r() - 0.5) * wob * j, y1 + (y2 - y1) * t + (r() - 0.5) * wob * j]); }
  return smooth(pts);
}
// hand-drawn circle that overshoots its start a little, like a pen stroke
function wcircle(r, cx, cy, rad, wob = 0.018, over = 0.12, n = 26) {
  const a0 = r() * Math.PI * 2, pts = [];
  for (let i = 0; i <= n * (1 + over); i++) { const a = a0 + (i / n) * Math.PI * 2;
    const k = 1 + (r() - 0.5) * wob * 2 + (i > n ? 0.025 * (i - n) / (n * over) : 0);
    pts.push([cx + Math.cos(a) * rad * k, cy + Math.sin(a) * rad * k]); }
  return smooth(pts);
}
const P = (d, color, w, extra = '') => `<path d="${d}" fill="none" stroke="${color}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" ${extra}/>`;

// the tangled "overthinking" scribble
function scribble(r, cx, cy, sx, sy, color, loops = 34, w = 7) {
  let s = '';
  for (let i = 0; i < loops; i++) {
    const ox = cx + (r() - 0.5) * sx * 1.25, oy = cy + (r() - 0.5) * sy * 1.1;
    const rx = 40 + r() * 75, ry = 30 + r() * 60, rot = r() * Math.PI, turns = 1 + r() * 0.8, n = 22, pts = [];
    for (let k = 0; k <= n * turns; k++) { const a = (k / n) * Math.PI * 2, rr = 1 + (r() - 0.5) * 0.12;
      const x = Math.cos(a) * rx * rr, y = Math.sin(a) * ry * rr;
      pts.push([ox + x * Math.cos(rot) - y * Math.sin(rot), oy + x * Math.sin(rot) + y * Math.cos(rot)]); }
    s += P(smooth(pts), color, w * (0.75 + r() * 0.4), `opacity="${(0.82 + r() * 0.18).toFixed(2)}"`);
  }
  return s;
}
function star(x, y, s, color) {   // 4-point sparkle
  return `<path d="M${x},${y - s} Q${x + s * 0.18},${y - s * 0.18} ${x + s},${y} Q${x + s * 0.18},${y + s * 0.18} ${x},${y + s} ` +
    `Q${x - s * 0.18},${y + s * 0.18} ${x - s},${y} Q${x - s * 0.18},${y - s * 0.18} ${x},${y - s} Z" fill="${color}"/>`;
}
function sparkles(r, cx, cy, rx, ry, color, n = 10, dots = 40, avoid = null) {
  let s = '';
  const zones = !avoid ? [] : Array.isArray(avoid[0]) ? avoid : [avoid];
  const clear = (x, y) => zones.every(([ax, ay, ar]) => Math.hypot(x - ax, y - ay) > ar);
  const place = () => { for (let t = 0; t < 40; t++) { const a = r() * Math.PI * 2, d = 0.72 + r() * 0.4;
    const x = cx + Math.cos(a) * rx * d, y = cy + Math.sin(a) * ry * d;
    if (clear(x, y)) return [x, y]; } return [cx, cy - ry]; };
  for (let i = 0; i < n; i++) { const [x, y] = place();
    s += i % 4 === 3 ? P(`M${x - 11},${y - 11} L${x + 11},${y + 11} M${x + 11},${y - 11} L${x - 11},${y + 11}`, color, 5)
      : star(x, y, 9 + r() * 14, color); }
  for (let i = 0; i < dots; i++) { const a = r() * Math.PI * 2, d = 0.3 + r() * 0.95;
    const x = cx + Math.cos(a) * rx * d, y = cy + Math.sin(a) * ry * d; if (!clear(x, y)) continue;
    s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(1.5 + r() * 3.5).toFixed(1)}" fill="${color}" opacity="${(0.35 + r() * 0.6).toFixed(2)}"/>`; }
  return s;
}
// stick figure: head centre + radius; body/arms/legs scale with the head
function figure(r, x, y, hr, { w = 8, pose = 'stand', eyes = true } = {}) {
  let s = P(wcircle(r, x, y, hr), INK, w);
  if (eyes) s += `<circle cx="${x - hr * 0.3}" cy="${y - hr * 0.08}" r="${w * 0.75}" fill="${INK}"/><circle cx="${x + hr * 0.3}" cy="${y - hr * 0.08}" r="${w * 0.75}" fill="${INK}"/>`;
  const neck = y + hr, hip = neck + hr * 1.9, sh = neck + hr * 0.55;
  s += P(wline(r, x, neck, x + 2, hip), INK, w);
  s += P(wline(r, x + 2, hip, x - hr * 0.75, hip + hr * 1.6), INK, w) + P(wline(r, x + 2, hip, x + hr * 0.8, hip + hr * 1.6), INK, w);
  if (pose === 'point') {        // right arm points up-right, left arm down
    s += P(wline(r, x, sh, x + hr * 1.25, sh - hr * 0.95), INK, w) + P(wline(r, x, sh, x - hr * 0.9, sh + hr * 1.1), INK, w);
  } else if (pose === 'chin') {   // hand on chin (thinking)
    s += P(smooth([[x, sh], [x + hr * 0.75, sh + hr * 0.35], [x + hr * 0.45, y + hr * 0.95]]), INK, w) + P(wline(r, x, sh, x - hr * 0.85, sh + hr * 1.15), INK, w);
  } else {
    s += P(wline(r, x, sh, x - hr * 0.95, sh + hr * 1.15), INK, w) + P(wline(r, x, sh, x + hr * 0.95, sh + hr * 1.15), INK, w);
  }
  return s;
}
const bubbleDots = (x1, y1, x2, y2) => [0.0, 0.45, 1.0].map((t, i) =>
  `<circle cx="${x1 + (x2 - x1) * t}" cy="${y1 + (y2 - y1) * t}" r="${7 + i * 5}" fill="none" stroke="${INK}" stroke-width="5"/>`).join('');

function gear(r, cx, cy, R, teeth, color, w) {
  const pts = [], rin = R * 0.8;
  for (let i = 0; i < teeth; i++) { const a = (i / teeth) * Math.PI * 2, st = (Math.PI * 2) / teeth;
    for (const [f, rad] of [[0, rin], [0.18, R], [0.5, R], [0.68, rin]]) { const ang = a + st * f, k = 1 + (r() - 0.5) * 0.03;
      pts.push([cx + Math.cos(ang) * rad * k, cy + Math.sin(ang) * rad * k]); } }
  const d = 'M' + pts.map((p) => p.map((v) => v.toFixed(1)).join(',')).join(' L') + ' Z';
  return P(d, color, w) + P(wcircle(r, cx, cy, R * 0.32), color, w);
}

// ---- the six pictures (1000x1000 viewBox) ----
const ART = {
  'app-icon': { color: '#FFD60A', seed: 7, draw(r, c) {
    return sparkles(r, 500, 400, 330, 250, c, 12, 55, [[500, 640, 165]]) + `<g filter="url(#glow)">${scribble(r, 500, 395, 330, 210, c, 40, 8)}</g>` +
      figure(r, 500, 640, 128, { w: 9 }); } },
  overthought: { color: '#FFD60A', seed: 11, draw(r, c) {
    return sparkles(r, 500, 385, 330, 250, c, 12, 55, [[500, 620, 160]]) + `<g filter="url(#glow)">${scribble(r, 500, 380, 320, 200, c, 40, 8)}</g>` +
      figure(r, 500, 620, 122, { w: 9 }); } },
  'money-brain': { color: '#3DDC97', seed: 23, draw(r, c) {
    let s = sparkles(r, 560, 330, 300, 230, c, 9, 35, [[560, 330, 210], [360, 660, 130]]);
    s += `<g filter="url(#glow)">${P(wcircle(r, 560, 330, 175, 0.012, 0.06), c, 10)}${P(wcircle(r, 560, 330, 142, 0.015, 0.04), c, 5, 'opacity="0.7"')}` +
      `<text x="560" y="392" text-anchor="middle" font-family="Hand" font-size="210" fill="${c}">$</text></g>`;
    for (const [x, y, rr] of [[285, 210, 34], [835, 520, 28], [790, 150, 22]])
      s += P(wcircle(r, x, y, rr, 0.03, 0.05), c, 6) + `<path d="M${x - rr * 0.15},${y - rr * 0.4} L${x - rr * 0.15},${y + rr * 0.4}" stroke="${c}" stroke-width="5" stroke-linecap="round"/>`;
    return s + bubbleDots(430, 560, 480, 500) + figure(r, 360, 660, 92, { w: 8, pose: 'chin' }); } },
  'tiny-history': { color: '#FF7A59', seed: 31, draw(r, c) {
    const T = 150, B = 760, L = 315, R = 685, N = 455, mid = 500;
    let s = sparkles(r, 500, 450, 360, 330, c, 9, 30, [[500, 450, 290], [500, 150, 60], [790, 760, 90]]);
    // sand (filled, soft) then the glass outline
    s += `<path d="M${L + 58},${T + 120} L${R - 58},${T + 120} Q${mid + 40},${N - 30} ${mid},${N - 6} Q${mid - 40},${N - 30} ${L + 58},${T + 120} Z" fill="${c}" opacity="0.9"/>`;
    s += `<path d="M${mid - 150},${B - 14} Q${mid},${B - 150} ${mid + 150},${B - 14} Z" fill="${c}" opacity="0.9"/>`;
    s += P(wline(r, mid, N + 4, mid, B - 120, 1.5, 4), c, 5, 'stroke-dasharray="2 14"');
    s += `<g filter="url(#glow)">` + P(wline(r, L - 35, T, R + 35, T, 2.5), INK, 10) + P(wline(r, L - 35, B, R + 35, B, 2.5), INK, 10) +
      P(smooth([[L, T + 6], [L + 25, T + 170], [mid - 26, N - 20], [mid - 16, N], [mid - 26, N + 20], [L + 25, B - 170], [L, B - 6]]), INK, 9) +
      P(smooth([[R, T + 6], [R - 25, T + 170], [mid + 26, N - 20], [mid + 16, N], [mid + 26, N + 20], [R - 25, B - 170], [R, B - 6]]), INK, 9) + `</g>`;
    return s + figure(r, 790, 735, 34, { w: 6, eyes: false, pose: 'point' }); } },
  'how-it-works': { color: '#4CC9F0', seed: 43, draw(r, c) {
    let s = sparkles(r, 520, 320, 340, 240, c, 9, 35, [520, 320, 230]);
    s += `<g filter="url(#glow)">${gear(r, 600, 290, 165, 10, c, 10)}${gear(r, 375, 430, 108, 8, c, 9)}</g>`;
    return s + bubbleDots(500, 620, 470, 560) + figure(r, 540, 720, 92, { w: 8, pose: 'chin' }); } },
  'myth-busted': { color: '#FF4D6D', seed: 59, draw(r, c) {
    let s = sparkles(r, 520, 330, 360, 250, c, 8, 30, [[520, 330, 290], [330, 720, 120]]);
    // speech bubble with "text" lines, crossed out
    const bub = smooth([[300, 170], [520, 135], [740, 175], [790, 320], [730, 460], [560, 485], [500, 560], [480, 485], [320, 465], [255, 320]], true);
    s += P(bub, INK, 9);
    for (const [y, w] of [[265, 320], [325, 360], [385, 250]]) s += P(wline(r, 520 - w / 2, y, 520 + w / 2, y, 3), INK, 9, 'opacity="0.55"');
    s += `<g filter="url(#glow)">${P(wline(r, 250, 140, 800, 520, 9, 6), c, 26)}${P(wline(r, 795, 135, 255, 530, 9, 6), c, 26)}</g>`;
    return s + figure(r, 330, 720, 88, { w: 8, pose: 'point' }); } },
};

function svg(key, size) {
  const a = ART[key], r = rng(a.seed);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 1000 1000">
  <defs><radialGradient id="bg" cx="50%" cy="45%" r="70%"><stop offset="0" stop-color="#1c1b19"/><stop offset="1" stop-color="#0e0e0d"/></radialGradient>
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="7" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
  <rect width="1000" height="1000" fill="url(#bg)"/>${a.draw(r, a.color)}</svg>`;
}
const page = (body) => `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:Hand;src:url("file://${FONT}")}html,body{margin:0;background:#0e0e0d}</style></head><body>${body}</body></html>`;

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'art-'));
  const b = await chromium.launch();
  const shots = [['app-icon', 1024, 'app-icon-1024.png'],
    ...['overthought', 'money-brain', 'tiny-history', 'how-it-works', 'myth-busted'].map((k) => [k, 1080, `profile-${k}.png`])];
  for (const [key, size, file] of shots) {
    const f = path.join(tmp, key + '.html'); fs.writeFileSync(f, page(svg(key, size)));
    const p = await b.newPage({ viewport: { width: size, height: size } });
    await p.goto('file://' + f); await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: path.join(OUT, file) }); await p.close();
    console.log(file, (fs.statSync(path.join(OUT, file)).size / 1024).toFixed(0) + ' KB');
  }
  // preview sheet: how each looks in TikTok's round crop, big and tiny
  const cells = shots.map(([k, , file]) => `<div style="text-align:center;color:#bbb;font:15px sans-serif">
    <img src="file://${path.join(OUT, file)}" style="width:300px;height:300px;border-radius:${k === 'app-icon' ? '22%' : '50%'};display:block">
    <img src="file://${path.join(OUT, file)}" style="width:56px;height:56px;border-radius:50%;margin-top:10px"><div>${file}</div></div>`).join('');
  const f = path.join(tmp, 'preview.html');
  fs.writeFileSync(f, page(`<div style="display:grid;grid-template-columns:repeat(3,320px);gap:28px;padding:30px">${cells}</div>`));
  const p = await b.newPage({ viewport: { width: 1040, height: 900 } });
  await p.goto('file://' + f); await p.waitForTimeout(300);
  await p.screenshot({ path: path.join(OUT, '_preview.png'), fullPage: true });
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
