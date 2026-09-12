"""Export PNGs and verify SVG text stays within the canvas."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'source' / 'manifest.json').read_text())
results = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    for item in manifest:
        page = browser.new_page(viewport={'width': item['width'], 'height': item['height']}, device_scale_factor=2)
        page.goto((root / item['file']).as_uri(), wait_until='load')
        page.screenshot(path=str(root / item['file'].replace('.svg', '.png')))
        checks = page.evaluate('''() => {
            const svg = document.querySelector('svg'), r = svg.getBoundingClientRect();
            const clipped = Array.from(svg.querySelectorAll('text')).filter(t => {
                const b = t.getBoundingClientRect();
                return b.left < 0 || b.right > r.width + 1 || b.top < 0 || b.bottom > r.height + 1;
            }).map(t => t.textContent);
            return {textElements: svg.querySelectorAll('text').length,
                    embeddedIcons: svg.querySelectorAll('image').length, clipped};
        }''')
        assert not checks['clipped'], checks
        results.append({'file': item['file'], **checks})
        page.close()
    browser.close()
(root / 'source' / 'render-checks.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results))
