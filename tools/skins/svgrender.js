// Render SVG files to transparent PNGs with headless Chromium (Playwright).
//
// Usage: node svgrender.js manifest.json
// manifest: {"fonts": [{"family": "...", "weight": 700, "style": "normal", "path": "/abs/font.ttf"}],
//            "jobs": [{"svg": "/abs/in.svg", "png": "/abs/out.png", "width": 96, "height": 16}]}
//
// Fonts are embedded as data: URLs so the SVGs can name them by family.
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const manifest = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const faces = manifest.fonts.map(f => {
    const otf = f.path.toLowerCase().endsWith('.otf');
    return `@font-face{font-family:'${f.family}';font-weight:${f.weight};font-style:${f.style};` +
      `src:url(data:font/${otf ? 'otf' : 'ttf'};base64,${fs.readFileSync(f.path).toString('base64')}) ` +
      `format('${otf ? 'opentype' : 'truetype'}');}`;
  }).join('\n');
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  await page.setContent(`<!doctype html><html><head><style>${faces}
    html,body{margin:0;padding:0;background:transparent;overflow:hidden}
    #c svg{display:block}</style></head><body><div id="c"></div></body></html>`);
  // Load every face up front so no job renders with a fallback font.
  await page.evaluate(async () => { await Promise.all([...document.fonts].map(f => f.load())); });
  for (const job of manifest.jobs) {
    await page.setViewportSize({ width: job.width, height: job.height });
    const svg = fs.readFileSync(job.svg, 'utf8');
    await page.evaluate(s => { document.getElementById('c').innerHTML = s; }, svg);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: job.png, omitBackground: true,
                            clip: { x: 0, y: 0, width: job.width, height: job.height } });
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
