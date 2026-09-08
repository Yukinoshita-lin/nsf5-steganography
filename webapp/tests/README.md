# Interactive Website Tests

Runs the bilingual interactive lab against the live GitHub Pages site in a
real browser (Chrome or Edge) and checks:

- default Chinese + language toggle to English
- LSB embed changes pixels
- Hamming random/solve
- wet-paper auto-play cycle
- keyboard operation of Hamming and wet-paper canvases
- decision-threshold slider
- payload-scan slider
- mobile menu
- no console/page errors

Install and run:

```bash
npm install   # or: pnpm install
npx playwright install chromium   # only needed if no system Chrome/Edge
SITE_URL=https://yukinoshita-lin.github.io/nsf5-steganography/ npm test
```
